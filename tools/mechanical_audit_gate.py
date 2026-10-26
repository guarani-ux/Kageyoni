"""Deterministic Mechanical Zero-Trust Code Auditor (Zero Quota Dependency).

Implements strict AST-level adversarial scanning, test discrimination verification,
and in-memory AST mutation testing:
1. AST SHORTCUT SCANNING & SOURCE LINTING:
   - Scans code for unconditional promotions (`promoted = True` or `verdict = "ACCEPT"`
     outside conditional verification branches or inside tautological/else branches).
   - Flags swallowed exceptions (`except:` or `except Exception:` without re-raise or logging).
   - Flags leftover debug instrumentation tags (`[DEBUG-...]`).
   - Flags AI comment slop (e.g. `# ... existing code ...`, `# Here we ...`, `# Function to ...`).
   - Preserves machine-linted directives (`# @invariant:`, `# type: ignore`, etc.).
2. TEST AST & IMPORT VERIFICATION:
   - Verifies the test module actually imports the target implementation module.
   - Enforces presence of both positive assertions and fail-closed `assertRaises` checks.
   - Flags tautological assertions (`assert True`, `assertTrue(True)`).
3. IN-MEMORY AST MUTATION AUDITOR:
   - Compiles mutated AST variants of the implementation module directly into `sys.modules`
     in an isolated child process (inverting comparisons/returns and stripping fail-closed
     exception guards) per function or globally without modifying files on disk.
   - Rejects any candidate whose test suite fails to kill the injected AST mutants.
4. PHYSICAL DISCRIMINATION & DIFF AUDIT:
   - Discovers modified files via git diff with touched-line targeting.
   - Executes valid golden vectors and adversarial mutants via unittest.

Returns exit code 0 on clean ACCEPT, exit code 1 on REJECT with exact line-level reasons.
Does NOT consume external LLM API quota.
"""
from __future__ import annotations

import argparse
import ast
import copy
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent


class AstAdversarialVisitor(ast.NodeVisitor):
    """Parses Python AST and source text to mechanically flag shortcuts, swallowed errors, debug tags, and AI slop."""

    DEBUG_TAG_PATTERN = re.compile(r"\[DEBUG-[0-9a-zA-Z_-]+\]")

    COMMENT_SLOP_PATTERNS = [
        re.compile(r"^\s*#\s*(\.\.\.|\.\.\.\s*(existing|remaining)\s*code|rest\s+of\s+code)\b", re.IGNORECASE),
        re.compile(r"^\s*#\s*\.\.\.", re.IGNORECASE),
        re.compile(r"^\s*#\s*(here\s+(we|is|are)|in\s+this\s+step|now\s+we)\b", re.IGNORECASE),
        re.compile(r"^\s*#\s*(function\s+(to|for|that|which)|method\s+(to|for)|class\s+(to|for)|helper\s+(to|for))\b", re.IGNORECASE),
        re.compile(r"^\s*#\s*this\s+(function|method|class)\s+(does|is|handles|implements)\b", re.IGNORECASE),
        re.compile(r"^\s*#\s*initialize[sd]?\s+(the\s+)?class\b", re.IGNORECASE),
    ]

    ALLOWED_DIRECTIVE_PREFIXES = (
        "type:",
        "noqa",
        "pragma:",
        "pylint:",
        "flake8:",
        "mypy:",
        "isort:",
        "nosec",
        "fmt:",
        "autopep8:",
        "black:",
    )

    def __init__(self, filename: str, source: Optional[str] = None):
        self.filename = filename
        self.violations: List[str] = []
        self._conditional_depth: int = 0
        self._in_else_branch: bool = False
        if source is not None:
            self.scan_source_text(source)

    def scan_source_text(self, source: str) -> None:
        """Flags leftover debug instrumentation tags and AI comment slop."""
        for lineno, line in enumerate(source.splitlines(), start=1):
            for match in self.DEBUG_TAG_PATTERN.finditer(line):
                msg = f"{self.filename}:{lineno}: Leftover debug instrumentation tag detected: '{match.group(0)}'."
                if msg not in self.violations:
                    self.violations.append(msg)

        try:
            tokens = tokenize.generate_tokens(io.StringIO(source).readline)
            for tok_type, tok_string, (srow, scol), (erow, ecol), line in tokens:
                if tok_type == tokenize.COMMENT:
                    comment_body = tok_string.lstrip("#").strip()
                    if comment_body.startswith("@"):
                        continue
                    lower_body = comment_body.lower()
                    if any(lower_body.startswith(prefix) for prefix in self.ALLOWED_DIRECTIVE_PREFIXES):
                        continue
                    for pattern in self.COMMENT_SLOP_PATTERNS:
                        if pattern.search(tok_string):
                            msg = f"{self.filename}:{srow}: AI comment slop detected: '{tok_string.strip()}'."
                            if msg not in self.violations:
                                self.violations.append(msg)
                            break
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        # Check if exception is completely swallowed (body only contains 'pass' or ellipsis)
        if len(node.body) == 1 and (
            isinstance(node.body[0], ast.Pass)
            or (
                isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and node.body[0].value.value is Ellipsis
            )
        ):
            if node.type is None or (
                isinstance(node.type, ast.Name)
                and node.type.id in ("Exception", "BaseException")
            ):
                exc_name = node.type.id if isinstance(node.type, ast.Name) else ""
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Swallowed generic exception "
                    f"(`except {exc_name}: pass`) without logging or re-raise."
                )
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        is_tautological = (
            isinstance(node.test, ast.Constant) and bool(node.test.value) is True
        )
        self.visit(node.test)

        if not is_tautological:
            self._conditional_depth += 1
        prev_else = self._in_else_branch
        self._in_else_branch = False
        for stmt in node.body:
            self.visit(stmt)
        if not is_tautological:
            self._conditional_depth -= 1

        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                self._in_else_branch = prev_else
                self.visit(node.orelse[0])
            else:
                self._in_else_branch = True
                for stmt in node.orelse:
                    self.visit(stmt)
        self._in_else_branch = prev_else

    def _check_promotion_assignment(self, target: ast.AST, value: ast.AST, lineno: int) -> None:
        if not isinstance(target, ast.Name):
            return
        if target.id == "promoted" and isinstance(value, ast.Constant) and value.value is True:
            if self._conditional_depth == 0 or self._in_else_branch:
                self.violations.append(
                    f"{self.filename}:{lineno}: Unconditional promotion (`promoted = True`) "
                    f"outside verified conditional branch."
                )
        elif (
            target.id == "verdict"
            and isinstance(value, ast.Constant)
            and value.value in ("ACCEPT", "ACCEPTED", "PASS", "READY")
        ):
            if self._conditional_depth == 0 or self._in_else_branch:
                self.violations.append(
                    f"{self.filename}:{lineno}: Unconditional verdict assignment "
                    f"(`verdict = {value.value!r}`) outside verified conditional branch."
                )

    def visit_Assign(self, node: ast.Assign):
        for target in node.targets:
            self._check_promotion_assignment(target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value is not None:
            self._check_promotion_assignment(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            match = self.DEBUG_TAG_PATTERN.search(node.value)
            if match:
                msg = f"{self.filename}:{node.lineno}: Leftover debug instrumentation tag detected: '{match.group(0)}'."
                if msg not in self.violations:
                    self.violations.append(msg)
        self.generic_visit(node)


class TestAstVerificationVisitor(ast.NodeVisitor):
    """Inspects test suite AST to verify target module import, positive assertions, and fail-closed checks."""

    POSITIVE_ASSERT_METHODS = {
        "assertEqual",
        "assertNotEqual",
        "assertTrue",
        "assertFalse",
        "assertIs",
        "assertIsNot",
        "assertIsNone",
        "assertIsNotNone",
        "assertIn",
        "assertNotIn",
        "assertIsInstance",
        "assertNotIsInstance",
        "assertGreater",
        "assertGreaterEqual",
        "assertLess",
        "assertLessEqual",
        "assertAlmostEqual",
        "assertRegex",
        "assertCountEqual",
    }
    FAIL_CLOSED_ASSERT_METHODS = {
        "assertRaises",
        "assertRaisesRegex",
    }

    def __init__(self, filename: str, impl_module: str, impl_stem: str):
        self.filename = filename
        self.impl_module = impl_module
        self.impl_stem = impl_stem
        self.imports_target: bool = False
        self.positive_assertions: int = 0
        self.fail_closed_assertions: int = 0
        self.violations: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if (
                alias.name == self.impl_module
                or alias.name.endswith(f".{self.impl_stem}")
                or alias.name == self.impl_stem
            ):
                self.imports_target = True
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        if (
            mod == self.impl_module
            or mod.endswith(f".{self.impl_stem}")
            or mod == self.impl_stem
        ):
            self.imports_target = True
        for alias in node.names:
            if alias.name == self.impl_stem:
                self.imports_target = True
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        if isinstance(node.test, ast.Constant) and bool(node.test.value) is True:
            self.violations.append(
                f"{self.filename}:{node.lineno}: Tautological assertion (`assert {node.test.value!r}`)."
            )
        else:
            self.positive_assertions += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func_name = None
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

        if func_name in self.FAIL_CLOSED_ASSERT_METHODS:
            self.fail_closed_assertions += 1
        elif func_name in self.POSITIVE_ASSERT_METHODS:
            if (
                func_name == "assertTrue"
                and len(node.args) >= 1
                and isinstance(node.args[0], ast.Constant)
                and bool(node.args[0].value) is True
            ):
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Tautological assertion (`assertTrue({node.args[0].value!r})`)."
                )
            elif (
                func_name == "assertEqual"
                and len(node.args) >= 2
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[1], ast.Constant)
                and node.args[0].value == node.args[1].value
            ):
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Tautological constant assertion "
                    f"(`assertEqual({node.args[0].value!r}, {node.args[1].value!r})`)."
                )
            else:
                self.positive_assertions += 1
        self.generic_visit(node)


_MUTATION_RUNNER_SCRIPT = r"""
import ast
import copy
import importlib
import io
import json
import sys
import unittest
from pathlib import Path

impl_file = Path(sys.argv[1]).resolve()
impl_mod_name = sys.argv[2]
test_mod_name = sys.argv[3]
touched_lines = None
if len(sys.argv) > 4 and sys.argv[4]:
    try:
        raw_lines = json.loads(sys.argv[4])
        if raw_lines is not None:
            touched_lines = set(raw_lines)
    except Exception:
        touched_lines = None

source = impl_file.read_text(encoding="utf-8")
base_tree = ast.parse(source, filename=str(impl_file))

class TargetedComparisonAndReturnMutator(ast.NodeTransformer):
    def __init__(self, target_qname=None):
        self.target_qname = target_qname
        self.mutated_count = 0
        self._class_stack = []
        self._in_target = (target_qname is None)

    def visit_ClassDef(self, node):
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()
        return node

    def _check_func_match(self, node):
        if self.target_qname is None:
            return True
        cls_prefix = ".".join(self._class_stack)
        qname = f"{cls_prefix}.{node.name}" if cls_prefix else node.name
        return qname == self.target_qname

    def visit_FunctionDef(self, node):
        if self.target_qname is None:
            self.generic_visit(node)
            return node
        if self._check_func_match(node):
            prev = self._in_target
            self._in_target = True
            self.generic_visit(node)
            self._in_target = prev
        return node

    def visit_AsyncFunctionDef(self, node):
        if self.target_qname is None:
            self.generic_visit(node)
            return node
        if self._check_func_match(node):
            prev = self._in_target
            self._in_target = True
            self.generic_visit(node)
            self._in_target = prev
        return node

    def visit_Compare(self, node):
        self.generic_visit(node)
        if not self._in_target:
            return node
        new_ops = []
        for op in node.ops:
            if isinstance(op, ast.Eq):
                new_ops.append(ast.NotEq())
                self.mutated_count += 1
            elif isinstance(op, ast.NotEq):
                new_ops.append(ast.Eq())
                self.mutated_count += 1
            elif isinstance(op, ast.Lt):
                new_ops.append(ast.GtE())
                self.mutated_count += 1
            elif isinstance(op, ast.LtE):
                new_ops.append(ast.Gt())
                self.mutated_count += 1
            elif isinstance(op, ast.Gt):
                new_ops.append(ast.LtE())
                self.mutated_count += 1
            elif isinstance(op, ast.GtE):
                new_ops.append(ast.Lt())
                self.mutated_count += 1
            elif isinstance(op, ast.Is):
                new_ops.append(ast.IsNot())
                self.mutated_count += 1
            elif isinstance(op, ast.IsNot):
                new_ops.append(ast.Is())
                self.mutated_count += 1
            elif isinstance(op, ast.In):
                new_ops.append(ast.NotIn())
                self.mutated_count += 1
            elif isinstance(op, ast.NotIn):
                new_ops.append(ast.In())
                self.mutated_count += 1
            else:
                new_ops.append(op)
        node.ops = new_ops
        return node

    def visit_Return(self, node):
        self.generic_visit(node)
        if not self._in_target:
            return node
        if isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, bool):
                node.value = ast.Constant(value=not node.value.value)
                self.mutated_count += 1
            elif isinstance(node.value.value, (int, float)):
                node.value = ast.Constant(value=node.value.value + 999999)
                self.mutated_count += 1
            elif isinstance(node.value.value, str):
                node.value = ast.Constant(value="__MUTATED_INVALID_RETURN__")
                self.mutated_count += 1
        elif node.value is not None:
            node.value = ast.Constant(value=None)
            self.mutated_count += 1
        return node

class TargetedGuardStripperMutator(ast.NodeTransformer):
    def __init__(self, target_qname=None):
        self.target_qname = target_qname
        self.mutated_count = 0
        self._class_stack = []
        self._in_target = (target_qname is None)

    def visit_ClassDef(self, node):
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()
        return node

    def _check_func_match(self, node):
        if self.target_qname is None:
            return True
        cls_prefix = ".".join(self._class_stack)
        qname = f"{cls_prefix}.{node.name}" if cls_prefix else node.name
        return qname == self.target_qname

    def visit_FunctionDef(self, node):
        if self.target_qname is None:
            self.generic_visit(node)
            return node
        if self._check_func_match(node):
            prev = self._in_target
            self._in_target = True
            self.generic_visit(node)
            self._in_target = prev
        return node

    def visit_AsyncFunctionDef(self, node):
        if self.target_qname is None:
            self.generic_visit(node)
            return node
        if self._check_func_match(node):
            prev = self._in_target
            self._in_target = True
            self.generic_visit(node)
            self._in_target = prev
        return node

    def visit_Raise(self, node):
        if not self._in_target:
            return node
        self.mutated_count += 1
        return ast.copy_location(ast.Pass(), node)

ComparisonAndReturnMutator = TargetedComparisonAndReturnMutator
GuardStripperMutator = TargetedGuardStripperMutator

# Discover candidate functions
all_candidates = []
for node in base_tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if not (node.name.startswith("__") and node.name.endswith("__")):
            all_candidates.append((node.name, node.lineno, getattr(node, "end_lineno", node.lineno)))
    elif isinstance(node, ast.ClassDef):
        class_name = node.name
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not (item.name.startswith("__") and item.name.endswith("__")):
                    all_candidates.append((f"{class_name}.{item.name}", item.lineno, getattr(item, "end_lineno", item.lineno)))

candidate_functions = all_candidates
if touched_lines is not None:
    intersected = [
        (qname, s, e)
        for qname, s, e in all_candidates
        if any(s <= line <= e for line in touched_lines)
    ]
    if intersected:
        candidate_functions = intersected

mutants = []
for func_qname, s_line, e_line in candidate_functions:
    m1_tree = copy.deepcopy(base_tree)
    m1 = TargetedComparisonAndReturnMutator(target_qname=func_qname)
    m1_tree = ast.fix_missing_locations(m1.visit(m1_tree))
    if m1.mutated_count > 0:
        mutants.append((f"comparison_and_return::{func_qname}", m1_tree, m1.mutated_count))

    m2_tree = copy.deepcopy(base_tree)
    m2 = TargetedGuardStripperMutator(target_qname=func_qname)
    m2_tree = ast.fix_missing_locations(m2.visit(m2_tree))
    if m2.mutated_count > 0:
        mutants.append((f"guard_strip::{func_qname}", m2_tree, m2.mutated_count))

if not mutants:
    m1_tree = copy.deepcopy(base_tree)
    m1 = ComparisonAndReturnMutator(target_qname=None)
    m1_tree = ast.fix_missing_locations(m1.visit(m1_tree))
    if m1.mutated_count > 0:
        mutants.append(("comparison_and_return_inversion", m1_tree, m1.mutated_count))

    m2_tree = copy.deepcopy(base_tree)
    m2 = GuardStripperMutator(target_qname=None)
    m2_tree = ast.fix_missing_locations(m2.visit(m2_tree))
    if m2.mutated_count > 0:
        mutants.append(("fail_closed_guard_strip", m2_tree, m2.mutated_count))

report = {"mutants_tested": len(mutants), "mutants_killed": 0, "surviving": []}

for name, tree, count in mutants:
    if impl_mod_name in sys.modules:
        del sys.modules[impl_mod_name]
    mod = importlib.import_module(impl_mod_name)
    code_obj = compile(tree, filename=str(impl_file), mode="exec")
    exec(code_obj, mod.__dict__)

    if test_mod_name in sys.modules:
        del sys.modules[test_mod_name]

    suite = unittest.defaultTestLoader.loadTestsFromName(test_mod_name)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    res = runner.run(suite)
    if res.testsRun == 0 or res.wasSuccessful():
        report["surviving"].append(name)
    else:
        report["mutants_killed"] += 1

print(json.dumps(report))
"""


class MechanicalAuditorGate:
    """Zero-quota mechanical code and test auditor."""

    EXCLUDED_DIFF_PREFIXES = (
        "tests/",
        ".venv/",
        "external_repos/",
        "tools/",
        "build/",
        "dist/",
        ".git/",
        "__pycache__/",
    )

    @classmethod
    def audit_ast(cls, file_paths: List[Path]) -> List[str]:
        violations = []
        for path in file_paths:
            if path.suffix == ".py" and path.exists():
                try:
                    source = path.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(path))
                    visitor = AstAdversarialVisitor(str(path.name), source=source)
                    visitor.visit(tree)
                    violations.extend(visitor.violations)
                except Exception as e:
                    violations.append(f"AST parse failure on {path.name}: {e}")
        return violations

    @classmethod
    def audit_test_ast(cls, test_path: Path, impl_file: str) -> List[str]:
        """Verifies test file AST imports target module and contains both positive and fail-closed assertions."""
        if not test_path.exists():
            return [f"MISSING_TEST_FILE: Test file does not exist: {test_path.name}"]

        clean_impl = impl_file.replace("\\", "/").strip()
        if clean_impl.endswith(".py"):
            clean_impl = clean_impl[:-3]
        impl_module = clean_impl.replace("/", ".")
        impl_stem = Path(impl_file).stem

        try:
            source = test_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(test_path))
        except Exception as e:
            return [f"AST parse failure on {test_path.name}: {e}"]

        visitor = TestAstVerificationVisitor(test_path.name, impl_module, impl_stem)
        visitor.visit(tree)

        violations = list(visitor.violations)
        if not visitor.imports_target:
            violations.append(
                f"{test_path.name}: MISSING_TARGET_IMPORT: Test suite does not import target module '{impl_module}'."
            )
        if visitor.positive_assertions == 0:
            violations.append(
                f"{test_path.name}: MISSING_POSITIVE_ASSERTIONS: Test suite contains 0 positive assertions."
            )
        if visitor.fail_closed_assertions == 0:
            violations.append(
                f"{test_path.name}: MISSING_FAIL_CLOSED_ASSERTIONS: Test suite contains 0 `assertRaises` checks."
            )
        return violations

    @classmethod
    def audit_ast_mutations(
        cls,
        impl_path: Path,
        impl_file: str,
        test_module: str,
        touched_lines: Optional[List[int]] = None,
    ) -> Tuple[bool, List[str]]:
        """Executes in-memory AST mutation testing in an isolated child process."""
        clean_impl = impl_file.replace("\\", "/").strip()
        if clean_impl.endswith(".py"):
            clean_impl = clean_impl[:-3]
        impl_mod_name = clean_impl.replace("/", ".")

        cmd = [
            sys.executable,
            "-c",
            _MUTATION_RUNNER_SCRIPT,
            str(impl_path),
            impl_mod_name,
            test_module,
        ]
        if touched_lines is not None:
            cmd.append(json.dumps(touched_lines))

        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
        if res.returncode != 0:
            return False, [
                f"IN_MEMORY_MUTATION_ERROR: Mutation runner failed: {(res.stderr or res.stdout).strip()[-300:]}"
            ]

        try:
            lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            report = json.loads(lines[-1])
        except Exception as e:
            return False, [f"IN_MEMORY_MUTATION_PARSE_ERROR: {e}"]

        if report.get("mutants_tested", 0) == 0:
            return False, [
                f"{impl_path.name}: ZERO_MUTANTS_GENERATED: Implementation contains no mutable comparisons, returns, or guards."
            ]

        surviving = report.get("surviving", [])
        if surviving:
            return False, [
                f"{test_module}: SURVIVING_AST_MUTANT: Test suite failed to kill in-memory AST mutant(s): {', '.join(surviving)}."
            ]

        return True, []

    @classmethod
    def verify_mutation_kill(
        cls,
        impl_path: Path,
        impl_file: str,
        test_module: str,
        touched_lines: Optional[List[int]] = None,
    ) -> Tuple[bool, List[str]]:
        """Alias for audit_ast_mutations."""
        return cls.audit_ast_mutations(impl_path, impl_file, test_module, touched_lines=touched_lines)

    @classmethod
    def run_unit_tests(cls, test_module: str) -> Tuple[bool, str]:
        cmd = [sys.executable, "-m", "unittest", "-v", test_module]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, env=env)
        return res.returncode == 0, res.stdout + res.stderr

    @classmethod
    def discover_diff_files(cls, ref: str = "HEAD") -> List[Tuple[Path, Optional[List[int]]]]:
        """Discovers modified Python files and touched line numbers from git diff and untracked files."""
        cmd_diff = ["git", "diff", "--name-only", ref]
        res_diff = subprocess.run(cmd_diff, cwd=REPO_ROOT, capture_output=True, text=True)
        tracked_files: List[str] = []
        if res_diff.returncode == 0:
            tracked_files = [line.strip() for line in res_diff.stdout.splitlines() if line.strip()]

        cmd_untracked = ["git", "ls-files", "--others", "--exclude-standard"]
        res_untracked = subprocess.run(cmd_untracked, cwd=REPO_ROOT, capture_output=True, text=True)
        untracked_files: List[str] = []
        if res_untracked.returncode == 0:
            untracked_files = [line.strip() for line in res_untracked.stdout.splitlines() if line.strip()]

        discovered: List[Tuple[Path, Optional[List[int]]]] = []
        seen_paths: Set[str] = set()

        for rel_str in tracked_files:
            norm_str = rel_str.replace("\\", "/")
            if any(norm_str.startswith(prefix) for prefix in cls.EXCLUDED_DIFF_PREFIXES):
                continue
            if not norm_str.endswith(".py"):
                continue
            full_path = (REPO_ROOT / norm_str).resolve()
            if not full_path.exists():
                continue
            if norm_str in seen_paths:
                continue
            seen_paths.add(norm_str)

            cmd_lines = ["git", "diff", "-U0", ref, "--", rel_str]
            res_lines = subprocess.run(cmd_lines, cwd=REPO_ROOT, capture_output=True, text=True)
            touched: List[int] = []
            if res_lines.returncode == 0:
                for m in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", res_lines.stdout):
                    start = int(m.group(1))
                    count = int(m.group(2)) if m.group(2) is not None else 1
                    if count > 0:
                        touched.extend(range(start, start + count))

            discovered.append((full_path, touched if touched else None))

        for rel_str in untracked_files:
            norm_str = rel_str.replace("\\", "/")
            if any(norm_str.startswith(prefix) for prefix in cls.EXCLUDED_DIFF_PREFIXES):
                continue
            if not norm_str.endswith(".py"):
                continue
            full_path = (REPO_ROOT / norm_str).resolve()
            if not full_path.exists():
                continue
            if norm_str in seen_paths:
                continue
            seen_paths.add(norm_str)

            discovered.append((full_path, None))

        return discovered

    @classmethod
    def find_test_for_impl(cls, impl_path: Path) -> Optional[Path]:
        """Locates the matching test file for a given implementation file."""
        stem = impl_path.stem
        tests_dir = REPO_ROOT / "tests"
        if not tests_dir.exists():
            return None

        # 1. Check tests/test_<stem>.py
        direct = tests_dir / f"test_{stem}.py"
        if direct.exists():
            return direct

        # 2. Check tests/test_<stem>_*.py and tests/test_*_<stem>.py
        prefix_matches = sorted(tests_dir.glob(f"test_{stem}_*.py"))
        if prefix_matches:
            return prefix_matches[0]
        suffix_matches = sorted(tests_dir.glob(f"test_*_{stem}.py"))
        if suffix_matches:
            return suffix_matches[0]

        # 3. Scan tests/test_*.py for imports importing the implementation module or stem
        try:
            rel = impl_path.resolve().relative_to(REPO_ROOT)
        except ValueError:
            rel = impl_path
        clean_rel = str(rel).replace("\\", "/")
        if clean_rel.endswith(".py"):
            clean_rel = clean_rel[:-3]
        impl_module = clean_rel.replace("/", ".")

        for test_file in sorted(tests_dir.glob("test_*.py")):
            try:
                content = test_file.read_text(encoding="utf-8")
                if impl_module in content or stem in content:
                    try:
                        tree = ast.parse(content, filename=str(test_file))
                        for node in ast.walk(tree):
                            if isinstance(node, ast.Import):
                                for alias in node.names:
                                    if alias.name == impl_module or alias.name.endswith(f".{stem}") or alias.name == stem:
                                        return test_file
                            elif isinstance(node, ast.ImportFrom):
                                mod = node.module or ""
                                if mod == impl_module or mod.endswith(f".{stem}") or mod == stem:
                                    return test_file
                                for alias in node.names:
                                    if alias.name == stem:
                                        return test_file
                    except Exception:
                        pass
            except Exception:
                pass

        return None

    @classmethod
    def audit_implementation_file(
        cls, impl_path: Path, touched_lines: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Audits an implementation file against its corresponding test suite."""
        test_path = cls.find_test_for_impl(impl_path)
        if test_path is None:
            return {
                "impl_file": str(impl_path),
                "test_file": None,
                "verdict": "REJECT",
                "reasons": [f"No test file found for {impl_path.name}"],
                "anti_patterns": ["NO_TEST_FILE_FOUND"],
                "anti_patterns_found": ["NO_TEST_FILE_FOUND"],
                "mutation_kill_verified": False,
            }

        try:
            rel_impl = impl_path.resolve().relative_to(REPO_ROOT)
        except ValueError:
            rel_impl = impl_path
        impl_rel_str = str(rel_impl).replace("\\", "/")

        try:
            rel_test = test_path.resolve().relative_to(REPO_ROOT)
        except ValueError:
            rel_test = test_path
        test_rel_str = str(rel_test).replace("\\", "/")
        clean_test = test_rel_str[:-3] if test_rel_str.endswith(".py") else test_rel_str
        test_module = clean_test.replace("/", ".")

        reasons: List[str] = []
        anti_patterns: List[str] = []

        # 1. Adversarial AST Linting (implementation + test)
        ast_violations = cls.audit_ast([impl_path, test_path])
        if ast_violations:
            anti_patterns.extend(ast_violations)
            reasons.extend(ast_violations)

        # 2. Test AST Structure & Import Verification
        test_ast_violations = cls.audit_test_ast(test_path, impl_rel_str)
        if test_ast_violations:
            anti_patterns.extend(test_ast_violations)
            reasons.extend(test_ast_violations)

        # 3. Physical Execution of Unit Tests
        test_passed, test_output = cls.run_unit_tests(test_module)
        if not test_passed:
            reasons.append(f"Test suite failed:\n{test_output[-500:]}")
            anti_patterns.append("TEST_FAILURE")
        else:
            reasons.append("Physical execution suite passed cleanly.")

        # 4. In-Memory AST Mutation Discrimination Audit
        mutation_passed = False
        if test_passed and not test_ast_violations:
            mutation_passed, mutation_violations = cls.audit_ast_mutations(
                impl_path, impl_rel_str, test_module, touched_lines=touched_lines
            )
            if not mutation_passed:
                anti_patterns.extend(mutation_violations)
                reasons.extend(mutation_violations)
            else:
                reasons.append("In-memory AST mutation audit passed (all injected mutants killed).")

        if not anti_patterns and test_passed and mutation_passed:
            verdict = "ACCEPT"
            reasons.append("Zero AST shortcuts detected. Invariants verified under physical test and mutation execution.")
        else:
            verdict = "REJECT"

        return {
            "impl_file": str(impl_path),
            "test_file": str(test_path),
            "verdict": verdict,
            "reasons": reasons,
            "anti_patterns_found": anti_patterns,
            "mutation_kill_verified": mutation_passed,
        }

    @classmethod
    def audit_diff(cls, ref: str = "HEAD") -> Dict[str, Any]:
        """Discovers modified implementation files and audits each against its test suite."""
        diff_files = cls.discover_diff_files(ref)
        if not diff_files:
            return {
                "ref": ref,
                "verdict": "ACCEPT",
                "files_audited": 0,
                "results": [],
                "reasons": [f"No modified implementation files discovered against ref '{ref}'."],
                "anti_patterns_found": [],
            }

        results: List[Dict[str, Any]] = []
        all_passed = True
        all_anti_patterns: List[str] = []
        reasons: List[str] = []

        for impl_path, touched_lines in diff_files:
            file_res = cls.audit_implementation_file(impl_path, touched_lines=touched_lines)
            results.append(file_res)
            if file_res["verdict"] != "ACCEPT":
                all_passed = False
                all_anti_patterns.extend(file_res.get("anti_patterns_found", []))
                reasons.append(f"REJECT {impl_path.name}: {', '.join(file_res.get('anti_patterns_found', []))}")
            else:
                reasons.append(f"ACCEPT {impl_path.name}")

        return {
            "ref": ref,
            "verdict": "ACCEPT" if all_passed else "REJECT",
            "files_audited": len(diff_files),
            "results": results,
            "reasons": reasons,
            "anti_patterns_found": all_anti_patterns,
        }

    @classmethod
    def audit_channel(cls, channel_number: int, channel_name: str, impl_file: str, test_module: str) -> Dict[str, Any]:
        impl_path = REPO_ROOT / impl_file
        test_path = REPO_ROOT / f"{test_module.replace('.', '/')}.py"

        reasons: List[str] = []
        anti_patterns: List[str] = []

        if not impl_path.exists():
            return {
                "channel_number": channel_number,
                "channel_name": channel_name,
                "verdict": "REJECT",
                "reasons": [f"Implementation file does not exist: {impl_file}"],
                "anti_patterns": ["MISSING_IMPLEMENTATION"],
                "anti_patterns_found": ["MISSING_IMPLEMENTATION"],
                "mutation_kill_verified": False,
            }

        # 1. Adversarial AST Linting (implementation + test)
        ast_violations = cls.audit_ast([impl_path, test_path])
        if ast_violations:
            anti_patterns.extend(ast_violations)
            reasons.extend(ast_violations)

        # 2. Test AST Structure & Import Verification
        test_ast_violations = cls.audit_test_ast(test_path, impl_file)
        if test_ast_violations:
            anti_patterns.extend(test_ast_violations)
            reasons.extend(test_ast_violations)

        # 3. Physical Execution of Unit Tests
        test_passed, test_output = cls.run_unit_tests(test_module)
        if not test_passed:
            reasons.append(f"Test suite failed:\n{test_output[-500:]}")
            anti_patterns.append("TEST_FAILURE")
        else:
            reasons.append("Physical execution suite passed cleanly.")

        # 4. In-Memory AST Mutation Discrimination Audit (only if tests pass and test AST is valid)
        mutation_passed = False
        if test_passed and not test_ast_violations:
            mutation_passed, mutation_violations = cls.audit_ast_mutations(impl_path, impl_file, test_module)
            if not mutation_passed:
                anti_patterns.extend(mutation_violations)
                reasons.extend(mutation_violations)
            else:
                reasons.append("In-memory AST mutation audit passed (all injected mutants killed).")

        # Verdict evaluation
        if not anti_patterns and test_passed and mutation_passed:
            verdict = "ACCEPT"
            reasons.append("Zero AST shortcuts detected. Invariants verified under physical test and mutation execution.")
        else:
            verdict = "REJECT"

        return {
            "channel_number": channel_number,
            "channel_name": channel_name,
            "verdict": verdict,
            "reasons": reasons,
            "anti_patterns_found": anti_patterns,
            "mutation_kill_verified": mutation_passed,
        }


def main():
    parser = argparse.ArgumentParser(description="Mechanical Zero-Trust Auditor Gate")
    parser.add_argument(
        "--diff",
        nargs="?",
        const="HEAD",
        default=None,
        help="Audit modified files from git diff [ref, default: HEAD]",
    )
    parser.add_argument("--channel", type=int, required=False, help="Channel number")
    parser.add_argument("--name", type=str, required=False, help="Channel name")
    parser.add_argument("--impl", type=str, required=False, help="Path to implementation file")
    parser.add_argument("--test", type=str, required=False, help="Test module name (e.g. tests.test_ninshu_elf_parser)")
    args = parser.parse_args()

    if args.diff is not None:
        result = MechanicalAuditorGate.audit_diff(args.diff)

        print("\n" + "=" * 65)
        print(f" MECHANICAL AUDIT DIFF RESULT: ref={args.diff}")
        print("=" * 65)
        print(f" VERDICT:             {result['verdict']}")
        print(f" FILES AUDITED:       {result['files_audited']}")
        print(" REASONS:")
        for r in result["reasons"]:
            print(f"   [+] {r}")
        if result["anti_patterns_found"]:
            print(" ANTI-PATTERNS DETECTED:")
            for ap in result["anti_patterns_found"]:
                print(f"   [!] {ap}")
        print("=" * 65 + "\n")

        sys.exit(0 if result["verdict"] == "ACCEPT" else 1)
    else:
        if not (args.channel is not None and args.name and args.impl and args.test):
            parser.error("--channel, --name, --impl, and --test are required when --diff is not specified.")

        result = MechanicalAuditorGate.audit_channel(args.channel, args.name, args.impl, args.test)

        print("\n" + "=" * 65)
        print(f" MECHANICAL AUDIT RESULT: CH {args.channel:02d} ({args.name})")
        print("=" * 65)
        print(f" VERDICT:             {result['verdict']}")
        print(" REASONS:")
        for r in result["reasons"]:
            print(f"   [+] {r}")
        if result["anti_patterns_found"]:
            print(" ANTI-PATTERNS DETECTED:")
            for ap in result["anti_patterns_found"]:
                print(f"   [!] {ap}")
        print("=" * 65 + "\n")

        sys.exit(0 if result["verdict"] == "ACCEPT" else 1)


if __name__ == "__main__":
    main()
