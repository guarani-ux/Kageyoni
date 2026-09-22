from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
env={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'tests')}
legacy=[
 'test_characters','test_checkpoint_gate','test_coliseum','test_contributions','test_decisions','test_development','test_durable_campaign','test_engine',
 'test_expression','test_foundation','test_full_chain','test_integration_causal','test_learning','test_learning_integration','test_methods','test_personality',
 'test_release_integration','test_terminal','test_v2_adversarial','test_v3_adversarial','test_v4_v8_adversarial','test_v4_world','test_v5_workspaces','test_v6_composition',
 'test_v6_network','test_v7_integration','test_v7_pipeline','test_v8_operations','test_will_system','test_workflows','test_world_engine','test_writing',
]
def run(cmd, timeout=90):
    try: result=subprocess.run(cmd,cwd=ROOT,env=env,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        print('qualification timeout:', ' '.join(cmd), file=sys.stderr); raise SystemExit(124) from exc
    if result.returncode: raise SystemExit(result.returncode)
for index,name in enumerate(legacy,1):
    print(f'legacy qualification {index}/{len(legacy)}: {name}',flush=True)
    run([sys.executable,'-m','unittest','-q',name])
print('v10 qualification',flush=True)
run([sys.executable,'-m','unittest','discover','-s','tests/v10','-q'])
print('v10 full qualification: PASS')
