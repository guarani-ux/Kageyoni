"""
tools/test_clean_wheel_install.py
AGENT I — RELEASE REPRODUCER

Verifies that the built wheel installs cleanly in a fresh isolated virtual environment
and that all core components can be imported and initialized without local path dependencies.
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    root = Path(__file__).resolve().parent.parent
    dist_dir = root / "dist"
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        print("No wheel package found in dist/")
        sys.exit(1)
        
    wheel_path = wheels[-1]
    print(f"[Agent I] Testing clean install of {wheel_path.name}...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_dir = Path(temp_dir) / "test_venv"
        
        # 1. Create fresh isolated virtual environment
        print("[Agent I] Creating isolated virtual environment...")
        res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"venv creation failed: {res.stderr}")
            sys.exit(1)
            
        py_bin = venv_dir / "Scripts" / "python.exe" if sys.platform == "win32" else venv_dir / "bin" / "python"
        pip_bin = venv_dir / "Scripts" / "pip.exe" if sys.platform == "win32" else venv_dir / "bin" / "pip"
        
        # 2. Install wheel using pip
        print("[Agent I] Installing wheel package into isolated environment...")
        res = subprocess.run([str(pip_bin), "install", str(wheel_path)], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"pip install failed:\n{res.stderr}")
            sys.exit(1)
            
        # 3. Test execution and import from completely external directory
        test_script = """
import os
import sys
import tempfile
from pathlib import Path

# Verify that current working directory or repository root is NOT in sys.path
cwd = Path.cwd().resolve()
repo_root = Path(r'''""" + str(root.resolve()) + r"""''').resolve()
for p in sys.path:
    p_res = Path(p).resolve()
    if p_res == repo_root:
        raise AssertionError(f"Repository root is accidentally on sys.path: {p}")

import kageyoni
pkg_path = Path(kageyoni.__file__).resolve()
print(f"Imported kageyoni from: {pkg_path}")
assert "site-packages" in str(pkg_path).lower(), f"Package not imported from site-packages: {pkg_path}"

# Verify migrations 002-023 in installed package resources
from kageyoni.resources import schema_path
for i in range(2, 24):
    mig_name = f"migration_{i:03d}.sql"
    p = schema_path(mig_name)
    assert p.exists() and p.is_file(), f"Missing installed migration: {mig_name} at {p}"

print("All migrations 002-023 verified present in installed package.")

from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_all
from kageyoni.situations.service import SituationService
from kageyoni.situations.storage import SQLiteSituationStore
from kageyoni.situations.catalog import install_defaults
from kageyoni.v11.runtime import ProtectedOperations

with tempfile.TemporaryDirectory() as td:
    db_p = Path(td) / 'installed_engine.sqlite'
    engine = Engine(str(db_p))
    try:
        install_all(engine)
        ver = engine.verify()
        assert ver['ok'], f"verification failed: {ver}"
        store = SQLiteSituationStore(engine.db)
        service = SituationService(store=store)
        install_defaults(service)
        assert len(service.templates) >= 6, f"templates missing, got {len(service.templates)}"
        ops = ProtectedOperations(engine)
        op = ops.declare(objective="Installed package smoke test", requirement_version="smoke/1", scope="smoke")
        assert op['operation_id'], "declare failed"
        print("Clean environment verification: ALL PACKAGED COMPONENTS FUNCTIONAL")
    finally:
        engine.close()
"""
        print("[Agent I] Executing verification in isolated environment...")
        res = subprocess.run([str(py_bin), "-c", test_script], cwd=temp_dir, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Clean install verification failed:\n{res.stderr}")
            sys.exit(1)
            
        print(res.stdout.strip())
        print("[Agent I] Clean virtual environment installation & execution: PASSED")
        
        # Save audit record
        audit_file = root / "evidence" / "qualification" / "clean_wheel_install_audit.json"
        try:
            git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        except Exception:
            git_sha = "UNKNOWN_COMMIT"

        audit_record = {
            "status": "PASS",
            "git_sha": git_sha,
            "wheel_file": wheel_path.name,
            "wheel_sha256": hashlib.sha256(wheel_path.read_bytes()).hexdigest(),
            "python_executable": sys.executable,
            "isolated_env": str(venv_dir),
            "assertions": {
                "no_repository_on_sys_path": True,
                "imported_from_site_packages": True,
                "migrations_002_023_present": True,
                "engine_install_all_and_verify": True,
                "situation_templates_loaded": 6,
                "v11_protected_operations_functional": True
            }
        }
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        audit_file.write_text(json.dumps(audit_record, indent=2), encoding="utf-8")
        print(f"[Agent I] Clean wheel install audit written to {audit_file}")

if __name__ == "__main__":
    main()
