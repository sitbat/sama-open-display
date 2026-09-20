"""Portable display themes supplied by SamaRP plugin packages."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
import shutil
import zipfile

from PIL import Image
from .plugin import PLUGIN_EXTENSION, load_manifest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class DisplayTheme:
    theme_id: str
    name: str
    author: str = "SamaRP contributors"
    description: str = ""
    preset: str = "dashboard"
    background: str = "#07111f"
    surface: str = "#10243b"
    surface_alt: str = "#1c3850"
    text: str = "#eef7ff"
    muted: str = "#8ba7bd"
    accent: str = "#32d3a2"
    accent_2: str = "#4fb6ff"
    accent_3: str = "#b084ff"
    background_image: Image.Image | None = None
    source: Path | None = None
    plugin_id: str = ""
    dependencies: tuple[str, ...] = ()


BUILTIN_THEMES = (
    DisplayTheme("midnight", "午夜蓝", description="默认深色系统仪表盘"),
    DisplayTheme(
        "daylight", "日光", description="清爽明亮的系统仪表盘", background="#edf4fb",
        surface="#ffffff", surface_alt="#dce8f2", text="#10233d", muted="#60758e",
        accent="#008c78", accent_2="#157ad6", accent_3="#7157c8",
    ),
    DisplayTheme(
        "minimal", "极简时钟", description="突出时间，弱化系统信息", preset="minimal_clock",
        background="#f7f8fb", surface="#ffffff", surface_alt="#e5e9f0", text="#162033",
        muted="#697386", accent="#0067c0", accent_2="#00a3a3", accent_3="#7a5af8",
    ),
)


def _color(value: object, key: str, fallback: str) -> str:
    value = fallback if value is None else str(value)
    if not _COLOR.fullmatch(value):
        raise ValueError(f"{key} must be a #RRGGBB color")
    return value.lower()


def _parse_theme(raw: dict, *, source: Path | None = None, background_image=None,
                 plugin_id: str = "", dependencies: tuple[str, ...] = ()) -> DisplayTheme:
    allowed_sections = {"theme", "display", "palette"}
    unknown = set(raw) - allowed_sections
    if unknown:
        raise ValueError(f"unknown theme section(s): {', '.join(sorted(unknown))}")
    meta, display, palette = raw.get("theme", {}), raw.get("display", {}), raw.get("palette", {})
    theme_id = str(meta.get("id", "")).strip()
    name = str(meta.get("name", "")).strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,47}", theme_id):
        raise ValueError("theme.id must be 2-48 lowercase letters, digits, _ or -")
    if not name or len(name) > 60:
        raise ValueError("theme.name must be 1-60 characters")
    preset = str(display.get("preset", "dashboard"))
    if preset not in {"dashboard", "minimal_clock", "system_grid"}:
        raise ValueError("display.preset must be dashboard, minimal_clock or system_grid")
    defaults = BUILTIN_THEMES[0]
    return DisplayTheme(
        theme_id=theme_id, name=name, author=str(meta.get("author", "Unknown"))[:80],
        description=str(meta.get("description", ""))[:240], preset=preset,
        background=_color(palette.get("background"), "background", defaults.background),
        surface=_color(palette.get("surface"), "surface", defaults.surface),
        surface_alt=_color(palette.get("surface_alt"), "surface_alt", defaults.surface_alt),
        text=_color(palette.get("text"), "text", defaults.text),
        muted=_color(palette.get("muted"), "muted", defaults.muted),
        accent=_color(palette.get("accent"), "accent", defaults.accent),
        accent_2=_color(palette.get("accent_2"), "accent_2", defaults.accent_2),
        accent_3=_color(palette.get("accent_3"), "accent_3", defaults.accent_3),
        background_image=background_image, source=source, plugin_id=plugin_id,
        dependencies=dependencies,
    )


def load_theme(path: str | Path) -> DisplayTheme:
    """Validate and load one theme package without extracting arbitrary files."""
    path = Path(path)
    if path.suffix.lower() != PLUGIN_EXTENSION:
        raise ValueError(f"theme file must use {PLUGIN_EXTENSION}")
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("plugin package exceeds 20 MB")
    with zipfile.ZipFile(path) as package:
        names = set(package.namelist())
        manifest = load_manifest(package)
        if manifest.kind != "theme":
            raise ValueError("plugin is not a theme")
        entry = manifest.entry
        if entry not in names:
            raise ValueError("theme package does not contain theme.toml")
        raw = tomllib.loads(package.read(entry).decode("utf-8"))
        image = None
        background_name = str(raw.get("display", {}).get("background_image", "")).strip()
        if background_name:
            if background_name not in names or "/" in background_name or "\\" in background_name:
                raise ValueError("background_image must name a file in the package root")
            if package.getinfo(background_name).file_size > 12 * 1024 * 1024:
                raise ValueError("background image exceeds 12 MB")
            with Image.open(BytesIO(package.read(background_name))) as opened:
                image = opened.convert("RGB")
        return _parse_theme(raw, source=path, background_image=image,
                            plugin_id=manifest.plugin_id, dependencies=manifest.dependencies)


def discover_themes(directory: str | Path, enabled_ids: set[str] | None = None) -> list[DisplayTheme]:
    themes = list(BUILTIN_THEMES)
    directory = Path(directory)
    if directory.exists():
        for path in sorted(directory.glob(f"*{PLUGIN_EXTENSION}")):
            try:
                loaded = load_theme(path)
            except (OSError, ValueError, zipfile.BadZipFile):
                continue
            if enabled_ids is not None and loaded.plugin_id not in enabled_ids:
                continue
            themes = [theme for theme in themes if theme.theme_id != loaded.theme_id]
            themes.append(loaded)
    return themes


def install_theme(source: str | Path, directory: str | Path) -> DisplayTheme:
    theme = load_theme(source)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    extension = Path(source).suffix.lower()
    destination = directory / f"{theme.theme_id}{extension}"
    if Path(source).resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return load_theme(destination)
