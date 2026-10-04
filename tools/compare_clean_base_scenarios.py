"""Paired synthetic behavior comparison against a separately pinned source tree."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

SCENARIOS = {
'narrative': '''
from examples.v4_demo import setup
from kageyoni.engine import Engine
with tempfile.TemporaryDirectory() as folder:
 e=Engine(Path(folder)/'world.sqlite');f=setup(e);w=f['app'].encounters
 w.start('main','passage',1,'journey','start',e.branch('main')['revision'],f['participants'])
 for action in ('bridge','offer','shield','accept','depart'):w.act('main','journey',action,action,e.branch('main')['revision'])
 view=w.inspect('main','journey')
 result=dict(phase=view['phase'],outcome=view['outcome'],guard=e.get('main','guard')['data']['condition'],loops=view['loops'],continuations=view['continuations'])
 e.close()
''',
'research_retraction': '''
from kageyoni.research_compiler.claims import ClaimGraph,ClaimNode,EpistemicStatus
s=ClaimGraph()
for key,parents in [('root',[]),('child',['root']),('grandchild',['child']),('unrelated',[])]:s.add_claim(ClaimNode(key,key,EpistemicStatus.INFERENCE,parent_claim_ids=parents))
s.invalidate_claim('root','retracted')
result={k:v.is_invalidated for k,v in s.claims.items()}
''',
'production_approval': '''
from kageyoni.vantage.graph import EpistemicDependencyGraph
s=EpistemicDependencyGraph();s.add_node('root','source','Source');s.add_node('output','artifact','Output',dependencies=['root'])
assert s.grant_approval('output','reviewer','fixture')
s.invalidate('root','retracted')
result=dict(status=s.get_node('output').status.value,approved=s.get_node('output').approval_status)
''',
'participant_continuity': '''
from kageyoni.engine import Engine
from kageyoni.application import Application
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'participant.sqlite';e=Engine(path);app=Application(e,migrate_all=True)
 p=app.participant('speaker',label='Speaker');app.participant('listener',label='Listener')
 identity=p.node_id;p.send_dialogue(text='Declared fixture report',listeners=['listener'],act='report')
 e.close();e=Engine(path);p=Application(e).participant('speaker')
 result=dict(same_identity=p.node_id==identity,dialogue=e.db.execute("SELECT COUNT(*) FROM dialogue_turn WHERE speaker='speaker'").fetchone()[0])
 e.close()
''',
'situation_continuation': '''
from kageyoni.engine import Engine
from kageyoni.application import Application
from kageyoni.situations.integration import KageyoniSituationAdapter
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.runtime import SituationRuntime,WorkflowRun
with tempfile.TemporaryDirectory() as folder:
 path=Path(folder)/'situations.sqlite';e=Engine(path);Application(e,migrate_all=True)
 s=install_defaults(KageyoniSituationAdapter(e).service());s.genesis('campaign','launch',{'objective':'launch','audience':'members'},situation_id='s')
 s.bind_workflow('s','campaign.default');r=SituationRuntime(s,test_mode=True);r.start(WorkflowRun('r','s','campaign.default',objective='launch'));r.wait('r','approval');e.close()
 e=Engine(path);s=install_defaults(KageyoniSituationAdapter(e).service());r=SituationRuntime(s,test_mode=True)
 waiting=r._run('r').status;r.resume('r',condition_satisfied=True)
 result=dict(objective=s.snapshot('s')['objective'],waiting=waiting,resumed=r._run('r').status);e.close()
''',
'ledger_outer_rollback': '''
import sqlite3
from kageyoni.ledger import EvidenceLedger
from kageyoni.persistence.unit_of_work import UnitOfWork
c=sqlite3.connect(':memory:');ledger=EvidenceLedger(c)
try:
 with UnitOfWork(c):
  ledger.record(kind='fixture',actor_id='fixture',topic='rollback',payload={})
  raise RuntimeError('interruption')
except Exception:pass
result=dict(remaining_records=len(ledger.query()));c.close()
''',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path)
    args=parser.parse_args();results={}
    for name,script in SCENARIOS.items():
        cells={}
        for label,root in [('baseline',args.baseline),('candidate',args.candidate)]:
            code='import json,tempfile\nfrom pathlib import Path\n'+script+'\nprint(json.dumps(result,sort_keys=True))'
            run=subprocess.run([sys.executable,'-c',code],cwd=root,capture_output=True,text=True)
            if run.returncode:raise RuntimeError(name+' '+label+': '+run.stderr)
            cells[label]=json.loads(run.stdout)
        cells['same_behavior']=cells['baseline']==cells['candidate'];results[name]=cells
    print(json.dumps({'scope':'synthetic mechanics and continuity, not model cognition or emergence','scenarios':results},indent=2))

if __name__=='__main__':main()
