import tempfile
import unittest
from pathlib import Path
import subprocess
import json
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from sama_display.data_provider import DataService
from sama_display.plugin import InstalledPlugin, PluginManager, inspect_plugin
from sama_display.theme import SYSTEM_METRICS_PLUGIN_ID


class DataProviderTests(unittest.TestCase):
    def setUp(self):
        metrics = patch("sama_display.data_provider.psutil")
        self.metrics = metrics.start()
        self.addCleanup(metrics.stop)
        self.metrics.cpu_percent.return_value = 12.5
        self.metrics.virtual_memory.return_value = SimpleNamespace(percent=25, used=1024, total=4096)
        self.metrics.disk_usage.return_value = SimpleNamespace(percent=50, used=2048, total=4096)
        self.metrics.boot_time.return_value = 0
        self.metrics.net_io_counters.return_value = SimpleNamespace(bytes_sent=100, bytes_recv=200)
        self.metrics.pids.return_value = [1, 2]

    def _bundled_provider(self):
        path = Path(__file__).resolve().parents[1] / "plugins" / f"{SYSTEM_METRICS_PLUGIN_ID}.sodpkg"
        return InstalledPlugin(inspect_plugin(path), path, True)

    def test_bundled_system_metrics_provider_is_loadable(self):
        provider = self._bundled_provider()
        self.assertTrue(provider.enabled)
        self.assertFalse(provider.problem)
        with DataService([provider]) as service:
            values = service.snapshot()
        self.assertIn("system.cpu.percent", values)
        self.assertIn("system.memory.percent", values)
        self.assertIn("system.uptime.seconds", values)
        self.assertIn("storage.root.percent", values)

    def test_required_ids_filter_builtin_metrics(self):
        with DataService([self._bundled_provider()]) as service:
            self.assertEqual(service.snapshot(()), {})
            self.assertEqual(service.snapshot(("org.test.sensor",)), {})
            self.assertEqual(self.metrics.mock_calls, [])

            values = service.snapshot((SYSTEM_METRICS_PLUGIN_ID,))
            self.assertEqual(values["system.cpu.percent"], 12.5)
            self.metrics.cpu_percent.assert_called_once_with(interval=0.05)

            calls = list(self.metrics.mock_calls)
            self.assertEqual(service.snapshot(()), {})
            self.assertEqual(self.metrics.mock_calls, calls)
            self.assertEqual(service.snapshot(None)["system.cpu.percent"], 12.5)
            self.assertEqual(self.metrics.cpu_percent.call_count, 2)

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
                with DataService(manager.scan() + [self._bundled_provider()]) as service:
                    self.assertEqual(service.snapshot(()), {})
                    run.assert_not_called()
                    values = service.snapshot(("org.test.sensor",))
                    run.assert_called_once()
                    self.assertEqual(self.metrics.mock_calls, [])
                    all_values = service.snapshot(None)
                    self.assertEqual(all_values["system.cpu.percent"], 12.5)
                    self.assertEqual(all_values["org.test.sensor.temperature"], 42.5)
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

    def test_refresh_interval_starts_when_sample_begins(self):
        manifest = b'''[plugin]\nschema=2\nid="org.test.sensor"\nname="Sensor"\nversion="1.0.0"\nauthor="Tests"\nkind="data-provider"\nentry="provider.toml"\npermissions=["code.execute"]\n'''
        provider = b'''[provider]\nadapter="external.process"\ncommand="sensor.exe"\nmode="resident"\nrefresh_interval_ms=1000\n[fields]\ntemperature="number"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "provider.sodpkg"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("provider.toml", provider)
                package.writestr("sensor.exe", b"test executable")
            plugin = InstalledPlugin(inspect_plugin(path), path, True)
            for duration in (0.2, 1.2):
                with self.subTest(duration=duration):
                    now = [10.0]

                    def sample():
                        now[0] += duration
                        return {"org.test.sensor.temperature": 42.5}

                    with patch("sama_display.data_provider.monotonic", side_effect=lambda: now[0]), \
                            patch("sama_display.data_provider._ResidentProcess") as start:
                        resident = start.return_value
                        resident.process.poll.return_value = None
                        resident.sample.side_effect = sample
                        with DataService([plugin]) as service:
                            first = service.snapshot(("org.test.sensor",))
                            self.assertEqual(service._next_refresh["org.test.sensor"], 11.0)
                            resident.sample.assert_called_once()
                            if duration < 1:
                                now[0] = 10.99
                                self.assertEqual(service.snapshot(("org.test.sensor",)), first)
                                resident.sample.assert_called_once()
                            now[0] = max(now[0], 11.0)
                            self.assertEqual(service.snapshot(("org.test.sensor",)), first)
                            self.assertEqual(resident.sample.call_count, 2)

    def test_small_tick_jitter_does_not_reuse_every_other_sample(self):
        manifest = b'''[plugin]\nschema=2\nid="org.test.sensor"\nname="Sensor"\nversion="1.0.0"\nauthor="Tests"\nkind="data-provider"\nentry="provider.toml"\npermissions=["code.execute"]\n'''
        provider = b'''[provider]\nadapter="external.process"\ncommand="sensor.exe"\nmode="resident"\nrefresh_interval_ms=1000\n[fields]\ntemperature="number"\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "provider.sodpkg"
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("manifest.toml", manifest)
                package.writestr("provider.toml", provider)
                package.writestr("sensor.exe", b"test executable")
            plugin = InstalledPlugin(inspect_plugin(path), path, True)
            now = [10.0]
            with patch("sama_display.data_provider.monotonic", side_effect=lambda: now[0]), \
                    patch("sama_display.data_provider._ResidentProcess") as start:
                resident = start.return_value
                resident.process.poll.return_value = None
                resident.sample.side_effect = lambda: {"org.test.sensor.temperature": resident.sample.call_count}
                with DataService([plugin]) as service:
                    for index in range(8):
                        now[0] = 10 + index + (0.001 if index % 2 == 0 else 0)
                        value = service.snapshot(("org.test.sensor",))
                        self.assertEqual(value["org.test.sensor.temperature"], index + 1)
                        self.assertEqual(service.snapshot(("org.test.sensor",)), value)
                        self.assertEqual(resident.sample.call_count, index + 1)
                    # Arriving 10 ms early still uses the cache, not another sample.
                    now[0] = service._next_refresh["org.test.sensor"] - 0.010
                    service.snapshot(("org.test.sensor",))
                    self.assertEqual(resident.sample.call_count, 8)
                    resident.sample.side_effect = ValueError("failed sample")
                    now[0] = service._next_refresh["org.test.sensor"]
                    self.assertEqual(service.snapshot(("org.test.sensor",)), {})
                    self.assertEqual(resident.sample.call_count, 9)
                    now[0] = service._next_refresh["org.test.sensor"] - 0.001
                    self.assertEqual(service.snapshot(("org.test.sensor",)), {})
                    self.assertEqual(resident.sample.call_count, 9)
                    start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
