from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
env={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'tests')}
commands=[
 [sys.executable,'-m','unittest','discover','-s','tests/v10','-v'],
 [sys.executable,'-m','unittest','-q','test_engine'],
 [sys.executable,'-m','unittest','-q','test_release_integration'],
 [sys.executable,'-m','unittest','-q','test_v8_operations'],
 [sys.executable,'-m','unittest','-q','test_integration_causal'],
]
for cmd in commands:
    try: result=subprocess.run(cmd,cwd=ROOT,env=env,timeout=60)
    except subprocess.TimeoutExpired as exc:
        print('fast qualification timeout:', ' '.join(cmd), file=sys.stderr); raise SystemExit(124) from exc
    if result.returncode: raise SystemExit(result.returncode)
print('v10 fast qualification: PASS')
