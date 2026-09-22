"""Bounded collective calculations. Node bodies are received, compared and retained.

This is a transparent aggregation policy, not independent agents or semantic
judgment. A configured method must actually execute to supply a ballot.
"""
import json
from pathlib import Path
from uuid import uuid4
from ..engine import require, digest, encoded, Rejected
from ..persistence.unit_of_work import UnitOfWork


def synthesize(contributions):
    """Deduplicate identical calculations; never equate repetitions with sources."""
    bodies=[];ballots=[];sources={};seen=set();receptions=[]
    for value in contributions:
        receipt=value['receipt'];result=value['result'];cid=receipt['contribution_id']
        artifact=result.get('artifact')
        bodies.append({'contribution_id':cid,'node_id':receipt['node_id'],'phase':result['phase'],
                       'body':artifact['content'] if artifact else None,'reasons':result.get('reasons',[])})
        for ref in result.get('binding',{}).get('sources',[]):sources[digest(ref)]=ref
        used=False
        if result['phase']=='completed' and artifact:
            for operation in artifact['content'].get('results',[]):
                ranked=operation['result'].get('ranked',[])
                order=[r['candidate_id'] for r in ranked]
                if not order:continue
                # Participants were validated against the same task. Identical
                # checked outputs count once, regardless of method provenance.
                # This conservative policy can also collapse coincident outputs.
                signature=digest(operation['result'])
                duplicate=signature in seen
                receptions.append({'contribution_id':cid,'receiver':'engine:kageyoni','method_id':operation.get('method_id'),
                                   'calculation_digest':signature,'disposition':'duplicate_calculation' if duplicate else 'used',
                                   'ranked_candidates':order})
                if not duplicate:
                    seen.add(signature);ballots.append({'contribution_id':cid,'order':order});used=True
        if not used and not any(r['contribution_id']==cid for r in receptions):
            receptions.append({'contribution_id':cid,'receiver':'engine:kageyoni','disposition':'not_rankable'})
    disagreements=[]
    for i,a in enumerate(ballots):
        for b in ballots[i+1:]:
            if a['order']!=b['order']:
                disagreements.append({'left':a['contribution_id'],'right':b['contribution_id'],
                                      'left_order':a['order'],'right_order':b['order'],'resolution':'preserved; equal-weight rank aggregation'})
    # Intersection prevents a node from winning by dropping difficult options.
    shared=set(ballots[0]['order']) if ballots else set()
    for b in ballots:shared.intersection_update(b['order'])
    ranked=sorted(({'candidate_id':c,'rank_sum':sum(b['order'].index(c) for b in ballots)} for c in shared),
                  key=lambda r:(r['rank_sum'],r['candidate_id']))
    return {'phase':'completed' if ranked else 'blocked','outcome':'synthesized' if ranked else 'no_eligible_contribution',
            'reason':None if ranked else 'No executable ranking with shared candidates; configure a qualified method or resolve its handoff.',
            'policy':'equal-rank-sum-v1; exact duplicate calculations count once; lexical tie break',
            'bodies':bodies,'receptions':receptions,'disagreements':disagreements,'ranked':ranked,
            'selected':ranked[0]['candidate_id'] if ranked else None,
            'source_ancestry':[sources[k] for k in sorted(sources)],'unique_source_snapshots':len(sources),
            'independent_corroboration':'not_established','unique_calculations':len(ballots),
            'objective_scope':'registered_rank_aggregation','task_objective':'unresolved',
            'cost':{'contributions_attempted':len(contributions),'rank_calculations_consumed':len(ballots)}}


class Network:
    def __init__(self,engine):self.engine=engine;self.db=engine.db
    def _installed(self):
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='network_interface' AND version='1'").fetchone(),'network interface not installed')
    def run(self,branch,request_id,participants,viewer=None,workspace_id=None):
        self._installed()
        self.engine.branch(branch)
        require(workspace_id in (None,'world:'+branch),'destination contributions require compose with qualified document drafts')
        require(isinstance(request_id,str) and 0<len(request_id)<=256,'request_id required')
        require(isinstance(participants,list) and len(participants)<=16,'at most 16 participants')
        require(all(isinstance(p,dict) and set(p)=={'character_id','task'} for p in participants),'participant requires character_id and task')
        require(all(isinstance(p['task'],dict) for p in participants),'participant task must be an object')
        ids=[p['character_id'] for p in participants]
        require(all(isinstance(x,str) and x for x in ids) and len(set(ids))==len(ids),'distinct character participants required')
        # Every node receives the identical problem; method_ids may vary.
        problems=[{k:v for k,v in p['task'].items() if k!='method_ids'} for p in participants]
        require(not problems or all(encoded(t)==encoded(problems[0]) for t in problems),'participants must address the same task')
        payload=dict(branch=branch,request_id=request_id,participants=participants,viewer=viewer,workspace_id=workspace_id)
        require(len(encoded(payload))<=2000000,'network request too large')
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT * FROM collective_runs WHERE request_id=?',(request_id,)).fetchone()
            if old:
                result=self.read(branch,old['run_id'],viewer=viewer)
                require(old['request_hash']==digest(payload),'request key reused with different payload')
                return dict(result,replayed=True)
            from ..persistence.contributions import Contributions
            service=Contributions(self.engine);values=[]
            for p in participants:
                child='network:'+digest({'request_id':request_id,'character_id':p['character_id']})
                receipt=service.run(branch,p['character_id'],child,p['task'],viewer=viewer,workspace_id=workspace_id)
                values.append(service.read(branch,receipt['contribution_id'],viewer=viewer))
            result=synthesize(values)
            result.update(network_interface='1',run_id='network-run:'+uuid4().hex,branch=branch,
                          workspace_id=workspace_id or 'world:'+branch,viewer=viewer,request_id=request_id,
                          coordinator={'node_id':'engine:kageyoni','kind':'engine','human_identity':False},
                          contribution_ids=[v['receipt']['contribution_id'] for v in values],replayed=False)
            self.db.execute('INSERT INTO collective_runs VALUES(?,?,?,?,?,?,?,?)',
                            (result['run_id'],request_id,branch,viewer,encoded(payload),digest(payload),encoded(result),digest(result)))
            return result
    def read(self,branch,run_id,viewer=None):
        self._installed()
        with UnitOfWork(self.db):
            row=self.db.execute('SELECT * FROM collective_runs WHERE branch=? AND run_id=?',(branch,run_id)).fetchone()
            require(row is not None and (viewer is None or row['viewer']==viewer),'collective run unavailable')
            value=json.loads(row['result_json']);require(digest(value)==row['result_hash'],'network result hash mismatch')
            from ..persistence.contributions import Contributions
            for cid in value['contribution_ids']:Contributions(self.engine).read(branch,cid,viewer=viewer)
            return value
    def list(self,branch,viewer=None):
        self._installed();out=[]
        for row in self.db.execute('SELECT run_id FROM collective_runs WHERE branch=? ORDER BY rowid',(branch,)):
            try:out.append(self.read(branch,row[0],viewer=viewer))
            except Rejected:continue
        return out
    def compare(self,branch,single_run_id,network_run_id,acceptable_candidates,viewer=None):
        """Measured fixture acceptance + operation counts, not real-world quality."""
        a=self.read(branch,single_run_id,viewer);b=self.read(branch,network_run_id,viewer)
        require(isinstance(acceptable_candidates,list) and acceptable_candidates and all(isinstance(x,str) for x in acceptable_candidates),'explicit acceptance candidates required')
        pa=json.loads(self.db.execute('SELECT request_json FROM collective_runs WHERE run_id=?',(single_run_id,)).fetchone()[0])
        pb=json.loads(self.db.execute('SELECT request_json FROM collective_runs WHERE run_id=?',(network_run_id,)).fetchone()[0])
        require(len(pa['participants'])==1 and len(pb['participants'])>=2,'comparison requires single and multiple nodes')
        require(pa['participants'][0] in pb['participants'] and pa['workspace_id']==pb['workspace_id'],'comparison must retain exact baseline participant/task/workspace')
        return {'single':{'run_id':single_run_id,'accepted':a['selected'] in acceptable_candidates,'selected':a['selected'],'cost':a['cost']},
                'network':{'run_id':network_run_id,'accepted':b['selected'] in acceptable_candidates,'selected':b['selected'],'cost':b['cost']},
                'criterion':{'kind':'operator_supplied_candidate_acceptance','acceptable_candidates':acceptable_candidates},
                'limits':'Observed calculation count and candidate acceptance only; no independent semantic quality, elapsed-time or cognitive-benefit claim.'}
    def compose(self,branch,request_id,workspace_id,draft_ids,synthesis=None,viewer=None):
        """Receive actual qualified destination drafts; host authors any prose synthesis.

        Verbatim excerpts must reach the output. Their interpretation remains an
        attributed operator judgment. Unknowns and disagreements stay attached.
        """
        self._installed()
        require(isinstance(request_id,str) and request_id,'request_id required')
        require(isinstance(draft_ids,list) and 1<=len(draft_ids)<=16 and len(set(draft_ids))==len(draft_ids),'distinct draft ids required')
        from ..workspaces.documents import Documents
        from ..workspaces.registry import Registry
        from ..persistence.artifacts import Artifacts
        payload=dict(branch=branch,request_id=request_id,workspace_id=workspace_id,draft_ids=draft_ids,synthesis=synthesis,viewer=viewer)
        require(len(encoded(payload))<=2000000,'composition too large')
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT * FROM collective_compositions WHERE request_id=?',(request_id,)).fetchone()
            if old:
                result=self.read_composition(branch,old['composition_id'],viewer)
                require(old['request_hash']==digest(payload),'request key reused with different payload')
                return dict(result,replayed=True)
            workspace=Registry(self.engine).read(workspace_id,viewer=viewer)
            require(workspace['branch']==branch,'composition workspace branch mismatch')
            drafts=[Documents(self.engine).read(x,viewer=viewer) for x in draft_ids]
            require(all(d['branch']==branch for d in drafts),'draft branch mismatch')
            require(len({d['node_id'] for d in drafts})>=2,'collective composition requires distinct configured nodes')
            require(all(d.get('transfer_trial_id') and d.get('method_effect') for d in drafts),'qualified destination method contributions required')
            from .transfer import Transfers
            for draft in drafts:
                current=Transfers(self.engine).require_qualified(draft['transfer_trial_id'],draft['workspace_id'],'document',viewer=viewer)
                effect=draft['method_effect'];trial=current['latest_trial']
                require(effect.get('trial_id')==trial['trial_id'] and effect.get('trial_artifact_digest')==trial['artifact_digest'] and effect.get('method_digest')==current['method_digest'],'draft transfer qualification changed; create a new draft')
            bodies=[dict(draft_id=d['draft_id'],node_id=d['node_id'],workspace_id=d['workspace_id'],text=d['text'],
                         source_refs=d['source_refs'],method_effect=d['method_effect'],unknowns=d.get('unknowns',[]),obligations=d.get('obligations',[])) for d in drafts]
            sources={digest(ref):ref for d in drafts for ref in d['source_refs']}
            challenges=[{'left':a['draft_id'],'right':b['draft_id'],'left_method_effect':a['method_effect'],
                         'right_method_effect':b['method_effect'],'resolution':'unresolved; host interpretation required'}
                        for i,a in enumerate(drafts) for b in drafts[i+1:] if a['method_effect']!=b['method_effect']]
            receptions=[{'draft_id':d['draft_id'],'receiver':'engine:kageyoni','disposition':'received','body_digest':digest(d['text'])} for d in drafts]
            artifact=None
            if synthesis is not None:
                require(isinstance(synthesis,dict) and set(synthesis)=={'text','uses','rationale'},'synthesis requires text, uses, rationale')
                require(isinstance(synthesis['text'],str) and synthesis['text'].strip() and isinstance(synthesis['rationale'],str) and synthesis['rationale'].strip(),'authored text and rationale required')
                require(isinstance(synthesis['uses'],list) and len(synthesis['uses'])<=64,'bounded source uses required')
                byid={d['draft_id']:d for d in drafts};used=set()
                for use in synthesis['uses']:
                    require(isinstance(use,dict) and set(use)=={'draft_id','quote'},'source use requires draft_id and quote')
                    quote=use['quote'];did=use['draft_id']
                    require(did in byid and isinstance(quote,str) and len(quote.strip())>=min(32,len(byid[did]['text'].strip())) and quote in byid[did]['text'] and quote in synthesis['text'],'consumed excerpt must contain at least 32 characters (or the entire shorter draft) and occur in exact draft and output')
                    used.add(did)
                require(used==set(draft_ids),'every contribution must reach authored synthesis')
                for reception in receptions:reception['disposition']='consumed_verbatim'
                artifact=Artifacts(self.engine).put(synthesis['text'], 'text/markdown', 'network-artifact:'+request_id,workspace_id=workspace_id,viewer=viewer)
            result=dict(composition_id='composition:'+uuid4().hex,branch=branch,workspace_id=workspace_id,
                        phase='completed' if artifact else 'waiting',outcome='authored_synthesis' if artifact else 'requires_judgment',
                        coordinator={'node_id':'engine:kageyoni','kind':'engine','human_identity':False},
                        bodies=bodies,receptions=receptions,disagreements=challenges,artifact=artifact,
                        source_ancestry=[sources[k] for k in sorted(sources)],independent_corroboration='not_established',
                        judgment_authority='operator',semantic_quality='unverified',
                        pending=None if artifact else {'action':'provide_synthesis','fields':['text','uses','rationale'],'draft_ids':draft_ids},replayed=False)
            self.db.execute('INSERT INTO collective_compositions VALUES(?,?,?,?,?,?,?,?)',
                            (result['composition_id'],request_id,branch,viewer,encoded(payload),digest(payload),encoded(result),digest(result)))
            return result
    def read_composition(self,branch,composition_id,viewer=None):
        self._installed()
        row=self.db.execute('SELECT * FROM collective_compositions WHERE branch=? AND composition_id=?',(branch,composition_id)).fetchone()
        require(row is not None and (viewer is None or row['viewer']==viewer),'composition unavailable')
        result=json.loads(row['result_json']);request=json.loads(row['request_json'])
        require(digest(result)==row['result_hash'] and digest(request)==row['request_hash'],'composition digest mismatch')
        from ..workspaces.documents import Documents
        from ..workspaces.registry import Registry
        from ..persistence.artifacts import Artifacts
        Registry(self.engine).read(request['workspace_id'],viewer=viewer)
        drafts=[Documents(self.engine).read(did,viewer=viewer) for did in request['draft_ids']]
        expected=[dict(draft_id=d['draft_id'],node_id=d['node_id'],workspace_id=d['workspace_id'],text=d['text'],source_refs=d['source_refs'],method_effect=d['method_effect'],unknowns=d.get('unknowns',[]),obligations=d.get('obligations',[])) for d in drafts]
        require(result['bodies']==expected,'composition body ancestry mismatch')
        challenges=[{'left':a['draft_id'],'right':b['draft_id'],'left_method_effect':a['method_effect'],
                     'right_method_effect':b['method_effect'],'resolution':'unresolved; host interpretation required'}
                    for i,a in enumerate(drafts) for b in drafts[i+1:] if a['method_effect']!=b['method_effect']]
        sources={digest(ref):ref for d in drafts for ref in d['source_refs']}
        require(result['disagreements']==challenges and result['source_ancestry']==[sources[k] for k in sorted(sources)],'composition challenge or source ancestry mismatch')
        authored=request['synthesis'] is not None
        receptions=[{'draft_id':d['draft_id'],'receiver':'engine:kageyoni','disposition':'consumed_verbatim' if authored else 'received','body_digest':digest(d['text'])} for d in drafts]
        require(result['receptions']==receptions and bool(result['artifact'])==authored and result['phase']==('completed' if authored else 'waiting'),'composition reception or disposition mismatch')
        if authored:
            byid={d['draft_id']:d for d in drafts};used=set()
            for use in request['synthesis']['uses']:
                did=use['draft_id'];quote=use['quote']
                require(did in byid and isinstance(quote,str) and len(quote.strip())>=min(32,len(byid[did]['text'].strip())) and quote in byid[did]['text'] and quote in request['synthesis']['text'],'composition consumption mismatch')
                used.add(did)
            require(used==set(request['draft_ids']),'composition missing received body')

        if result['artifact']:
            actual=Artifacts(self.engine).read(result['artifact']['artifact_id'],viewer=viewer)
            require(actual['content'].decode('utf-8')==request['synthesis']['text'] and actual['digest']==result['artifact']['digest'],'composition artifact mismatch')
            result['artifact']={k:v for k,v in actual.items() if k!='content'}
        return result
    def coordination_lessons(self,branch,viewer=None):
        self._installed()
        require(viewer is None,'owner required to inspect engine coordination lessons')
        results=[]
        for row in self.db.execute('SELECT * FROM coordination_lessons WHERE branch=? ORDER BY rowid',(branch,)):
            result=json.loads(row['result_json']);require(digest(result)==row['result_hash'],'coordination lesson digest mismatch')
            results.append(result)
        return results
    def record_coordination_lesson(self,branch,request_id,single_run_id,network_run_id,acceptable_candidates,rationale,status='proposed',viewer=None):
        self._installed()
        require(viewer is None,'owner required to review coordination lessons')
        require(status in ('proposed','qualified','rejected'),'invalid lesson status')
        require(isinstance(request_id,str) and request_id and isinstance(rationale,str) and rationale.strip(),'request and rationale required')
        payload=dict(branch=branch,request_id=request_id,single_run_id=single_run_id,network_run_id=network_run_id,
                     acceptable_candidates=acceptable_candidates,rationale=rationale,status=status)
        with UnitOfWork(self.db):
            old=self.db.execute('SELECT * FROM coordination_lessons WHERE request_id=?',(request_id,)).fetchone()
            if old:
                require(old['payload_hash']==digest(payload),'request key reused with different payload')
                return dict(json.loads(old['result_json']),replayed=True)
            comparison=self.compare(branch,single_run_id,network_run_id,acceptable_candidates)
            if status=='qualified':require(comparison['network']['accepted'] and not comparison['single']['accepted'],'qualification requires observed candidate acceptance improvement')
            value=dict(lesson_id='coordination-lesson:'+uuid4().hex,node_id='engine:kageyoni',kind='engine',status=status,
                       comparison=comparison,rationale=rationale,review_authority='operator',automatic_policy_change=False,
                       scope={'branch':branch,'single_run_id':single_run_id,'network_run_id':network_run_id},replayed=False)
            self.db.execute('INSERT INTO coordination_lessons VALUES(?,?,?,?,?,?,?)',(value['lesson_id'],request_id,branch,encoded(payload),digest(payload),encoded(value),digest(value)))
            return value


def verify_network(engine):
    import hashlib
    db=engine.db
    if not db.execute("SELECT 1 FROM engine_versions WHERE component='network_interface'").fetchone():return {'installed':False}
    from ..resources import schema_path
    path=schema_path('migration_015.sql')
    row=db.execute('SELECT checksum FROM migration_checks WHERE version=15').fetchone()
    require(row and row[0]==hashlib.sha256(path.read_bytes()).hexdigest(),'network migration checksum mismatch')
    from ..persistence.contributions import Contributions
    identity=db.execute('SELECT * FROM coordination_nodes').fetchall()
    require(len(identity)==1 and identity[0]['node_id']=='engine:kageyoni' and identity[0]['kind']=='engine' and json.loads(identity[0]['roles_json'])==['receive','challenge','synthesize','observe'],'coordination identity mismatch')
    n=0
    for row in db.execute('SELECT * FROM collective_runs'):
        request=json.loads(row['request_json']);result=json.loads(row['result_json'])
        require(digest(request)==row['request_hash'] and digest(result)==row['result_hash'],'network digest mismatch')
        require(result['run_id']==row['run_id'] and request['request_id']==row['request_id']==result['request_id'] and request['branch']==row['branch']==result['branch'] and request['viewer']==row['viewer']==result['viewer'],'network scope mismatch')
        require(result['workspace_id']==(request['workspace_id'] or 'world:'+row['branch']) and result['coordinator']=={'node_id':'engine:kageyoni','kind':'engine','human_identity':False},'network workspace or coordinator mismatch')
        values=[Contributions(engine).read(row['branch'],cid) for cid in result['contribution_ids']]
        calculated=synthesize(values)
        require(all(result.get(k)==v for k,v in calculated.items()),'network synthesis mismatch')
        require(len(values)==len(request['participants']),'network participant ancestry mismatch')
        for p,v in zip(request['participants'],values):
            child=db.execute('SELECT request_json FROM contributions WHERE contribution_id=?',(v['receipt']['contribution_id'],)).fetchone()
            cp=json.loads(child[0]);require(cp['character_id']==p['character_id'] and cp['task']==p['task'] and cp['viewer']==request['viewer'] and cp['workspace_id']==request['workspace_id'],'network input ancestry mismatch')
        n+=1
    for row in db.execute('SELECT * FROM coordination_lessons'):
        p=json.loads(row['payload_json']);r=json.loads(row['result_json'])
        require(digest(p)==row['payload_hash'] and digest(r)==row['result_hash'],'coordination lesson digest mismatch')
        require(p['request_id']==row['request_id'] and p['branch']==row['branch'] and r['lesson_id']==row['lesson_id'],'coordination lesson identity mismatch')
        c=Network(engine).compare(p['branch'],p['single_run_id'],p['network_run_id'],p['acceptable_candidates'])
        require(c==r['comparison'] and p['status']==r['status'] and p['rationale']==r['rationale'] and r['automatic_policy_change'] is False,'coordination lesson observation mismatch')
        require(r['status']!='qualified' or (c['network']['accepted'] and not c['single']['accepted']),'unsupported coordination qualification')
    for row in db.execute('SELECT * FROM collective_compositions'):
        request=json.loads(row['request_json']);result=json.loads(row['result_json'])
        require(digest(request)==row['request_hash'] and digest(result)==row['result_hash'],'composition digest mismatch')
        require(result['composition_id']==row['composition_id'] and request['request_id']==row['request_id'] and request['branch']==row['branch']==result['branch'],'composition identity mismatch')
        Network(engine).read_composition(row['branch'],row['composition_id'])
    return {'installed':True,'runs':n,'lessons':db.execute('SELECT count(*) FROM coordination_lessons').fetchone()[0],'interface':'1'}
