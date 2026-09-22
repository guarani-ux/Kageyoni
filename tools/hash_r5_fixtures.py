"""
tools/hash_r5_fixtures.py
Computes SHA-256 hashes for all R5 fixtures and rubrics and writes FIXTURE_MANIFEST.json.
"""
import hashlib
import json
from pathlib import Path

def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root = Path(__file__).resolve().parent.parent / "experiments" / "r5"
    fixtures_dir = root / "fixtures"
    rubrics_dir = root / "rubrics"
    
    manifest = {
        "title": "Kageyoni v11 R5 Comparative Evaluation Immutable Fixture Manifest",
        "timestamp": "2026-09-22T14:16:00Z",
        "fixtures": {},
        "rubrics": {}
    }
    
    for f in sorted(fixtures_dir.glob("*.json")):
        manifest["fixtures"][f.name] = {
            "path": str(f.relative_to(root.parent.parent)),
            "sha256": file_hash(f)
        }
        
    for r in sorted(rubrics_dir.glob("*.json")):
        manifest["rubrics"][r.name] = {
            "path": str(r.relative_to(root.parent.parent)),
            "sha256": file_hash(r)
        }
        
    out_file = root / "FIXTURE_MANIFEST.json"
    out_file.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote fixture manifest to {out_file}")

if __name__ == "__main__":
    main()
