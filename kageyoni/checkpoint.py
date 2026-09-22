"""Publish backups only after independent close/reopen verification."""
import json,os,sqlite3,subprocess,sys,tempfile
from pathlib import Path

def checked_backup(engine,destination):
    destination=Path(destination)
    expected={r['id']:r['revision'] for r in engine.db.execute('SELECT id,revision FROM branches')}
    fd,name=tempfile.mkstemp(prefix='.kageyoni-check-',suffix='.sqlite',dir=destination.parent);os.close(fd);stage=Path(name)
    try:
        out=sqlite3.connect(stage)
        try:engine.db.backup(out)
        finally:out.close()
        code='''import json,sys
sys.path.insert(0,sys.argv[2])
from kageyoni.engine import Engine
for _ in range(2):
 e=Engine(sys.argv[1], read_only=True)
 try:
  e.verify()
  revisions={r['id']:r['revision'] for r in e.db.execute('SELECT id,revision FROM branches')}
 finally:e.close()
print(json.dumps(revisions))
'''
        try:
            result=subprocess.run([sys.executable,'-c',code,str(stage.resolve()),str(Path(__file__).resolve().parent.parent)],capture_output=True,text=True,check=True)
        except subprocess.CalledProcessError as exc:
            exc.add_note(exc.stderr)
            raise
        if json.loads(result.stdout)!=expected:raise RuntimeError('checkpoint revision mismatch')
        try:
            with stage.open('r+b') as f:
                os.fsync(f.fileno())
        except OSError:
            pass
        # Exclusive publication: a racing writer cannot overwrite an existing save.
        try:
            os.link(stage,destination)
        except OSError:
            if destination.exists():
                raise FileExistsError(f"destination exists: {destination}")
            import shutil
            shutil.copy2(stage,destination)
        if sys.platform != 'win32':
            try:
                dfd=os.open(destination.parent,os.O_RDONLY)
                try:os.fsync(dfd)
                finally:os.close(dfd)
            except OSError:
                pass
        return str(destination)
    finally:
        for suffix in ('','-wal','-shm','-journal'):
            Path(str(stage)+suffix).unlink(missing_ok=True)
