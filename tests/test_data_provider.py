import tempfile
import unittest
from pathlib import Path
import subprocess
from unittest.mock import patch
import zipfile

from sama_display.data_provider import DataService
from sama_display.plugin import PluginManager


class DataProviderTests(unittest.TestCase):
    def test_bundled_system_metrics_provider_is_loadable(self):
        plugin_directory = Path(__file__).resolve().parents[1] / "plugins"
        plugins = PluginManager(plugin_directory).scan()
        provider = next(
            (item for item in plugins if item.manifest.plugin_id ==
             "io.github.sitbat.sama-open-display.system-metrics"),
            None,
        )
        self.assertIsNotNone(provider)
        self.assertTrue(provider.enabled)
        self.assertFalse(provider.problem)
        values = DataService(plugins).snapshot()
        self.assertIn("system.cpu.percent", values)
        self.assertIn("system.memory.percent", values)
        self.assertIn("system.uptime.seconds", values)
        self.assertIn("storage.root.percent", values)

    def test_permission_scoped_snapshot(self):
        manifest = b'''[plugin]\nschema=1\nid="org.test.metrics"\nname="Metrics"\nversion="1.0.0"\nauthor="Tests"\nkind="data-provider"\nentry="provider.toml"\npermissions=["system.cpu","system.uptime"]\n'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "provider.sodpkg"
            with zipfile.ZipFile(source, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("provider.toml", b'[provider]\nadapter="builtin.system"\n')
            manager = PluginManager(root / "installed")
            manager.install_many([source])
            values = DataService(manager.scan()).snapshot()
            self.assertIn("system.cpu.percent", values)
            self.assertIn("system.uptime.seconds", values)
            self.assertNotIn("system.memory.percent", values)
            self.assertNotIn("storage.root.percent", values)

    def test_external_provider_returns_namespaced_declared_fields(self):
        manifest = b'''[plugin]\nschema=2\nid="org.test.sensor"\nname="Sensor"\nversion="1.0.0"\nauthor="Tests"\nkind="data-provider"\nentry="provider.toml"\npermissions=["code.execute"]\n'''
        provider = b'''[provider]\nadapter="external.process"\ncommand="sensor.exe"\ntimeout_ms=500\n[fields]\ntemperature="number"\nlabel="string"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "provider.sodpkg"
            with zipfile.ZipFile(source, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("provider.toml", provider)
                package.writestr("sensor.exe", b"test executable")
            manager = PluginManager(root / "installed")
            manager.install_many([source])
            completed = subprocess.CompletedProcess([], 0, '{"temperature": 42.5, "label": "CPU"}', "")
            with patch("sama_display.data_provider.subprocess.run", return_value=completed) as run:
                service = DataService(manager.scan())
                self.assertEqual(service.snapshot(()), {})
                run.assert_not_called()
                values = service.snapshot(("org.test.sensor",))
                run.assert_called_once()
            self.assertEqual(values["org.test.sensor.temperature"], 42.5)
            self.assertEqual(values["org.test.sensor.label"], "CPU")


if __name__ == "__main__":
    unittest.main()
