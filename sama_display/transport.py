"""Minimal Windows serial transport implemented with Win32 APIs.

Opening a device and writing are deliberately explicit operations. Merely
importing or constructing this class never touches hardware.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os


class SerialError(OSError):
    pass


class DCB(ctypes.Structure):
    _fields_ = [
        ("DCBlength", wintypes.DWORD), ("BaudRate", wintypes.DWORD),
        ("flags", wintypes.DWORD), ("wReserved", wintypes.WORD),
        ("XonLim", wintypes.WORD), ("XoffLim", wintypes.WORD),
        ("ByteSize", ctypes.c_ubyte), ("Parity", ctypes.c_ubyte),
        ("StopBits", ctypes.c_ubyte), ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char), ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
        ("wReserved1", wintypes.WORD),
    ]


class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [
        ("ReadIntervalTimeout", wintypes.DWORD),
        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
        ("ReadTotalTimeoutConstant", wintypes.DWORD),
        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
        ("WriteTotalTimeoutConstant", wintypes.DWORD),
    ]


class Win32Serial:
    def __init__(self, port: str, baudrate: int = 115200, timeout_ms: int = 1000):
        if os.name != "nt":
            raise SerialError("Win32Serial is available only on Windows")
        self.port = port.upper()
        self.baudrate = baudrate
        self.timeout_ms = timeout_ms
        self.handle = None
        self._kernel32 = None

    @staticmethod
    def _api():
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        kernel32.GetCommState.restype = wintypes.BOOL
        kernel32.BuildCommDCBW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DCB)]
        kernel32.BuildCommDCBW.restype = wintypes.BOOL
        kernel32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        kernel32.SetCommState.restype = wintypes.BOOL
        kernel32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.POINTER(COMMTIMEOUTS)]
        kernel32.SetCommTimeouts.restype = wintypes.BOOL
        kernel32.WriteFile.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        ]
        kernel32.WriteFile.restype = wintypes.BOOL
        kernel32.ReadFile.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        ]
        kernel32.ReadFile.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32

    def open(self) -> "Win32Serial":
        if self.handle is not None:
            return self
        kernel32 = self._api()
        handle = kernel32.CreateFileW("\\\\.\\" + self.port, 0xC0000000, 0, None, 3, 0, None)
        invalid = wintypes.HANDLE(-1).value
        if handle == invalid:
            raise SerialError(ctypes.get_last_error(), f"cannot open {self.port}")
        self._kernel32 = kernel32
        self.handle = handle
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if not kernel32.GetCommState(handle, ctypes.byref(dcb)):
            self.close()
            raise SerialError(ctypes.get_last_error(), "GetCommState failed")
        config = f"baud={self.baudrate} parity=n data=8 stop=1 dtr=on rts=on"
        if not kernel32.BuildCommDCBW(config, ctypes.byref(dcb)) or not kernel32.SetCommState(handle, ctypes.byref(dcb)):
            self.close()
            raise SerialError(ctypes.get_last_error(), "serial configuration failed")
        timeouts = COMMTIMEOUTS(50, 0, self.timeout_ms, 0, self.timeout_ms)
        if not kernel32.SetCommTimeouts(handle, ctypes.byref(timeouts)):
            self.close()
            raise SerialError(ctypes.get_last_error(), "SetCommTimeouts failed")
        return self

    def write(self, data: bytes) -> int:
        if self.handle is None:
            raise SerialError("serial port is not open")
        written = wintypes.DWORD()
        buffer = ctypes.create_string_buffer(data)
        ok = self._kernel32.WriteFile(self.handle, buffer, len(data), ctypes.byref(written), None)
        if not ok or written.value != len(data):
            raise SerialError(ctypes.get_last_error(), f"short write: {written.value}/{len(data)}")
        return written.value

    def read(self, size: int) -> bytes:
        if self.handle is None:
            raise SerialError("serial port is not open")
        buffer = ctypes.create_string_buffer(size)
        count = wintypes.DWORD()
        ok = self._kernel32.ReadFile(self.handle, buffer, size, ctypes.byref(count), None)
        if not ok:
            raise SerialError(ctypes.get_last_error(), "ReadFile failed")
        return buffer.raw[: count.value]

    def close(self) -> None:
        if self.handle is not None:
            self._kernel32.CloseHandle(self.handle)
            self.handle = None
            self._kernel32 = None

    def __enter__(self) -> "Win32Serial":
        return self.open()

    def __exit__(self, *_exc) -> None:
        self.close()
