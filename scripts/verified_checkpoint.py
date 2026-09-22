"""Create a standalone backup and validate it in a fresh process before delivery."""
import argparse,json,subprocess,sys
from pathlib import Path
from kageyoni.engine import Engine

def checkpoint(source,destination):
    e=Engine(source)
    try:
        e.verify()
        expected=e.branch('main')['revision']
        e.backup(destination)
    finally:e.close()
    code='from kageyoni.engine import Engine; import json,sys; e=Engine(sys.argv[1]); print(json.dumps({"verification":e.verify(),"revision":e.branch("main")["revision"]})); e.close()'
    result=subprocess.run([sys.executable,'-c',code,str(destination)],capture_output=True,text=True,check=True)
    receipt=json.loads(result.stdout)
    if receipt['revision']!=expected or not receipt['verification']['ok']:raise RuntimeError('checkpoint verification failed')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('destination');a=p.parse_args();print(json.dumps(checkpoint(a.source,a.destination)))
