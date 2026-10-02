"""Permission-scoped data providers exposed to layout themes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Collection
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import subprocess
import threading
from time import monotonic
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
MAX_RESPONSE_BYTES = 1024 * 1024
REFRESH_SCHEDULING_TOLERANCE_SECONDS = 0.005


@dataclass(frozen=True)
class ProviderConfig:
    adapter: str
    command: str = ""
    timeout_ms: int = 1000
    fields: tuple[tuple[str, str], ...] = ()
    mode: str = "oneshot"
    refresh_interval_ms: int = 1000


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
        allowed = {"adapter", "command", "timeout_ms", "mode", "refresh_interval_ms"}
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
        mode = str(provider.get("mode", "oneshot"))
        if mode not in {"oneshot", "resident"}:
            raise ValueError("provider.mode must be oneshot or resident")
        refresh_interval_ms = int(provider.get(
            "refresh_interval_ms", 60000 if mode == "resident" else 1000,
        ))
        if not 1000 <= refresh_interval_ms <= 300000:
            raise ValueError("provider.refresh_interval_ms must be between 1000 and 300000")
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
        return ProviderConfig(adapter, command, timeout_ms, tuple(fields), mode, refresh_interval_ms)


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


def _parse_external_values(
    plugin: InstalledPlugin, config: ProviderConfig, output: str,
) -> dict[str, str | float | int | bool]:
    if len(output.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("provider output exceeds 1 MB")
    values = json.loads(output)
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


def _external_snapshot(plugin: InstalledPlugin, config: ProviderConfig) -> dict[str, str | float | int | bool]:
    command = _materialize_command(plugin, config)
    completed = subprocess.run(
        [str(command)],
        cwd=command.parent,
        input=json.dumps({"protocol": 1, "plugin_id": plugin.manifest.plugin_id}),
        text=True,
        capture_output=True,
        timeout=config.timeout_ms / 1000,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"provider exited with {completed.returncode}")
    return _parse_external_values(plugin, config, completed.stdout)


class _ResidentProcess:
    """One line-delimited request/response process for an active theme dependency."""

    def __init__(self, plugin: InstalledPlugin, config: ProviderConfig):
        command = _materialize_command(plugin, config)
        self.plugin = plugin
        self.config = config
        self.process = subprocess.Popen(
            [str(command)], cwd=command.parent,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._responses: Queue[str | None] = Queue(maxsize=2)
        self._overflow = False
        self._stderr_tail: deque[str] = deque(maxlen=8)
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        try:
            assert self.process.stdout is not None
            while True:
                line = self.process.stdout.readline(MAX_RESPONSE_BYTES + 2)
                try:
                    self._responses.put_nowait(line or None)
                except Full:
                    self._overflow = True
                    if self.process.poll() is None:
                        try:
                            self.process.terminate()
                        except OSError:
                            pass
                    break
                if not line:
                    break
        except (OSError, ValueError):
            try:
                self._responses.put_nowait(None)
            except Full:
                self._overflow = True

    def _read_stderr(self) -> None:
        try:
            assert self.process.stderr is not None
            while chunk := self.process.stderr.read(1024):
                self._stderr_tail.append(chunk)
        except (OSError, ValueError):
            pass

    def sample(self) -> dict[str, str | float | int | bool]:
        if self.process.poll() is not None:
            raise RuntimeError("resident provider exited: " + "".join(self._stderr_tail)[-2048:])
        if self._overflow or not self._responses.empty():
            raise ValueError("resident provider sent an unsolicited response")
        assert self.process.stdin is not None
        request = {"protocol": 2, "plugin_id": self.plugin.manifest.plugin_id, "action": "sample"}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        try:
            response = self._responses.get(timeout=self.config.timeout_ms / 1000)
        except Empty as exc:
            raise subprocess.TimeoutExpired(self.process.args, self.config.timeout_ms / 1000) from exc
        if response is None:
            raise RuntimeError("resident provider closed stdout: " + "".join(self._stderr_tail)[-2048:])
        if self._overflow or not response.endswith("\n"):
            raise ValueError("resident provider response must be one JSON line of at most 1 MB")
        return _parse_external_values(self.plugin, self.config, response)

    def close(self) -> None:
        if self.process.poll() is None:
            try:
                assert self.process.stdin is not None
                request = {"protocol": 2, "plugin_id": self.plugin.manifest.plugin_id, "action": "shutdown"}
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=0.5)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                if self.process.poll() is None:
                    try:
                        self.process.terminate()
                    except OSError:
                        pass
                    try:
                        self.process.wait(timeout=0.5)
                    except subprocess.TimeoutExpired:
                        try:
                            self.process.kill()
                            self.process.wait(timeout=1)
                        except (OSError, subprocess.TimeoutExpired):
                            pass
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass


class DataService:
    """Collect namespaced values from enabled providers.

    Built-in providers remain permission-scoped. Schema-2 external providers run
    out of process and return one declared JSON object. Process isolation avoids
    loading third-party code into the host, but it is not an operating-system
    sandbox; installing ``code.execute`` means trusting that executable.
    """

    def __init__(self, plugins: list[InstalledPlugin]):
        self.plugins: list[tuple[InstalledPlugin, ProviderConfig]] = []
        self._resident: dict[str, _ResidentProcess] = {}
        self._cached: dict[str, dict[str, str | float | int | bool]] = {}
        self._next_refresh: dict[str, float] = {}
        self._lock = threading.RLock()
        for plugin in plugins:
            if not plugin.enabled or plugin.problem or plugin.manifest.kind != "data-provider":
                continue
            try:
                config = load_provider_config(plugin)
            except (OSError, ValueError, zipfile.BadZipFile, KeyError):
                continue
            self.plugins.append((plugin, config))

    def __enter__(self) -> DataService:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            for process in self._resident.values():
                try:
                    process.close()
                except (OSError, subprocess.SubprocessError):
                    pass
            self._resident.clear()
            self._cached.clear()
            self._next_refresh.clear()

    def snapshot(self, required_plugin_ids: Collection[str] | None = None) -> dict[str, str | float | int | bool]:
        """Sample only requested providers, or all enabled providers for ``None``."""
        with self._lock:
            return self._snapshot(required_plugin_ids)

    def _snapshot(self, required_plugin_ids: Collection[str] | None) -> dict[str, str | float | int | bool]:
        required = set(required_plugin_ids) if required_plugin_ids is not None else None
        for plugin_id in tuple(self._resident):
            if required is not None and plugin_id not in required:
                try:
                    self._resident.pop(plugin_id).close()
                except (OSError, subprocess.SubprocessError):
                    pass
                self._cached.pop(plugin_id, None)
                self._next_refresh.pop(plugin_id, None)
        values: dict[str, str | float | int | bool] = {}
        for plugin, config in self.plugins:
            plugin_id = plugin.manifest.plugin_id
            if required is not None and plugin_id not in required:
                continue
            if config.adapter == EXTERNAL_ADAPTER:
                resident = self._resident.get(plugin_id)
                if resident is not None and resident.process.poll() is not None:
                    try:
                        self._resident.pop(plugin_id).close()
                    except (OSError, subprocess.SubprocessError):
                        pass
                    self._next_refresh.pop(plugin_id, None)
                sample_started = monotonic()
                # A 1 Hz renderer can arrive a fraction of a millisecond before
                # the previous sample's deadline. Do not hold that value for an
                # entire extra frame. Only successful cached samples get this
                # small tolerance; failure retry deadlines remain unchanged.
                tolerance = REFRESH_SCHEDULING_TOLERANCE_SECONDS if plugin_id in self._cached else 0.0
                if sample_started < self._next_refresh.get(plugin_id, 0) - tolerance:
                    values.update(self._cached.get(plugin_id, {}))
                    continue
                try:
                    if config.mode == "resident":
                        resident = self._resident.get(plugin_id)
                        if resident is None:
                            resident = _ResidentProcess(plugin, config)
                            self._resident[plugin_id] = resident
                        sample = resident.sample()
                    else:
                        sample = _external_snapshot(plugin, config)
                    self._cached[plugin_id] = sample
                    # The interval is start-to-start, so sample latency does not skip
                    # the next regular frame. Calls are serialized; overdue samples
                    # run once on the next call, with no catch-up loop.
                    self._next_refresh[plugin_id] = sample_started + config.refresh_interval_ms / 1000
                    values.update(sample)
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
                    self._cached.pop(plugin_id, None)
                    self._next_refresh[plugin_id] = monotonic() + min(config.refresh_interval_ms / 1000, 5)
                    resident = self._resident.pop(plugin_id, None)
                    if resident is not None:
                        try:
                            resident.close()
                        except (OSError, subprocess.SubprocessError):
                            pass
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
