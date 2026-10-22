r"""Unit and adversarial verification suite for Electron Active Hook & IPC Boundary Scanner (CH 26).

Verifies:
1. Valid preload scripts with contextBridge.exposeInMainWorld and IPC calls:
   - ipcRenderer.send
   - ipcRenderer.invoke
   - ipcRenderer.on
   - ipcMain.handle
   - ipcMain.on
2. Security posture detection:
   - nodeIntegration (true -> CRITICAL risk)
   - contextIsolation (false -> CRITICAL risk)
   - dynamic IPC channel sinks (ipcRenderer.send(arg) -> MEDIUM risk)
3. Fail-closed invariants:
   - empty payload
   - oversized payload (>64 KB)
   - malformed input
4. Performance & catastrophic backtracking resistance:
   - Minified / single-line code
   - Massive repetition / adversarial inputs
5. Thermodynamic profiling (peak heap memory <= 64 KB).
6. Adversarial mutant fuzzing.
"""
from __future__ import annotations

import time
import unittest

from kageyoni.ninshu.electron_ipc_scanner import (
    ElectronIpcScanner,
    ElectronScanSummary,
    InvalidInputError,
    IpcChannelDeclaration,
    ContextBridgeExposure,
    SecurityConfiguration,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestElectronIpcScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = ElectronIpcScanner()

    def test_valid_preload_script_parsing(self):
        script = """
        const { contextBridge, ipcRenderer } = require('electron');

        contextBridge.exposeInMainWorld('electronAPI', {
            fetchData: (id) => ipcRenderer.invoke('api:fetch-data', id),
            notifyReady: () => ipcRenderer.send('window:ready'),
            onUpdate: (callback) => ipcRenderer.on('app:update-available', (_event, value) => callback(value))
        });
        """
        summary = self.scanner.scan(script)
        self.assertIsInstance(summary, ElectronScanSummary)
        self.assertEqual(len(summary.bridge_exposures), 1)
        self.assertEqual(summary.bridge_exposures[0].api_key, "electronAPI")

        self.assertEqual(len(summary.ipc_channels), 3)
        channels = {c.channel_name: c for c in summary.ipc_channels}
        self.assertIn("api:fetch-data", channels)
        self.assertEqual(channels["api:fetch-data"].api_method, "invoke")
        self.assertEqual(channels["api:fetch-data"].direction, "renderer_to_main")
        self.assertFalse(channels["api:fetch-data"].is_dynamic)

        self.assertIn("window:ready", channels)
        self.assertEqual(channels["window:ready"].api_method, "send")
        self.assertEqual(channels["window:ready"].direction, "renderer_to_main")

        self.assertIn("app:update-available", channels)
        self.assertEqual(channels["app:update-available"].api_method, "on")
        self.assertEqual(channels["app:update-available"].direction, "listener")

        self.assertEqual(summary.dynamic_sinks_count, 0)

    def test_ipc_main_handlers(self):
        script = """
        const { ipcMain } = require('electron');

        ipcMain.handle('api:fetch-data', async (event, id) => {
            return await queryDatabase(id);
        });

        ipcMain.on('window:ready', (event) => {
            console.log('Window is ready');
        });
        """
        summary = self.scanner.scan(script)
        self.assertEqual(len(summary.ipc_channels), 2)
        handlers = {c.channel_name: c for c in summary.ipc_channels}
        self.assertIn("api:fetch-data", handlers)
        self.assertEqual(handlers["api:fetch-data"].api_method, "handle")
        self.assertEqual(handlers["api:fetch-data"].direction, "main_handler")

        self.assertIn("window:ready", handlers)
        self.assertEqual(handlers["window:ready"].api_method, "on")
        self.assertEqual(handlers["window:ready"].direction, "listener")

    def test_dynamic_channel_sink_detection(self):
        script = """
        function sendDynamic(channelName, payload) {
            ipcRenderer.send(channelName, payload);
        }
        ipcRenderer.invoke(getCustomRoute());
        """
        summary = self.scanner.scan(script)
        self.assertEqual(len(summary.ipc_channels), 2)
        self.assertEqual(summary.dynamic_sinks_count, 2)
        for c in summary.ipc_channels:
            self.assertTrue(c.is_dynamic)

        self.assertEqual(summary.security.risk_level, "MEDIUM")
        self.assertTrue(any("VULN_DYNAMIC_IPC_SINKS" in v for v in summary.security.vulnerabilities))

    def test_security_posture_critical_node_integration(self):
        script = """
        const mainWindow = new BrowserWindow({
            webPreferences: {
                nodeIntegration: true,
                contextIsolation: false,
                sandbox: false,
                enableRemoteModule: true
            }
        });
        """
        summary = self.scanner.scan(script)
        sec = summary.security
        self.assertTrue(sec.node_integration)
        self.assertFalse(sec.context_isolation)
        self.assertFalse(sec.sandbox)
        self.assertTrue(sec.enable_remote_module)
        self.assertEqual(sec.risk_level, "CRITICAL")
        self.assertTrue(any("VULN_NODE_INTEGRATION_ENABLED" in v for v in sec.vulnerabilities))
        self.assertTrue(any("VULN_CONTEXT_ISOLATION_DISABLED" in v for v in sec.vulnerabilities))
        self.assertTrue(any("VULN_REMOTE_MODULE_ENABLED" in v for v in sec.vulnerabilities))

    def test_security_posture_secure_defaults(self):
        script = """
        const mainWindow = new BrowserWindow({
            webPreferences: {
                nodeIntegration: false,
                contextIsolation: true,
                sandbox: true
            }
        });
        """
        summary = self.scanner.scan(script)
        sec = summary.security
        self.assertFalse(sec.node_integration)
        self.assertTrue(sec.context_isolation)
        self.assertTrue(sec.sandbox)
        self.assertEqual(sec.risk_level, "SECURE")
        self.assertEqual(len(sec.vulnerabilities), 0)

    def test_minified_script_scanning(self):
        minified = (
            "const a=require('electron');a.contextBridge.exposeInMainWorld('api',{call:()=>a.ipcRenderer.invoke('fast:call')});"
            "new a.BrowserWindow({webPreferences:{nodeIntegration:false,contextIsolation:true}});"
        )
        summary = self.scanner.scan(minified)
        self.assertEqual(len(summary.bridge_exposures), 1)
        self.assertEqual(summary.bridge_exposures[0].api_key, "api")
        self.assertEqual(len(summary.ipc_channels), 1)
        self.assertEqual(summary.ipc_channels[0].channel_name, "fast:call")
        self.assertEqual(summary.security.risk_level, "SECURE")

    def test_fail_closed_empty_payload(self):
        with self.assertRaises(InvalidInputError):
            self.scanner.scan("")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan("   \n\t  ")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan(b"")

        with self.assertRaises(InvalidInputError):
            self.scanner.scan(None)

    def test_fail_closed_memory_ceiling_exceeded(self):
        oversized = "a" * (65536 + 1)
        with self.assertRaises(InvalidInputError):
            self.scanner.scan(oversized)

        oversized_bytes = b"a" * (65536 + 1)
        with self.assertRaises(InvalidInputError):
            self.scanner.scan(oversized_bytes)

    def test_catastrophic_backtracking_protection(self):
        adversarial = "ipcRenderer.send(" + " " * 5000 + "foo"
        start = time.perf_counter()
        summary = self.scanner.scan(adversarial)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.5)
        self.assertEqual(len(summary.ipc_channels), 1)

    def test_thermodynamic_heap_ceiling(self):
        script = b"""
        const { contextBridge, ipcRenderer } = require('electron');
        contextBridge.exposeInMainWorld('bridgeAPI', {
            sendPing: () => ipcRenderer.send('ping'),
            fetchStatus: () => ipcRenderer.invoke('status')
        });
        """
        summary, receipt = ThermodynamicProfiler.profile_callable(
            ElectronIpcScanner.parse_bytes,
            script,
            candidate_id="electron_ipc_scanner_ch26",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(len(summary.ipc_channels), 2)
        self.assertEqual(len(summary.bridge_exposures), 1)

    def test_adversarial_mutant_fuzzing(self):
        base_payload = b"""
        const { contextBridge, ipcRenderer } = require('electron');
        contextBridge.exposeInMainWorld('bridge', {
            action: () => ipcRenderer.send('action')
        });
        """
        mutants = AdversarialMutator.generate_adversarial_suite(base_payload)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = ElectronIpcScanner.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except InvalidInputError:
                pass
            except Exception as e:
                self.fail(f"Unexpected exception {type(e).__name__} on mutant {m.mutant_id}: {e}")


if __name__ == "__main__":
    unittest.main()
