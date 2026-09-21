import tempfile
import unittest
from pathlib import Path

from sama_display.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = load_config()
        self.assertEqual((config.display.width, config.display.height), (1568, 720))
        self.assertEqual(config.display.panel_rotation, 90)
        self.assertEqual(config.connection.port, "auto")
        self.assertEqual(config.content.fps, 1.0)

    def test_load_and_validate(self):
        content = b"[display]\nbrightness=42\n[content]\nfps=5\nfit='contain'\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.toml")
            path.write_bytes(content)
            config = load_config(path)
        self.assertEqual(config.display.brightness, 42)
        self.assertEqual(config.content.fit, "contain")

    def test_unknown_option_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "config.toml")
            path.write_text("[display]\nmagic=true\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
