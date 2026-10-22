"""Operator lifecycle for one reviewed, installed support composition.

No entry point is imported or executed from metadata. Native property effects,
resources and events remain authoritative; these rows pin admission and endings.
"""
import hashlib
import json
from importlib.resources import files
from .protocol import Fault,digest,encoded
from .properties import CAPACITY

EXT='fixture:support-extension'
SOURCE='fixture:support-extension-source'
ENDING='fixture:ending:lower-load'


class Extensions:
    def __init__(self,app):
        self.app,self.engine,self.db,self.ws=app,app.engine,app.db,app.workspace_id

    def operator(self,context):
        if context.role!='operator':raise Fault('UNAVAILABLE')

    def reference(self,version):
        return {'id':EXT,'version':version,'digest':digest([self.app.property_runtime_digest,EXT,version])}

    def ending_spec(self):
        return {'handler':ENDING,'installed_module':'samsara.properties',
            'code_sha256':hashlib.sha256(files('samsara').joinpath('properties.py').read_bytes()).hexdigest(),
            'data':{'destination':'studio','availability':'on the studio floor','history':'retain accepted native events'},
            'call':'Properties.end / Properties.release; known installed code only'}

    def asset(self):
        expected=self.ending_spec();sha=digest(expected)
        row=self.db.execute('SELECT * FROM extension_assets WHERE workspace_id=? AND asset_id=? AND digest=?',(self.ws,ENDING,sha)).fetchone()
        if not row or not row['available'] or json.loads(row['content_json'])!=expected:raise Fault('DEPENDENCY')
        return {'id':ENDING,'digest':sha}

    def source(self,context):
        row=self.app.properties.entity(context,SOURCE)
        if row['visibility']!='public':raise Fault('DEPENDENCY')
        return {'id':SOURCE,'version':row['version'],'digest':digest(row)}

    def catalog(self,context,version):
        self.operator(context)
        stored=self.db.execute('SELECT state,manifest_digest,manifest_json FROM extension_versions WHERE workspace_id=? AND extension_id=? AND version=?',(self.ws,EXT,version)).fetchone()
        captured=json.loads(stored['manifest_json']) if stored else None
        return {'kind':'extension_catalog','definition':self.reference(version),'class':'composition',
            'consumer_refs':captured['consumer_refs'] if captured else [self.app.properties.consumer_ref()],
            'ending_handler':self.app.properties.ref(ENDING),
            'check_refs':[self.app.properties.ref('fixture:support-extension:checks')],
            'boundary':'checkpoint','pending_policies':['drain','cancel_and_reconcile'],
            'candidate_digest':stored['manifest_digest'] if stored else None,'status':stored['state'] if stored else 'absent'}

    def manifest(self,context,op):
        if op['definition']!=self.reference(op['definition']['version']):raise Fault('DEPENDENCY')
        catalog=self.catalog(context,op['definition']['version'])
        if op['class']!='composition' or op['boundary']!='checkpoint':raise Fault('UNSUPPORTED')
        for key in ('consumer_refs','ending_handler','check_refs'):
            if op[key]!=catalog[key]:raise Fault('DEPENDENCY')
        if op['consumer_refs']!=[self.app.properties.consumer_ref()]:raise Fault('DEPENDENCY')
        if not self.engine.validate_registry()['ok']:raise Fault('DEPENDENCY')
        return {k:op[k] for k in ('definition','class','consumer_refs','ending_handler','check_refs','pending_policy','boundary')}|{
            'source':self.source(context),'ending_asset':self.asset(),
            'property_definition_digest':digest(dict(self.engine._definition(CAPACITY,1))),
            'compatibility':'Same installed capacity replace and native support consumer; no executable discovery.',
            'consumers':['prepared property overrides','active property effects','maintained native support resources'],
            'issued_worker_or_causal_handlers':[]}

    def row(self,definition):
        if definition['id']!=EXT:raise Fault('UNAVAILABLE')
        row=self.db.execute('SELECT * FROM extension_versions WHERE workspace_id=? AND extension_id=? AND version=?',(self.ws,EXT,definition['version'])).fetchone()
        if not row:raise Fault('UNAVAILABLE')
        if json.loads(row['manifest_json'])['definition']!=definition:raise Fault('CONFLICT')
        return dict(row)

    def pending(self,version):
        changes=[dict(r) for r in self.db.execute('''SELECT c.* FROM property_change_sets c JOIN extension_pins p
            ON p.workspace_id=c.workspace_id AND p.reference_id=c.change_id AND p.kind='change'
            WHERE p.workspace_id=? AND p.extension_id=? AND p.version=? AND c.status IN ('prepared','active')''',(self.ws,EXT,version))]
        supports=[dict(r) for r in self.db.execute('''SELECT s.* FROM property_support_bindings s JOIN extension_pins p
            ON p.workspace_id=s.workspace_id AND p.reference_id=s.support_id AND p.kind='support'
            WHERE p.workspace_id=? AND p.extension_id=? AND p.version=? AND s.active=1''',(self.ws,EXT,version))]
        return changes,supports

    def view(self,context,definition,sha):
        self.operator(context);row=self.row(definition)
        if row['manifest_digest']!=sha:raise Fault('CONFLICT')
        changes,supports=self.pending(row['version'])
        preview=json.loads(row['preview_ref_json']);capsule=json.loads(row['capsule_ref_json'])
        self.app.artifact_bytes(context,preview);self.app.artifact_bytes(context,capsule)
        return {'kind':'extension','definition':definition,'candidate_digest':sha,'status':row['state'],
            'boundary':'checkpoint','preview_ref':preview,'ending_capsule_ref':capsule,
            'ending_trace_ref':json.loads(row['ending_trace_ref_json']) if row['ending_trace_ref_json'] else None,
            'pending_changes':[x['change_id'] for x in changes],'maintained_supports':[x['support_id'] for x in supports]}

    def prepare(self,context,op):
        self.operator(context);manifest=self.manifest(context,op);sha=digest(manifest);version=op['definition']['version']
        prior=self.db.execute('SELECT * FROM extension_versions WHERE workspace_id=? AND extension_id=? AND version=?',(self.ws,EXT,version)).fetchone()
        if prior:
            if prior['manifest_digest']!=sha:raise Fault('CONFLICT')
            if prior['state']=='prepared' and prior['prepared_revision']!=self.app.revision():raise Fault('STALE')
            return self.view(context,op['definition'],sha)
        latest=self.db.execute('SELECT max(version) FROM extension_versions WHERE workspace_id=? AND extension_id=?',(self.ws,EXT)).fetchone()[0] or 0
        if version!=latest+1 or version>32:raise Fault('CONFLICT')
        active=self.db.execute("SELECT version FROM extension_versions WHERE workspace_id=? AND extension_id=? AND state='active'",(self.ws,EXT)).fetchone()
        changes,supports=self.pending(active[0]) if active else ([],[])
        capsule=self.app.put_json({'manifest':manifest,'ending':self.ending_spec(),
            'retention':'Keep installed code/hash/data and capsule while any consumer pin remains.'},
            self.app.key('extension-capsule',version,sha))
        preview=self.app.put_json({'definition':op['definition'],'manifest':manifest,'prior_active_version':active[0] if active else None,
            'pending_disposition':op['pending_policy'],'prepared_changes':[x['change_id'] for x in changes if x['status']=='prepared'],
            'maintained_effects':[x['change_id'] for x in changes if x['status']=='active'],'maintained_supports':[x['support_id'] for x in supports],
            'effect':'Future admissions select this installed composition; existing active loads retain their old callable endings.'},
            self.app.key('extension-preview',version,sha))
        self.db.execute('INSERT INTO extension_versions VALUES(?,?,?,?,?,?,?,?,?,NULL,NULL)',
            (self.ws,EXT,version,'prepared',self.app.revision(),encoded(manifest),sha,encoded(capsule),encoded(preview)))
        return self.view(context,op['definition'],sha)

    def validate_ending(self,version):
        row=self.db.execute('SELECT * FROM extension_versions WHERE workspace_id=? AND extension_id=? AND version=?',(self.ws,EXT,version)).fetchone()
        if not row:raise Fault('DEPENDENCY')
        manifest=json.loads(row['manifest_json'])
        if self.asset()!=manifest['ending_asset']:raise Fault('DEPENDENCY')
        ref=json.loads(row['capsule_ref_json'])
        content=self.app.services.artifacts.read(ref['id'],viewer=None)
        if content['digest']!=ref['digest'] or json.loads(content['content'])!={'manifest':manifest,'ending':self.ending_spec(),
            'retention':'Keep installed code/hash/data and capsule while any consumer pin remains.'}:raise Fault('DEPENDENCY')
        return dict(row)

    def require_new_use(self,context):
        row=self.db.execute("SELECT * FROM extension_versions WHERE workspace_id=? AND extension_id=? AND state='active'",(self.ws,EXT)).fetchone()
        if not row:raise Fault('DEPENDENCY')
        manifest=json.loads(row['manifest_json']);self.validate_ending(row['version'])
        if self.source(context)!=manifest['source'] or self.app.properties.consumer_ref() not in manifest['consumer_refs'] or digest(dict(self.engine._definition(CAPACITY,1)))!=manifest['property_definition_digest']:raise Fault('DEPENDENCY')
        return dict(row)

    def pin(self,context,kind,reference):
        row=self.require_new_use(context)
        self.db.execute('INSERT INTO extension_pins VALUES(?,?,?,?,?)',(self.ws,kind,reference,EXT,row['version']))

    def ending_for(self,kind,reference):
        pin=self.db.execute('SELECT version FROM extension_pins WHERE workspace_id=? AND kind=? AND reference_id=?',(self.ws,kind,reference)).fetchone()
        if pin:self.validate_ending(pin[0])

    def apply_pin(self,context,cid):
        pin=self.db.execute("SELECT version FROM extension_pins WHERE workspace_id=? AND kind='change' AND reference_id=?",(self.ws,cid)).fetchone()
        if pin and self.require_new_use(context)['version']!=pin[0]:raise Fault('DEPENDENCY')

    def captured_consumers(self,cid):
        row=self.db.execute("""SELECT e.manifest_json FROM extension_pins p JOIN extension_versions e
            ON e.workspace_id=p.workspace_id AND e.extension_id=p.extension_id AND e.version=p.version
            WHERE p.workspace_id=? AND p.kind='change' AND p.reference_id=?""",(self.ws,cid)).fetchone()
        return json.loads(row[0])['consumer_refs'] if row else None

    def persist(self,version,state,event):
        self.db.execute('UPDATE extension_versions SET state=?,last_event=coalesce(?,last_event) WHERE workspace_id=? AND extension_id=? AND version=?',(state,event,self.ws,EXT,version))

    def control(self,context,op):
        self.operator(context);row=self.row(op['definition'])
        if row['manifest_digest']!=op['candidate_digest']:raise Fault('CONFLICT')
        if op['replacement'] is not None:raise Fault('UNSUPPORTED')
        action=op['name'].split('.')[1]
        if action=='preview':return self.view(context,op['definition'],op['candidate_digest'])
        changes,supports=self.pending(row['version']);manifest=json.loads(row['manifest_json'])
        if action=='delete':
            if changes or supports or row['state']!='retired':raise Fault('DEPENDENCY')
            raise Fault('UNSUPPORTED')  # Append-only history is retained; no purge claim.
        if action=='replace':raise Fault('UNSUPPORTED')
        target={'activate':'active','disable':'disabled','retire':'retired'}[action]
        previous_active=None
        if row['state']==target:return self.view(context,op['definition'],op['candidate_digest'])
        if row['state']=='retired':raise Fault('DEPENDENCY')
        if action=='activate':
            if row['state']!='prepared':raise Fault('DEPENDENCY')
            if row['prepared_revision']!=self.app.revision():raise Fault('STALE')
            proposal={k:manifest[k] for k in ('definition','class','consumer_refs','ending_handler','check_refs','pending_policy','boundary')}
            if self.manifest(context,proposal)!=manifest:raise Fault('DEPENDENCY')
            active=self.db.execute("SELECT version FROM extension_versions WHERE workspace_id=? AND extension_id=? AND state='active'",(self.ws,EXT)).fetchone()
            if active:
                previous_active=active[0]
                older,_=self.pending(active[0]);prepared=[x for x in older if x['status']=='prepared']
                if prepared and manifest['pending_policy']=='drain':raise Fault('DEPENDENCY')
                for change in prepared:self.app.properties.withdraw(context,{'change_id':change['change_id'],'digest':change['proposal_digest'],'boundary':'checkpoint'})
                self.persist(active[0],'disabled',row['last_event'])
        if action=='retire':
            if (changes or supports) and manifest['pending_policy']=='drain':raise Fault('DEPENDENCY')
            if changes or supports:self.validate_ending(row['version'])
            for change in changes:self.app.properties.withdraw(context,{'change_id':change['change_id'],'digest':change['proposal_digest'],'boundary':'checkpoint'})
            for support in supports:self.app.properties.release(context,support['support_id'])
        # Configuration/maintenance is recorded without inventing a fictional
        # consequence record. Actual ending effects use native resource events.
        event=self.engine.apply({'api_version':3,'branch':self.app.branch,
            'request_id':self.app.key('extension-event',self.ws,row['version'],action,row['manifest_digest']),
            'expected_revision':self.app.revision(),'actor':context.character_id or 'fixture','kind':'maintenance',
            'narrative':f'{action.capitalize()} installed synthetic support configuration at an explicit checkpoint; this is not a fictional event.',
            'changes':[],
            'dependencies':[{'kind':'record','ref_id':manifest['source']['id'],
                'version':manifest['source']['version'],'usage':'configuration basis'}]})
        if previous_active is not None:self.persist(previous_active,'disabled',event['event_id'])
        self.persist(row['version'],target,event['event_id'])
        if action=='retire':
            trace={'definition':op['definition'],'state':'retired','event':event,'ended_changes':[x['change_id'] for x in changes],
                'lowered_supports':[x['support_id'] for x in supports],'history':'Earlier accepted native events and exact input traces remain.',
                'resources_after':[self.engine.get(self.app.branch,x['resource_id']) for x in supports]}
            subjects={x['entity_id'] for x in supports}
            for change in changes:subjects.update(json.loads(change['proposal_json'])['targets'])
            scope=[(SOURCE,None,None)]+[(eid,CAPACITY,1) for eid in sorted(subjects)]
            ref=self.app.properties.artifact(context,trace,('extension-ending',row['version'],event['event_id']),scope,recipient='visitor')
            self.app.grant(ref,'character:keeper')
            self.db.execute('UPDATE extension_versions SET ending_trace_ref_json=? WHERE workspace_id=? AND extension_id=? AND version=?',(encoded(ref),self.ws,EXT,row['version']))
            return self.view(context,op['definition'],op['candidate_digest'])
        return self.view(context,op['definition'],op['candidate_digest'])

    def initialize(self,context):
        spec=self.ending_spec();self.db.execute('INSERT INTO extension_assets VALUES(?,?,?,?,1)',(self.ws,ENDING,digest(spec),encoded(spec)))
        catalog=self.catalog(context,1)
        op={k:catalog[k] for k in ('definition','class','consumer_refs','ending_handler','check_refs','boundary')}
        op.update(name='extension.prepare',pending_policy='cancel_and_reconcile')
        ready=self.prepare(context,op)
        self.control(context,{'name':'extension.activate','definition':ready['definition'],'candidate_digest':ready['candidate_digest'],'replacement':None})
