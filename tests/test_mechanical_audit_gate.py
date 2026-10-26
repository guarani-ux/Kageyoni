"""Unit tests for deterministic MechanicalAuditorGate and AstAdversarialVisitor.

Validates:
1. `test_debug_tag_detection`: Flagging `[DEBUG-...]` in code, comments, and strings.
2. `test_comment_slop_detection`: Flagging AI comment slop patterns.
3. `test_machine_directives_allowed`: Preserving machine-linted directives starting with `@`
   and tooling directives (`# type: ignore`, `# noqa`, etc.).
4. `test_per_function_mutation_kill`: Per-function mutation targeting and touched_lines filtering.
5. `test_diff_mode_discovery_and_filtering`: Filtering excluded prefixes, test locating,
   and NO_TEST_FILE_FOUND reporting.
6. `test_cli_diff_and_channel_backward_compat`: CLI argument parsing for `--diff` and `--channel`.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mechanical_audit_gate import AstAdversarialVisitor, MechanicalAuditorGate


class TestMechanicalAuditGate(unittest.TestCase):
    """Qualification suite for MechanicalAuditorGate enhancements."""

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

    def _create_temp_file(self, rel_path: str, content: str) -> Path:
        full_path = REPO_ROOT / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        self.temp_files.append(full_path)
        return full_path

    def test_debug_tag_detection(self) -> None:
        """Verifies leftover [DEBUG-...] tags are flagged in comments, strings, and code."""
        # 1. In comment
        source_comment = (
            "# [DEBUG-550e8400-e29b-41d4-a716-446655440000] temporary trace probe\n"
            "def calculate(x: int) -> int:\n"
            "    return x + 1\n"
        )
        visitor = AstAdversarialVisitor("mod_comment.py", source=source_comment)
        self.assertTrue(any("Leftover debug instrumentation tag detected" in v for v in visitor.violations))
        self.assertTrue(any("[DEBUG-550e8400-e29b-41d4-a716-446655440000]" in v for v in visitor.violations))

        # 2. In string literal
        source_str = (
            "def log_state() -> str:\n"
            '    return "[DEBUG-instrumentation_tag] entering critical state"\n'
        )
        visitor_str = AstAdversarialVisitor("mod_str.py", source=source_str)
        self.assertTrue(any("Leftover debug instrumentation tag detected" in v for v in visitor_str.violations))
        self.assertTrue(any("[DEBUG-instrumentation_tag]" in v for v in visitor_str.violations))

        # 3. Clean source
        source_clean = (
            "def clean_func(x: int) -> int:\n"
            "    # Normal engineering explanation\n"
            '    msg = "Clean string without tag"\n'
            "    return x * 2\n"
        )
        visitor_clean = AstAdversarialVisitor("mod_clean.py", source=source_clean)
        self.assertEqual(len(visitor_clean.violations), 0)

    def test_comment_slop_detection(self) -> None:
        """Verifies AI comment slop patterns are flagged across source code."""
        slop_cases = [
            "# ... existing code ...",
            "# ... remaining code ...",
            "# ...",
            "# rest of code",
            "# here we compute the checksum",
            "# here is the parser implementation",
            "# here are the state variables",
            "# in this step we validate headers",
            "# now we execute the routine",
            "# function to parse incoming packet",
            "# function for validating signatures",
            "# function that extracts metadata",
            "# function which handles errors",
            "# method to format buffer",
            "# method for decoding payload",
            "# class to represent transaction",
            "# class for managing connections",
            "# helper to sanitize inputs",
            "# helper for reading bytes",
            "# this function does cryptographic hashing",
            "# this method is an entrypoint for parsing",
            "# this class handles packet reassembly",
            "# this function implements RFC 793",
            "# initialize the class",
            "# initializes the class",
        ]

        for slop in slop_cases:
            source = f"{slop}\ndef dummy():\n    pass\n"
            visitor = AstAdversarialVisitor("slop_test.py", source=source)
            self.assertTrue(
                any("AI comment slop detected" in v for v in visitor.violations),
                f"Failed to flag slop pattern: '{slop}'",
            )

    def test_machine_directives_allowed(self) -> None:
        """Verifies machine-linted directives starting with @ and tooling directives are preserved."""
        allowed_cases = [
            "# @invariant: memory consumption bounded to 64KB",
            "# @chestertons-fence: preserve legacy opcode parsing for DOS compatibility",
            "# @rule: causal DAG consistency required",
            "# type: ignore",
            "# type: ignore[assignment]",
            "# noqa",
            "# noqa: E501, F401",
            "# pragma: no cover",
            "# pylint: disable=too-many-branches",
            "# flake8: noqa",
            "# mypy: ignore-errors",
            "# Parse 32-bit PE optional header entries",
            "# Extract export directory RVA and size",
        ]

        for allowed in allowed_cases:
            source = f"{allowed}\ndef dummy(x: int) -> int:\n    return x + 1\n"
            visitor = AstAdversarialVisitor("allowed_test.py", source=source)
            self.assertEqual(
                len(visitor.violations),
                0,
                f"Incorrectly flagged allowed comment: '{allowed}', violations: {visitor.violations}",
            )

    def test_per_function_mutation_kill(self) -> None:
        """Verifies in-memory AST mutations target functions individually and respect touched_lines."""
        impl_code = (
            "def tested_func(x: int) -> int:\n"
            "    if x > 10:\n"
            "        return x * 2\n"
            "    return x\n"
            "\n"
            "def untested_func(y: int) -> int:\n"
            "    if y == 0:\n"
            "        raise ValueError('y must not be zero')\n"
            "    return y + 999\n"
        )
        test_code_partial = (
            "import unittest\n"
            "from kageyoni.ninshu._zt_temp_mut_impl import tested_func\n"
            "\n"
            "class TestPartial(unittest.TestCase):\n"
            "    def test_tested_func(self):\n"
            "        self.assertEqual(tested_func(20), 40)\n"
            "        self.assertEqual(tested_func(5), 5)\n"
            "    def test_dummy_fail_closed(self):\n"
            "        with self.assertRaises(ZeroDivisionError):\n"
            "            _ = 1 / 0\n"
        )

        impl_path = self._create_temp_file("kageyoni/ninshu/_zt_temp_mut_impl.py", impl_code)
        self._create_temp_file("tests/_test_zt_temp_mut_partial.py", test_code_partial)

        # 1. Without touched_lines: untested_func must be flagged as a surviving mutant
        passed, violations = MechanicalAuditorGate.audit_ast_mutations(
            impl_path,
            "kageyoni/ninshu/_zt_temp_mut_impl.py",
            "tests._test_zt_temp_mut_partial",
        )
        self.assertFalse(passed)
        joined_violations = "\n".join(violations)
        self.assertIn("SURVIVING_AST_MUTANT", joined_violations)
        self.assertTrue(
            "untested_func" in joined_violations,
            f"Expected surviving mutant for untested_func, got: {joined_violations}",
        )

        # 2. With touched_lines targeting only tested_func (lines 1..4): untested_func is skipped
        passed_touched, violations_touched = MechanicalAuditorGate.audit_ast_mutations(
            impl_path,
            "kageyoni/ninshu/_zt_temp_mut_impl.py",
            "tests._test_zt_temp_mut_partial",
            touched_lines=[1, 2, 3, 4],
        )
        self.assertTrue(
            passed_touched,
            f"Expected mutation audit to pass when filtering to tested_func, got: {violations_touched}",
        )

    def test_diff_mode_discovery_and_filtering(self) -> None:
        """Verifies diff file discovery excludes ignored prefixes and locates tests."""
        # 1. Test find_test_for_impl for existing module
        elf_impl = REPO_ROOT / "kageyoni/ninshu/elf_parser.py"
        test_found = MechanicalAuditorGate.find_test_for_impl(elf_impl)
        self.assertIsNotNone(test_found)
        self.assertTrue(test_found.name.endswith("elf_parser.py"))

        # 2. Test audit_implementation_file on an implementation file with no test suite
        orphan_code = "def orphan_utility():\n    return 42\n"
        orphan_path = self._create_temp_file("kageyoni/ninshu/_zt_temp_orphan.py", orphan_code)
        audit_res = MechanicalAuditorGate.audit_implementation_file(orphan_path)
        self.assertEqual(audit_res["verdict"], "REJECT")
        self.assertIn("NO_TEST_FILE_FOUND", audit_res["anti_patterns_found"])

        # 3. Test diff prefix exclusion invariant
        prefixes = MechanicalAuditorGate.EXCLUDED_DIFF_PREFIXES
        self.assertIn("tests/", prefixes)
        self.assertIn("tools/", prefixes)
        self.assertIn(".venv/", prefixes)

    def test_cli_diff_and_channel_backward_compat(self) -> None:
        """Verifies CLI argument parsing for --diff (default and custom ref) and backward compatibility."""
        # Check CLI argument parser definition
        parser = argparse.ArgumentParser()
        parser.add_argument("--diff", nargs="?", const="HEAD", default=None)
        parser.add_argument("--channel", type=int, required=False)
        parser.add_argument("--name", type=str, required=False)
        parser.add_argument("--impl", type=str, required=False)
        parser.add_argument("--test", type=str, required=False)

        # --diff flag without arg defaults to "HEAD"
        args1 = parser.parse_args(["--diff"])
        self.assertEqual(args1.diff, "HEAD")

        # --diff with explicit ref
        args2 = parser.parse_args(["--diff", "origin/main"])
        self.assertEqual(args2.diff, "origin/main")

        # Channel invocation
        args3 = parser.parse_args([
            "--channel", "2",
            "--name", "ELF Parser",
            "--impl", "kageyoni/ninshu/elf_parser.py",
            "--test", "tests.test_ninshu_elf_parser",
        ])
        self.assertIsNone(args3.diff)
        self.assertEqual(args3.channel, 2)
        self.assertEqual(args3.name, "ELF Parser")

        # Verify CLI execution on non-existent implementation rejects with code 1
        cmd = [
            sys.executable,
            "tools/mechanical_audit_gate.py",
            "--channel", "1",
            "--name", "PE Parser",
            "--impl", "kageyoni/ninshu/pe_parser.py",
            "--test", "tests.test_ninshu_pe_parser",
        ]
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertIn("MISSING_IMPLEMENTATION", res.stdout)


if __name__ == "__main__":
    unittest.main()
