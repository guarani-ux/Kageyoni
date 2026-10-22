"""Frozen-packet byte packaging only; no candidate or native imports/DB opens."""
from pathlib import Path
import os,stat,hashlib,json,zipfile,base64,shutil
S=Path('/dev/shm/product32-checkpoint');B=Path('/dev/shm/github-product32-attachment-award')
def sha(b):return hashlib.sha256(b).hexdigest()
def git(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def save(n,v):
 p=B/n;assert not p.exists(),str(p);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def meta(p):
 s=p.lstat();v={'source':str(p),'mode':stat.S_IMODE(s.st_mode),'inode':s.st_ino,'device':s.st_dev,'mtime_ns':s.st_mtime_ns}
 if stat.S_ISDIR(s.st_mode):return dict(v,kind='dir',file_type=stat.S_IFDIR)
 if stat.S_ISLNK(s.st_mode):
  t=os.readlink(p);b=os.fsencode(t);return dict(v,kind='symlink',file_type=stat.S_IFLNK,symlink_target=t,bytes=len(b),sha256=sha(b))
 assert stat.S_ISREG(s.st_mode),str(p)
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return dict(v,kind='file',file_type=stat.S_IFREG,bytes=s.st_size,sha256=h.hexdigest())
def catalog():
 rows={}
 for p in [S]+sorted(S.rglob('*')):
  v=meta(p);r=str(p.relative_to(S));n='sealed-packet'+('/' if r=='.' else '/'+r);n+=('/' if v['kind']=='dir' and not n.endswith('/') else '');rows[n]=v
 return rows
def makezip(name,rows):
 p=B/name
 with zipfile.ZipFile(p,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,v in sorted(rows.items()):
   i=zipfile.ZipInfo(n,(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(v['file_type']|v['mode'])<<16;i.compress_type=zipfile.ZIP_DEFLATED
   if v['kind']=='dir':z.writestr(i,b'');continue
   if v['kind']=='symlink':b=os.fsencode(os.readlink(v['source']));assert sha(b)==v['sha256'];z.writestr(i,b);continue
   h=hashlib.sha256();count=0
   with Path(v['source']).open('rb') as f,z.open(i,'w') as out:
    for b in iter(lambda:f.read(1024*1024),b''):out.write(b);h.update(b);count+=len(b)
   assert count==v['bytes'] and h.hexdigest()==v['sha256'],n
  i=zipfile.ZipInfo('CHECKPOINT-MANIFEST.json',(1980,1,1,0,0,0));i.create_system=3;i.external_attr=(stat.S_IFREG|0o600)<<16;i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,(json.dumps(rows,indent=2,sort_keys=True)+'\n').encode())
 return p
def provider(key,path):
 before=meta(path);members=[]
 with zipfile.ZipFile(path) as z:
  assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()))
  for i in z.infolist():
   b=z.read(i);typ=stat.S_IFMT(i.external_attr>>16);assert typ in (stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK) or (typ==0 and i.filename=='CAPTURE-MANIFEST.json');members.append({'path':i.filename,'bytes':len(b),'sha256':sha(b),'mode':stat.S_IMODE(i.external_attr>>16),'file_type':typ,'dir':i.is_dir(),'symlink_target':os.fsdecode(b) if typ==stat.S_IFLNK else None})
 d=B/(key+'-parts');d.mkdir();parts=[];off=0
 with path.open('rb') as f:
  for idx,b in enumerate(iter(lambda:f.read(500000),b'')):
   a=base64.b64encode(b);n=f'{key}-parts/part-{idx:03}.base64';(B/n).write_bytes(a);parts.append({'path':n,'offset':off,'bytes':len(b),'sha256':sha(b),'raw_git_sha1':git(b),'ASCII_bytes':len(a),'ASCII_sha256':sha(a),'git_sha1':git(a)});off+=len(b)
 assert meta(path)==before
 r={'format':'exact-ASCII500000-raw-provider/2','filename':path.name,'bytes':before['bytes'],'sha256':before['sha256'],'zip_entries':len(members),'members':members,'parts':parts,'scope':'Installed product32/native18 bounded attachment/scripted play/nativeaward/currentwithdrawal preparation IN_PROGRESS. No helperrepair/season/fullF3/human/independentAIentrant qualification; source33excluded; prior scopes preserved.'};save(key+'-recipe.json',r);return r


assert sha((S/'MANIFEST.json').read_bytes())=='45b54675f87ebee83520572c2acd1251a84b698dbecdffb4e2c5cce0b2fd78fb'
assert sha((S/'BUILD_STATUS.json').read_bytes())=='560fab2cb3c8a7ea3a42e6b79b55f195a2513bbbe46a38645ea625bf8d18253f'
manifest=json.loads((S/'MANIFEST.json').read_bytes());allfiles={str(p.relative_to(S)) for p in S.rglob('*') if p.is_file()}
assert len(manifest)==146 and allfiles==set(manifest)|{'MANIFEST.json'}
for n,v in manifest.items():
 m=meta(S/n);assert all(m[k]==v[k] for k in ('bytes','sha256')),n
before=catalog();save('source-before.json',before)
critical={n:v for n,v in before.items() if Path(v['source']).name!='Product32_Play_Award_Failure_Withdrawal_Raw.zip'}
cp=makezip('Product32_Attachment_Play_Award_Critical_IN_PROGRESS.zip',critical);cr=provider('critical',cp)
bp=makezip('Product32_Attachment_Play_Award_Complete_Packet_IN_PROGRESS.zip',before);br=provider('body',bp)
rp=S/'Product32_Play_Award_Failure_Withdrawal_Raw.zip';assert rp.stat().st_size==6225032 and sha(rp.read_bytes())=='4a384087c7fb2ac04cd694e428900a26747dee065628a6a08a249f03e58c061a'
rr=provider('raw',rp)
after=catalog();assert before==after;save('source-after.json',after)
context={'status':'BOUNDED_INSTALLED_EXHIBITION_ATTACHMENT_PLAY_NATIVE_AWARD_AND_WITHDRAWAL_PREPARATION_ONLY_IN_PROGRESS','packet':str(S),'manifest_sha256':'45b54675f87ebee83520572c2acd1251a84b698dbecdffb4e2c5cce0b2fd78fb','ledger_sha256':'560fab2cb3c8a7ea3a42e6b79b55f195a2513bbbe46a38645ea625bf8d18253f','manifest_files':146,'physical_files':147,'runtime_sha256':'84cc8c4c9e1d511a5aba7d724296c205a1b8eea8c48612b065a3e82035bd9a4b','product_wheel_sha256':'d5b9e10bf58aa5cbe2017a22dc42730564b76d68b7c3c25626a165d89fa5ac64','native18_wheel_sha256':'d2d6cbec7b404a451c13d20a61d1640bb7e2b639ae970f8f254b49a46c895626','source_entries':42,'source_trees':{'package':42,'source32-unbuilt-reviewed-antecedent/package':42},'actual_evidence':'One genuinely new ordinaryClient SCRIPTED synthetic world: separately bound two ownaccepted consents, exactlysame initial nativeepisodeattachment once, actual leftadvance/rightyield/leftfinish achievedeligibleevent. NativeContests alone derived one conserved material award pool2->1/leftaward0->1/right0/incorporated0. Exact+differentrequest replay allocatednothing, bothboundactors readnormal settlementartifact. Nativeverify/directregistry/FK/checkedbackup and243source/wheel/installedpayload correspondence retained. Writer doesnot rerun runtimechecks.','original_failure_and_following_controls':'Original negativeharness FAIL preserved: expected DEPENDENCY but unchanged earlier revisiongate correctly STALE after actualwithdrawal. Allreplies/6Ownerexits/script/world retained. Following exactclosedcopy actualpause/newresume refusesnewpreparation DEPENDENCY; alltablerows unchangedexcept documentedlast_wall; commonnativecancel succeeds/no consumption/geometry/settlement. No stale retry/assertion/productweakening. Positive+failure+followingcontrols are NOT onecleansuite. Build/harnessfailure+repairs/sourceantecedents retained.','limits':['bounded attachment/scripted play/nativeaward/currentwithdrawalpreparation only','no helperoffer/willingness/repair; incorporated0isnotrepairedmaterial','no independentAIentrant choices/human/mastery/canon/sponsor/season/fullF3/allF1-F5/fullrelease/generalhost','no current32 dualSIGKILL/physicalrelocation/restore/independentrecipient laterrepair proof','31AIrecipient+relocation/28bounded/current26media remain exacthistorical runtimes, no transfer','source33activework explicitlyexcluded, no current33 qualification','compact147file packet not fullhistoricalcontinuation; separate current28reconstructionKIT excludes30/31/32; no newLibraryversion'],'raw_capture':'Existing3actualOwnerlocks captured3completeworldtrees,235sourceentries+originalCAPTUREmanifest236ZIPmembers. SourcebeforeafterCRC/SHA/modes; no DBcapture/globalFDabsenceclaim. Writer byteonly frozenpacket/ZIPread; originalCAPTUREmanifest filetype0 preserved; no universalhealthyworld claim.','native_source_anchor':{'SAM':'78f68bde6496a3598d9059bf0e052b51ec494ca7','Kage':'1598555d04c3846a6ba4208b4b35dc701515474b','checkpoint':'F3A-NATIVE18-20261022-IN_PROGRESS','source_files':745},'preceding_current31_heads':{'SAM':'789b595753e4ea4e801d780346719881765e949f','Kage':'9e5889adebfae37eecacbcc9ae4ed5998e412dd5'},'preceding_historical28_KIT_heads':{'SAM':'f7d67a1cb01def718808e7b8bca65da50bcc39e5','Kage':'33f7bfbcbb7bba1a9bb268b565fa681261aeb73b'},'providers':{k:{x:r[x] for x in ('filename','bytes','sha256','zip_entries')} for k,r in [('critical',cr),('body',br),('raw',rr)]},'source_before_after_metadata_exact':True,'writer_execution':'Byte packaging only, no DB/Engine/Client/native/processprobe/build/test/world/source/Library/automation effects; nochildren'}
save('context.json',context)
shutil.copy2('/dev/shm/github-product31-offers/reconstruct.py',B/'reconstruct.py')
for n in ['verify_readback.py','check_tree_hash.py']:
 t=(Path('/dev/shm/github-product31-offers')/n).read_text().replace('/dev/shm/github-product31-offers','/dev/shm/github-product32-attachment-award');(B/n).write_text(t)
selected=['BUILD_STATUS.json','MANIFEST.json','CONTINUE.md','RAW_CAPTURE.json','REPORT.json','ROOT-CONTRACT.md','SOURCE_MANIFEST.json','STATUS.json','WIRE_RESULT.json','identity-lock.json','native18-canonical-source-manifest.json','native18-paired-dependency-receipt.json','complete28-recovery-kit-local-receipt.json','build-harness-repair.json']
direct=[{'path':n,'local':str(B/n)} for n in ['context.json','critical-recipe.json','reconstruct.py']]+[{'path':'selected/'+n,'local':str(S/n)} for n in selected]+[{'path':'attachment32-package/'+str(p.relative_to(S/'package')),'local':str(p)} for p in sorted((S/'package').rglob('*')) if p.is_file()]
assert len([x for x in direct if x['path'].startswith('attachment32-package/')])==42
(B/'upload-text').mkdir()
def plan(items,key):
 for idx,x in enumerate(items):
  b=Path(x['local']).read_bytes();t=B/'upload-text'/f'{key}-{idx:03}.base64';t.write_bytes(base64.b64encode(b));x.update(bytes=len(b),sha256=sha(b),git_sha1=git(b),encoding='base64',transport=str(t),transport_bytes=t.stat().st_size)
 return items
direct=plan(direct,'critical')
for x in cr['parts']:direct.append({'path':x['path'],'local':str(B/x['path']),'transport':str(B/x['path']),'transport_bytes':x['ASCII_bytes'],'bytes':x['ASCII_bytes'],'sha256':x['ASCII_sha256'],'git_sha1':x['git_sha1'],'encoding':'utf-8'})
save('critical-upload-plan.json',direct)
body=plan([{'path':n,'local':str(B/n)} for n in ['body-recipe.json','raw-recipe.json','source-before.json','source-after.json']],'body')
for r in [br,rr]:
 for x in r['parts']:body.append({'path':x['path'],'local':str(B/x['path']),'transport':str(B/x['path']),'transport_bytes':x['ASCII_bytes'],'bytes':x['ASCII_bytes'],'sha256':x['ASCII_sha256'],'git_sha1':x['git_sha1'],'encoding':'utf-8'})
save('body-upload-plan.json',body)
save('capture-result.json',dict(manifest_files=146,physical_files=147,bytes=sum((S/n).stat().st_size for n in allfiles),providers=context['providers'],source_before_after_metadata_exact=True,DB_opened=False))
print(json.dumps({'providers':context['providers'],'critical_uploads':len(direct),'body_uploads':len(body)},indent=2))



