"""Safety-gated display controller and deterministic transfer planning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from time import sleep
from collections.abc import Callable
from typing import Protocol
from PIL import Image

from .codec import encode_full_frame
from .device import primary_display
from .protocol import (
    Command, DeviceIdentity, brightness_packet, command_packet,
    display_bitmap_header, pad_command, parse_device_identity, start_bitmap_packet,
    update_bitmap_packets,
)
from .transport import Win32Serial


class AuthorizationRequired(PermissionError):
    pass


class ControllerState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    READY = "ready"
    ERROR = "error"


class Transport(Protocol):
    def open(self): ...
    def close(self) -> None: ...
    def write(self, data: bytes) -> int: ...
    def read(self, size: int) -> bytes: ...


@dataclass(frozen=True)
class TransferStep:
    name: str
    data: bytes
    read_size: int = 0


def full_frame_plan(image: Image.Image, brightness: int = 70, panel_rotation: int = 90) -> list[TransferStep]:
    """Build the exact byte plan without opening or writing to hardware."""
    pixels = pad_command(encode_full_frame(image, panel_rotation=panel_rotation))
    options = bytes((0, 0, 0, 0))
    return [
        TransferStep("stop-video", command_packet(Command.STOP_VIDEO)),
        TransferStep("stop-media", command_packet(Command.STOP_MEDIA), 1024),
        TransferStep("brightness", brightness_packet(brightness)),
        TransferStep("options", command_packet(Command.OPTIONS, options)),
        TransferStep("pre-update", command_packet(Command.PRE_UPDATE_BITMAP)),
        TransferStep("start-bitmap", start_bitmap_packet()),
        TransferStep("display-header", pad_command(display_bitmap_header())),
        TransferStep("pixels", pixels, 1024),
        TransferStep("query-status", command_packet(Command.QUERY_STATUS), 1024),
    ]


class DisplayController:
    """Hardware access requires ``allow_hardware=True`` on every connection."""

    def __init__(self, transport: Transport | None = None):
        self.transport = transport
        self.state = ControllerState.DISCONNECTED
        self.device_id: bytes | None = None
        self.identity: DeviceIdentity | None = None
        self.update_count = 0

    def connect(self, *, allow_hardware: bool = False) -> None:
        if not allow_hardware:
            raise AuthorizationRequired("hardware writes are disabled; explicit authorization is required")
        if self.transport is None:
            device = primary_display()
            if device is None or device.port is None:
                raise ConnectionError("SAMA display serial port was not found")
            self.transport = Win32Serial(device.port)
        try:
            self.transport.open()
            self.state = ControllerState.CONNECTED
        except Exception:
            self.state = ControllerState.ERROR
            raise

    def hello(self) -> bytes:
        if self.state is not ControllerState.CONNECTED or self.transport is None:
            raise ConnectionError("controller is not connected")
        self.transport.write(command_packet(Command.HELLO))
        self.device_id = self.transport.read(23)
        if not self.device_id:
            self.state = ControllerState.ERROR
            raise TimeoutError("display did not answer HELLO")
        try:
            self.identity = parse_device_identity(self.device_id)
        except (UnicodeDecodeError, ValueError):
            self.state = ControllerState.ERROR
            raise
        self.state = ControllerState.READY
        return self.device_id

    def display(
        self,
        image: Image.Image,
        brightness: int = 70,
        panel_rotation: int = 90,
        progress: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        if self.state is not ControllerState.READY or self.transport is None:
            raise ConnectionError("HELLO handshake has not completed")
        if self.identity is None or self.identity.model != "65inch" or self.identity.rom_version <= 88:
            raise RuntimeError("full-frame BGRA transfer is not validated for this device identity")
        try:
            plan = full_frame_plan(image, brightness, panel_rotation)
            total = sum(len(step.data) for step in plan)
            sent = 0
            for step in plan:
                for offset in range(0, len(step.data), 250):
                    if cancelled and cancelled():
                        raise InterruptedError("display transfer cancelled")
                    block = step.data[offset : offset + 250]
                    self.transport.write(block)
                    sent += len(block)
                    if progress:
                        progress(sent, total)
                if step.read_size:
                    self.transport.read(step.read_size)
        except Exception:
            self.state = ControllerState.ERROR
            raise

    def reconnect(self, attempts: int = 3, delay: float = 0.5, *, allow_hardware: bool = False) -> None:
        self.close()
        last_error: Exception | None = None
        for attempt in range(max(1, attempts)):
            try:
                self.connect(allow_hardware=allow_hardware)
                self.hello()
                return
            except Exception as exc:
                last_error = exc
                self.close()
                if attempt + 1 < attempts:
                    sleep(delay)
        raise ConnectionError(f"reconnect failed after {attempts} attempt(s)") from last_error

    def update_frame(
        self,
        previous: Image.Image,
        current: Image.Image,
        frame_id: int,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        """Send a hardware-validated OEM CC delta from one complete frame to the next."""
        if self.state is not ControllerState.READY or self.transport is None:
            raise ConnectionError("HELLO handshake has not completed")
        if self.identity is None or self.identity.model != "65inch" or self.identity.rom_version <= 88:
            raise RuntimeError("region update is not valid for this device identity")
        packets = update_bitmap_packets(previous, current, frame_id)
        if packets is None:
            return False
        header, pixels = packets
        try:
            # The OEM 3.1.1 CC path sends only the command block and framed
            # delta stream. A status command here can race the firmware's
            # application of the preceding update.
            for packet in (header, pixels):
                for offset in range(0, len(packet), 250):
                    if cancelled and cancelled():
                        raise InterruptedError("display transfer cancelled")
                    self.transport.write(packet[offset : offset + 250])
            self.update_count = (self.update_count + 1) & 0xFFFFFFFF
            return True
        except Exception:
            self.state = ControllerState.ERROR
            raise

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
        self.state = ControllerState.DISCONNECTED

    def __enter__(self):
        raise AuthorizationRequired("use connect(allow_hardware=True) explicitly")

    def __exit__(self, *_exc):
        self.close()
