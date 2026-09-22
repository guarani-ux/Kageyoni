from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
env={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'tests')}
legacy=[
 'test_characters','test_checkpoint_gate','test_coliseum','test_contributions','test_decisions','test_development','test_durable_campaign','test_engine',
 'test_expression','test_foundation','test_full_chain','test_integration_causal','test_learning','test_learning_integration','test_methods','test_personality',
 'test_release_integration','test_terminal','test_v2_adversarial','test_v3_adversarial','test_v4_v8_adversarial','test_v4_world','test_v5_workspaces','test_v6_composition',
 'test_v6_network','test_v7_integration','test_v7_pipeline','test_v8_operations','test_will_system','test_workflows','test_world_engine','test_writing',
]
results=[]
def run(label,cmd):
    try:
        p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
        text=(p.stdout or '')+'\n'+(p.stderr or '')
        m=re.search(r'Ran (\d+) tests?',text)
        result={'label':label,'status':'pass' if p.returncode==0 else 'fail','returncode':p.returncode,'tests':int(m.group(1)) if m else None,'tail':'\n'.join(text.strip().splitlines()[-8:])}
    except subprocess.TimeoutExpired as exc:
        result={'label':label,'status':'timeout','returncode':124,'tests':None,'tail':str(exc)}
    results.append(result)
for name in legacy: run(name,[sys.executable,'-m','unittest','-q',name])
run('v10',[sys.executable,'-m','unittest','discover','-s','tests/v10','-q'])
ok=all(x['status']=='pass' for x in results)
report={'ok':ok,'legacy_modules':len(legacy),'legacy_tests':sum(x['tests'] or 0 for x in results if x['label']!='v10'),'v10_tests':next((x['tests'] for x in results if x['label']=='v10'),0),'total_tests':sum(x['tests'] or 0 for x in results),'results':results}
out=ROOT/'evidence/v10/isolated-qualification.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
raise SystemExit(0 if ok else 1)
