"""Rate-controlled frame updates for the live dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic, sleep
from collections.abc import Callable, Iterable
from PIL import Image

from .controller import DisplayController


@dataclass(frozen=True)
class DisplayFrame:
    image: Image.Image
    duration_ms: int
    index: int


@dataclass(frozen=True)
class PlaybackStats:
    frames: int
    elapsed_seconds: float
    effective_fps: float


def play_frames(
    controller: DisplayController,
    frames: Iterable[DisplayFrame],
    *,
    brightness: int = 60,
    panel_rotation: int = 90,
    max_frames: int | None = None,
    cancelled: Callable[[], bool] | None = None,
    on_frame: Callable[[int], None] | None = None,
) -> PlaybackStats:
    """Send one full baseline followed by OEM CC deltas without queueing."""
    started = monotonic()
    count = 0
    previous = None
    frame_id = 0
    for frame in frames:
        if cancelled and cancelled():
            break
        frame_started = monotonic()
        try:
            if previous is None:
                controller.display(
                    frame.image,
                    brightness=brightness,
                    panel_rotation=panel_rotation,
                    cancelled=cancelled,
                )
            else:
                changed = controller.update_frame(
                    previous,
                    frame.image,
                    frame_id,
                    cancelled=cancelled,
                )
                if changed:
                    frame_id = (frame_id + 1) & 0xFFFFFFFF
        except InterruptedError:
            if cancelled and cancelled():
                break
            raise
        previous = frame.image
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
