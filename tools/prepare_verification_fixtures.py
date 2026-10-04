"""Restore byte-verified archived inputs for tests; never replace a live save."""
from pathlib import Path
import gzip
import hashlib
import json


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'evidence/clean_base/verification-recovered-fixtures.json').read_text())
    for record in manifest['files']:
        target = root / record['path']
        packed = (root / record['compressed_path']).read_bytes()
        if hashlib.sha256(packed).hexdigest() != record['compressed_sha256']:
            raise RuntimeError('Compressed fixture digest mismatch: ' + record['path'])
        original = gzip.decompress(packed)
        if hashlib.sha256(original).hexdigest() != record['sha256']:
            raise RuntimeError('Archived fixture digest mismatch: ' + record['path'])
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
                raise RuntimeError('Refusing to replace a different fixture: ' + record['path'])
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(original)
    print('Prepared byte-verified archived test fixtures; no canonical save changed.')


if __name__ == '__main__':
    main()
