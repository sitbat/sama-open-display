"""Local 1568x720 landscape content renderer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import psutil

from . import WIDTH, HEIGHT
from .theme import BUILTIN_THEMES, DisplayTheme


BG = "#07111f"
PANEL = "#10243b"
TEXT = "#eef7ff"
MUTED = "#8ba7bd"
ACCENT = "#32d3a2"


def _font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_image(image: Image.Image, size: tuple[int, int] = (WIDTH, HEIGHT), mode: str = "cover") -> Image.Image:
    image = image.convert("RGB")
    if mode == "contain":
        contained = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, "black")
        canvas.paste(contained, ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2))
        return canvas
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def text_frame(text: str, subtitle: str = "SamaRP") -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((48, 48, WIDTH - 48, HEIGHT - 48), radius=32, fill=PANEL)
    draw.text((80, 85), subtitle, font=_font(30), fill=ACCENT)
    draw.multiline_text((80, 185), text, font=_font(58, True), fill=TEXT, spacing=24)
    return image


def _meter(draw: ImageDraw.ImageDraw, y: int, label: str, value: float, color: str) -> None:
    draw.text((64, y), label, font=_font(32, True), fill=TEXT)
    draw.text((WIDTH - 164, y), f"{value:5.1f}%", font=_font(30), fill=MUTED)
    top = y + 58
    draw.rounded_rectangle((64, top, WIDTH - 64, top + 34), radius=17, fill="#1c3850")
    end = 64 + int((WIDTH - 128) * max(0, min(100, value)) / 100)
    if end > 64:
        draw.rounded_rectangle((64, top, end, top + 34), radius=17, fill=color)


def _background(theme: DisplayTheme) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), theme.background)
    if theme.background_image is not None:
        image = ImageOps.fit(theme.background_image, (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", image.size, theme.background + "b8")
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    return image


def _system_values() -> tuple[float, float, float, int]:
    cpu = psutil.cpu_percent(interval=0.05)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage(Path.home().anchor or "C:\\").percent
    hours = int((datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds() // 3600)
    return cpu, memory, disk, hours


def dashboard_frame(now: datetime | None = None, theme: DisplayTheme | None = None) -> Image.Image:
    now = now or datetime.now()
    theme = theme or BUILTIN_THEMES[0]
    image = _background(theme)
    draw = ImageDraw.Draw(image)
    cpu, memory, disk, hours = _system_values()

    if theme.preset == "minimal_clock":
        draw.text((WIDTH // 2, 235), now.strftime("%H:%M"), font=_font(190, True), fill=theme.text, anchor="mm")
        draw.text((WIDTH // 2, 370), now.strftime("%Y-%m-%d  %A"), font=_font(34), fill=theme.muted, anchor="mm")
        values = (("CPU", cpu), ("MEM", memory), ("DISK", disk))
        for index, (label, value) in enumerate(values):
            x = 405 + index * 280
            draw.rounded_rectangle((x, 470, x + 240, 590), radius=26, fill=theme.surface)
            draw.text((x + 28, 495), label, font=_font(25, True), fill=theme.muted)
            draw.text((x + 212, 540), f"{value:.0f}%", font=_font(38, True), fill=theme.accent, anchor="ra")
        return image

    if theme.preset == "system_grid":
        draw.text((52, 45), now.strftime("%H:%M"), font=_font(92, True), fill=theme.text)
        draw.text((55, 155), now.strftime("%Y-%m-%d"), font=_font(28), fill=theme.muted)
        cards = (("CPU", cpu, theme.accent), ("MEMORY", memory, theme.accent_2),
                 ("DISK", disk, theme.accent_3), ("UPTIME", hours, theme.accent))
        for index, (label, value, color) in enumerate(cards):
            column, row = index % 2, index // 2
            x, y = 500 + column * 510, 55 + row * 310
            draw.rounded_rectangle((x, y, x + 460, y + 260), radius=30, fill=theme.surface)
            draw.text((x + 34, y + 32), label, font=_font(28, True), fill=theme.muted)
            suffix = " h" if label == "UPTIME" else "%"
            draw.text((x + 34, y + 112), f"{value:.0f}{suffix}", font=_font(70, True), fill=color)
        return image

    draw.text((56, 55), now.strftime("%H:%M"), font=_font(126, True), fill=theme.text)
    draw.text((64, 210), now.strftime("%Y-%m-%d  %A"), font=_font(28), fill=theme.muted)
    draw.rounded_rectangle((600, 46, WIDTH - 40, HEIGHT - 64), radius=34, fill=theme.surface)

    def landscape_meter(y: int, label: str, value: float, color: str) -> None:
        draw.text((650, y), label, font=_font(30, True), fill=theme.text)
        draw.text((WIDTH - 190, y), f"{value:5.1f}%", font=_font(28), fill=theme.muted)
        top = y + 48
        draw.rounded_rectangle((650, top, WIDTH - 90, top + 28), radius=14, fill=theme.surface_alt)
        end = 650 + int((WIDTH - 740) * max(0, min(100, value)) / 100)
        if end > 650:
            draw.rounded_rectangle((650, top, end, top + 28), radius=14, fill=color)

    landscape_meter(105, "CPU", cpu, theme.accent)
    landscape_meter(265, "MEMORY", memory, theme.accent_2)
    landscape_meter(425, "DISK", disk, theme.accent_3)
    draw.text((64, 350), "SYSTEM UPTIME", font=_font(28), fill=theme.muted)
    draw.text((64, 405), f"{hours} hours", font=_font(58, True), fill=theme.text)
    draw.text((64, 635), "1568 × 720  •  LANDSCAPE", font=_font(25), fill=theme.accent)
    return image


def hardware_test_card() -> Image.Image:
    """Orientation and channel test card for a single controlled hardware test."""
    image = Image.new("RGB", (WIDTH, HEIGHT), "#080808")
    draw = ImageDraw.Draw(image)
    draw.rectangle((3, 3, WIDTH - 4, HEIGHT - 4), outline="white", width=7)
    draw.text((WIDTH // 2, 38), "TOP / 上", font=_font(46, True), fill="white", anchor="ma")
    draw.polygon(((WIDTH // 2, 112), (WIDTH // 2 - 28, 170), (WIDTH // 2 + 28, 170)), fill="white")

    size = 145
    corners = [
        ((30, 135), (255, 0, 0), "TL  RED"),
        ((WIDTH - 30 - size, 135), (0, 255, 0), "TR  GREEN"),
        ((30, HEIGHT - 30 - size), (0, 0, 255), "BL  BLUE"),
        ((WIDTH - 30 - size, HEIGHT - 30 - size), (255, 255, 0), "BR  YELLOW"),
    ]
    for (x, y), color, label in corners:
        draw.rectangle((x, y, x + size, y + size), fill=color, outline="white", width=4)
        text_color = "black" if color in {(0, 255, 0), (255, 255, 0)} else "white"
        draw.multiline_text((x + size // 2, y + size // 2), label.replace("  ", "\n"),
                            font=_font(27, True), fill=text_color, anchor="mm", align="center")

    draw.line((WIDTH // 2, 115, WIDTH // 2, HEIGHT - 115), fill="#666666", width=3)
    draw.line((110, HEIGHT // 2, WIDTH - 110, HEIGHT // 2), fill="#666666", width=3)
    draw.ellipse((WIDTH // 2 - 105, HEIGHT // 2 - 105, WIDTH // 2 + 105, HEIGHT // 2 + 105),
                 outline="white", width=6)
    draw.text((WIDTH // 2, HEIGHT // 2 - 18), "CENTER", font=_font(42, True), fill="white", anchor="mm")
    draw.text((WIDTH // 2, HEIGHT // 2 + 40), "1568 × 720", font=_font(27), fill="#bbbbbb", anchor="mm")

    palette_y = HEIGHT // 2 + 150
    palette = ["#ff0000", "#00ff00", "#0000ff", "#00ffff", "#ff00ff", "#ffff00", "#ffffff", "#000000"]
    block = (WIDTH - 80) // len(palette)
    for index, color in enumerate(palette):
        x = 40 + index * block
        draw.rectangle((x, palette_y, x + block, palette_y + 65), fill=color, outline="#777777")
    draw.text((WIDTH // 2, palette_y + 88), "RGB / CMY / WHITE / BLACK", font=_font(24), fill="white", anchor="ma")
    return image
