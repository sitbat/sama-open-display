"""Configuration model and TOML loading."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class DisplayConfig:
    width: int = 1568
    height: int = 720
    brightness: int = 70
    orientation: str = "landscape"
    panel_rotation: int = 90


@dataclass(frozen=True)
class ConnectionConfig:
    port: str = "auto"
    baudrate: int = 115200
    timeout_ms: int = 1500
    reconnect_attempts: int = 3


@dataclass(frozen=True)
class ContentConfig:
    mode: str = "dashboard"
    fps: float = 2.0
    fit: str = "cover"


@dataclass(frozen=True)
class AppConfig:
    display: DisplayConfig = DisplayConfig()
    connection: ConnectionConfig = ConnectionConfig()
    content: ContentConfig = ContentConfig()


def _section(cls, data: dict) -> object:
    allowed = {field.name for field in fields(cls)}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"unknown {cls.__name__} option(s): {', '.join(sorted(unknown))}")
    return cls(**data)


def validate(config: AppConfig) -> AppConfig:
    if config.display.width <= 0 or config.display.height <= 0:
        raise ValueError("display dimensions must be positive")
    if not 0 <= config.display.brightness <= 100:
        raise ValueError("brightness must be 0..100")
    if config.display.orientation not in {"portrait", "reverse_portrait", "landscape", "reverse_landscape"}:
        raise ValueError("invalid orientation")
    if config.display.panel_rotation not in {0, 90, 180, 270}:
        raise ValueError("panel_rotation must be 0, 90, 180 or 270")
    if config.connection.baudrate <= 0 or config.connection.timeout_ms < 0:
        raise ValueError("invalid serial configuration")
    if config.connection.reconnect_attempts < 0:
        raise ValueError("reconnect_attempts cannot be negative")
    if not 0 < config.content.fps <= 60:
        raise ValueError("fps must be in (0, 60]")
    if config.content.fit not in {"cover", "contain"}:
        raise ValueError("fit must be cover or contain")
    return config


def load_config(path: str | Path | None = None) -> AppConfig:
    if path is None:
        return validate(AppConfig())
    with Path(path).open("rb") as handle:
        raw = tomllib.load(handle)
    known = {"display", "connection", "content"}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown configuration section(s): {', '.join(sorted(unknown))}")
    config = AppConfig(
        display=_section(DisplayConfig, raw.get("display", {})),
        connection=_section(ConnectionConfig, raw.get("connection", {})),
        content=_section(ContentConfig, raw.get("content", {})),
    )
    return validate(config)
