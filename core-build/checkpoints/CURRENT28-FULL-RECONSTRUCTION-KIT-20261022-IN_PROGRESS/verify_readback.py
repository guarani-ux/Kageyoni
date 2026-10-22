"""Byte-only transport padding adapter; complete SHA256/Git-ID binds exact original bytes."""
from pathlib import Path
import json,hashlib,sys
B=Path('/dev/shm/github-current28-reconstruction-kit')
kind=sys.argv[1];rows=json.loads((B/(kind+'-readback-plan.json')).read_bytes());obs=[]
for x in rows:
 raw=Path(x['capture']).read_bytes();b=raw[:x['bytes']];tail=raw[x['bytes']:]
 assert tail in (b'',b'\n'),(x['repo'],x['path'],'tail')
 assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'],(x['repo'],x['path'],'sha256')
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==x['git_sha1'],(x['repo'],x['path'],'git')
 p=B/'remote-readback'/x['repo']/x['path'];p.parent.mkdir(parents=True,exist_ok=True)
 if p.exists():assert p.read_bytes()==b
 else:p.write_bytes(b)
 obs.append(dict(repo=x['repo'],path=x['path'],bytes=len(b),sha256=x['sha256'],git_sha1=x['git_sha1'],transport_padding_bytes=len(tail)))
out=B/(kind+'-full-readback.json');assert not out.exists();out.write_text(json.dumps(obs,indent=2)+'\n')
print(json.dumps({'all_full_bytes_verified':True,'payloads':len(obs),'by_repo':{r:sum(x['repo']==r for x in obs) for r in {x['repo'] for x in obs}}}))

