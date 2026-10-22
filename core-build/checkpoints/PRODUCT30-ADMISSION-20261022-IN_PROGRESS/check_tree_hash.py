from pathlib import Path
import json,hashlib,sys
B=Path('/dev/shm/github-product30-admission');kind=sys.argv[1];d=json.loads((B/(kind+'-tree-proof.json')).read_bytes());out={}
for repo,x in d.items():
 e=sorted(x['levels'][0]['tree'],key=lambda e:e['path'].encode()+(b'/' if e['type']=='tree' else b''))
 b=b''.join((('40000' if i['type']=='tree' else i['mode'])+' '+i['path']).encode()+b'\0'+bytes.fromhex(i['sha']) for i in e)
 h=hashlib.sha1(b'tree '+str(len(b)).encode()+b'\0'+b).hexdigest();assert h==x['commit']['tree']['sha'];out[repo]=h
if kind=='critical':
 p=(B/'SOURCE-PROVIDER.json').read_bytes();r=json.loads((B/'critical-commits-staged.json').read_bytes())['pointer_reply'];assert hashlib.sha1(b'blob '+str(len(p)).encode()+b'\0'+p).hexdigest()==r['structuredContent']['sha']
print(json.dumps({'independent_Git_tree_serialization':out,'ok':True}))

