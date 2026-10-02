"""Portable display themes supplied by SAMA Open Display plugin packages."""

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
_BINDING = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PALETTE_NAMES = {"background", "surface", "surface_alt", "text", "muted", "accent", "accent_2", "accent_3"}
SYSTEM_METRICS_PLUGIN_ID = "io.github.sitbat.sama-open-display.system-metrics"


@dataclass(frozen=True)
class LayoutElement:
    element_type: str
    x: int
    y: int
    width: int = 0
    height: int = 0
    text: str = ""
    bind: str = ""
    format_spec: str = ""
    prefix: str = ""
    suffix: str = ""
    color: str = "text"
    background: str = "surface"
    font_size: int = 32
    bold: bool = False
    align: str = "left"
    radius: int = 0
    minimum: float = 0
    maximum: float = 100
    asset: str = ""
    fit: str = "cover"


@dataclass(frozen=True)
class DisplayTheme:
    theme_id: str
    name: str
    author: str = "SAMA Open Display contributors"
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
    elements: tuple[LayoutElement, ...] = ()
    assets: tuple[tuple[str, Image.Image], ...] = ()


BUILTIN_THEMES = (
    DisplayTheme("midnight", "午夜蓝", description="默认深色系统仪表盘",
                 dependencies=(SYSTEM_METRICS_PLUGIN_ID,)),
    DisplayTheme(
        "daylight", "日光", description="清爽明亮的系统仪表盘", background="#edf4fb",
        surface="#ffffff", surface_alt="#dce8f2", text="#10233d", muted="#60758e",
        accent="#008c78", accent_2="#157ad6", accent_3="#7157c8",
        dependencies=(SYSTEM_METRICS_PLUGIN_ID,),
    ),
    DisplayTheme(
        "minimal", "极简时钟", description="突出时间，弱化系统信息", preset="minimal_clock",
        background="#f7f8fb", surface="#ffffff", surface_alt="#e5e9f0", text="#162033",
        muted="#697386", accent="#0067c0", accent_2="#00a3a3", accent_3="#7a5af8",
        dependencies=(SYSTEM_METRICS_PLUGIN_ID,),
    ),
)


def _color(value: object, key: str, fallback: str) -> str:
    value = fallback if value is None else str(value)
    if not _COLOR.fullmatch(value):
        raise ValueError(f"{key} must be a #RRGGBB color")
    return value.lower()


def _layout_color(value: object, key: str, fallback: str) -> str:
    value = fallback if value is None else str(value)
    if value in _PALETTE_NAMES or _COLOR.fullmatch(value):
        return value.lower()
    raise ValueError(f"{key} must be a palette name or #RRGGBB color")


def _integer(data: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    value = int(data.get(key, default))
    if not minimum <= value <= maximum:
        raise ValueError(f"element.{key} must be in [{minimum}, {maximum}]")
    return value


def _parse_elements(raw_elements: object) -> tuple[LayoutElement, ...]:
    if not isinstance(raw_elements, list) or not raw_elements:
        raise ValueError("custom layout requires at least one [[element]]")
    if len(raw_elements) > 128:
        raise ValueError("custom layout exceeds 128 elements")
    elements: list[LayoutElement] = []
    common = {"type", "x", "y", "width", "height", "color", "background", "radius"}
    allowed_by_type = {
        "rectangle": common,
        "text": common | {"text", "bind", "format", "prefix", "suffix", "font_size", "bold", "align"},
        "progress": common | {"bind", "minimum", "maximum"},
        "image": common | {"asset", "fit"},
    }
    for index, item in enumerate(raw_elements):
        if not isinstance(item, dict):
            raise ValueError(f"element {index} must be a table")
        element_type = str(item.get("type", ""))
        if element_type not in allowed_by_type:
            raise ValueError(f"unsupported element type: {element_type}")
        unknown = set(item) - allowed_by_type[element_type]
        if unknown:
            raise ValueError(f"unknown {element_type} option(s): {', '.join(sorted(unknown))}")
        x = _integer(item, "x", 0, 0, 1568)
        y = _integer(item, "y", 0, 0, 720)
        width = _integer(item, "width", 0, 0, 1568)
        height = _integer(item, "height", 0, 0, 720)
        if element_type in {"rectangle", "progress", "image"} and (width <= 0 or height <= 0):
            raise ValueError(f"{element_type} requires positive width and height")
        if x + width > 1568 or y + height > 720:
            raise ValueError(f"element {index} exceeds the 1568x720 canvas")
        bind = str(item.get("bind", ""))
        if bind and not _BINDING.fullmatch(bind):
            raise ValueError(f"invalid element binding: {bind}")
        if element_type == "progress" and not bind:
            raise ValueError("progress element requires bind")
        text = str(item.get("text", ""))
        if element_type == "text" and not text and not bind:
            raise ValueError("text element requires text or bind")
        align = str(item.get("align", "left"))
        if align not in {"left", "center", "right"}:
            raise ValueError("element.align must be left, center or right")
        fit = str(item.get("fit", "cover"))
        if fit not in {"cover", "contain"}:
            raise ValueError("element.fit must be cover or contain")
        minimum = float(item.get("minimum", 0))
        maximum = float(item.get("maximum", 100))
        if maximum <= minimum:
            raise ValueError("element.maximum must be greater than minimum")
        format_spec = str(item.get("format", ""))
        if len(format_spec) > 24 or any(character in format_spec for character in "{}!"):
            raise ValueError("element.format contains unsupported characters")
        asset = str(item.get("asset", ""))
        if element_type == "image" and (not asset or "/" in asset or "\\" in asset):
            raise ValueError("image element asset must name a package-root file")
        elements.append(LayoutElement(
            element_type=element_type, x=x, y=y, width=width, height=height,
            text=text[:500], bind=bind, format_spec=format_spec,
            prefix=str(item.get("prefix", ""))[:80], suffix=str(item.get("suffix", ""))[:80],
            color=_layout_color(item.get("color"), "element.color", "text"),
            background=_layout_color(item.get("background"), "element.background", "surface"),
            font_size=_integer(item, "font_size", 32, 8, 240), bold=bool(item.get("bold", False)),
            align=align, radius=_integer(item, "radius", 0, 0, 200),
            minimum=minimum, maximum=maximum, asset=asset, fit=fit,
        ))
    return tuple(elements)


def _parse_theme(raw: dict, *, source: Path | None = None, background_image=None,
                 plugin_id: str = "", dependencies: tuple[str, ...] = (),
                 schema: int = 1, assets: tuple[tuple[str, Image.Image], ...] = ()) -> DisplayTheme:
    allowed_sections = {"theme", "display", "palette", "element"}
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
    if preset not in {"dashboard", "minimal_clock", "system_grid", "custom"}:
        raise ValueError("display.preset must be dashboard, minimal_clock, system_grid or custom")
    if preset == "custom" and schema < 2:
        raise ValueError("custom layout requires plugin schema 2")
    elements = _parse_elements(raw.get("element")) if preset == "custom" else ()
    if preset != "custom" and "element" in raw:
        raise ValueError("[[element]] is only valid for the custom preset")
    if preset != "custom" and SYSTEM_METRICS_PLUGIN_ID not in dependencies:
        dependencies = (*dependencies, SYSTEM_METRICS_PLUGIN_ID)
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
        dependencies=dependencies, elements=elements, assets=assets,
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
        assets: list[tuple[str, Image.Image]] = []
        asset_names = {
            str(element.get("asset", ""))
            for element in raw.get("element", [])
            if isinstance(element, dict) and str(element.get("type", "")) == "image"
        }
        for asset_name in sorted(asset_names):
            if not asset_name or asset_name not in names or "/" in asset_name or "\\" in asset_name:
                raise ValueError("image element asset must name a package-root file")
            if package.getinfo(asset_name).file_size > 12 * 1024 * 1024:
                raise ValueError(f"layout image exceeds 12 MB: {asset_name}")
            with Image.open(BytesIO(package.read(asset_name))) as opened:
                assets.append((asset_name, opened.convert("RGBA")))
        return _parse_theme(raw, source=path, background_image=image,
                            plugin_id=manifest.plugin_id, dependencies=manifest.dependencies,
                            schema=manifest.schema, assets=tuple(assets))


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
