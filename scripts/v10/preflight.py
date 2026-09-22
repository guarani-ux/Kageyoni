from __future__ import annotations
import argparse, json, py_compile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from kageyoni.composition.gates import list_gates
from kageyoni.engine import Engine


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);args=ap.parse_args()
    checks=[]
    def record(name,fn):
        try: detail=fn();checks.append({'name':name,'status':'pass','detail':detail})
        except Exception as exc: checks.append({'name':name,'status':'fail','detail':f'{type(exc).__name__}: {exc}'})
    record('python_version',lambda: sys.version if sys.version_info >= (3,10) else (_ for _ in ()).throw(RuntimeError('Python 3.10+ required')))
    record('manifest',lambda: json.loads((ROOT/'kageyoni.manifest.json').read_text())['engine_version'])
    def frames():
        names=[]
        for p in sorted((ROOT/'kageyoni/composition/data').glob('*.json')):
            f=json.loads(p.read_text())
            if not isinstance(f,dict) or not f.get('frame_id'):
                continue
            ids=[slot['slot_id'] for slot in f['slots']]
            if len(ids)!=len(set(ids)): raise ValueError(f'duplicate slot in {p.name}')
            unknown=set(f.get('verification',[]))-set(list_gates())
            if unknown: raise ValueError(f'unknown gates in {p.name}: {sorted(unknown)}')
            names.append(f['frame_id'])
        return names
    record('frame_contracts',frames)
    def aspect_types():
        data=json.loads((ROOT/'kageyoni/composition/data/aspect_types.json').read_text())
        if not isinstance(data,list) or not data: raise ValueError('aspect type registry missing')
        ids=[x.get('type_id') for x in data]
        if any(not x for x in ids) or len(ids)!=len(set(ids)): raise ValueError('invalid or duplicate aspect type')
        return {'count':len(ids),'families':sorted({x['family'] for x in data})}
    record('aspect_type_contracts',aspect_types)
    record('composition_compile',lambda: [py_compile.compile(str(p),doraise=True) for p in (ROOT/'kageyoni/composition').glob('*.py')])
    def database():
        e=Engine(args.db)
        try:
            result=e.verify(); versions=dict(e.db.execute('SELECT component,version FROM engine_versions'))
            return {'verify':result,'versions':versions,'revision':e.branch('main')['revision'] if e.db.execute("SELECT 1 FROM branches WHERE id='main'").fetchone() else None}
        finally:e.close()
    record('database',database)
    passed=all(c['status']=='pass' for c in checks)
    print(json.dumps({'ok':passed,'checks':checks},indent=2,default=str))
    raise SystemExit(0 if passed else 1)
if __name__=='__main__':main()
