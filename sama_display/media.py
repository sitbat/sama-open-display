"""Normalized video frame sources for preview and future transmission."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator
from PIL import Image

from . import WIDTH, HEIGHT
from .render import fit_image


@dataclass(frozen=True)
class MediaFrame:
    image: Image.Image
    duration_ms: int
    index: int


def iter_video(
    path: str | Path,
    size: tuple[int, int] = (WIDTH, HEIGHT),
    fit: str = "cover",
    max_fps: float = 10,
) -> Iterator[MediaFrame]:
    """Yield throttled video frames. Install the optional ``video`` extra."""
    if max_fps <= 0:
        raise ValueError("max_fps must be positive")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("video support requires: pip install .[video]") from exc
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"cannot open video: {path}")
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or max_fps)
    source_fps = source_fps if source_fps > 0 else max_fps
    output_fps = min(source_fps, max_fps)
    step = max(1, round(source_fps / output_fps))
    duration_ms = max(1, round(1000 / output_fps))
    source_index = 0
    output_index = 0
    try:
        while True:
            ok, bgr = capture.read()
            if not ok:
                break
            if source_index % step == 0:
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb)
                yield MediaFrame(fit_image(image, size, fit), duration_ms, output_index)
                output_index += 1
            source_index += 1
    finally:
        capture.release()


def iter_media(
    path: str | Path,
    size: tuple[int, int] = (WIDTH, HEIGHT),
    fit: str = "cover",
    max_fps: float = 10,
) -> Iterator[MediaFrame]:
    path = Path(path)
    if path.suffix.lower() == ".gif":
        raise ValueError("GIF input is not supported")
    yield from iter_video(path, size=size, fit=fit, max_fps=max_fps)
