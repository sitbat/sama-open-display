import tempfile
import unittest
from pathlib import Path
import zipfile

from sama_display.render import dashboard_frame
from sama_display.theme import (
    BUILTIN_THEMES, SYSTEM_METRICS_PLUGIN_ID, discover_themes, install_theme, load_theme,
)


THEME = b'''[theme]\nid="test-blue"\nname="Test Blue"\nauthor="Tests"\n[display]\npreset="system_grid"\n[palette]\nbackground="#001122"\naccent="#00aaff"\n'''
MANIFEST = b'''[plugin]\nschema=1\nid="org.test.blue"\nname="Test Blue"\nversion="1.0.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\n'''


class ThemeTests(unittest.TestCase):
    def _package(self, directory: Path, data=THEME, manifest=MANIFEST) -> Path:
        path = directory / "source.sodpkg"
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("manifest.toml", manifest)
            package.writestr("theme.toml", data)
        return path

    def test_loads_portable_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = load_theme(self._package(Path(tmp)))
            self.assertEqual(theme.theme_id, "test-blue")
            self.assertEqual(theme.preset, "system_grid")
            self.assertEqual(theme.accent, "#00aaff")
            self.assertEqual(theme.dependencies, (SYSTEM_METRICS_PLUGIN_ID,))

    def test_builtins_declare_system_metrics(self):
        for theme in BUILTIN_THEMES:
            with self.subTest(theme=theme.theme_id):
                self.assertEqual(theme.dependencies, (SYSTEM_METRICS_PLUGIN_ID,))

    def test_legacy_presets_declare_system_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            for preset in (b"dashboard", b"minimal_clock", b"system_grid"):
                with self.subTest(preset=preset):
                    data = THEME.replace(b"system_grid", preset)
                    theme = load_theme(self._package(Path(tmp), data))
                    self.assertEqual(theme.dependencies, (SYSTEM_METRICS_PLUGIN_ID,))

    def test_preset_preserves_explicit_dependencies_without_duplicate_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            for dependencies in (("org.test.sensor",), ("org.test.sensor", SYSTEM_METRICS_PLUGIN_ID)):
                with self.subTest(dependencies=dependencies):
                    declared = ",".join(f'"{item}"' for item in dependencies)
                    manifest = MANIFEST.replace(b"schema=1", b"schema=2") + f"dependencies=[{declared}]\n".encode()
                    theme = load_theme(self._package(Path(tmp), manifest=manifest))
                    self.assertEqual(theme.dependencies, ("org.test.sensor", SYSTEM_METRICS_PLUGIN_ID))

    def test_custom_layout_keeps_only_declared_dependencies(self):
        layout = b'''[theme]\nid="custom-layout"\nname="Custom Layout"\n[display]\npreset="custom"\n[[element]]\ntype="text"\ntext="Static content"\nx=0\ny=0\n'''
        with tempfile.TemporaryDirectory() as tmp:
            for dependencies in ((), (SYSTEM_METRICS_PLUGIN_ID,)):
                with self.subTest(dependencies=dependencies):
                    declared = ",".join(f'"{item}"' for item in dependencies)
                    manifest = MANIFEST.replace(b"schema=1", b"schema=2") + f"dependencies=[{declared}]\n".encode()
                    theme = load_theme(self._package(Path(tmp), layout, manifest))
                    self.assertEqual(theme.dependencies, dependencies)

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
