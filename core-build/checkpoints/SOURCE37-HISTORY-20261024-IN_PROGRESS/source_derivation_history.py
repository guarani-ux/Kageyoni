"""Isolated complete creation-history reader; no installation or body return.

Caller retains ordinary authorization and the owning snapshot before invoking
these diagnostics. Presence/layout installer and Engine integration remain
separate mandatory activation gates. This is not an authenticated producer.
"""
from copy import deepcopy
from source_derivation_facts import (PROFILE,DOMAIN,PREFIX,OP_PREFIX,ARTIFACT_KEYS,
    require,canonical,digest,validate_command,validate_record,derivation_id)
from kageyoni.workspaces.source_authority_installation import strict_json

AUX=('properties','facet_changes','processes','consequence_runs','resolution',
     'observations','process_runs','profiles','entity_links','classification_claims','choice','will_attempt')

def signal(value,parent=None):
    if type(value)is dict:
        for key,child in value.items():
            name=key.casefold()
            if name.startswith(('source_derivation','source-derivation')):return True
            if type(child)is str:
                word=child.casefold()
                if name=='profile'and word.startswith('samsara-source-derivation/'):return True
                if name=='domain'and word.startswith(DOMAIN):return True
                if name in ('id','record_id')and word.startswith(PREFIX):return True
                if name in ('request_id','kind')and word.startswith((OP_PREFIX,DOMAIN)):return True
            if signal(child,name):return True
    elif type(value)is list:
        for child in value:
            if parent in ('changed','record_ids')and type(child)is str and child.casefold().startswith(PREFIX):return True
            if signal(child,parent):return True
    return False

def projection_signal(db,row):
    from kageyoni.model import DOMAINS
    domain=row['domain']
    fields={'contract':'json'}if domain==DOMAIN else DOMAINS.get(domain)
    require(fields is not None,'unknown native projection domain')
    names=[k for k,v in fields.items()if v=='json']
    if not names:return False
    quote=lambda s:'"'+s.replace('"','""')+'"'
    data=db.execute('SELECT '+','.join(quote(n)for n in names)+' FROM '+quote(domain)+' WHERE branch=? AND id=?',(row['branch'],row['id'])).fetchone()
    require(data is not None,'native JSON projection missing')
    return any(signal(strict_json(data[n]))for n in names if data[n]is not None)

def event_fact(db,row,changes):
    e=dict(row);c=strict_json(e['command_json']);v=validate_command(c);rid=derivation_id(v)
    require(len(changes)==1,'one immutable derivation change required')
    change=dict(changes[0]);require(type(change['ordinal'])is int and change['ordinal']==0 and change['record_id']==rid and change['before_json']is None,'derivation change identity/before differs')
    after=validate_record(strict_json(change['after_json']))
    require(after['updated_event']==e['id']and after['branch']==v['branch'],'derivation event record identity differs')
    for key in ('id','domain','data','status','visibility','audience','evidence'):
        require(canonical(after[key])==canonical(c['changes'][0][key]),'native command/change differs')
    require(e['branch']==c['branch']and e['request_id']==c['request_id']and e['payload_hash']==digest(c)and e['kind']==c['kind']and e['actor']==c['actor']and e['narrative']==c['narrative']and e['clock_id']is None and e['tick']is None and strict_json(e['causes_json'])==[]and type(e['revision'])is int and e['revision']==c['expected_revision']+1,'native event metadata differs')
    expected_hash=digest({'previous':e['prev_hash'],'payload_hash':e['payload_hash'],'changes':[[None,after]]})
    require(e['event_hash']==expected_hash,'native event hash differs')
    prior=db.execute('SELECT event_hash FROM events WHERE branch=? AND revision=?',(e['branch'],e['revision']-1)).fetchone()
    require((e['revision']==1 or prior is not None)and e['prev_hash']==(prior[0]if prior else''),'native predecessor missing/different')
    head=db.execute('SELECT revision FROM branches WHERE id=?',(e['branch'],)).fetchone();require(head is not None and head[0]>=e['revision'],'native event exceeds branch head')
    receipt=dict(event_id=e['id'],branch=e['branch'],revision=e['revision'],request_id=e['request_id'],event_hash=expected_hash,changed=[rid],changed_properties=[],changed_processes=[],changed_profiles=[],changed_links=[],changed_classifications=[],triggered_processes=[],will_attempt_id=None,replayed=False,committed=True,aux_digest=digest({k:c.get(k)for k in AUX}))
    require(canonical(strict_json(e['receipt_json']))==canonical(receipt),'native receipt differs')
    return {'creation':v,'record':after,'event_id':e['id'],'revision':e['revision']}

def collect_derivation_metadata(engine):
    db=engine.db;require(db.in_transaction,'existing coherent UnitOfWork required')
    current={}
    for row in db.execute('SELECT * FROM records'):
        raw=dict(row)
        selected=(raw['domain'].casefold().startswith(DOMAIN)or raw['id'].casefold().startswith(PREFIX)or signal(strict_json(raw['audience_json']))or signal(strict_json(raw['evidence_json']))or projection_signal(db,row))
        if not selected:continue
        require(raw['domain']==DOMAIN,'reserved derivation record domain differs')
        p=db.execute('SELECT contract FROM source_derivation WHERE branch=? AND id=?',(raw['branch'],raw['id'])).fetchone();require(p is not None,'derivation projection missing')
        raw['audience']=strict_json(raw.pop('audience_json'));raw['evidence']=strict_json(raw.pop('evidence_json'));raw['data']={'contract':strict_json(p[0])}
        record=validate_record(raw);current[record['branch'],record['id']]=record
    changes={};signaled=set()
    for row in db.execute('SELECT * FROM changes ORDER BY event_id,ordinal'):
        c=dict(row);changes.setdefault(c['event_id'],[]).append(c)
        if c['record_id'].casefold().startswith(PREFIX)or any(signal(strict_json(c[k]))for k in ('before_json','after_json')if c[k]is not None):signaled.add(c['event_id'])
    facts={};known=set()
    for row in db.execute('SELECT * FROM events ORDER BY branch,revision'):
        e=dict(row)
        if not(e['id']in signaled or e['request_id'].casefold().startswith(OP_PREFIX)or e['kind'].casefold().startswith(DOMAIN)or signal(strict_json(e['command_json']))or signal(strict_json(e['receipt_json']))):continue
        fact=event_fact(db,e,changes.get(e['id'],[]));r=fact['record'];key=(r['branch'],r['id']);require(key not in facts,'derivation creation repeated/rewritten');facts[key]=fact;known.add(e['id'])
    require(signaled<=known,'orphan derivation change/event')
    require(set(facts)==set(current),'derivation current/history identity sets differ')
    exists=db.execute("SELECT name FROM sqlite_master WHERE type='table' AND lower(name)=?",(DOMAIN,)).fetchall()
    if exists:
        require(len(exists)==1 and exists[0][0]==DOMAIN,'aliased derivation projection')
        projections={(r['branch'],r['id'])for r in db.execute('SELECT branch,id FROM source_derivation')}
        require(projections==set(current),'orphan derivation projection')
    else:require(not current and not facts,'missing derivation projection')
    from kageyoni.workspaces.source_authority_history import collect_source_authority_metadata
    source_metadata=collect_source_authority_metadata(engine)
    outputs={}
    for key,fact in facts.items():
        require(canonical(current[key])==canonical(fact['record']),'current derivation differs from creation history')
        v=fact['creation'];output=v['output'];aid=output['artifact_id']
        require(aid not in outputs,'derivation output identity ambiguous')
        row=db.execute('SELECT '+','.join(sorted(ARTIFACT_KEYS))+' FROM artifacts WHERE artifact_id=?',(aid,)).fetchone()
        require(row is not None and canonical(dict(row))==canonical(output),'actual output metadata differs')
        workspace=db.execute('SELECT branch FROM operational_workspaces WHERE workspace_id=?',(v['workspace_id'],)).fetchone();require(workspace is not None and workspace[0]==v['branch'],'actual output workspace branch differs')
        recipient=db.execute('SELECT domain FROM records WHERE branch=? AND id=?',(v['branch'],v['recipient'])).fetchone();require(recipient is not None and recipient[0]=='character','actual native recipient missing')
        for item in v['bindings']['inputs']:
            old=item['source_row'];row=db.execute('SELECT workspace_id,source_id,revision,request_id,payload_hash,artifact_id,metadata_json FROM document_sources WHERE workspace_id=? AND source_id=? AND revision=?',(old['workspace_id'],old['source_id'],old['revision'])).fetchone()
            require(row is not None and canonical(dict(row))==canonical(old),'historical input source metadata differs')
            row=db.execute('SELECT '+','.join(sorted(ARTIFACT_KEYS))+' FROM artifacts WHERE artifact_id=?',(item['artifact']['artifact_id'],)).fetchone()
            require(row is not None and canonical(dict(row))==canonical(item['artifact']),'historical input artifact metadata differs')
            controlled=source_metadata['families'].get((old['workspace_id'],old['source_id']))
            if item['control']is None:require(controlled is None,'uncontrolled input was retroactively controlled')
            else:
                require(controlled is not None,'historical input control missing')
                record=controlled['record'];history=source_metadata['histories'][record['branch'],record['id']]
                expected={'id':record['id'],'version':1,'creation_digest':digest(controlled['creation']),'event_id':history[0]['event_id']}
                require(canonical(expected)==canonical(item['control']),'immutable input control creation correspondence differs')
        outputs[aid]=fact
    for row in db.execute('SELECT * FROM snapshots'):
        s=dict(row);payload=strict_json(s['state_json']);require(digest(payload)==s['sha256'],'snapshot digest differs')
        records=payload if type(payload)is list else payload.get('records')if type(payload)is dict else None;require(type(records)is list,'snapshot records missing')
        selected={}
        for record in records:
            require(type(record)is dict,'snapshot record required')
            if signal(record):
                r=validate_record(record);require(r['branch']==s['branch']and r['id']not in selected,'snapshot branch/duplicate differs');selected[r['id']]=r
        expected={rid:f['record']for (branch,rid),f in facts.items()if branch==s['branch']and f['revision']<=s['revision']}
        require(canonical(selected)==canonical(expected),'derivation snapshot/history correspondence differs')
        if type(payload)is dict:require(not signal({k:v for k,v in payload.items()if k!='records'}),'unsupported derivation snapshot auxiliary marker')
    return {'facts':deepcopy(facts),'outputs':deepcopy(outputs),'projection_present':bool(exists)}

def validate_current_inputs(engine,creation,unit):
    """Direct-source current correspondence only; not host auth or body access.

    Generic reverse guard must first call collect_derivation_metadata and check
    its own ordinary audience/Registry authorization, in this same snapshot.
    First profile refuses deriving from a prior derived artifact as a source.
    """
    from source_derivation_facts import validate_creation
    from source_derivation_bindings import bind_inquiry_inputs
    from kageyoni.persistence.unit_of_work import _lexical_generation
    _lexical_generation(engine.db,unit);v=validate_creation(creation)
    resolved=collect_derivation_metadata(engine)
    require(not any(i['artifact']['artifact_id']in resolved['outputs']for i in v['bindings']['inputs']),'nested derived-source input unsupported in first profile')
    now=bind_inquiry_inputs(engine,v['payload'],unit)
    require(canonical(now)==canonical(v['bindings']),'current input metadata/control correspondence differs')
    return True
