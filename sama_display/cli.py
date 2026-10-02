"""Command-line entry point."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

from .config import load_config
from .controller import DisplayController, full_frame_plan
from .device import discover_devices
from .playback import DisplayFrame, play_frames
from .plugin import InstalledPlugin, PluginManager, inspect_plugin
from .data_provider import DataService, load_provider_config
from .protocol import display_bitmap_header
from .render import dashboard_frame, fit_image, hardware_test_card, text_frame
from .theme import BUILTIN_THEMES, discover_themes, load_theme


def _inspect_installable_plugin(path: Path):
    manifest = inspect_plugin(path)
    if manifest.kind == "theme":
        load_theme(path)
    else:
        load_provider_config(InstalledPlugin(manifest, path, True))
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sama-display", description="SAMA 6.5-inch display tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("detect", help="read-only USB/COM device detection")
    preview = sub.add_parser("preview", help="render content to a PNG without touching hardware")
    preview.add_argument("--image", type=Path)
    preview.add_argument("--text")
    preview.add_argument("--output", type=Path, default=Path("outputs/dashboard.png"))
    preview.add_argument("--config", type=Path)
    preview.add_argument("--fit", choices=("cover", "contain"))
    preview.add_argument("--theme-id")
    preview.add_argument("--plugins-directory", type=Path, default=Path("plugins"))
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
    live = sub.add_parser("dashboard-live", help="run the system dashboard with explicit hardware confirmation")
    live.add_argument("--seconds", type=float, default=30)
    live.add_argument("--interval", type=float, default=1.0)
    live.add_argument("--brightness", type=int, default=60)
    live.add_argument("--device-id", required=True)
    live.add_argument("--write-hardware", action="store_true")
    live.add_argument("--theme-id")
    live.add_argument("--plugins-directory", type=Path, default=Path("plugins"))
    live.add_argument("--stop-file", type=Path)
    sub.add_parser("protocol", help="print inferred full-frame header")
    plugin_list = sub.add_parser("plugin-list", help="list installed plugins as JSON")
    plugin_list.add_argument("--directory", type=Path, default=Path("plugins"))
    plugin_inspect = sub.add_parser("plugin-inspect", help="inspect plugin packages before installation")
    plugin_inspect.add_argument("paths", nargs="+", type=Path)
    plugin_install = sub.add_parser("plugin-install", help="validate and install one or more plugins")
    plugin_install.add_argument("paths", nargs="+", type=Path)
    plugin_install.add_argument("--directory", type=Path, default=Path("plugins"))
    for command in ("plugin-enable", "plugin-disable", "plugin-uninstall"):
        operation = sub.add_parser(command, help=f"{command.replace('plugin-', '')} one or more plugins")
        operation.add_argument("ids", nargs="+")
        operation.add_argument("--directory", type=Path, default=Path("plugins"))
    metrics = sub.add_parser("metrics", help="read permission-scoped provider data as JSON")
    metrics.add_argument("--directory", type=Path, default=Path("plugins"))
    theme_list = sub.add_parser("theme-list", help="list selectable display themes as JSON")
    theme_list.add_argument("--directory", type=Path, default=Path("plugins"))
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
    if args.command == "theme-list":
        manager = PluginManager(args.directory)
        themes = discover_themes(args.directory, manager.enabled_ids())
        print(json.dumps([
            {
                "id": theme.theme_id,
                "name": theme.name,
                "author": theme.author,
                "description": theme.description,
                "plugin_id": theme.plugin_id,
            }
            for theme in themes
        ], ensure_ascii=False))
        return 0
    if args.command == "plugin-inspect":
        manifests = [_inspect_installable_plugin(path) for path in args.paths]
        print(json.dumps([
            {
                "id": item.plugin_id, "name": item.name, "version": item.version,
                "author": item.author, "kind": item.kind, "description": item.description,
                "dependencies": list(item.dependencies), "permissions": list(item.permissions),
                "enabled": True, "problem": "",
            }
            for item in manifests
        ], ensure_ascii=False))
        return 0
    if args.command.startswith("plugin-") or args.command == "metrics":
        manager = PluginManager(args.directory)
        if args.command == "plugin-install":
            for path in args.paths:
                _inspect_installable_plugin(path)
            manager.install_many(args.paths)
        elif args.command == "plugin-enable":
            manager.set_enabled(args.ids, True)
        elif args.command == "plugin-disable":
            manager.set_enabled(args.ids, False)
        elif args.command == "plugin-uninstall":
            manager.uninstall(args.ids)
        if args.command == "metrics":
            with DataService(manager.scan()) as data_service:
                print(json.dumps(data_service.snapshot(), ensure_ascii=False))
            return 0
        inventory = [
            {
                "id": item.manifest.plugin_id,
                "name": item.manifest.name,
                "version": item.manifest.version,
                "author": item.manifest.author,
                "kind": item.manifest.kind,
                "description": item.manifest.description,
                "dependencies": list(item.manifest.dependencies),
                "permissions": list(item.manifest.permissions),
                "enabled": item.enabled,
                "problem": item.problem,
                "path": str(item.path.resolve()),
            }
            for item in manager.scan()
        ]
        print(json.dumps(inventory, ensure_ascii=False))
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
    if args.command == "dashboard-live":
        if not args.write_hardware:
            raise SystemExit("refusing hardware access: add --write-hardware after checking the target device")
        if args.seconds <= 0 or args.interval < 0.1:
            raise SystemExit("seconds must be positive and interval must be at least 0.1 second")
        manager = PluginManager(args.plugins_directory)
        themes = discover_themes(args.plugins_directory, manager.enabled_ids())
        selected = next((theme for theme in themes if theme.theme_id == args.theme_id), None)
        if args.theme_id and selected is None:
            raise SystemExit(f"theme is not installed or enabled: {args.theme_id}")
        with DataService(manager.scan()) as data_service:
            count = max(1, int(args.seconds / args.interval))
            frames = (
                DisplayFrame(
                    dashboard_frame(
                        theme=selected,
                        data=data_service.snapshot((selected or BUILTIN_THEMES[0]).dependencies),
                    ),
                    round(args.interval * 1000),
                    index,
                )
                for index in range(count)
            )
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
                    max_frames=count,
                    cancelled=(lambda: bool(args.stop_file and args.stop_file.exists())),
                    on_frame=lambda count: print(f"frame {count}", file=sys.stderr, flush=True),
                )
                print(json.dumps({
                    "frames": stats.frames,
                    "elapsed_seconds": round(stats.elapsed_seconds, 3),
                    "effective_fps": round(stats.effective_fps, 3),
                    "startup_seconds": (round(stats.startup_seconds, 3)
                                        if stats.startup_seconds is not None else None),
                    "steady_elapsed_seconds": round(stats.steady_elapsed_seconds, 3),
                    "steady_fps": (round(stats.steady_fps, 3)
                                   if stats.steady_fps is not None else None),
                }))
                return 0
            finally:
                controller.close()
    config = load_config(args.config)
    if args.image:
        with Image.open(args.image) as source:
            frame = fit_image(
                source,
                (config.display.width, config.display.height),
                args.fit or config.content.fit,
            )
    elif args.text:
        frame = text_frame(args.text)
    else:
        manager = PluginManager(args.plugins_directory)
        themes = discover_themes(args.plugins_directory, manager.enabled_ids())
        selected = next((theme for theme in themes if theme.theme_id == args.theme_id), None)
        if args.theme_id and selected is None:
            raise SystemExit(f"theme is not installed or enabled: {args.theme_id}")
        with DataService(manager.scan()) as data_service:
            data = data_service.snapshot((selected or BUILTIN_THEMES[0]).dependencies)
        frame = dashboard_frame(theme=selected, data=data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.save(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
