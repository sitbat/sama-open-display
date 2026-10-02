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
    startup_seconds: float | None = None
    steady_elapsed_seconds: float = 0.0
    steady_fps: float | None = None


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
    """Pace frame generation and transfer together, without queued catch-up frames.

    ``effective_fps`` includes startup and shutdown waits. ``steady_fps`` uses
    completion intervals between delta frames (the second through last frame),
    excluding the expensive full baseline and its transition to the first delta.
    At least three completed frames are needed to measure that rate.
    """
    started = monotonic()
    next_frame_at = started
    count = 0
    previous = None
    frame_id = 0
    iterator = iter(frames)
    first_completed_at = None
    steady_started_at = None
    last_completed_at = None
    while max_frames is None or count < max_frames:
        if cancelled and cancelled():
            break
        # Re-read the clock after every sleep: scheduler delays must not be
        # added once per polling slice. Check cancellation before next(), which
        # can start a provider or spend time rendering a lazily generated frame.
        remaining = next_frame_at - monotonic()
        if remaining > 0:
            sleep(min(0.05, remaining))
            continue
        frame_started = monotonic()
        try:
            frame = next(iterator)
        except StopIteration:
            break
        if cancelled and cancelled():
            break
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
        completed_at = monotonic()
        if count == 1:
            first_completed_at = completed_at
        elif count == 2:
            steady_started_at = completed_at
        last_completed_at = completed_at
        if on_frame:
            on_frame(count)
        # Acquisition, rendering, encoding, transfer and callback all share the
        # same budget. If a frame overruns it, start one fresh frame next; never
        # accumulate missed ticks or send bursts to catch up after slow startup.
        next_frame_at = max(frame_started + frame.duration_ms / 1000, monotonic())
    elapsed = monotonic() - started
    steady_elapsed = (last_completed_at - steady_started_at
                      if count >= 3 else 0.0)
    return PlaybackStats(
        count, elapsed, count / elapsed if elapsed > 0 else 0.0,
        first_completed_at - started if first_completed_at is not None else None,
        steady_elapsed,
        (count - 2) / steady_elapsed if steady_elapsed > 0 else None,
    )
