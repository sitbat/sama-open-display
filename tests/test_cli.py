import unittest
import tempfile
from pathlib import Path

from sama_display.cli import build_parser, main


class CliTests(unittest.TestCase):
    def test_plugin_list_is_read_only_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main(["plugin-list", "--directory", str(Path(tmp))]), 0)

    def test_send_requires_device_identity(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["send"])

    def test_send_refuses_hardware_without_acknowledgement(self):
        with self.assertRaisesRegex(SystemExit, "refusing hardware access"):
            main(["send", "--device-id", "chs_65inch.dev1_rom1.91"])

    def test_plan_is_offline(self):
        args = build_parser().parse_args(["plan"])
        self.assertEqual(args.command, "plan")

    def test_live_dashboard_refuses_hardware_without_acknowledgement(self):
        with self.assertRaisesRegex(SystemExit, "refusing hardware access"):
            main(["dashboard-live", "--device-id", "chs_65inch.dev1_rom1.91"])


if __name__ == "__main__":
    unittest.main()
