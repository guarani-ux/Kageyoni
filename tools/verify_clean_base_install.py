"""Verify selected clean-base paths from an installed wheel outside the checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

PROBE = r'''
import json,sys,tempfile
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
print(json.dumps({'status':'pass','scope':'installed migrations 002-025, issued dispatch/retry, durable situation, engine verification','package':kageyoni.__file__}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel',type=Path)
    args=parser.parse_args()
    wheel=args.wheel.resolve()
    with tempfile.TemporaryDirectory() as folder:
        environment=Path(folder)/'environment'
        subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
        python=environment/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        subprocess.run([str(python),'-m','pip','install','--no-deps','--no-index',str(wheel)],check=True,cwd=folder,capture_output=True)
        result=subprocess.run([str(python),'-c',PROBE],check=True,cwd=folder,capture_output=True,text=True)
        print(result.stdout.strip())

if __name__=='__main__':main()
