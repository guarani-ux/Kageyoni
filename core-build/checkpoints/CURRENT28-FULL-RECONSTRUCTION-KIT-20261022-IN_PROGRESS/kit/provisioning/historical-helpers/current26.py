#!/usr/bin/env python3
"""Reconstruct/verify exact compact current26 source/offline bytes from immutable custody.
Inputs are verified Git-exported baseZIP and ASCIIpart files. No network/credentials,
database opening, campaign changes, code execution or semantic qualification.
"""
from pathlib import Path
import argparse,json,hashlib,zipfile,stat,io,base64
p=argparse.ArgumentParser();p.add_argument('--recipe',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--parts-dir',type=Path,required=True);p.add_argument('--verify-file',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=json.loads(a.recipe.read_text());assert bool(a.verify_file)!=bool(a.output)
assert a.base.stat().st_size==r['base']['bytes'] and hashlib.sha256(a.base.read_bytes()).hexdigest()==r['base']['sha256'];raw={}
for key,v in r['providers'].items():
 b=bytearray()
 for part in v['parts']:
  t=(a.parts_dir/part['path']).read_bytes().rstrip(b'\n');assert len(t)==part['ASCII_bytes'] and hashlib.sha256(t).hexdigest()==part['ASCII_sha256'];assert hashlib.sha1(b'blob '+str(len(t)).encode()+b'\0'+t).hexdigest()==part['git_sha1'];x=base64.b64decode(t);assert len(x)==part['bytes'] and hashlib.sha256(x).hexdigest()==part['sha256'];assert hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest()==part['raw_git_sha1'];b.extend(x)
 assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'];raw[key]=bytes(b)
opened={'base':zipfile.ZipFile(a.base),'delta':zipfile.ZipFile(io.BytesIO(raw['delta']))};buffer=io.BytesIO()
try:
 with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_STORED) as z:
  for x in r['files']:
   b=opened[x['provider']].read(x['archive_member']) if x['provider'] in opened else raw[x['provider']];assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'],x['path'];n=zipfile.ZipInfo(x['archive_member'],date_time=(1980,1,1,0,0,0));n.create_system=3;n.compress_type=zipfile.ZIP_STORED;n.external_attr=(stat.S_IFREG|x['unix_mode'])<<16;z.writestr(n,b)
finally:
 for z in opened.values():z.close()
b=buffer.getvalue();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
with zipfile.ZipFile(io.BytesIO(b)) as z:
 assert z.testzip() is None;names=z.namelist();assert len(names)==len(set(names))==r['physical_files'];m=json.loads(z.read('samsara_core/MANIFEST.json'));assert len(m['files'])==r['declared_manifest_files'] and set(names)=={'samsara_core/'+x['path'] for x in m['files']}|{'samsara_core/MANIFEST.json'};assert hashlib.sha256(z.read('samsara_core/MANIFEST.json')).hexdigest()==r['root_manifest_sha256']
if a.verify_file:assert a.verify_file.read_bytes()==b
else:
 with a.output.open('xb') as f:f.write(b)
print(json.dumps({'ok':True,'bytes':len(b),'sha256':r['sha256'],'physical_files':r['physical_files'],'manifest_files':r['declared_manifest_files'],'all_provider_parts_raw_ASCII_GitID_SHA':True,'complete_reconstruction_CRC_every_member_SHA':True,'existing_download_byte_equal':bool(a.verify_file),'database_opened':False,'full_release':False}))
