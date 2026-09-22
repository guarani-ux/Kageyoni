"""Grounded composition and presentation, separate from fictional causality.

The host writes prose and judges semantics. This module supplies scoped briefs,
validates structured evidence, and records presentation/reception without rolls.
"""
import copy
import hashlib
import json
from pathlib import Path
from .resources import schema_path

VERSION='1'
FORMS={
 'narration':'Orient through perceptible action and concrete detail; leave room to act.',
 'dialogue':'Connect intention, voice, relationship, subtext and a fallible listener model.',
 'situation':'Present participants, competing aims, pressure and open possibilities; do not prescribe a solution.',
 'scenario':'Prepare a network of conditions and possible consequences, not a predetermined sequence.',
 'event':'Describe resolved action and observable change; distinguish outcome from interpretation.',
 'history':'Connect evidenced causes and consequences; identify whose account this is and preserve disputed versions.',
 'discovery':'Reveal through encounter, need or investigation; retain the difference between clue and conclusion.',
 'reflection':'Connect experience to the character’s interpretation; permit uncertainty and unchanged convictions.',
 'recap':'Select consequential established developments and unresolved questions without inventing connective facts.',
 'description':'Choose details that orient, evoke or invite attention; quiet enjoyment is sufficient purpose.'}
CONTRACT={
 'version':VERSION,'upstream':['audience','purpose','perspective','context'],
 'drafting':['Read the brief before drafting.','Distinguish what the speaker knows from what they assume about a listener.',
 'Use established voice and current emotion; a type label never supplies a line by itself.',
 'Choose detail, sequence, silence and pace for this situation. Do not manufacture changes to danger or motive.',
 'Leave meaningful player decisions open. Quiet scenes may offer beauty, familiarity or play.',
 'Use speaker names for dialogue.'],
 'review':['grounding','perspective','voice','agency','pacing'],
 'boundary':'Checks validate metadata and references. Prose meaning, emotional credibility, humor and quality require recorded GM review.',
 'forms':FORMS}
DOMAINS={
 'writing_delivery':dict(audience='ref:character',form='enum:'+'|'.join(FORMS),text='text',scene='ref:scene',supersedes='ref:writing_delivery'),
 'dialogue_reception':dict(listener='ref:character',turn='ref:dialogue_turn',interpretation='text',certainty='enum:tentative|confident|unknown',response='text',supersedes='ref:dialogue_reception')}
REQUIRED={'writing_delivery':['audience','form','text'],'dialogue_reception':['listener','turn','interpretation','certainty']}

def require(ok,message):
 from .engine import require as check
 check(ok,message)

def install(e):
 p=schema_path('migration_008.sql'); checksum=hashlib.sha256(p.read_bytes()).hexdigest()
 old=e.db.execute('SELECT checksum FROM migration_checks WHERE version=8').fetchone()
 if old: require(old[0]==checksum,'writing migration checksum mismatch')
 else:
  require(e.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0]==7,'writing migration predecessor mismatch')
  e._backup_before_versioned_migration(8)
  try:
   e.db.executescript('BEGIN IMMEDIATE;\n'+p.read_text())
   require(not e.db.execute('PRAGMA foreign_key_check').fetchall(),'writing migration foreign key failure')
   require(e.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','writing migration integrity failure')
   e.db.execute("INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(8,7,'migration_008.sql',?,'4')",(checksum,));e.db.commit()
  except Exception:e.db.rollback();raise
 require(e.db.execute("SELECT version FROM engine_versions WHERE component='writing_interface'").fetchone()[0]==VERSION,'unsupported writing interface')
 for command,fn in {'writing_brief':'brief','writing_publish':'publish','dialogue_receive':'receive'}.items():
  e.register_component('command',command,'1','kageyoni/writing.py:'+fn,status='verified',compatibility={'writing_interface':'1'},readers=['Workflows'],writers=['Engine.apply'] if fn!='brief' else [])
  for domain in ('character','character_aspect','knowledge','dialogue_turn','dialogue_reception','writing_delivery','scene','thread'):
   e.db.execute('INSERT OR IGNORE INTO registry_dependencies VALUES(?,?,?,?,?,?,?)',('command',command,'1','domain',domain,'1','declared scoped read/write'))
 e.register_component('migration','migration_008.sql','7','migration_008.sql',status='verified',compatibility={'runtime_schema':'4'})

def validate_record(r):
 if r['domain'] not in DOMAINS:return
 d=r['data'];person=d['audience'] if r['domain']=='writing_delivery' else d['listener']
 require(r['visibility']=='restricted' and r['audience']==[person],'writing records require their explicit recipient scope')
 field='text' if r['domain']=='writing_delivery' else 'interpretation'
 require(bool(d[field].strip()),'empty writing record')
 require(d.get('supersedes')!=r['id'],'self-supersession is invalid')

def validate_world(records):
 for r in records.values():
  if r['domain'] not in DOMAINS:continue
  d=r['data'];key='audience' if r['domain']=='writing_delivery' else 'listener'
  if r['domain']=='dialogue_reception':
   require(d['listener'] in records[d['turn']]['data']['listeners'],'reception listener did not participate')
  parent=d.get('supersedes');seen={r['id']}
  while parent:
   require(parent not in seen,'writing supersession cycle');seen.add(parent)
   older=records[parent]
   require(older['domain']==r['domain'] and older['data'][key]==d[key],'writing correction ownership mismatch')
   if r['domain']=='dialogue_reception':require(older['data']['turn']==d['turn'],'reception correction turn mismatch')
   parent=older['data'].get('supersedes')

def _shape(value,required,optional=()):
 require(isinstance(value,dict) and set(required)<=set(value)<=set(required)|set(optional),'invalid writing fields')

def _text(value):require(isinstance(value,str) and bool(value.strip()),'nonempty writing text required')

def brief(e,branch,form,audience,purpose,perspective=None,scene=None,focus=None,event_ids=None):
 from .personality import brief as character_brief
 from .engine import digest
 require(form in FORMS,'unsupported writing form');_text(purpose)
 viewer=e.get(branch,audience);require(viewer and viewer['domain']=='character','writing audience unavailable')
 focus=[] if focus is None else focus;event_ids=[] if event_ids is None else event_ids
 require(all(isinstance(v,list) and all(isinstance(x,str) for x in v) and len(v)==len(set(v)) for v in (focus,event_ids)),'invalid writing scope')
 if scene:
  sr=e.get(branch,scene);require(sr and sr['domain']=='scene' and e._visible(sr,audience),'writing scene unavailable')
 # GM-only authoring context may include secrets; only the separate recipient
 # projection may support delivered factual claims.
 private=[]
 for rid in focus:
  r=e.get(branch,rid);require(r is not None,'writing focus unavailable');private.append(r)
 safe=e.context(branch,viewer=audience)['records']; visible={r['id']:r for r in safe}
 character=character_brief(e,branch,perspective or audience,domain='dialogue',scene=scene)
 audience_mind=character_brief(e,branch,audience,domain='dialogue',scene=scene,viewer=audience)
 eligible={r['id'] for r in audience_mind['perceived']+audience_mind['knowledge']}
 eligible.update(r['id'] for r in private if r['id'] in visible and (r['domain']!='knowledge' or r['data']['holder']==audience))
 facts=[visible[rid] for rid in sorted(eligible) if rid in visible]
 events=[]
 for eid in event_ids:
  exists=e.db.execute('SELECT id,revision,kind,clock_id,tick,causes_json FROM events WHERE id=? AND branch=?',(eid,branch)).fetchone()
  require(exists is not None,'writing event unavailable')
  changes=[]
  for row in e.db.execute('SELECT before_json,after_json FROM changes WHERE event_id=? ORDER BY ordinal',(eid,)):
   after=json.loads(row['after_json'])
   if after['id'] in visible and e._visible(after,audience):
    # Historical inputs stay private; narration cites the visible record and
    # exact historical image only after its reference fields are projected.
    safe_after=copy.deepcopy(after);safe_after.pop('evidence',None);safe_after.pop('audience',None)
    from .model import DOMAINS as ALL_DOMAINS
    for field,kind in ALL_DOMAINS[after['domain']].items():
     if kind.startswith('ref:') and safe_after['data'].get(field) not in visible:safe_after['data'][field]=None
    if after['domain'].startswith('will_'):safe_after['data'].pop('contract',None)
    if after['domain']=='dialogue_turn':safe_after['data']['listeners']=[x for x in safe_after['data']['listeners'] if x in visible]
    changes.append(safe_after)
  if changes:events.append({'id':eid,'causes':json.loads(exists['causes_json']),'recording_revision':exists['revision'],'world_time':{'clock':exists['clock_id'] if exists['clock_id'] in visible else None,'tick':exists['tick'] if exists['clock_id'] in visible else None},'changes':changes})
 allowed_events={ev['id'] for ev in events}
 for ev in events:ev['causes']=[eid for eid in ev['causes'] if eid in allowed_events]
 deliveries=[r for r in safe if r['domain']=='writing_delivery' and r['data']['audience']==audience]
 result={'writing_interface':VERSION,'branch':branch,'revision':e.branch(branch)['revision'],'request':dict(form=form,audience=audience,purpose=purpose,perspective=perspective,scene=scene,focus=focus,event_ids=event_ids),
 'guidance':CONTRACT,'character_context':character,'private_focus':private,'audience_facts':facts,'audience_properties':[v for v in e.properties(branch,viewer=audience) if v['entity_id'] in visible],'event_evidence':events,'previous_deliveries':deliveries,
 'open_threads':[r for r in facts if r['domain']=='thread' and r['data']['phase'] in ('open','investigating')],
 'questions':['What is perceived, believed, assumed, or still unknown?','What is this speaker trying to accomplish with this listener?','What detail or silence serves this moment?','Where should narration stop to leave a meaningful decision?'],
 'semantic_boundary':'Audience facts are eligible references, not a guarantee that prose is true or that a character consciously knows every visible fact.'}
 result['brief_hash']=digest(result)
 return result

def validate_rhetoric(e,branch,actor,request,rhetoric):
 from .personality import brief as character_brief
 _shape(rhetoric,('purpose','strategy','subtext','listener_assumptions'))
 for key in ('purpose','strategy','subtext'):_text(rhetoric[key])
 require(isinstance(rhetoric['listener_assumptions'],list),'listener assumptions must be a list')
 b=character_brief(e,branch,actor,interlocutors=request.get('interlocutors'))
 own={r['id']:r for r in b['knowledge']}
 for assumption in rhetoric['listener_assumptions']:
  _shape(assumption,('listener','interpretation','basis'))
  require(assumption['listener'] in request.get('interlocutors',[]),'listener assumption outside dialogue')
  _text(assumption['interpretation']);require(isinstance(assumption['basis'],list),'invalid assumption basis')
  for ref in assumption['basis']:
   _shape(ref,('id','version'));r=own.get(ref['id'])
   require(r and r['version']==ref['version'],'listener model uses unavailable speaker knowledge')
 # An empty basis explicitly means a conjecture; the interpretation is never
 # promoted to the listener's actual knowledge or intention.

def _review(review):
 _shape(review,('by','rationale','checks'))
 _text(review['by']);_text(review['rationale'])
 require(isinstance(review['checks'],dict) and set(review['checks'])==set(CONTRACT['review']) and all(v is True for v in review['checks'].values()),'writing semantic review incomplete')

def _retry(e,branch,request_id,payload):
 from .engine import digest
 row=e.db.execute('SELECT command_json,receipt_json FROM events WHERE branch=? AND request_id=?',(branch,request_id)).fetchone()
 if row:
  cmd=json.loads(row['command_json'])
  require(cmd.get('judgment',{}).get('writing_request_hash')==digest(payload),'writing request reused with changed content')
  return json.loads(row['receipt_json'])|{'replayed':True}

def publish(e,branch,request_id,expected_revision,brief_spec,brief_hash,text,claims,review,supersedes=None,interface_version='1'):
 from .engine import digest
 require(str(interface_version)==VERSION,'unsupported writing interface');_text(request_id)
 payload=copy.deepcopy({k:v for k,v in locals().items() if k not in ('e','digest')})
 rid='writing:'+request_id
 e.db.execute('BEGIN IMMEDIATE')
 try:
  prior=_retry(e,branch,rid,payload)
  if prior:e.db.rollback();return prior
  require(e.branch(branch)['revision']==expected_revision,'stale writing revision')
  _shape(brief_spec,('form','audience','purpose'),('perspective','scene','focus','event_ids'))
  b=brief(e,branch,**brief_spec);require(b['brief_hash']==brief_hash,'stale or altered writing brief')
  _text(text);_review(review);require(isinstance(claims,list),'writing claims required')
  sources={(r['id'],r['version']):r for r in b['audience_facts']}
  for ev in b['event_evidence']:
   sources.update({(r['id'],r['version']):r for r in ev['changes']})
  deps=[]
  for claim in claims:
   _shape(claim,('status','statement','basis'));_text(claim['statement'])
   require(claim['status'] in ('fact','belief','possibility'),'invalid writing claim status')
   require(isinstance(claim['basis'],list) and (claim['basis'] or claim['status']=='possibility'),'factual writing claim requires evidence')
   for ref in claim['basis']:
    _shape(ref,('id','version'));require(isinstance(ref['id'],str) and type(ref['version']) is int and ref['version']>0,'invalid writing evidence version');r=sources.get((ref['id'],ref['version']))
    require(r is not None,'writing evidence unavailable to audience')
    if claim['status']=='fact':
     require(r['domain'] not in ('knowledge','historical_account','dialogue_reception') and r['status']=='confirmed','subjective or unresolved source cannot certify a world fact')
    deps.append({'kind':'record','ref_id':r['id'],'version':str(r['version']),'usage':'writing'})
  audience=brief_spec['audience'];delivery='delivery:'+request_id
  data=dict(audience=audience,form=brief_spec['form'],text=text,scene=brief_spec.get('scene'),supersedes=supersedes)
  command=dict(api_version=3,branch=branch,request_id=rid,expected_revision=expected_revision,kind='observation',actor='gm',narrative='Record host-presented writing; no physical world or knowledge change',changes=[dict(op='create',domain='writing_delivery',id=delivery,data=data,status='confirmed',visibility='restricted',audience=[audience],evidence=[{'note':'Host attests presentation; this record does not certify the prose as objective history.'}])],dependencies=list({(x['ref_id'],x['version']):x for x in deps}.values()),judgment={'writing_request_hash':digest(payload),'brief':b,'claims':claims,'review':review,'presentation_only':True})
  e._writing_command=digest(command)
  try:
   receipt=e.apply(command)
   e.db.commit()  # This workflow owns the transaction opened above.
   return receipt
  finally:e._writing_command=None
 except Exception:e.db.rollback();raise

def receive(e,branch,request_id,expected_revision,listener,turn,interpretation,certainty,response,review,supersedes=None,interface_version='1'):
 from .engine import digest
 require(str(interface_version)==VERSION,'unsupported writing interface');_text(request_id)
 payload=copy.deepcopy({k:v for k,v in locals().items() if k not in ('e','digest')})
 rid='writing-reception:'+request_id;e.db.execute('BEGIN IMMEDIATE')
 try:
  prior=_retry(e,branch,rid,payload)
  if prior:e.db.rollback();return prior
  require(e.branch(branch)['revision']==expected_revision,'stale reception revision')
  _review(review);_text(interpretation)
  r=e.get(branch,turn);require(r and r['domain']=='dialogue_turn' and listener in r['data']['listeners'],'dialogue reception unavailable')
  heard=e.db.execute('SELECT 1 FROM observations WHERE branch=? AND observer_id=? AND event_id=? AND subject_id=? AND assertion=?',(branch,listener,r['updated_event'],r['data']['speaker'],r['data']['text'])).fetchone()
  require(heard is not None,'reception requires recorded hearing')
  command=dict(api_version=3,branch=branch,request_id=rid,expected_revision=expected_revision,kind='observation',actor=listener,narrative='Record listener interpretation, not objective truth',changes=[dict(op='create',domain='dialogue_reception',id='reception:'+request_id,data=dict(listener=listener,turn=turn,interpretation=interpretation,certainty=certainty,response=response,supersedes=supersedes),status='reported',visibility='restricted',audience=[listener],evidence=[{'note':'Explicit GM-reviewed listener interpretation.'}])],judgment={'writing_request_hash':digest(payload),'review':review},dependencies=[dict(kind='record',ref_id=turn,version=str(r['version']),usage='reception')])
  e._writing_command=digest(command)
  try:
   receipt=e.apply(command)
   e.db.commit()  # This workflow owns the transaction opened above.
   return receipt
  finally:e._writing_command=None
 except Exception:e.db.rollback();raise
