"""Exact immutable ASCII byte reconstruction only; no DB/source execution."""
from pathlib import Path
import argparse,base64,hashlib,json,zipfile,io
p=argparse.ArgumentParser();p.add_argument('--recipe',type=Path,required=True);p.add_argument('--parts-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=json.loads(a.recipe.read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
out=bytearray()
for x in r['parts']:
 t=(a.parts_dir/x['path']).read_bytes();assert len(t)==x['ASCII_bytes'] and sha(t)==x['ASCII_sha256'] and git(t)==x['git_sha1']
 b=base64.b64decode(t,validate=True);assert len(out)==x['offset'] and len(b)==x['bytes'] and sha(b)==x['sha256'] and git(b)==x['raw_git_sha1'];out.extend(b)
b=bytes(out);assert len(b)==r['bytes'] and sha(b)==r['sha256']
with zipfile.ZipFile(io.BytesIO(b)) as z:
 assert z.testzip() is None;names=z.namelist();assert len(names)==len(set(names))==r['zip_entries']
 prefix='product27_checkpoint/' if r.get('source_files')==109 else ''
 expected=set()
 for m in r['members']:
  name=prefix+m['path'];raw=z.read(name);assert len(raw)==m['bytes'] and sha(raw)==m['sha256'];expected.add(name)
 if prefix:
  name=prefix+'MANIFEST.json';assert sha(z.read(name))==r['manifest_sha256'];expected.add(name)
 assert set(names)==expected
with a.output.open('xb') as f:f.write(b)
print(json.dumps({'ok':True,'bytes':len(b),'sha256':sha(b),'zip_entries':len(names),'source_files':r['source_files'],'all_ASCII_raw_SHA_Git_ID_offsets_CRC_member_SHA':True,'database_opened':False,'source_executed':False,'semantic_qualified':False,'full_release':False}))
