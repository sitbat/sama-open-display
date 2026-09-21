import unittest
import tempfile
import io
from pathlib import Path
from contextlib import redirect_stdout
from PIL import Image

from sama_display.cli import build_parser, main


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


if __name__ == "__main__":
    unittest.main()
