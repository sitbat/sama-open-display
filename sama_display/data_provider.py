"""Permission-scoped, read-only computer data exposed to themes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import zipfile

import psutil

from .plugin import InstalledPlugin

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


SUPPORTED_ADAPTER = "builtin.system"


def validate_provider(plugin: InstalledPlugin) -> str:
    """Return the adapter name after validating a declarative provider entry."""
    if plugin.manifest.kind != "data-provider":
        raise ValueError("plugin is not a data provider")
    with zipfile.ZipFile(plugin.path) as package:
        raw = tomllib.loads(package.read(plugin.manifest.entry).decode("utf-8"))
    if set(raw) != {"provider"} or set(raw["provider"]) != {"adapter"}:
        raise ValueError("provider entry must contain only provider.adapter")
    adapter = str(raw["provider"]["adapter"])
    if adapter != SUPPORTED_ADAPTER:
        raise ValueError(f"unsupported data adapter: {adapter}")
    return adapter


class DataService:
    """Collect only the fields granted by enabled provider plugins."""

    def __init__(self, plugins: list[InstalledPlugin]):
        self.permissions: set[str] = set()
        for plugin in plugins:
            if plugin.enabled and not plugin.problem and plugin.manifest.kind == "data-provider":
                try:
                    validate_provider(plugin)
                except (OSError, ValueError, zipfile.BadZipFile, KeyError):
                    continue
                else:
                    self.permissions.update(plugin.manifest.permissions)

    def snapshot(self) -> dict[str, float | int]:
        values: dict[str, float | int] = {}
        if "system.cpu" in self.permissions:
            values["system.cpu.percent"] = psutil.cpu_percent(interval=0.05)
        if "system.memory" in self.permissions:
            memory = psutil.virtual_memory()
            values["system.memory.percent"] = memory.percent
            values["system.memory.used_bytes"] = memory.used
            values["system.memory.total_bytes"] = memory.total
        if "system.uptime" in self.permissions:
            values["system.uptime.seconds"] = int((datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds())
        if "storage.usage" in self.permissions:
            disk = psutil.disk_usage(Path.home().anchor or "C:\\")
            values["storage.root.percent"] = disk.percent
            values["storage.root.used_bytes"] = disk.used
            values["storage.root.total_bytes"] = disk.total
        if "network.counters" in self.permissions:
            network = psutil.net_io_counters()
            values["network.sent_bytes"] = network.bytes_sent
            values["network.received_bytes"] = network.bytes_recv
        if "process.summary" in self.permissions:
            values["process.count"] = len(psutil.pids())
        return values
