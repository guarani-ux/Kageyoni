"""Package the verified development copy, including campaign and recovery saves.

Run from project root after closing SQLite writers. No network or deployment.
Existing source files and saves are read; only this release's manifest/archive
and checksum are replaced. Earlier release archives remain untouched.
"""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'build/Kageyoni-Personality-Engine-v7.zip'

def included(path):
    relative=path.relative_to(ROOT)
    if not path.is_file() or '__pycache__' in relative.parts or any(x.startswith('.') for x in relative.parts): return False
    if relative.as_posix()=='MANIFEST.json' or path.name.endswith(('-wal','-shm','.pyc')): return False
    if relative.parts[:2]==('build','development-attempts'): return False
    if path.suffix=='.zip' and relative.parts[:2]!=('build','recovery'): return False
    if path.name.startswith(('personality-journey.sqlite','personality-fixture.sqlite.pre-','PACKAGE-SHA256-personality')): return False
    return True

def build():
    for required in ('build/kageyoni.sqlite','build/personality-fixture.sqlite','build/recovery/pre-personality-v1.sqlite','build/recovery/legacy-personality-pending.sqlite','build/personality-test-results.txt'):
        if not (ROOT/required).is_file(): raise SystemExit('Required deliverable missing: '+required)
    files=sorted(p for p in ROOT.rglob('*') if included(p))
    manifest={'format':'kageyoni-personality-v7','sql_schema':'2','latest_migration':7,'runtime_schema':'4','workflow_api':'3','character_schema':'1','decision_interface':'1','personality_interface':'1','property_registry':'1','resolution_rules':'1','story_state':'1','installed_skill_sources':'preserved; personality workflow is documented in project','canonical_campaign':'build/kageyoni.sqlite','noncanonical_fixture':'build/personality-fixture.sqlite','handoff':'docs/PERSONALITY-HANDOFF.md','files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (ROOT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in files+[ROOT/'MANIFEST.json']:
            z.write(path,Path('kageyoni-local-dev')/path.relative_to(ROOT))
    checksum=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    (ROOT/'build/PACKAGE-SHA256-personality-v7.txt').write_text(checksum+'  '+ARCHIVE.name+'\n')
    return {'archive':str(ARCHIVE),'files':len(files)+1,'sha256':checksum,'bytes':ARCHIVE.stat().st_size}

if __name__=='__main__': print(json.dumps(build(),indent=2))
