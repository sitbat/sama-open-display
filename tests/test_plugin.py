import tempfile
import unittest
from pathlib import Path
import zipfile

from sama_display.plugin import inspect_plugin


class PluginTests(unittest.TestCase):
    def test_inspects_theme_plugin(self):
        manifest = b'''[plugin]\nschema=1\nid="org.test.theme"\nname="Theme"\nversion="1.2.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.samarppkg"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("theme.toml", b'[theme]\nid="test-theme"\nname="Test"\n')
            plugin = inspect_plugin(path)
            self.assertEqual(plugin.plugin_id, "org.test.theme")
            self.assertEqual(plugin.kind, "theme")


if __name__ == "__main__":
    unittest.main()
