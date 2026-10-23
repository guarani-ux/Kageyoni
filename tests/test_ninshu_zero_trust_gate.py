"""Comprehensive Zero-Trust Qualification Gate & In-Memory AST Mutation Test Suite.

Validates:
1. `MechanicalAuditorGate` rejects swallowed generic exceptions (`except Exception: pass`).
2. `MechanicalAuditorGate` rejects unconditional promotions (`promoted = True` or `verdict = "ACCEPT"`
   outside verified conditional branches or in `else` / `if True:` branches).
3. `MechanicalAuditorGate` rejects test suites that fail to import the target implementation module
   or lack positive assertions or fail-closed `assertRaises` checks.
4. `MechanicalAuditorGate` in-memory AST mutation auditor rejects tautological test suites that
   do not actually exercise or kill injected AST faults in the implementation module.
5. `MechanicalAuditorGate` accepts valid, fail-closed parser implementations with discriminating test suites.
6. `tools/audit_completion.py` executes all 48/48 channels live via `Patchbay.execute_channel()`
   with `thermodynamic_passed == True`.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.audit_completion import run_empirical_audit
from tools.mechanical_audit_gate import MechanicalAuditorGate


class TestNinshuZeroTrustGate(unittest.TestCase):
    """Mechanical verification suite for MechanicalAuditorGate and 48/48 audit_completion."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_files: list[Path] = []

    @classmethod
    def tearDownClass(cls) -> None:
        for p in cls.temp_files:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

    def _write_temp_pair(self, tag: str, impl_code: str, test_code: str) -> tuple[str, str]:
        impl_rel = f"kageyoni/ninshu/_zt_temp_{tag}.py"
        test_mod = f"tests._test_zt_temp_{tag}"
        impl_path = REPO_ROOT / impl_rel
        test_path = REPO_ROOT / "tests" / f"_test_zt_temp_{tag}.py"

        impl_path.write_text(impl_code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")
        self.temp_files.extend([impl_path, test_path])
        return impl_rel, test_mod

    def test_01_rejects_swallowed_exceptions(self) -> None:
        """Verifies AST linter catches swallowed `except Exception: pass` and bare `except: pass`."""
        impl_code = '''"""Swallowed exception test module."""
class SwallowedParser:
    @classmethod
    def parse(cls, data: bytes) -> dict:
        if not isinstance(data, bytes):
            raise TypeError("expected bytes")
        try:
            if len(data) < 4:
                raise ValueError("too short")
        except Exception:
            pass
        return {"ok": True}
'''
        test_code = '''import unittest
from kageyoni.ninshu._zt_temp_swallow import SwallowedParser

class TestSwallow(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(SwallowedParser.parse(b"ABCD")["ok"], True)
    def test_bad(self):
        with self.assertRaises(TypeError):
            SwallowedParser.parse(123)
'''
        impl_rel, test_mod = self._write_temp_pair("swallow", impl_code, test_code)
        res = MechanicalAuditorGate.audit_channel(901, "swallow_test", impl_rel, test_mod)
        self.assertEqual(res["verdict"], "REJECT")
        joined = "\n".join(res["anti_patterns_found"])
        self.assertIn("Swallowed generic exception", joined)

    def test_02_rejects_unconditional_promotions_and_verdicts(self) -> None:
        """Verifies AST linter catches unconditional `promoted = True` and `verdict = 'ACCEPT'`."""
        impl_code = '''"""Unconditional promotion shortcut module."""
class ShortcutParser:
    @classmethod
    def parse(cls, data: bytes) -> dict:
        if not isinstance(data, bytes) or len(data) < 4:
            raise ValueError("invalid")
        promoted = True
        if len(data) > 100:
            verdict = "ACCEPT"
        else:
            verdict = "ACCEPT"
        return {"promoted": promoted, "verdict": verdict, "len": len(data)}
'''
        test_code = '''import unittest
from kageyoni.ninshu._zt_temp_promo import ShortcutParser

class TestPromo(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(ShortcutParser.parse(b"ABCD")["len"], 4)
    def test_bad(self):
        with self.assertRaises(ValueError):
            ShortcutParser.parse(b"A")
'''
        impl_rel, test_mod = self._write_temp_pair("promo", impl_code, test_code)
        res = MechanicalAuditorGate.audit_channel(902, "promo_test", impl_rel, test_mod)
        self.assertEqual(res["verdict"], "REJECT")
        joined = "\n".join(res["anti_patterns_found"])
        self.assertIn("Unconditional promotion (`promoted = True`)", joined)
        self.assertIn("Unconditional verdict assignment (`verdict = 'ACCEPT'`)", joined)

    def test_03_rejects_missing_test_imports_and_assertions(self) -> None:
        """Verifies TestAstVerificationVisitor catches missing target import, missing positive asserts, or missing assertRaises."""
        impl_code = '''"""Valid implementation with weak test."""
class ValidMiniParser:
    @classmethod
    def parse(cls, data: bytes) -> int:
        if not isinstance(data, bytes) or len(data) < 4:
            raise ValueError("invalid")
        return len(data)
'''
        # Case A: Does not import target module and has no assertRaises
        test_code_no_import = '''import unittest

class TestNoImport(unittest.TestCase):
    def test_something(self):
        x = 10
        self.assertEqual(x, 10)
'''
        impl_rel, test_mod = self._write_temp_pair("no_import", impl_code, test_code_no_import)
        res = MechanicalAuditorGate.audit_channel(903, "no_import_test", impl_rel, test_mod)
        self.assertEqual(res["verdict"], "REJECT")
        joined = "\n".join(res["anti_patterns_found"])
        self.assertIn("MISSING_TARGET_IMPORT", joined)
        self.assertIn("MISSING_FAIL_CLOSED_ASSERTIONS", joined)

    def test_04_rejects_tautological_tests_via_in_memory_ast_mutation(self) -> None:
        """Verifies in-memory AST mutation auditor rejects tests that import the module but fail to kill mutants."""
        impl_code = '''"""Valid implementation paired with a tautological non-calling test."""
class UncalledParser:
    @classmethod
    def parse(cls, data: bytes) -> int:
        if not isinstance(data, bytes) or data[:2] != b"OK":
            raise ValueError("invalid magic")
        return len(data)
'''
        # Test imports UncalledParser, has a positive assertion and an assertRaises,
        # but never actually calls UncalledParser.parse!
        test_code_tautological = '''import unittest
from kageyoni.ninshu._zt_temp_tautology import UncalledParser

class TestTautological(unittest.TestCase):
    def test_fake_positive(self):
        self.assertIsNotNone(UncalledParser)

    def test_fake_negative(self):
        with self.assertRaises(ValueError):
            raise ValueError("synthetic raise without calling parser")
'''
        impl_rel, test_mod = self._write_temp_pair("tautology", impl_code, test_code_tautological)
        res = MechanicalAuditorGate.audit_channel(904, "tautology_test", impl_rel, test_mod)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertFalse(res["mutation_kill_verified"])
        joined = "\n".join(res["anti_patterns_found"])
        self.assertIn("SURVIVING_AST_MUTANT", joined)

    def test_05_accepts_valid_fail_closed_module(self) -> None:
        """Verifies MechanicalAuditorGate accepts a genuine fail-closed module and discriminating test suite."""
        impl_code = '''"""Genuine fail-closed parser module."""
class GenuineParser:
    MAGIC = b"KAGE"

    @classmethod
    def parse(cls, data: bytes) -> dict:
        if not isinstance(data, bytes):
            raise TypeError("expected bytes")
        if len(data) < 6:
            raise ValueError("truncated input")
        if data[:4] != cls.MAGIC:
            raise ValueError("magic mismatch")
        if len(data) >= 6:
            promoted = True
        else:
            promoted = False
        return {"magic": "KAGE", "payload_len": len(data) - 4, "promoted": promoted}
'''
        test_code = '''import unittest
from kageyoni.ninshu._zt_temp_genuine import GenuineParser

class TestGenuineParser(unittest.TestCase):
    def test_golden_valid(self):
        res = GenuineParser.parse(b"KAGE1234")
        self.assertEqual(res["magic"], "KAGE")
        self.assertEqual(res["payload_len"], 4)
        self.assertTrue(res["promoted"])

    def test_rejects_bad_magic(self):
        with self.assertRaises(ValueError):
            GenuineParser.parse(b"FAIL1234")

    def test_rejects_truncated(self):
        with self.assertRaises(ValueError):
            GenuineParser.parse(b"KA")

    def test_rejects_bad_type(self):
        with self.assertRaises(TypeError):
            GenuineParser.parse("not_bytes")  # type: ignore
'''
        impl_rel, test_mod = self._write_temp_pair("genuine", impl_code, test_code)
        res = MechanicalAuditorGate.audit_channel(905, "genuine_test", impl_rel, test_mod)
        self.assertEqual(res["verdict"], "ACCEPT", f"Expected ACCEPT, got {res}")
        self.assertTrue(res["mutation_kill_verified"])
        self.assertEqual(len(res["anti_patterns_found"]), 0)

    def test_06_audit_completion_48_of_48_live_execution(self) -> None:
        """Verifies tools/audit_completion.py executes all 48/48 channels via Patchbay.execute_channel."""
        receipt = run_empirical_audit()
        self.assertEqual(receipt["total_channels"], 48)
        self.assertEqual(receipt["verified_channels"], 48)
        self.assertEqual(receipt["failed_channels_count"], 0)
        self.assertTrue(receipt["all_passed"])
        self.assertEqual(len(receipt["passed_channels"]), 48)
        for ch_entry in receipt["passed_channels"]:
            self.assertTrue(ch_entry["thermodynamic_passed"])
            self.assertLessEqual(ch_entry["peak_memory_bytes"], 64 * 1024)
            self.assertEqual(len(ch_entry["output_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
