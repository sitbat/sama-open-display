import unittest
import tempfile
import io
import json
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
from PIL import Image

from sama_display.cli import build_parser, main
from sama_display.playback import PlaybackStats
from sama_display.theme import SYSTEM_METRICS_PLUGIN_ID


class CliTests(unittest.TestCase):
    def test_plugin_list_is_read_only_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["plugin-list", "--directory", str(Path(tmp))]), 0)

    def test_theme_list_is_read_only_json(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["theme-list", "--directory", str(Path(tmp))]), 0)
            self.assertIn('"id": "midnight"', output.getvalue())

    def test_send_requires_device_identity(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["send"])

    def test_send_refuses_hardware_without_acknowledgement(self):
        with self.assertRaisesRegex(SystemExit, "refusing hardware access"):
            main(["send", "--device-id", "chs_65inch.dev1_rom1.91"])

    def test_plan_is_offline(self):
        args = build_parser().parse_args(["plan"])
        self.assertEqual(args.command, "plan")

    def test_image_preview_honors_contain_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "square.png"
            output = Path(tmp) / "preview.png"
            Image.new("RGB", (100, 100), "red").save(source)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([
                    "preview", "--image", str(source), "--fit", "contain",
                    "--output", str(output),
                ]), 0)
            with Image.open(output) as preview:
                self.assertEqual(preview.size, (1568, 720))
                self.assertEqual(preview.getpixel((0, 0)), (0, 0, 0))

    def test_text_preview_is_rendered_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "text.png"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([
                    "preview", "--text", "WinUI text", "--output", str(output),
                ]), 0)
            with Image.open(output) as preview:
                self.assertEqual(preview.size, (1568, 720))

    def test_live_dashboard_refuses_hardware_without_acknowledgement(self):
        with self.assertRaisesRegex(SystemExit, "refusing hardware access"):
            main(["dashboard-live", "--device-id", "chs_65inch.dev1_rom1.91"])

    def test_live_dashboard_accepts_theme_and_stop_file_options(self):
        args = build_parser().parse_args([
            "dashboard-live", "--device-id", "test", "--theme-id", "minimal",
            "--plugins-directory", "plugins", "--stop-file", "stop.signal",
        ])
        self.assertEqual(args.theme_id, "minimal")
        self.assertEqual(args.stop_file, Path("stop.signal"))
        self.assertEqual(args.interval, 1.0)

    def test_builtin_preview_requests_its_metrics_with_or_without_theme_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            for options in ([], ["--theme-id", "midnight"]):
                with self.subTest(options=options), patch("sama_display.cli.DataService") as service:
                    service.return_value.__enter__.return_value.snapshot.return_value = {}
                    with redirect_stdout(io.StringIO()):
                        main(["preview", "--plugins-directory", tmp,
                              "--output", str(Path(tmp) / "preview.png"), *options])
                    service.return_value.__enter__.return_value.snapshot.assert_called_once_with(
                        (SYSTEM_METRICS_PLUGIN_ID,))

    def test_live_default_theme_keeps_metrics_and_reports_startup_separately(self):
        def offline_play(_controller, frames, **_kwargs):
            self.assertEqual(len(list(frames)), 3)
            return PlaybackStats(3, 12.0, 0.25, 8.0, 1.0, 1.0)

        with tempfile.TemporaryDirectory() as tmp, \
                patch("sama_display.cli.DisplayController") as controller, \
                patch("sama_display.cli.DataService") as service, \
                patch("sama_display.cli.play_frames", side_effect=offline_play), \
                redirect_stdout(io.StringIO()) as output:
            controller.return_value.identity.raw = "test-device"
            snapshot = service.return_value.__enter__.return_value.snapshot
            snapshot.return_value = {}
            main(["dashboard-live", "--device-id", "test-device", "--write-hardware",
                  "--seconds", "3", "--plugins-directory", tmp])
            self.assertEqual(snapshot.call_count, 3)
            self.assertTrue(all(call.args == ((SYSTEM_METRICS_PLUGIN_ID,),)
                                for call in snapshot.call_args_list))
            result = json.loads(output.getvalue())
            self.assertEqual(result["effective_fps"], 0.25)
            self.assertEqual(result["startup_seconds"], 8.0)
            self.assertEqual(result["steady_elapsed_seconds"], 1.0)
            self.assertEqual(result["steady_fps"], 1.0)


if __name__ == "__main__":
    unittest.main()
