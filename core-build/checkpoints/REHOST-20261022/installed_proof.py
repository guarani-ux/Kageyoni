"""Fresh current26 source/wheel/install correspondence; no world operation."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import sys
import zipfile

ROOT=Path('/workspace/scratch/5c7ed9200168/recovery-20261022/current26')
SOURCE=ROOT/'extracted/samsara_core'
SITE=Path(sys.prefix)/'lib/python3.12/site-packages'
EXPECTED_RUNTIME='26a07d047655cfc3fec7c431e13e64239d2e7707c3b73940fbd49f9c87eb02ef'
WHEELS={
 'product':('samsara_world-0.5.3.dev26-py3-none-any.whl','dcc81ae95ddd0eaee4e5ccd47a6e056be45fe5cc49342742e9898634c20ef06a'),
 'engine':('kageyoni_engine-11.1.0.dev15-py3-none-any.whl','ed30ab970dfe198fe948b2a3b776b9dae864654dd5cd2b84d0f8ef453bfc843e')}

def proof():
    assert Path(sys.prefix)==ROOT/'env',sys.prefix
    rows=[]
    for kind,(name,digest) in WHEELS.items():
        wheel=SOURCE/'distributions'/name
        assert hashlib.sha256(wheel.read_bytes()).hexdigest()==digest
        with zipfile.ZipFile(wheel) as archive:
            assert archive.testzip() is None
            for member in archive.namelist():
                if member.endswith('/') or not member.startswith(('samsara/','kageyoni/','contracts/')):continue
                original=SOURCE/kind/member
                if not original.exists() and member.startswith('kageyoni/data/'):
                    original=SOURCE/kind/Path(member).name
                data=archive.read(member)
                assert original.read_bytes()==data==(SITE/member).read_bytes(),member
                rows.append({'path':member,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    assert len(rows)==233,len(rows)
    from samsara.protocol import runtime_fingerprint
    runtime=runtime_fingerprint()
    assert runtime==EXPECTED_RUNTIME,runtime
    origins=[]
    for name,module in sorted(sys.modules.items()):
        if name.split('.')[0] not in ('samsara','kageyoni','contracts'):continue
        paths=[module.__file__] if getattr(module,'__file__',None) else list(getattr(module,'__path__',[]))
        for path in paths:
            assert Path(path).resolve().is_relative_to(SITE),(name,path)
            origins.append({'module':name,'path':path})
    return {'runtime':runtime,'versions':{name:importlib.metadata.version(name) for name in ('samsara-world','kageyoni-engine')},
            'wheel_sha256':{kind:item[1] for kind,item in WHEELS.items()},'payloads':rows,'origins':origins,
            'scope':'Fresh installed correspondence only; no database, process-control, semantic or human qualification.'}

if __name__=='__main__':
    import samsara.mediawork,samsara.runner,samsara.sourcework,kageyoni.workspaces.worker_liveness
    result=proof()
    (ROOT/'installed-before.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'runtime':result['runtime'],'versions':result['versions'],'payloads':len(result['payloads']),'origins':len(result['origins'])}))
