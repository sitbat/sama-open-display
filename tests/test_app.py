import unittest

from sama_display.app import application_directory, application_icon_path, external_config_path, plugins_directory


class AppPathTests(unittest.TestCase):
    def test_source_config_is_external(self):
        self.assertEqual(external_config_path(), application_directory() / "config.toml")
        self.assertFalse(str(external_config_path()).endswith("runtime\\config.toml"))

    def test_assets_and_themes_stay_external(self):
        self.assertEqual(plugins_directory(), application_directory() / "plugins")
        self.assertEqual(application_icon_path(), application_directory() / "assets" / "app-icon.ico")


if __name__ == "__main__":
    unittest.main()
