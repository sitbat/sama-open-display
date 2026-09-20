import tempfile
import unittest
from pathlib import Path
import zipfile

from sama_display.theme import BUILTIN_THEMES, discover_themes, install_theme, load_theme


THEME = b'''[theme]\nid="test-blue"\nname="Test Blue"\nauthor="Tests"\n[display]\npreset="system_grid"\n[palette]\nbackground="#001122"\naccent="#00aaff"\n'''
MANIFEST = b'''[plugin]\nschema=1\nid="org.test.blue"\nname="Test Blue"\nversion="1.0.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\n'''


class ThemeTests(unittest.TestCase):
    def _package(self, directory: Path, data=THEME) -> Path:
        path = directory / "source.samarppkg"
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("manifest.toml", MANIFEST)
            package.writestr("theme.toml", data)
        return path

    def test_loads_portable_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = load_theme(self._package(Path(tmp)))
            self.assertEqual(theme.theme_id, "test-blue")
            self.assertEqual(theme.preset, "system_grid")
            self.assertEqual(theme.accent, "#00aaff")

    def test_installs_under_stable_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = install_theme(self._package(root), root / "installed")
            self.assertEqual(installed.source.name, "test-blue.samarppkg")
            self.assertTrue(installed.source.exists())

    def test_discovery_always_has_builtins(self):
        with tempfile.TemporaryDirectory() as tmp:
            themes = discover_themes(tmp)
            self.assertEqual(themes, list(BUILTIN_THEMES))

    def test_rejects_invalid_color(self):
        bad = THEME.replace(b'#001122', b'blue')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_theme(self._package(Path(tmp), bad))


if __name__ == "__main__":
    unittest.main()
