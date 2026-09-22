"""Acquire exact source bytes, expose gaps, and draft a constrained document.

Source interpretation is attributed to supplied passage mappings. Code checks
identity declarations, freshness, spans, obligations and transferred operations;
it never invents a premise, visual, schedule or sensory assessment.
"""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
from uuid import uuid4
from ..engine import require,digest,encoded,Rejected
from ..persistence.artifacts import Artifacts
from ..persistence.unit_of_work import UnitOfWork
from ..execution.operations import run,pending_guards,failed_guards,finite_number
from .registry import Registry
from .contracts import text,finite,timestamp

class Documents:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def ingest(self,workspace_id,request_id,source_id,text,identity,expected_identity,captured_at,expires_at=None,viewer=None,locator='subscription-host supplied'):
        from .contracts import text as checktext
        for value,label in ((request_id,'request id'),(source_id,'source id'),(identity,'source identity'),(expected_identity,'expected identity'),(locator,'source locator')):checktext(value,label)
        require(isinstance(text,str) and 0<len(text)<=1000000,'bounded source text required')
        captured=timestamp(captured_at);require(captured<=datetime.now(timezone.utc)+timedelta(minutes=5),'source capture time is in the future')
        if expires_at is not None:require(timestamp(expires_at)>=captured,'source expiry precedes capture')
        payload=dict(workspace_id=workspace_id,source_id=source_id,text=text,identity=identity,expected_identity=expected_identity,captured_at=captured_at,expires_at=expires_at,viewer=viewer,locator=locator)
        with UnitOfWork(self.db):
            Registry(self.engine).read(workspace_id,viewer=viewer)
            old=self.db.execute('SELECT source_id,revision,payload_hash FROM document_sources WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'source request conflict');return self.source(workspace_id,old['source_id'],viewer=viewer,revision=old['revision'])
            revision=self.db.execute('SELECT coalesce(MAX(revision),0)+1 FROM document_sources WHERE workspace_id=? AND source_id=?',(workspace_id,source_id)).fetchone()[0]
            artifact=Artifacts(self.engine).put(text,'text/plain; charset=utf-8',request_id+':source',workspace_id=workspace_id,viewer=viewer)
            metadata=dict(identity=identity,expected_identity=expected_identity,captured_at=captured_at,expires_at=expires_at,locator=locator,acquisition='exact captured bytes',identity_limit='Identity attribution supplied by operator; equality does not independently identify a business.')
            self.db.execute('INSERT INTO document_sources VALUES(?,?,?,?,?,?,?)',(workspace_id,source_id,revision,request_id,digest(payload),artifact['artifact_id'],encoded(metadata)))
            return self.source(workspace_id,source_id,viewer=viewer,revision=revision)
    def acquire_file(self,workspace_id,request_id,path,source_id,identity,expected_identity,captured_at,expires_at=None,viewer=None):
        source=Path(path);require(source.is_file() and source.stat().st_size<=1000000,'source file unavailable or too large')
        try:content=source.read_bytes().decode('utf-8')
        except UnicodeError:raise Rejected('source must be UTF-8 text') from None
        return self.ingest(workspace_id,request_id,source_id,content,identity,expected_identity,captured_at,expires_at=expires_at,viewer=viewer,locator=str(source.resolve()))
    def world_source(self,workspace_id,request_id,record_id,field_path,source_id,viewer=None):
        workspace=Registry(self.engine).read(workspace_id,viewer=viewer)
        record=next((r for r in workspace['context']['records'] if r['id']==record_id),None);require(record is not None,'workspace source unavailable')
        require(isinstance(field_path,list) and field_path and field_path[0]=='data','world source path must start in permitted data')
        value=record
        for part in field_path:
            require(isinstance(value,dict) and isinstance(part,str) and part in value,'world source field unavailable');value=value[part]
        require(type(value) in (str,int,float,bool),'world source field must be an available scalar')
        return self.ingest(workspace_id,request_id,source_id,str(value),record_id,record_id,datetime.now(timezone.utc).isoformat(),viewer=viewer,locator='world:'+workspace['branch']+'/'+record_id)
    def source(self,workspace_id,source_id,viewer=None,revision=None):
        Registry(self.engine).read(workspace_id,viewer=viewer)
        if revision is None:row=self.db.execute('SELECT * FROM document_sources WHERE workspace_id=? AND source_id=? ORDER BY revision DESC LIMIT 1',(workspace_id,source_id)).fetchone()
        else:row=self.db.execute('SELECT * FROM document_sources WHERE workspace_id=? AND source_id=? AND revision=?',(workspace_id,source_id,revision)).fetchone()
        require(row is not None,'document source unavailable')
        metadata=json.loads(row['metadata_json']);artifact=Artifacts(self.engine).read(row['artifact_id'],viewer=viewer)
        status='available'
        if metadata['identity']!=metadata['expected_identity']:status='identity_mismatch'
        elif metadata['expires_at'] is not None and timestamp(metadata['expires_at'])<datetime.now(timezone.utc):status='stale'
        return dict(metadata,source_id=source_id,revision=row['revision'],digest=artifact['digest'],artifact_id=row['artifact_id'],status=status,text=artifact['content'].decode('utf-8'))
    def _passage(self,workspace_id,citation,viewer):
        require(isinstance(citation,dict) and set(citation)=={'source_id','revision','digest','start','end'},'exact source passage reference required')
        require(type(citation['revision']) is int and citation['revision']>0 and isinstance(citation['digest'],str),'valid source revision and digest required')
        source=self.source(workspace_id,citation['source_id'],viewer=viewer)
        require(source['revision']==citation['revision'] and source['digest']==citation['digest'],'source passage version unavailable or stale')
        start,end=citation['start'],citation['end'];require(type(start) is int and type(end) is int and 0<=start<end<=len(source['text']),'invalid source passage span')
        return {'text':source['text'][start:end],'citation':deepcopy(citation),'status':source['status'],'identity':source['identity'],'locator':source['locator'],'captured_at':source['captured_at']}
    def inquire(self,workspace_id,request_id,question,required_fields,claims,counters=None,viewer=None):
        text(request_id,'request id');text(question,'question');counters=[] if counters is None else counters
        require(isinstance(required_fields,list) and 1<=len(required_fields)<=64 and all(isinstance(f,str) and f for f in required_fields) and len(set(required_fields))==len(required_fields),'distinct required fields needed')
        require(isinstance(claims,list) and isinstance(counters,list) and len(claims)+len(counters)<=256,'bounded claim mappings required')
        payload=dict(workspace_id=workspace_id,question=question,required_fields=required_fields,claims=claims,counters=counters,viewer=viewer);finite(payload)
        with UnitOfWork(self.db):
            Registry(self.engine).read(workspace_id,viewer=viewer)
            old=self.db.execute('SELECT payload_hash,result_json FROM document_inquiries WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'inquiry request conflict');return json.loads(old['result_json'])
            attempts=sum(json.loads(r[0])['question']==question for r in self.db.execute('SELECT result_json FROM document_inquiries WHERE workspace_id=?',(workspace_id,)))
            fields={field:{'supports':[],'counters':[],'unavailable':[]} for field in required_fields}
            for kind,items in (('supports',claims),('counters',counters)):
                for item in items:
                    require(isinstance(item,dict) and set(item)=={'field','evidence'} and item['field'] in fields,'claim must map a required field to evidence')
                    passage=self._passage(workspace_id,item['evidence'],viewer)
                    fields[item['field']][kind if passage['status']=='available' else 'unavailable'].append(passage)
            unknowns=[name for name,data in fields.items() if not data['supports']]
            disputed=[name for name,data in fields.items() if data['supports'] and data['counters']]
            phase='blocked' if attempts>=3 else 'partial' if unknowns or disputed else 'completed'
            result=dict(inquiry_id='inquiry:'+uuid4().hex,workspace_id=workspace_id,question=question,phase=phase,fields=fields,unknowns=unknowns,disputed=disputed,coverage=(len(required_fields)-len(unknowns))/len(required_fields),attempt=attempts+1,
                next={'action':'stop_and_review_budget' if attempts>=3 else 'capture_or_map_passage' if unknowns or disputed else 'draft','fields':unknowns+disputed},
                limit='Exact source statements and mapped passages; field meanings, business identity and real-world truth still require judgment.')
            self.db.execute('INSERT INTO document_inquiries VALUES(?,?,?,?,?)',(result['inquiry_id'],workspace_id,request_id,digest(payload),encoded(result)));return result
    def decompose(self,workspace_id,source_id,viewer=None):
        source=self.source(workspace_id,source_id,viewer=viewer)
        return {'source_id':source_id,'revision':source['revision'],'digest':source['digest'],'transcript':source['text'],'visual':{'state':'unknown','value':None},'premise':{'state':'unknown','value':None},'source_status':source['status'],
                'next':'Supply a passage mapping or an explicitly proposed interpretation; no visual or premise is inferred from unrelated transcript words.'}
    def checked_candidates(self,workspace_id,candidates,viewer=None):
        require(isinstance(candidates,list) and 1<=len(candidates)<=100,'bounded destination candidates required')
        result=[];seen=set()
        for candidate in candidates:
            require(isinstance(candidate,dict) and set(candidate)<= {'id','metrics'} and 'id' in candidate,'invalid destination candidate');text(candidate['id'],'candidate id',128)
            require(candidate['id'] not in seen,'duplicate candidate');seen.add(candidate['id'])
            metrics=candidate.get('metrics',{});require(isinstance(metrics,dict) and len(metrics)<=64,'bounded metrics required');claims={}
            for field,metric in metrics.items():
                text(field,'metric field',128);require(isinstance(metric,dict) and set(metric)=={'value','evidence'},'metric needs exact source evidence')
                value=metric['value'];require(finite_number(value),'finite numeric metric required')
                passage=self._passage(workspace_id,metric['evidence'],viewer)
                try:actual=float(passage['text'].strip())
                except ValueError:actual=None
                matched=passage['status']=='available' and actual is not None and math.isfinite(actual) and actual==value
                claims[field]={'value':value,'support':'matched' if matched else 'unmatched','evidence':[passage]}
            result.append({'id':candidate['id'],'claims':claims,'counterclaims':{}})
        return result
    def draft(self,workspace_id,request_id,brief,viewer=None,transfer_trial_id=None):
        text(request_id,'request id');finite(brief)
        require(isinstance(brief,dict) and {'brief_id','title','audience','purpose','sections'}<=set(brief)<= {'brief_id','title','audience','purpose','sections','obligations'},'invalid document brief')
        for field in ('brief_id','title','audience','purpose'):text(brief[field],field)
        sections=brief['sections'];require(isinstance(sections,list) and 1<=len(sections)<=100,'bounded document sections required')
        payload=dict(workspace_id=workspace_id,brief=brief,viewer=viewer,transfer_trial_id=transfer_trial_id)
        with UnitOfWork(self.db):
            workspace=Registry(self.engine).read(workspace_id,viewer=viewer);require(workspace['kind']=='document','document workspace required')
            old=self.db.execute('SELECT draft_id,payload_hash FROM document_drafts WHERE request_id=?',(request_id,)).fetchone()
            if old:require(old['payload_hash']==digest(payload),'draft request conflict');return self.read(old['draft_id'],viewer=viewer)
            section_map={};unknowns=[];refs=[];required_missing=False
            for section in sections:
                require(isinstance(section,dict) and {'id','heading','field'}<=set(section)<= {'id','heading','field','required','claims','metrics'},'invalid section')
                for key in ('id','heading','field'):text(section[key],'section '+key,256)
                require(section['id'] not in section_map,'duplicate section');require(type(section.get('required',True)) is bool,'required flag must be boolean')
                citations=section.get('claims',[]);require(isinstance(citations,list) and len(citations)<=32,'bounded section citations required')
                passages=[self._passage(workspace_id,c,viewer) for c in citations];valid=[p for p in passages if p['status']=='available'];refs.extend(p['citation'] for p in passages)
                if not valid:unknowns.append(section['field']);required_missing=required_missing or section.get('required',True)
                section_map[section['id']]={'section':section,'passages':valid}
            order=list(section_map);method_effect=None
            if transfer_trial_id is not None:
                from ..intelligence.transfer import Transfers
                transfer=Transfers(self.engine).require_qualified(transfer_trial_id,workspace_id,'document',viewer=viewer)
                definition=dict(transfer['method_guards'],operation=transfer['operation'])
                require(not pending_guards(definition),'transferred method still requires judgment')
                candidates=self.checked_candidates(workspace_id,[{'id':s['id'],'metrics':s.get('metrics',{})} for s in sections],viewer=viewer)
                require(not failed_guards(definition,candidates),'transferred method precondition unmet')
                effect=run(transfer['operation'],candidates);require(effect['phase']=='completed','transferred method lacks supported destination inputs')
                if transfer['operation']['kind']=='constraint_rank':
                    ranked=[r['candidate_id'] for r in effect['ranked']];order=ranked+[identifier for identifier in order if identifier not in ranked]
                method_effect=dict(transfer_id=transfer_trial_id,trial_id=transfer['latest_trial']['trial_id'],trial_artifact_digest=transfer['latest_trial']['artifact_digest'],method_digest=transfer['method_digest'],operation=transfer['operation'],result=effect)
            obligations=[]
            require(isinstance(brief.get('obligations',[]),list) and len(brief.get('obligations',[]))<=128,'bounded brief obligations required')
            for obligation in brief.get('obligations',[]):
                require(isinstance(obligation,dict) and set(obligation)=={'id','status','evidence'} and obligation['status'] in ('required','cancelled'),'obligation must have scoped source evidence')
                passage=self._passage(workspace_id,obligation['evidence'],viewer);require(passage['status']=='available','obligation source unavailable')
                obligations.append(dict(id=obligation['id'],brief_id=brief['brief_id'],status=obligation['status'],passage=passage));refs.append(passage['citation'])
            lines=['# '+brief['title'],'','Audience: '+brief['audience'],'','Purpose: '+brief['purpose'],'']
            for identifier in order:
                value=section_map[identifier];lines.extend(['## '+value['section']['heading'],''])
                if not value['passages']:lines.extend(['Unknown: '+value['section']['field']+'. Source evidence or an explicit proposed interpretation is needed.',''])
                for passage in value['passages']:
                    citation=passage['citation'];lines.extend(['> '+passage['text'].replace('\n','\n> '),'',f"Source: {citation['source_id']} revision {citation['revision']}, characters {citation['start']}–{citation['end']}.",''])
            if obligations:
                lines.extend(['## Brief obligations',''])
                for obligation in obligations:lines.extend([f"- {obligation['status'].upper()}: {obligation['passage']['text']}"])
            if method_effect and transfer['operation']['kind']=='counterexample_check':lines.extend(['','## Supplied-evidence review','',encoded(method_effect['result'])])
            rendered='\n'.join(lines).rstrip()+'\n'
            artifact=Artifacts(self.engine).put(rendered,'text/markdown; charset=utf-8',request_id+':draft',workspace_id=workspace_id,viewer=viewer)
            result=dict(draft_id='draft:'+uuid4().hex,workspace_id=workspace_id,node_id=workspace['node_id'],branch=workspace['branch'],phase='partial' if required_missing else 'completed',artifact=artifact,brief_id=brief['brief_id'],source_refs=refs,unknowns=unknowns,obligations=obligations,transfer_trial_id=transfer_trial_id,method_effect=method_effect,section_order=order,
                objective_scope='source_constrained_draft',task_objective='unresolved',obligation_satisfaction='not_established',
                limit='A source-constrained draft with checked literal passages; semantic adaptation and audience effectiveness remain unverified judgments.')
            self.db.execute('INSERT INTO document_drafts VALUES(?,?,?,?,?,?)',(result['draft_id'],workspace_id,request_id,digest(payload),artifact['artifact_id'],encoded(result)))
            return dict(result,text=rendered)
    def read(self,draft_id,viewer=None):
        row=self.db.execute('SELECT * FROM document_drafts WHERE draft_id=?',(draft_id,)).fetchone();require(row is not None,'draft unavailable')
        Registry(self.engine).read(row['workspace_id'],viewer=viewer);result=json.loads(row['result_json'])
        if viewer is not None and result['transfer_trial_id']:
            from ..intelligence.transfer import Transfers
            transfer=Transfers(self.engine).require_qualified(result['transfer_trial_id'],result['workspace_id'],'document',viewer=viewer)
            require(transfer['latest_trial']['trial_id']==result['method_effect']['trial_id'],'draft trial requires revalidation')
        artifact=Artifacts(self.engine).read(row['artifact_id'],viewer=viewer);require(artifact['digest']==result['artifact']['digest'],'draft bytes changed')
        return dict(result,artifact={k:v for k,v in artifact.items() if k!='content'},text=artifact['content'].decode('utf-8'))
