"""Read-only Windows USB/COM device discovery."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import os
from typing import Iterable


DISPLAY_VID = 0x1D6B
DISPLAY_PID = 0xA065
HELPER_VID = 0x1A86
HELPER_PID = 0xCA65


@dataclass(frozen=True)
class DeviceInfo:
    role: str
    vid: int
    pid: int
    port: str | None
    instance_id: str
    friendly_name: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _value(key, name: str) -> str | None:
    try:
        import winreg
        value, _ = winreg.QueryValueEx(key, name)
        return str(value)
    except OSError:
        return None


def _port_name(instance_key) -> str | None:
    try:
        import winreg
        with winreg.OpenKey(instance_key, r"Device Parameters") as params:
            return _value(params, "PortName")
    except OSError:
        return None


def _enumerate_pair(vid: int, pid: int, role: str) -> Iterable[DeviceInfo]:
    if os.name != "nt":
        return
    import winreg

    path = rf"SYSTEM\CurrentControlSet\Enum\USB\VID_{vid:04X}&PID_{pid:04X}"
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
    except OSError:
        return
    with root:
        index = 0
        while True:
            try:
                instance = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            with winreg.OpenKey(root, instance) as instance_key:
                yield DeviceInfo(
                    role=role,
                    vid=vid,
                    pid=pid,
                    port=_port_name(instance_key),
                    instance_id=rf"USB\VID_{vid:04X}&PID_{pid:04X}\{instance}",
                    friendly_name=_value(instance_key, "FriendlyName") or _value(instance_key, "DeviceDesc"),
                )


def discover_devices() -> list[DeviceInfo]:
    """Discover supported devices without opening a serial port or writing data."""
    devices = list(_enumerate_pair(DISPLAY_VID, DISPLAY_PID, "display"))
    devices.extend(_enumerate_pair(HELPER_VID, HELPER_PID, "helper"))
    return sorted(devices, key=lambda item: (item.role != "display", item.port or ""))


def primary_display() -> DeviceInfo | None:
    return next((item for item in discover_devices() if item.role == "display" and item.port), None)

