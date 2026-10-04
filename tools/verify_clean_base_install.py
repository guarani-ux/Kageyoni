"""Verify selected clean-base paths from an installed wheel outside the checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PROBE = r'''
import json,sys,tempfile,shutil
from pathlib import Path
import kageyoni
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.resources import schema_path
from kageyoni.emergence.causal_encounter import CausalEncounterHarness
from kageyoni.situations.catalog import install_defaults
assert 'site-packages' in str(Path(kageyoni.__file__).resolve())
for version in range(2,26): assert schema_path(f'migration_{version:03d}.sql').is_file()
with tempfile.TemporaryDirectory() as folder:
    historical_checked = False
    if len(sys.argv) > 1:
        historical=Path(folder)/'historical.sqlite'
        shutil.copy2(sys.argv[1], historical)
        previous=Engine(historical)
        names=[r[0] for r in previous.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if r[0] not in ('engine_versions','migration_checks')]
        columns={name:[r[1] for r in previous.db.execute('PRAGMA table_info("'+name+'")')] for name in names}
        def retained_rows():
            return {name:sorted([tuple(row) for row in previous.db.execute('SELECT '+','.join('"'+column+'"' for column in columns[name])+' FROM "'+name+'"')],key=repr) for name in names}
        before=retained_rows()
        assert previous.verify()['ok']
        Application(previous,migrate_all=True).encounter_actions
        assert retained_rows()==before
        assert previous.verify()['ok']
        previous.close()
        historical_checked = True
    path=Path(folder)/'installed.sqlite'
    e=Engine(path);app=Application(e,migrate_all=True)
    service=install_defaults(app.situations)
    service.genesis('research','installed continuation',{'question':'stored?'},situation_id='installed')
    harness=CausalEncounterHarness(e);harness.define_clash_encounter()
    harness.start_encounter('constellation-clash',1,'installed')
    d=app.encounter_actions;r=d.prepare('main','installed','voss','wheel-turn')
    reply=dict(encounter_id='installed',request_hash=r['request_hash'],action=dict(kind='propose_action',action_id='voss_rupture'))
    assert d.dispatch('main','installed',r,reply).validation_status=='ACCEPTED'
    assert e.verify()['ok'];e.close()
    e=Engine(path);app=Application(e)
    assert app.situations.snapshot('installed')['objective']=='installed continuation'
    assert app.encounter_actions.dispatch('main','installed',r,reply).validation_status=='REPLAY_IDEMPOTENT'
    assert e.verify()['ok'];e.close()
print(json.dumps({'status':'pass','scope':'installed migrations 002-025, issued dispatch/retry, durable situation, engine verification','historical_existing_rows_preserved':historical_checked,'package':kageyoni.__file__}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    parser.add_argument('--historical-db',type=Path,help='Authentic database to copy and upgrade inside the isolated installation')
    args=parser.parse_args()
    wheel=args.wheel.resolve()
    with tempfile.TemporaryDirectory() as folder:
        environment=Path(folder)/'environment'
        subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
        python=environment/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        subprocess.run([str(python),'-m','pip','install','--no-deps','--no-index',str(wheel)],check=True,cwd=folder,capture_output=True)
        historical_args=[str(args.historical_db.resolve())] if args.historical_db else []
        result=subprocess.run([str(python),'-c',PROBE,*historical_args],check=True,cwd=folder,capture_output=True,text=True)
        print(result.stdout.strip())

if __name__=='__main__':main()
