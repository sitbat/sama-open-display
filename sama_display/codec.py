"""Pixel encoding helpers for Rev-C displays."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from PIL import Image, ImageChops


@dataclass(frozen=True)
class ChangedRegion:
    x: int
    y: int
    image: Image.Image


def chunks(data: bytes, size: int) -> Iterable[bytes]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for offset in range(0, len(data), size):
        yield data[offset : offset + size]


def image_to_bgra(image: Image.Image) -> bytes:
    """Return pixels in B,G,R,A byte order, row-major."""
    return image.convert("RGBA").tobytes("raw", "BGRA")


def landscape_pixel_index(x: int, y: int, width: int = 1568, height: int = 720) -> int:
    """Map a landscape canvas coordinate to the OEM CC scan-buffer index.

    The 6.5-inch panel consumes a clockwise-rotated ``720 x 1568`` BGRA
    buffer. The OEM encoder addresses that buffer in ordinary row-major
    order, so ``panel_x = height - 1 - y`` and ``panel_y = x``.
    """
    if not 0 <= x < width or not 0 <= y < height:
        raise ValueError(f"coordinate ({x}, {y}) is outside {width}x{height}")
    panel_x = height - 1 - y
    panel_y = x
    return panel_y * height + panel_x


def rotate_for_panel(image: Image.Image, clockwise_degrees: int = 90) -> Image.Image:
    """Apply the physical panel scan transform without interpolation."""
    transforms = {
        0: None,
        90: Image.Transpose.ROTATE_270,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_90,
    }
    if clockwise_degrees not in transforms:
        raise ValueError("rotation must be 0, 90, 180 or 270 degrees")
    transform = transforms[clockwise_degrees]
    return image.copy() if transform is None else image.transpose(transform)


def prepare_transfer_frame(
    image: Image.Image,
    protocol_width: int = 720,
    protocol_height: int = 1568,
    panel_rotation: int = 90,
) -> Image.Image:
    """Convert the user-facing canvas into the panel's fixed scan buffer."""
    expected = ((protocol_height, protocol_width)
                if panel_rotation in {90, 270}
                else (protocol_width, protocol_height))
    if image.size != expected:
        raise ValueError(f"canvas must be {expected[0]}x{expected[1]}, got {image.width}x{image.height}")
    prepared = rotate_for_panel(image, panel_rotation)
    if prepared.size != (protocol_width, protocol_height):
        raise AssertionError("panel transform did not produce the protocol scan dimensions")
    return prepared


def encode_full_frame(
    image: Image.Image,
    width: int = 720,
    height: int = 1568,
    panel_rotation: int = 90,
) -> bytes:
    panel_image = prepare_transfer_frame(image, width, height, panel_rotation)
    return b"\x00".join(chunks(image_to_bgra(panel_image), 249))


def changed_region(previous: Image.Image, current: Image.Image, margin: int = 0) -> ChangedRegion | None:
    """Return the smallest changed rectangle, or ``None`` for identical frames."""
    if previous.size != current.size:
        raise ValueError("frames must have the same dimensions")
    if margin < 0:
        raise ValueError("margin cannot be negative")
    old = previous.convert("RGB")
    new = current.convert("RGB")
    bbox = ImageChops.difference(old, new).getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(current.width, right + margin)
    bottom = min(current.height, bottom + margin)
    return ChangedRegion(left, top, current.crop((left, top, right, bottom)).convert("RGB"))
