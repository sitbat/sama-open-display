"""Rate-controlled frame playback shared by dashboards and media files."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from collections.abc import Callable, Iterable

from .controller import DisplayController
from .media import MediaFrame


@dataclass(frozen=True)
class PlaybackStats:
    frames: int
    elapsed_seconds: float
    effective_fps: float


def play_frames(
    controller: DisplayController,
    frames: Iterable[MediaFrame],
    *,
    brightness: int = 60,
    panel_rotation: int = 90,
    max_frames: int | None = None,
    cancelled: Callable[[], bool] | None = None,
    on_frame: Callable[[int], None] | None = None,
) -> PlaybackStats:
    """Display frames sequentially, never queueing faster than the USB link."""
    started = monotonic()
    count = 0
    for frame in frames:
        if cancelled and cancelled():
            break
        frame_started = monotonic()
        controller.display(
            frame.image,
            brightness=brightness,
            panel_rotation=panel_rotation,
            cancelled=cancelled,
        )
        count += 1
        if on_frame:
            on_frame(count)
        if max_frames is not None and count >= max_frames:
            break
        remaining = frame.duration_ms / 1000 - (monotonic() - frame_started)
        while remaining > 0:
            if cancelled and cancelled():
                break
            pause = min(0.05, remaining)
            sleep(pause)
            remaining -= pause
    elapsed = monotonic() - started
    return PlaybackStats(count, elapsed, count / elapsed if elapsed > 0 else 0.0)

