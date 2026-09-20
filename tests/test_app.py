import unittest

from sama_display.app import application_directory, external_config_path


class AppPathTests(unittest.TestCase):
    def test_source_config_is_external(self):
        self.assertEqual(external_config_path(), application_directory() / "config.toml")
        self.assertFalse(str(external_config_path()).endswith("runtime\\config.toml"))


if __name__ == "__main__":
    unittest.main()
