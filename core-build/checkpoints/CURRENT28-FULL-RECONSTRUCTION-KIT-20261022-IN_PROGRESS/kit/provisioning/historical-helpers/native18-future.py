"""Strict exact immutable provider reconstruction; never opens DB or extracts ZIP."""
from pathlib import Path,PurePosixPath
import argparse,base64,hashlib,json,zipfile,stat
p=argparse.ArgumentParser();p.add_argument('--recipe',type=Path,required=True);p.add_argument('--parts-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=json.loads(a.recipe.read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
count=0
with a.output.open('xb') as out:
 for x in r['parts']:
  t=(a.parts_dir/x['path']).read_bytes();assert len(t)==x['ASCII_bytes'] and sha(t)==x['ASCII_sha256'] and git(t)==x['git_sha1'];b=base64.b64decode(t,validate=True);assert count==x['offset'] and len(b)==x['bytes'] and sha(b)==x['sha256'] and git(b)==x['raw_git_sha1'];out.write(b);count+=len(b)
assert count==r['bytes'] and sha(a.output.read_bytes())==r['sha256']
with zipfile.ZipFile(a.output) as z:
 assert z.testzip() is None;names=z.namelist();assert len(names)==len(set(names))==r['zip_entries'];assert set(names)=={m['path'] for m in r['members']}
 for m in r['members']:
  i=z.getinfo(m['path']);b=z.read(i);kind=stat.S_IFMT(i.external_attr>>16);assert not PurePosixPath(i.filename).is_absolute() and '..' not in PurePosixPath(i.filename).parts
  assert len(b)==m['bytes'] and sha(b)==m['sha256'] and stat.S_IMODE(i.external_attr>>16)==m['mode'] and i.is_dir()==m['dir'] and kind==m['file_type'];assert (b.decode() if kind==stat.S_IFLNK else None)==m['symlink_target']
print(json.dumps({'ok':True,'bytes':count,'sha256':r['sha256'],'zip_entries':len(names),'full_ASCII_and_raw_Git_SHA_offsets_CRC_every_member_SHA_mode_type_symlinktarget':True,'DB_or_candidate_execution':False,'semantic_qualification':False}))
