"""Permission-scoped data providers exposed to layout themes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Collection
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import zipfile

import psutil

from .plugin import InstalledPlugin

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


BUILTIN_ADAPTER = "builtin.system"
EXTERNAL_ADAPTER = "external.process"
SUPPORTED_FIELD_TYPES = {"number", "integer", "string", "boolean"}
_FIELD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass(frozen=True)
class ProviderConfig:
    adapter: str
    command: str = ""
    timeout_ms: int = 1000
    fields: tuple[tuple[str, str], ...] = ()


def load_provider_config(plugin: InstalledPlugin) -> ProviderConfig:
    """Validate and return one provider's adapter configuration."""
    if plugin.manifest.kind != "data-provider":
        raise ValueError("plugin is not a data provider")
    with zipfile.ZipFile(plugin.path) as package:
        raw = tomllib.loads(package.read(plugin.manifest.entry).decode("utf-8"))
        if set(raw) - {"provider", "fields"} or "provider" not in raw:
            raise ValueError("provider entry supports only [provider] and [fields]")
        provider = raw["provider"]
        adapter = str(provider.get("adapter", ""))
        if adapter == BUILTIN_ADAPTER:
            if set(provider) != {"adapter"} or "fields" in raw:
                raise ValueError("builtin.system accepts only provider.adapter")
            return ProviderConfig(adapter)
        if adapter != EXTERNAL_ADAPTER:
            raise ValueError(f"unsupported data adapter: {adapter}")
        if plugin.manifest.schema < 2:
            raise ValueError("external.process requires plugin schema 2")
        if "code.execute" not in plugin.manifest.permissions:
            raise ValueError("external.process requires the code.execute permission")
        allowed = {"adapter", "command", "timeout_ms"}
        if set(provider) - allowed:
            raise ValueError("external provider contains unknown options")
        command = str(provider.get("command", ""))
        if not command or "/" in command or "\\" in command or command not in package.namelist():
            raise ValueError("provider.command must name a package-root executable")
        if Path(command).suffix.lower() != ".exe":
            raise ValueError("provider.command must be a Windows .exe file")
        timeout_ms = int(provider.get("timeout_ms", 1000))
        if not 100 <= timeout_ms <= 10000:
            raise ValueError("provider.timeout_ms must be between 100 and 10000")
        raw_fields = raw.get("fields", {})
        if not isinstance(raw_fields, dict) or not raw_fields:
            raise ValueError("external provider must declare at least one [fields] entry")
        fields: list[tuple[str, str]] = []
        for name, value_type in raw_fields.items():
            if not _FIELD_NAME.fullmatch(str(name)):
                raise ValueError(f"invalid provider field name: {name}")
            value_type = str(value_type)
            if value_type not in SUPPORTED_FIELD_TYPES:
                raise ValueError(f"unsupported type for provider field {name}: {value_type}")
            fields.append((str(name), value_type))
        return ProviderConfig(adapter, command, timeout_ms, tuple(fields))


def validate_provider(plugin: InstalledPlugin) -> str:
    """Backward-compatible adapter validation API."""
    return load_provider_config(plugin).adapter


def _materialize_command(plugin: InstalledPlugin, config: ProviderConfig) -> Path:
    with zipfile.ZipFile(plugin.path) as package:
        payload = package.read(config.command)
    digest = hashlib.sha256(payload).hexdigest()[:16]
    runtime = plugin.path.parent / ".runtime" / plugin.manifest.plugin_id / digest
    runtime.mkdir(parents=True, exist_ok=True)
    command = runtime / Path(config.command).name
    if not command.exists() or command.read_bytes() != payload:
        command.write_bytes(payload)
    if os.name != "nt":
        command.chmod(0o700)
    return command


def _matches_type(value: object, expected: str) -> bool:
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return isinstance(value, str)


def _external_snapshot(plugin: InstalledPlugin, config: ProviderConfig) -> dict[str, str | float | int | bool]:
    command = _materialize_command(plugin, config)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        [str(command)],
        cwd=command.parent,
        input=json.dumps({"protocol": 1, "plugin_id": plugin.manifest.plugin_id}),
        text=True,
        capture_output=True,
        timeout=config.timeout_ms / 1000,
        check=False,
        creationflags=creation_flags,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"provider exited with {completed.returncode}")
    if len(completed.stdout.encode("utf-8")) > 1024 * 1024:
        raise ValueError("provider output exceeds 1 MB")
    values = json.loads(completed.stdout)
    if not isinstance(values, dict):
        raise ValueError("provider output must be one JSON object")
    declared = dict(config.fields)
    unknown = set(values) - set(declared)
    if unknown:
        raise ValueError(f"provider returned undeclared fields: {', '.join(sorted(unknown))}")
    result: dict[str, str | float | int | bool] = {}
    for name, value in values.items():
        if not _matches_type(value, declared[name]):
            raise ValueError(f"provider field {name} does not match {declared[name]}")
        result[f"{plugin.manifest.plugin_id}.{name}"] = value
    return result


class DataService:
    """Collect namespaced values from enabled providers.

    Built-in providers remain permission-scoped. Schema-2 external providers run
    out of process and return one declared JSON object. Process isolation avoids
    loading third-party code into the host, but it is not an operating-system
    sandbox; installing ``code.execute`` means trusting that executable.
    """

    def __init__(self, plugins: list[InstalledPlugin]):
        self.plugins: list[tuple[InstalledPlugin, ProviderConfig]] = []
        for plugin in plugins:
            if not plugin.enabled or plugin.problem or plugin.manifest.kind != "data-provider":
                continue
            try:
                config = load_provider_config(plugin)
            except (OSError, ValueError, zipfile.BadZipFile, KeyError):
                continue
            self.plugins.append((plugin, config))

    def snapshot(self, required_plugin_ids: Collection[str] | None = None) -> dict[str, str | float | int | bool]:
        required = set(required_plugin_ids) if required_plugin_ids is not None else None
        values: dict[str, str | float | int | bool] = {}
        for plugin, config in self.plugins:
            if config.adapter == EXTERNAL_ADAPTER:
                if required is not None and plugin.manifest.plugin_id not in required:
                    continue
                try:
                    values.update(_external_snapshot(plugin, config))
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
                    continue
                continue

            permissions = set(plugin.manifest.permissions)
            if "system.cpu" in permissions:
                values["system.cpu.percent"] = psutil.cpu_percent(interval=0.05)
            if "system.memory" in permissions:
                memory = psutil.virtual_memory()
                values["system.memory.percent"] = memory.percent
                values["system.memory.used_bytes"] = memory.used
                values["system.memory.total_bytes"] = memory.total
            if "system.uptime" in permissions:
                values["system.uptime.seconds"] = int(
                    (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
                )
            if "storage.usage" in permissions:
                disk = psutil.disk_usage(Path.home().anchor or "C:\\")
                values["storage.root.percent"] = disk.percent
                values["storage.root.used_bytes"] = disk.used
                values["storage.root.total_bytes"] = disk.total
            if "network.counters" in permissions:
                network = psutil.net_io_counters()
                values["network.sent_bytes"] = network.bytes_sent
                values["network.received_bytes"] = network.bytes_recv
            if "process.summary" in permissions:
                values["process.count"] = len(psutil.pids())
        return values
