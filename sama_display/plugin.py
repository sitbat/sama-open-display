"""Validation, installation and state management for SAMA Open Display plugins."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


PLUGIN_EXTENSION = ".sodpkg"
PLUGIN_KINDS = {"theme", "data-provider"}
KNOWN_PERMISSIONS = {
    "system.cpu", "system.memory", "system.uptime", "storage.usage",
    "network.counters", "process.summary", "code.execute",
}
SUPPORTED_SCHEMAS = {1, 2}
MAX_PACKAGE_SIZE = 20 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    author: str
    kind: str
    entry: str
    description: str = ""
    dependencies: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    schema: int = 1


@dataclass(frozen=True)
class InstalledPlugin:
    manifest: PluginManifest
    path: Path
    enabled: bool
    problem: str = ""


def _string_list(data: dict, key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"plugin.{key} must be an array of strings")
    return tuple(dict.fromkeys(value))


def load_manifest(package: zipfile.ZipFile) -> PluginManifest:
    if "manifest.toml" not in package.namelist():
        raise ValueError("plugin package does not contain manifest.toml")
    raw = tomllib.loads(package.read("manifest.toml").decode("utf-8"))
    if set(raw) != {"plugin"}:
        raise ValueError("manifest must contain only a [plugin] section")
    data = raw["plugin"]
    allowed = {
        "schema", "id", "name", "version", "author", "kind", "entry",
        "description", "dependencies", "permissions",
    }
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown manifest option(s): {', '.join(sorted(unknown))}")
    schema = int(data.get("schema", 1))
    if schema not in SUPPORTED_SCHEMAS:
        raise ValueError(f"unsupported plugin schema: {schema}")
    plugin_id = str(data.get("id", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", plugin_id):
        raise ValueError("plugin.id must be a stable lowercase identifier")
    version = str(data.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        raise ValueError("plugin.version must use semantic versioning")
    kind = str(data.get("kind", ""))
    if kind not in PLUGIN_KINDS:
        raise ValueError(f"unsupported plugin kind: {kind}")
    entry = str(data.get("entry", ""))
    if not entry or "/" in entry or "\\" in entry or entry not in package.namelist():
        raise ValueError("plugin.entry must name a file in the package root")
    dependencies = _string_list(data, "dependencies")
    if plugin_id in dependencies:
        raise ValueError("a plugin cannot depend on itself")
    permissions = _string_list(data, "permissions")
    unknown_permissions = set(permissions) - KNOWN_PERMISSIONS
    if unknown_permissions:
        raise ValueError(f"unknown permission(s): {', '.join(sorted(unknown_permissions))}")
    return PluginManifest(
        plugin_id=plugin_id, name=str(data.get("name", plugin_id))[:80], version=version,
        author=str(data.get("author", "Unknown"))[:80], kind=kind, entry=entry,
        description=str(data.get("description", ""))[:240], dependencies=dependencies,
        permissions=permissions, schema=schema,
    )


def inspect_plugin(path: str | Path) -> PluginManifest:
    path = Path(path)
    if path.suffix.lower() != PLUGIN_EXTENSION:
        raise ValueError(f"plugin file must use {PLUGIN_EXTENSION}")
    if path.stat().st_size > MAX_PACKAGE_SIZE:
        raise ValueError("plugin package exceeds 20 MB")
    with zipfile.ZipFile(path) as package:
        if sum(item.file_size for item in package.infolist()) > MAX_UNCOMPRESSED_SIZE:
            raise ValueError("plugin package expands beyond 50 MB")
        return load_manifest(package)


class PluginManager:
    """Manage external packages while keeping plugin code out of the EXE."""

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.state_path = self.directory / "plugins.json"
        self._disabled = self._load_disabled()

    def _load_disabled(self) -> set[str]:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            values = raw.get("disabled", [])
            return {str(value) for value in values}
        except (OSError, ValueError, TypeError):
            return set()

    def _save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"disabled": sorted(self._disabled)}, indent=2), encoding="utf-8")
        temporary.replace(self.state_path)

    def scan(self) -> list[InstalledPlugin]:
        found: list[tuple[PluginManifest, Path]] = []
        if self.directory.exists():
            for path in sorted(self.directory.glob(f"*{PLUGIN_EXTENSION}")):
                try:
                    manifest = inspect_plugin(path)
                    if manifest.kind == "theme":
                        from .theme import load_theme
                        load_theme(path)
                    else:
                        from .data_provider import load_provider_config
                        load_provider_config(InstalledPlugin(manifest, path, True))
                    found.append((manifest, path))
                except (OSError, ValueError, zipfile.BadZipFile):
                    continue
        installed_ids = {manifest.plugin_id for manifest, _path in found}
        installed_kinds = {manifest.plugin_id: manifest.kind for manifest, _path in found}
        result = []
        for manifest, path in found:
            missing = [item for item in manifest.dependencies if item not in installed_ids]
            disabled = [item for item in manifest.dependencies if item in self._disabled]
            problem = ""
            if missing:
                problem = f"缺少前置：{', '.join(missing)}"
            elif disabled:
                problem = f"前置未启用：{', '.join(disabled)}"
            elif manifest.kind == "theme":
                invalid = [item for item in manifest.dependencies if installed_kinds.get(item) != "data-provider"]
                if invalid:
                    problem = f"前置不是数据接口：{', '.join(invalid)}"
            result.append(InstalledPlugin(manifest, path, manifest.plugin_id not in self._disabled, problem))
        return result

    def enabled_ids(self) -> set[str]:
        return {item.manifest.plugin_id for item in self.scan() if item.enabled and not item.problem}

    def install_many(self, sources: list[str | Path]) -> list[PluginManifest]:
        inspected = [(Path(source), inspect_plugin(source)) for source in sources]
        self.directory.mkdir(parents=True, exist_ok=True)
        for source, manifest in inspected:
            destination = self.directory / f"{manifest.plugin_id}{PLUGIN_EXTENSION}"
            runtime = self.directory / ".runtime" / manifest.plugin_id
            if runtime.exists():
                shutil.rmtree(runtime)
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            self._disabled.discard(manifest.plugin_id)
        self._save()
        return [manifest for _source, manifest in inspected]

    def set_enabled(self, plugin_ids: list[str], enabled: bool) -> None:
        inventory = {item.manifest.plugin_id: item for item in self.scan()}
        selected = set(plugin_ids)
        for plugin_id in plugin_ids:
            if plugin_id not in inventory:
                raise ValueError(f"plugin is not installed: {plugin_id}")
            if enabled:
                missing = [dependency for dependency in inventory[plugin_id].manifest.dependencies
                           if dependency not in inventory or
                           (dependency in self._disabled and dependency not in selected)]
                if missing:
                    raise ValueError(f"请先安装并启用前置插件：{', '.join(missing)}")
                if inventory[plugin_id].manifest.kind == "theme":
                    invalid = [dependency for dependency in inventory[plugin_id].manifest.dependencies
                               if inventory[dependency].manifest.kind != "data-provider"]
                    if invalid:
                        raise ValueError(f"主题前置必须是数据接口插件：{', '.join(invalid)}")
                self._disabled.discard(plugin_id)
            else:
                dependents = [item.manifest.name for item in inventory.values()
                              if item.enabled and item.manifest.plugin_id not in selected and
                              plugin_id in item.manifest.dependencies]
                if dependents:
                    raise ValueError(f"仍被以下插件使用：{', '.join(dependents)}")
                self._disabled.add(plugin_id)
        self._save()

    def uninstall(self, plugin_ids: list[str]) -> None:
        inventory = {item.manifest.plugin_id: item for item in self.scan()}
        blocked = [item.manifest.name for item in inventory.values() if item.enabled and
                   any(dependency in plugin_ids for dependency in item.manifest.dependencies) and
                   item.manifest.plugin_id not in plugin_ids]
        if blocked:
            raise ValueError(f"请先移除依赖这些前置的插件：{', '.join(blocked)}")
        for plugin_id in plugin_ids:
            item = inventory.get(plugin_id)
            if item:
                item.path.unlink()
            runtime = self.directory / ".runtime" / plugin_id
            if runtime.exists():
                shutil.rmtree(runtime)
            self._disabled.discard(plugin_id)
        self._save()
