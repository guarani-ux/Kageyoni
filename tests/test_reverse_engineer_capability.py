"""Test suite for Reverse Engineering & Binary Inspection (REA) capability."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path[:1]:
    sys.path.insert(0, str(REPO_ROOT))

from tools.reverse_engineer import (
    DotNetPEParser,
    JSApplicationParser,
    extract_strings,
    get_rea_bridge_status,
    inspect_target,
)
from shinobi.shinobi import scout_horizon


class ReverseEngineerCapabilityTests(unittest.TestCase):
    def test_rea_source_and_bridge_status(self):
        status = get_rea_bridge_status()
        self.assertIn("rea_source_present", status)
        self.assertTrue(status["rea_source_present"])
        self.assertIn("external_repos", status["rea_source_path"])
        self.assertIn(status["status"], ["ready", "source_available_needs_build"])

    def test_js_application_parser_extracts_metadata_and_ipc(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            pkg_path = Path(tmp_dir) / "package.json"
            pkg_path.write_text(
                json.dumps({
                    "name": "test-electron-app",
                    "version": "1.0.0",
                    "main": "main.js",
                    "dependencies": {"electron": "^28.0.0"},
                }),
                encoding="utf-8",
            )
            main_js = Path(tmp_dir) / "main.js"
            main_js.write_text(
                'const { ipcMain } = require("electron");\n'
                'ipcMain.on("channel:sync-doc", (event, arg) => {});\n'
                'ipcMain.handle("api:get-user", async () => {});\n',
                encoding="utf-8",
            )
            parser = JSApplicationParser(Path(tmp_dir))
            result = parser.parse()

            self.assertEqual(result["format"], "JavaScript/Node/Electron Application")
            self.assertEqual(result["package_metadata"]["name"], "test-electron-app")
            self.assertIn("electron dependency declared", result["electron_indicators"])
            self.assertIn("channel:sync-doc", result["api_surface"])
            self.assertIn("api:get-user", result["api_surface"])

    def test_inspect_real_or_synthetic_pe(self):
        # Test on local Grammarly assembly if present, otherwise test synthetic invalid binary
        grammarly_dll = Path(
            r"C:\Users\flowe\AppData\Local\Grammarly\DesktopIntegrations\Grammarly.CheetahClient.Protocol.dll"
        )
        if grammarly_dll.is_file():
            res = inspect_target(str(grammarly_dll))
            self.assertEqual(res["format"], ".NET Assembly (PE/CLR)")
            self.assertFalse(res["is_64bit"])
            self.assertIsNotNone(res["clr_runtime"])
            self.assertIn("#Strings", res["clr_runtime"]["streams"])
            self.assertGreater(res["clr_runtime"]["total_metadata_strings"], 50)
            self.assertTrue(any("Action" in s for s in res["clr_runtime"]["sample_types"]))
        else:
            res = DotNetPEParser(b"NOT_A_PE_FILE").parse()
            self.assertIn("error", res)

    def test_shinobi_scout_discovers_reverse_engineering_capability(self):
        # Verify that Shinobi's scout_horizon surfaces the reverse-engineering form
        results = scout_horizon(
            topic="reverse engineering",
            task="Inspect binary dll protocol and extract symbols",
            search_roots=[REPO_ROOT / "shinobi"],
        )
        self.assertIsInstance(results, list)
        form_names = [r.get("name") for r in results if isinstance(r, dict)]
        self.assertTrue(
            any("Reverse Engineering" in str(name) for name in form_names),
            f"Expected 'Reverse Engineering' in scout candidates: {form_names}",
        )


if __name__ == "__main__":
    unittest.main()
