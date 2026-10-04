"""
Unit tests for kageyoni.scout: Universal Static Carrier & AST Organ Scout.
"""

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.scout import CarrierScout, CarrierManifest, FunctionSignature


def test_ast_extraction(tmp_path):
    code_lines = [
        '"""Module docstring for sample carrier."""',
        "",
        'def standalone_task(alpha: int, beta: str = "default", *args, **kwargs) -> bool:',
        '    """Execute standalone calculation."""',
        "    return True",
        "",
        "class AutonomousOrgan:",
        '    """Class docstring."""',
        "",
        "    def execute(self, payload: dict):",
        '        """Execute organ action."""',
        "        pass",
    ]
    py_file = tmp_path / "sample_organ.py"
    py_file.write_text("\n".join(code_lines), encoding="utf-8")

    scout = CarrierScout()
    manifest = scout.scan_file(py_file, relative_to=tmp_path)

    assert manifest is not None
    assert manifest.module_docstring == "Module docstring for sample carrier."
    assert len(manifest.classes) == 1
    assert "AutonomousOrgan" in manifest.classes

    methods = manifest.classes["AutonomousOrgan"]
    assert len(methods) == 1
    assert methods[0].name == "execute"
    assert "payload" in methods[0].args
    assert methods[0].docstring == "Execute organ action."

    assert len(manifest.functions) == 1
    fn = manifest.functions[0]
    assert fn.name == "standalone_task"
    assert "alpha" in fn.args
    assert "beta" in fn.args
    assert "*args" in fn.args
    assert "**kwargs" in fn.args
    assert fn.docstring == "Execute standalone calculation."


def test_syntax_error_resilience(tmp_path):
    bad_code = "def broken_syntax(::: this is invalid python"
    bad_file = tmp_path / "corrupt.py"
    bad_file.write_text(bad_code, encoding="utf-8")

    scout = CarrierScout()
    manifest = scout.scan_file(bad_file)
    assert manifest is None


def test_keyword_bm25_scoring(tmp_path):
    f1 = tmp_path / "graph_invalidation.py"
    f1.write_text(
        'def cascade_invalidation(node_id: str):\n    """Perform forward invalidation cascade across causal graph."""\n    pass\n',
        encoding="utf-8",
    )

    f2 = tmp_path / "cryptographic_ledger.py"
    f2.write_text(
        'class EvidenceLedger:\n    """Append-only SHA-256 hash-chained cryptographic ledger."""\n    def record(self): pass\n',
        encoding="utf-8",
    )

    scout = CarrierScout()
    manifests = scout.scout_directory(tmp_path)
    assert len(manifests) == 2

    # Query 1: invalidation
    results_inv = scout.find_capability("invalidation cascade", manifests=manifests)
    assert len(results_inv) > 0
    assert "graph_invalidation.py" in results_inv[0][0].relative_path

    # Query 2: ledger
    results_led = scout.find_capability("cryptographic ledger hash", manifests=manifests)
    assert len(results_led) > 0
    assert "cryptographic_ledger.py" in results_led[0][0].relative_path


def test_directory_exclusion(tmp_path):
    # Valid dir
    src_dir = tmp_path / "kageyoni"
    src_dir.mkdir()
    (src_dir / "valid.py").write_text("def ok(): pass", encoding="utf-8")

    # Excluded dirs
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hidden.py").write_text("def secret(): pass", encoding="utf-8")

    pycache_dir = tmp_path / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "cache.py").write_text("def cached(): pass", encoding="utf-8")

    venv_dir = tmp_path / "temp_venv"
    venv_dir.mkdir()
    (venv_dir / "virtual.py").write_text("def venv(): pass", encoding="utf-8")

    scout = CarrierScout()
    manifests = scout.scout_directory(tmp_path)
    relative_paths = [m.relative_path for m in manifests]

    assert any("valid.py" in p for p in relative_paths)
    assert not any("hidden.py" in p for p in relative_paths)
    assert not any("cache.py" in p for p in relative_paths)
    assert not any("virtual.py" in p for p in relative_paths)
