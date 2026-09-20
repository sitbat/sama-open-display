"""Command-line entry point."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

from .config import load_config
from .controller import DisplayController, full_frame_plan
from .device import discover_devices
from .media import iter_media
from .media import MediaFrame
from .playback import play_frames
from .protocol import display_bitmap_header
from .render import dashboard_frame, fit_image, hardware_test_card, text_frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sama-display", description="SAMA 6.5-inch display tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect", help="read-only USB/COM device detection")
    preview = sub.add_parser("preview", help="render content to a PNG without touching hardware")
    preview.add_argument("--image", type=Path)
    preview.add_argument("--text")
    preview.add_argument("--output", type=Path, default=Path("outputs/dashboard.png"))
    preview.add_argument("--config", type=Path)
    animate = sub.add_parser("animate-dashboard", help="render a local animated GIF without touching hardware")
    animate.add_argument("--seconds", type=float, default=3)
    animate.add_argument("--fps", type=float, default=2)
    animate.add_argument("--output", type=Path, default=Path("outputs/dashboard-demo.gif"))
    media = sub.add_parser("media-info", help="decode GIF/video frames without touching hardware")
    media.add_argument("path", type=Path)
    media.add_argument("--max-frames", type=int, default=10)
    media.add_argument("--max-fps", type=float, default=10)
    plan = sub.add_parser("plan", help="inspect a full-frame byte plan without touching hardware")
    plan.add_argument("--image", type=Path)
    plan.add_argument("--brightness", type=int, default=70)
    plan.add_argument("--panel-rotation", type=int, choices=(0, 90, 180, 270), default=90)
    test_card = sub.add_parser("test-card", help="render an offline orientation/color test card")
    test_card.add_argument("--output", type=Path, default=Path("outputs/hardware-test-card.png"))
    send = sub.add_parser("send", help="send one frame with explicit hardware confirmation")
    send.add_argument("--image", type=Path, help="image to fit to the 1568x720 canvas; default is dashboard")
    send.add_argument("--config", type=Path)
    send.add_argument("--brightness", type=int, default=60)
    send.add_argument("--device-id", required=True, help="must exactly match the HELLO identity")
    send.add_argument("--write-hardware", action="store_true", help="required acknowledgement that COM5 will be written")
    play = sub.add_parser("play", help="play GIF/video with explicit hardware confirmation")
    play.add_argument("path", type=Path)
    play.add_argument("--max-fps", type=float, default=0.8)
    play.add_argument("--max-frames", type=int, default=0, help="0 means all frames")
    play.add_argument("--brightness", type=int, default=60)
    play.add_argument("--device-id", required=True)
    play.add_argument("--write-hardware", action="store_true")
    live = sub.add_parser("dashboard-live", help="run the system dashboard with explicit hardware confirmation")
    live.add_argument("--seconds", type=float, default=30)
    live.add_argument("--interval", type=float, default=2)
    live.add_argument("--brightness", type=int, default=60)
    live.add_argument("--device-id", required=True)
    live.add_argument("--write-hardware", action="store_true")
    sub.add_parser("protocol", help="print inferred full-frame header")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "detect":
        devices = discover_devices()
        print(json.dumps([device.to_dict() for device in devices], ensure_ascii=False, indent=2))
        return 0 if devices else 1
    if args.command == "protocol":
        print(display_bitmap_header().hex(" ").upper())
        return 0
    if args.command == "media-info":
        frames = []
        for frame in iter_media(args.path, max_fps=args.max_fps):
            frames.append({"index": frame.index, "size": frame.image.size, "duration_ms": frame.duration_ms})
            if len(frames) >= args.max_frames:
                break
        print(json.dumps({"path": str(args.path), "decoded_frames": frames}, indent=2))
        return 0 if frames else 1
    if args.command == "animate-dashboard":
        if args.seconds <= 0 or not 0 < args.fps <= 30:
            raise SystemExit("seconds must be positive and fps must be in (0, 30]")
        count = max(1, round(args.seconds * args.fps))
        start = datetime.now()
        frames = [dashboard_frame(start + timedelta(seconds=index / args.fps)) for index in range(count)]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(
            args.output,
            save_all=True,
            append_images=frames[1:],
            duration=round(1000 / args.fps),
            loop=0,
            optimize=True,
        )
        print(args.output.resolve())
        return 0
    if args.command == "plan":
        if args.image:
            with Image.open(args.image) as source:
                frame = fit_image(source)
        else:
            frame = dashboard_frame()
        steps = full_frame_plan(frame, args.brightness, args.panel_rotation)
        report = [
            {"name": step.name, "bytes": len(step.data), "read_size": step.read_size,
             "sha256": hashlib.sha256(step.data).hexdigest()[:16]}
            for step in steps
        ]
        print(json.dumps({"hardware_access": False, "steps": report,
                          "total_write_bytes": sum(len(step.data) for step in steps)}, indent=2))
        return 0
    if args.command == "test-card":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        hardware_test_card().save(args.output)
        print(args.output.resolve())
        return 0
    if args.command == "send":
        if not args.write_hardware:
            raise SystemExit("refusing hardware access: add --write-hardware after checking the target device")
        config = load_config(args.config)
        if args.image:
            with Image.open(args.image) as source:
                frame = fit_image(source, (config.display.width, config.display.height), config.content.fit)
        else:
            frame = dashboard_frame()
        controller = DisplayController()
        last_percent = -10

        def report(sent: int, total: int) -> None:
            nonlocal last_percent
            percent = sent * 100 // total
            if percent >= last_percent + 10 or sent == total:
                last_percent = percent
                print(f"send {percent:3d}%", file=sys.stderr, flush=True)

        try:
            controller.connect(allow_hardware=True)
            controller.hello()
            if controller.identity is None or controller.identity.raw != args.device_id:
                actual = controller.identity.raw if controller.identity else "unknown"
                raise RuntimeError(f"device identity mismatch: expected {args.device_id}, got {actual}")
            controller.display(
                frame,
                brightness=args.brightness,
                panel_rotation=config.display.panel_rotation,
                progress=report,
            )
            print(f"displayed on {controller.identity.raw}")
            return 0
        finally:
            controller.close()
    if args.command in {"play", "dashboard-live"}:
        if not args.write_hardware:
            raise SystemExit("refusing hardware access: add --write-hardware after checking the target device")
        if args.command == "play":
            if not 0 < args.max_fps <= 1:
                raise SystemExit("full-frame playback max-fps must be in (0, 1]")
            frames = iter_media(args.path, max_fps=args.max_fps)
            max_frames = args.max_frames or None
        else:
            if args.seconds <= 0 or args.interval < 1:
                raise SystemExit("seconds must be positive and interval must be at least 1 second")
            count = max(1, int(args.seconds / args.interval))
            frames = (
                MediaFrame(dashboard_frame(), round(args.interval * 1000), index)
                for index in range(count)
            )
            max_frames = count
        controller = DisplayController()
        try:
            controller.connect(allow_hardware=True)
            controller.hello()
            if controller.identity is None or controller.identity.raw != args.device_id:
                actual = controller.identity.raw if controller.identity else "unknown"
                raise RuntimeError(f"device identity mismatch: expected {args.device_id}, got {actual}")
            stats = play_frames(
                controller,
                frames,
                brightness=args.brightness,
                max_frames=max_frames,
                on_frame=lambda count: print(f"frame {count}", file=sys.stderr, flush=True),
            )
            print(json.dumps({"frames": stats.frames, "elapsed_seconds": round(stats.elapsed_seconds, 3),
                              "effective_fps": round(stats.effective_fps, 3)}))
            return 0
        finally:
            controller.close()
    config = load_config(args.config)
    if args.image:
        with Image.open(args.image) as source:
            frame = fit_image(source, (config.display.width, config.display.height), config.content.fit)
    elif args.text:
        frame = text_frame(args.text)
    else:
        frame = dashboard_frame()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.save(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
