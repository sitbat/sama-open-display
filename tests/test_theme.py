import tempfile
import unittest
from pathlib import Path
import zipfile

from sama_display.render import dashboard_frame
from sama_display.theme import BUILTIN_THEMES, discover_themes, install_theme, load_theme


THEME = b'''[theme]\nid="test-blue"\nname="Test Blue"\nauthor="Tests"\n[display]\npreset="system_grid"\n[palette]\nbackground="#001122"\naccent="#00aaff"\n'''
MANIFEST = b'''[plugin]\nschema=1\nid="org.test.blue"\nname="Test Blue"\nversion="1.0.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\n'''


class ThemeTests(unittest.TestCase):
    def _package(self, directory: Path, data=THEME) -> Path:
        path = directory / "source.sodpkg"
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
            self.assertEqual(installed.source.name, "test-blue.sodpkg")
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

    def test_schema_two_custom_layout_binds_provider_data(self):
        manifest = b'''[plugin]\nschema=2\nid="org.test.layout"\nname="Layout"\nversion="1.0.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\ndependencies=["org.test.sensor"]\n'''
        layout = b'''[theme]\nid="sensor-layout"\nname="Sensor Layout"\n[display]\npreset="custom"\n[palette]\nbackground="#000000"\naccent="#00ff00"\n[[element]]\ntype="rectangle"\nx=20\ny=20\nwidth=300\nheight=120\nbackground="surface"\nradius=20\n[[element]]\ntype="text"\nx=40\ny=40\nwidth=260\nbind="org.test.sensor.temperature"\nformat=".1f"\nsuffix=" C"\ncolor="accent"\nfont_size=48\nbold=true\n[[element]]\ntype="progress"\nx=40\ny=100\nwidth=240\nheight=20\nbind="org.test.sensor.temperature"\nminimum=0\nmaximum=100\ncolor="accent"\nbackground="surface_alt"\nradius=10\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.sodpkg"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("theme.toml", layout)
            theme = load_theme(path)
            frame = dashboard_frame(theme=theme, data={"org.test.sensor.temperature": 50.0})
            self.assertEqual(theme.dependencies, ("org.test.sensor",))
            self.assertEqual(theme.preset, "custom")
            self.assertEqual(len(theme.elements), 3)
            self.assertEqual(frame.getpixel((80, 110)), (0, 255, 0))


if __name__ == "__main__":
    unittest.main()
