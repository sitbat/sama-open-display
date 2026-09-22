import tempfile
import unittest
from pathlib import Path
import zipfile

from sama_display.plugin import PluginManager, inspect_plugin


class PluginTests(unittest.TestCase):
    def _package(self, path, plugin_id, *, kind="theme", entry="theme.toml", dependencies=()):
        dependency_line = f'dependencies={list(dependencies)!r}'.replace("'", '"') if dependencies else ""
        manifest = f'''[plugin]\nschema=1\nid="{plugin_id}"\nname="{plugin_id}"\nversion="1.0.0"\nauthor="Tests"\nkind="{kind}"\nentry="{entry}"\n{dependency_line}\n'''.encode()
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("manifest.toml", manifest)
            payload = (b'[provider]\nadapter="builtin.system"\n' if kind == "data-provider"
                       else b'[theme]\nid="test-theme"\nname="Test"\n')
            package.writestr(entry, payload)

    def test_inspects_theme_plugin(self):
        manifest = b'''[plugin]\nschema=1\nid="org.test.theme"\nname="Theme"\nversion="1.2.0"\nauthor="Tests"\nkind="theme"\nentry="theme.toml"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.sodpkg"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("theme.toml", b'[theme]\nid="test-theme"\nname="Test"\n')
            plugin = inspect_plugin(path)
            self.assertEqual(plugin.plugin_id, "org.test.theme")
            self.assertEqual(plugin.kind, "theme")

    def test_install_copies_package_into_selected_plugins_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "import.sodpkg"
            destination = root / "installed"
            self._package(source, "org.test.imported")

            PluginManager(destination).install_many([source])

            copied = destination / "org.test.imported.sodpkg"
            self.assertEqual(copied.read_bytes(), source.read_bytes())
            self.assertTrue((destination / "plugins.json").is_file())

    def test_batch_state_respects_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider = root / "provider.sodpkg"
            theme = root / "theme.sodpkg"
            self._package(provider, "org.test.provider", kind="data-provider", entry="provider.toml")
            self._package(theme, "org.test.consumer", dependencies=("org.test.provider",))
            manager = PluginManager(root / "installed")
            manager.install_many([provider, theme])
            with self.assertRaises(ValueError):
                manager.set_enabled(["org.test.provider"], False)
            manager.set_enabled(["org.test.consumer", "org.test.provider"], False)
            self.assertEqual(manager.enabled_ids(), set())
            manager.set_enabled(["org.test.provider", "org.test.consumer"], True)
            self.assertEqual(manager.enabled_ids(), {"org.test.provider", "org.test.consumer"})


if __name__ == "__main__":
    unittest.main()
