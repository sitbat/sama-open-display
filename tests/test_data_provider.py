import tempfile
import unittest
from pathlib import Path
import subprocess
import json
from queue import Queue
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

    def test_resident_provider_reuses_process_until_theme_no_longer_depends_on_it(self):
        manifest = b'''[plugin]\nschema=2\nid="org.test.sensor"\nname="Sensor"\nversion="1.0.0"\nauthor="Tests"\nkind="data-provider"\nentry="provider.toml"\npermissions=["code.execute"]\n'''
        provider = b'''[provider]\nadapter="external.process"\ncommand="sensor.exe"\nmode="resident"\ntimeout_ms=500\nrefresh_interval_ms=300000\n[fields]\ntemperature="number"\n'''

        class FakeProcess:
            def __init__(self):
                self.args = ["sensor.exe"]
                self.returncode = None
                self.respond = True
                self.requests = []
                self.responses = Queue()
                self.stdin = self
                self.stdout = self
                self.stderr = self

            def write(self, text):
                request = json.loads(text)
                self.requests.append(request)
                if request["action"] == "sample" and self.respond:
                    self.responses.put('{"temperature": 42.5}\n')
                elif request["action"] == "shutdown":
                    self.returncode = 0
                    self.responses.put("")

            def flush(self):
                pass

            def readline(self, _limit):
                return self.responses.get(timeout=2)

            def read(self, _limit):
                return ""

            def poll(self):
                return self.returncode

            def wait(self, timeout):
                if self.returncode is None:
                    raise subprocess.TimeoutExpired(self.args, timeout)
                return self.returncode

            def terminate(self):
                self.returncode = -15
                self.responses.put("")

            def kill(self):
                self.terminate()

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "provider.sodpkg"
            with zipfile.ZipFile(source, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("provider.toml", provider)
                package.writestr("sensor.exe", b"test executable")
            manager = PluginManager(root / "installed")
            manager.install_many([source])
            created = []

            def start(*_args, **_kwargs):
                process = FakeProcess()
                created.append(process)
                return process

            with patch("sama_display.data_provider.subprocess.Popen", side_effect=start):
                with DataService(manager.scan()) as service:
                    self.assertEqual(service.snapshot(()), {})
                    self.assertEqual(len(created), 0)
                    self.assertEqual(service.snapshot(("org.test.sensor",)),
                                     {"org.test.sensor.temperature": 42.5})
                    self.assertEqual(service.snapshot(("org.test.sensor",)),
                                     {"org.test.sensor.temperature": 42.5})
                    self.assertEqual(len(created), 1)
                    self.assertEqual([item["action"] for item in created[0].requests], ["sample"])
                    service._next_refresh["org.test.sensor"] = 0
                    service.snapshot(("org.test.sensor",))
                    self.assertEqual(len(created), 1)
                    self.assertEqual([item["action"] for item in created[0].requests],
                                     ["sample", "sample"])
                    service.snapshot(())
                    self.assertEqual(created[0].returncode, 0)
                    self.assertEqual(created[0].requests[-1]["action"], "shutdown")
                    service.snapshot(("org.test.sensor",))
                    self.assertEqual(len(created), 2)
                    created[1].respond = False
                    service._next_refresh["org.test.sensor"] = 0
                    self.assertEqual(service.snapshot(("org.test.sensor",)), {})
                    self.assertEqual(created[1].returncode, 0)
                self.assertEqual(created[1].returncode, 0)


if __name__ == "__main__":
    unittest.main()
