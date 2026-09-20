"""Rev-C protocol primitives for the SAMA USB display.

Derived in part from turing-smart-screen-python's lcd_comm_rev_c.py,
Copyright Mathoudebine and contributors, GPL-3.0-or-later.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from PIL import Image

from .codec import chunks, image_to_bgra, prepare_transfer_frame

MAGIC = b"\xEF\x69"
COMMAND_BLOCK_SIZE = 250
PIXEL_CHUNK_SIZE = 249


@dataclass(frozen=True)
class DeviceIdentity:
    raw: str
    model: str
    device_revision: int
    rom_family: int
    rom_version: int


_DEVICE_ID = re.compile(
    r"^chs_(?P<model>[^.]+)\.dev(?P<device>\d+)_rom(?P<family>\d+)\.(?P<version>\d+)$"
)


def parse_device_identity(value: bytes | str) -> DeviceIdentity:
    text = value.decode("ascii", errors="strict") if isinstance(value, bytes) else value
    text = text.rstrip("\x00\r\n")
    match = _DEVICE_ID.fullmatch(text)
    if match is None:
        raise ValueError(f"unsupported display identity: {text!r}")
    return DeviceIdentity(
        raw=text,
        model=match.group("model"),
        device_revision=int(match.group("device")),
        rom_family=int(match.group("family")),
        rom_version=int(match.group("version")),
    )


class Command(Enum):
    HELLO = bytes((0x01, 0xEF, 0x69, 0, 0, 0, 1, 0, 0, 0, 0xC5, 0xD3))
    OPTIONS = bytes((0x7D, 0xEF, 0x69, 0, 0, 0, 5, 0, 0, 0, 0x2D))
    RESTART = bytes((0x84, 0xEF, 0x69, 0, 0, 0, 1))
    SCREEN_OFF = bytes((0x83, 0xEF, 0x69, 0, 0, 0, 1))
    SCREEN_ON = bytes((0x83, 0xEF, 0x69, 0, 0, 0, 0))
    SET_BRIGHTNESS = bytes((0x7B, 0xEF, 0x69, 0, 0, 0, 1, 0, 0, 0))
    STOP_VIDEO = bytes((0x79, 0xEF, 0x69, 0, 0, 0, 1))
    STOP_MEDIA = bytes((0x96, 0xEF, 0x69, 0, 0, 0, 1))
    QUERY_STATUS = bytes((0xCF, 0xEF, 0x69, 0, 0, 0, 1))
    PRE_UPDATE_BITMAP = bytes((0x86, 0xEF, 0x69, 0, 0, 0, 1))
    UPDATE_BITMAP = bytes((0xCC, 0xEF, 0x69, 0))


def pad_command(data: bytes, pad: int = 0, block_size: int = COMMAND_BLOCK_SIZE) -> bytes:
    """Pad a command to an integral number of transport blocks."""
    if not 0 <= pad <= 255:
        raise ValueError("pad must be a byte")
    missing = (-len(data)) % block_size
    return data + bytes((pad,)) * missing


def command_packet(command: Command, payload: bytes = b"", pad: int = 0) -> bytes:
    return pad_command(command.value + payload, pad)


def brightness_packet(percent: int) -> bytes:
    if not 0 <= percent <= 100:
        raise ValueError("brightness must be 0..100")
    level = int(percent / 100 * 255)
    return command_packet(Command.SET_BRIGHTNESS, bytes((level,)))


def display_bitmap_header(width: int = 720, height: int = 1568) -> bytes:
    """Build the inferred Rev-C full-frame command for a display geometry."""
    if width <= 0 or height <= 0 or (width * height) % 64 or (width * width) % 64:
        raise ValueError("geometry must produce integral /64 protocol fields")
    total_units = width * height // 64
    row_units = width * width // 64
    if total_units > 0xFFFF or row_units > 0xFFFF:
        raise ValueError("geometry exceeds 16-bit protocol fields")
    return bytes((0xC8, 0xEF, 0x69, 0)) + total_units.to_bytes(2, "big") + row_units.to_bytes(2, "big")


def start_bitmap_packet() -> bytes:
    """The start command uses 0x2C as both first byte and padding."""
    return pad_command(b"\x2C", pad=0x2C)


def encode_delta_stream(previous: bytes, current: bytes, pixel_size: int = 4) -> bytes:
    """Encode the ROM >= 1.89 CC delta records used by the OEM application.

    A singleton is ``0x800000 | pixel_index`` followed by one pixel.  A run is
    a 23-bit pixel index, a 16-bit pixel count, then its pixels.  This format
    was recovered from the installed SAMA executable and checked against its
    encoder with controlled in-memory vectors.  It has not yet been sent to
    the physical 6.5-inch ROM 1.91 device.
    """
    if pixel_size <= 0:
        raise ValueError("pixel_size must be positive")
    if len(previous) != len(current) or len(current) % pixel_size:
        raise ValueError("frames must have equal, pixel-aligned byte lengths")
    pixel_count = len(current) // pixel_size
    if pixel_count > 0x800000:
        raise ValueError("frame exceeds the 23-bit CC pixel address space")

    changed: list[int] = []
    for index in range(pixel_count):
        offset = index * pixel_size
        if previous[offset : offset + pixel_size] != current[offset : offset + pixel_size]:
            changed.append(index)

    encoded = bytearray()
    position = 0
    while position < len(changed):
        start = changed[position]
        end = position + 1
        while end < len(changed) and changed[end] == changed[end - 1] + 1:
            end += 1
        run_length = end - position

        # The OEM encoder flushes a final singleton through the run form.
        if run_length == 1 and start != pixel_count - 1:
            encoded.extend((0x800000 | start).to_bytes(3, "big"))
            offset = start * pixel_size
            encoded.extend(current[offset : offset + pixel_size])
        else:
            remaining = run_length
            run_start = start
            while remaining:
                count = min(remaining, 0xFFFF)
                encoded.extend(run_start.to_bytes(3, "big"))
                encoded.extend(count.to_bytes(2, "big"))
                offset = run_start * pixel_size
                encoded.extend(current[offset : offset + count * pixel_size])
                run_start += count
                remaining -= count
        position = end
    return bytes(encoded)


def update_bitmap_packets(
    previous: Image.Image,
    current: Image.Image,
    frame_id: int,
    *,
    panel_rotation: int = 90,
) -> tuple[bytes, bytes] | None:
    """Build an offline CC command/data pair for two full presentation frames.

    The second metadata length is zero because the optional OEM auxiliary
    segment is intentionally not implemented.  Callers must keep this path
    hardware-disabled until a new controlled validation is explicitly approved.
    """
    if previous.size != current.size:
        raise ValueError("frames must have the same dimensions")
    if not 0 <= frame_id <= 0xFFFFFFFF:
        raise ValueError("frame_id must fit in 32 bits")
    old_panel = prepare_transfer_frame(previous, panel_rotation=panel_rotation)
    new_panel = prepare_transfer_frame(current, panel_rotation=panel_rotation)
    delta = encode_delta_stream(image_to_bgra(old_panel), image_to_bgra(new_panel))
    if not delta:
        return None

    stream = delta + MAGIC
    metadata = frame_id.to_bytes(4, "big") + (0).to_bytes(4, "big")
    header = (
        bytes((0xCC,)) + MAGIC + len(stream).to_bytes(4, "big")
        + b"\x00\x00\x00" + metadata
    )
    framed_stream = b"\x00".join(chunks(stream, PIXEL_CHUNK_SIZE))
    return pad_command(header), pad_command(framed_stream)
