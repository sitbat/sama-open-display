"""SamaRP declarative plugin package validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


PLUGIN_EXTENSION = ".samarppkg"


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    author: str
    kind: str
    entry: str
    description: str = ""
    schema: int = 1


def load_manifest(package: zipfile.ZipFile) -> PluginManifest:
    if "manifest.toml" not in package.namelist():
        raise ValueError("plugin package does not contain manifest.toml")
    raw = tomllib.loads(package.read("manifest.toml").decode("utf-8"))
    if set(raw) != {"plugin"}:
        raise ValueError("manifest must contain only a [plugin] section")
    data = raw["plugin"]
    allowed = {"schema", "id", "name", "version", "author", "kind", "entry", "description"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown manifest option(s): {', '.join(sorted(unknown))}")
    schema = int(data.get("schema", 1))
    if schema != 1:
        raise ValueError(f"unsupported plugin schema: {schema}")
    plugin_id = str(data.get("id", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", plugin_id):
        raise ValueError("plugin.id must be a stable lowercase identifier")
    version = str(data.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version):
        raise ValueError("plugin.version must use semantic versioning")
    kind = str(data.get("kind", ""))
    if kind not in {"theme"}:
        raise ValueError(f"unsupported plugin kind: {kind}")
    entry = str(data.get("entry", ""))
    if not entry or "/" in entry or "\\" in entry or entry not in package.namelist():
        raise ValueError("plugin.entry must name a file in the package root")
    return PluginManifest(
        plugin_id=plugin_id, name=str(data.get("name", plugin_id))[:80], version=version,
        author=str(data.get("author", "Unknown"))[:80], kind=kind, entry=entry,
        description=str(data.get("description", ""))[:240], schema=schema,
    )


def inspect_plugin(path: str | Path) -> PluginManifest:
    path = Path(path)
    if path.suffix.lower() != PLUGIN_EXTENSION:
        raise ValueError(f"plugin file must use {PLUGIN_EXTENSION}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("plugin package exceeds 20 MB")
    with zipfile.ZipFile(path) as package:
        return load_manifest(package)
