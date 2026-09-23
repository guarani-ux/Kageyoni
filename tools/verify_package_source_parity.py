"""
tools/verify_package_source_parity.py
AGENT I — RELEASE REPRODUCER

Verifies package/source parity for Kageyoni v11:
1. Builds wheel package from current repository source.
2. Unpacks wheel into an isolated temporary workspace.
3. Performs file-by-file inventory and checksum comparison against source tree:
   - All migrations (002 through 023)
   - All schemas
   - All v11 modules
   - All situation modules
   - Core engine modules
4. Emits authoritative evidence dossier to evidence/qualification/package_parity_audit.json.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root = Path(__file__).resolve().parent.parent
    dist_dir = root / "dist"
    
    print("[Agent I] Building wheel package...")
    cmd = [sys.executable, "setup.py", "bdist_wheel"]
    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Build failed:\n{res.stderr}")
        sys.exit(1)
        
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        print("No wheel found in dist/")
        sys.exit(1)
        
    wheel_path = sorted(wheels, key=lambda p: p.stat().st_mtime)[-1]
    wheel_hash = file_hash(wheel_path)
    print(f"[Agent I] Inspecting wheel: {wheel_path.name} (SHA256: {wheel_hash})")
    
    temp_dir = tempfile.TemporaryDirectory()
    unpack_dir = Path(temp_dir.name)
    
    with zipfile.ZipFile(wheel_path, 'r') as zf:
        zf.extractall(unpack_dir)
        wheel_files = set(zf.namelist())

    # Required files that must exist in wheel
    required_components = {
        "migrations": [f"kageyoni/data/migration_{i:03d}.sql" for i in range(2, 24)],
        "v11_modules": [
            "kageyoni/v11/__init__.py",
            "kageyoni/v11/adaptive.py",
            "kageyoni/v11/context.py",
            "kageyoni/v11/enforcement.py",
            "kageyoni/v11/frontier.py",
            "kageyoni/v11/integration.py",
            "kageyoni/v11/runtime.py"
        ],
        "situation_modules": [
            "kageyoni/situations/__init__.py",
            "kageyoni/situations/catalog.py",
            "kageyoni/situations/comparative.py",
            "kageyoni/situations/integration.py",
            "kageyoni/situations/long_horizon.py",
            "kageyoni/situations/memory.py",
            "kageyoni/situations/models.py",
            "kageyoni/situations/qualification.py",
            "kageyoni/situations/runtime.py",
            "kageyoni/situations/scar.py",
            "kageyoni/situations/service.py",
            "kageyoni/situations/storage.py",
            "kageyoni/situations/studio.py",
            "kageyoni/situations/v11_adapter.py"
        ],
        "core_modules": [
            "kageyoni/__init__.py",
            "kageyoni/engine.py",
            "kageyoni/operations.py",
            "kageyoni/console.py",
            "kageyoni/data/schema.sql"
        ]
    }

    missing_files = []
    parity_records = []
    
    for category, req_list in required_components.items():
        for req in req_list:
            # Normalized zip path
            norm_path = req.replace("\\", "/")
            if norm_path not in wheel_files:
                missing_files.append({"file": req, "category": category})
            else:
                unpacked_file = unpack_dir / req
                source_file = root / req
                if not source_file.exists():
                    # check top-level for migrations / schema
                    alt_source = root / Path(req).name
                    if alt_source.exists():
                        source_file = alt_source
                
                u_hash = file_hash(unpacked_file) if unpacked_file.exists() else None
                s_hash = file_hash(source_file) if source_file.exists() else None
                
                parity_records.append({
                    "path": req,
                    "category": category,
                    "in_wheel": True,
                    "wheel_sha256": u_hash,
                    "source_sha256": s_hash,
                    "hash_parity": (u_hash == s_hash) if (u_hash and s_hash) else False
                })

    passed = (len(missing_files) == 0) and all(r["hash_parity"] for r in parity_records)
    
    try:
        git_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        git_sha = "UNKNOWN_COMMIT"

    audit_report = {
        "title": "Kageyoni v11 Package / Source Parity Audit",
        "agent": "Agent I (Release Reproducer)",
        "git_sha": git_sha,
        "timestamp": "2026-09-22T14:41:00Z",
        "wheel_file": wheel_path.name,
        "wheel_sha256": wheel_hash,
        "total_files_in_wheel": len(wheel_files),
        "total_audited_targets": len(parity_records),
        "missing_files_count": len(missing_files),
        "missing_files": missing_files,
        "hash_mismatch_count": sum(1 for r in parity_records if not r["hash_parity"]),
        "parity_audit_passed": passed,
        "provenance": {
            "source_root": str(root),
            "python_executable": sys.executable,
            "platform": sys.platform
        },
        "records": parity_records
    }
    
    out_path = root / "evidence" / "qualification" / "package_parity_audit.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(audit_report, indent=2))
    
    temp_dir.cleanup()
    print(f"[Agent I] Package/Source Parity Audit Complete. Status: {'PASS' if passed else 'FAIL'}")
    print(f"[Agent I] Report saved to {out_path}")

if __name__ == "__main__":
    main()
