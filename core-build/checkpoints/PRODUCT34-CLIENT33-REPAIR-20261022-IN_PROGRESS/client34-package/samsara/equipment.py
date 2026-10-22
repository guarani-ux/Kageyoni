"""Explicit public own-equipment release through the ordinary native seam.

No content activation changes a retained loadout. A separately chosen native
release makes room before a later optional equipment exchange.
"""
import json
import hashlib
from copy import deepcopy
from kageyoni.workspaces.world import _expand, _validate
from .protocol import Fault, digest
from .situation import reference

KIND='samsara_equipment'
EVIDENCE=[{'note':'New synthetic participant equipment choice, not inherited history, skill or an automatic consequence of content admission.'}]

class Equipment:
    def __init__(self,app):
        self.app,self.engine,self.db=app,app.engine,app.db

    def _compile(self,snapshot):
        actor=snapshot['actor']['id'];loadout=snapshot['loadout']['id']
        did='synthetic:equipment:'+digest([self.app.workspace_id,snapshot])
        req=[{'record_id':loadout,'field':'holder','equals':actor},
             {'record_id':loadout,'field':'equipped','equals':1},
             {'record_id':actor,'field':'location','equals':snapshot['location']}]
        def action(label,state,changes):
            return {'label':label,'actor_role':'holder','kind':'event','payload':{'changes':changes},'next_state':state,'resolve_loops':[],'requirements':deepcopy(req)}
        spec={'title':'Put down an equipped item, or keep holding it','roles':['holder'],'visibility':'public','initial_state':'choice','max_steps':2,'loops':[],
            'states':{'choice':{'phase':'active','outcome':'unresolved','actions':['release','keep']},
                      'released':{'phase':'completed','outcome':'achieved','actions':[]},
                      'kept':{'phase':'completed','outcome':'not_achieved','actions':[]}},
            'actions':{'release':action('Put down '+snapshot['item_name']+'; do not equip a replacement.','released',[
                {'op':'patch','id':loadout,'expected_version':snapshot['loadout']['version'],'data':{'equipped':0},'evidence':EVIDENCE}]),
                'keep':action('Keep holding the item; no equipment change.','kept',[{'op':'create','id':{'$encounter':'kept-choice'},'domain':'historical_account','data':{'author':actor,'assertion':'I chose to keep holding '+snapshot['item_name']+' without equipping a replacement.'},'status':'reported','visibility':'public','evidence':EVIDENCE}])},
            'ending':{'label':'Leave equipment as last accepted; no automatic swap.','next_state':'kept','changes':[]}}
        value={'id':did,'version':1,'title':spec['title'],'kind':'life','handler':'encounter','participants':[actor],
            'start_location':snapshot['location'],'role_bindings':{'holder':actor},'encounter':_validate(spec),
            'action_scope_ids':{a:[actor,loadout,snapshot['item']['id']] for a in ('release','keep','__end__')}}
        value['reference']={'id':did,'version':1,'digest':digest(value)};return value

    def prepare(self,context,op,request_id):
        self.app.authorize(context)
        if context.role=='worker':raise Fault('UNAVAILABLE')
        actor=op.get('actor_id') if context.role=='operator' else context.character_id
        if not actor or (context.role!='operator' and op.get('actor_id') not in (None,actor)) or not self.app.content_sets.actor_admitted(actor):raise Fault('UNAVAILABLE')
        if self.db.execute('SELECT 1 FROM activity_runs WHERE workspace_id=? AND activity_id=?',(self.app.workspace_id,op['activity_id'])).fetchone():raise Fault('CONFLICT')
        records=self.app.situation.visible(actor);own=records.get(actor);row=records.get(op['loadout_ref']['id'])
        if not own or not row or row['domain']!='loadout' or reference(row)!=op['loadout_ref'] or row['data'].get('holder')!=actor or row['data'].get('equipped')!=1:raise Fault('UNAVAILABLE')
        item=records.get(row['data'].get('item'))
        # This additive lane exposes no private native equipment to future choosers.
        if not item or row['visibility']!='public' or item['visibility']!='public':raise Fault('UNAVAILABLE')
        self.app.exploration.movement_clear([actor])
        snapshot={'actor':reference(own),'loadout':reference(row),'item':reference(item),'item_name':item['data']['name'],'location':own['data']['location']}
        wrapper=self._compile(snapshot);stable=self.app.key(self.app.workspace_id,wrapper['id']);payload={'workspace_id':self.app.workspace_id,'snapshot':snapshot,'wrapper':wrapper};sha=digest(payload)
        old=self.db.execute('SELECT * FROM registry_entries WHERE kind=? AND stable_id=? AND version=?',(KIND,stable,'1')).fetchone()
        if old:
            if old['source_hash']!=sha:raise Fault('CONFLICT')
            self.reload()
        else:
            if self.db.execute('SELECT 1 FROM encounter_definitions WHERE definition_id=? AND version=1',(wrapper['id'],)).fetchone():raise Fault('CONFLICT')
            self.app.services.encounters.define(wrapper['id'],1,wrapper['encounter'],self.app.key('equipment-definition',wrapper['id']),viewer=None)
            ref=self.app.put_json(payload,self.app.key('equipment-wrapper',wrapper['id']),['operator:'+str(__import__('os').getuid())],private_viewer='operator:'+str(__import__('os').getuid()))
            self.engine.register_component(KIND,stable,'1',json.dumps({'workspace_id':self.app.workspace_id,'artifact_ref':ref},sort_keys=True),status='verified',readers=['Samsara.Equipment'],writers=['Samsara.Equipment'],compatibility={'format':'samsara_equipment/1'},source_hash=sha,declared_by='Samsara.Equipment')
            self.app.catalog[wrapper['id']]=wrapper
        return {'name':'activity.start','activity_id':op['activity_id'],'kind':'life','definition':wrapper['reference'],'parent_id':op.get('parent_id'),'participants':[actor],'purpose':None,'source_refs':[],'acceptance_ref':'native:encounter/1'}

    def reload(self):
        for key in list(self.app.catalog):
            if key.startswith('synthetic:equipment:'):self.app.catalog.pop(key)
        for row in self.db.execute('SELECT * FROM registry_entries WHERE kind=?',(KIND,)):
            locator=json.loads(row['locator'])
            if locator['workspace_id']!=self.app.workspace_id:continue
            ref=locator['artifact_ref'];meta=self.app.services.artifacts.read(ref['id'],viewer=None)
            if (ref['version']!=1 or meta['digest']!=ref['digest'] or hashlib.sha256(meta['content']).hexdigest()!=ref['digest'] or not (self.app.artifact_audience(ref) or '').startswith('operator:') or row['status']!='verified'):raise Fault('DEPENDENCY')
            grants=self.db.execute('SELECT principal_id FROM activity_artifact_grants WHERE workspace_id=? AND artifact_id=?',(self.app.workspace_id,ref['id'])).fetchall()
            if any(not g['principal_id'].startswith('operator:') for g in grants):raise Fault('DEPENDENCY')
            payload=json.loads(meta['content'])
            if payload['workspace_id']!=self.app.workspace_id or digest(payload)!=row['source_hash']:raise Fault('DEPENDENCY')
            wrapper=self._compile(payload['snapshot'])
            if wrapper!=payload['wrapper'] or row['stable_id']!=self.app.key(self.app.workspace_id,wrapper['id']):raise Fault('DEPENDENCY')
            native=self.app.services.encounters._definition(wrapper['id'],1)
            if native!=_validate(wrapper['encounter']):raise Fault('DEPENDENCY')
            self.app.catalog[wrapper['id']]=wrapper

    def guard(self,activity,action_id):
        definition=self.app.catalog[activity['spec']['definition']['id']]
        if definition['id'] not in self.app.content_sets.definitions and not definition['id'].startswith('synthetic:equipment:'):return
        expanded=_expand(definition['encounter'],self.app.exploration.bindings(definition,activity['spec']['participants']),activity['native']['encounter_id'])
        changes=expanded['actions'].get(action_id,{}).get('payload',{}).get('changes',[])
        loadouts={r[0]:deepcopy(self.engine.get(self.app.branch,r[0])['data']) for r in self.db.execute("SELECT id FROM records WHERE branch=? AND domain='loadout'",(self.app.branch,))}
        # A handoff affects both custodians. Checking only the old holder lets
        # an otherwise free donor alter a recipient's live practice inventory.
        # Keep the complete post-image for native slot/item constraints too.
        touched=set()
        if not isinstance(changes,list) or any(not isinstance(c,dict) or not isinstance(c.get('id'),str) for c in changes):raise Fault('INVALID')
        created={c.get('id'):c.get('domain') for c in changes
                 if c.get('op')=='create' and isinstance(c.get('id'),str)}
        for c in changes:
            identity=c.get('id');operation=c.get('op')
            is_loadout=identity in loadouts or c.get('domain')=='loadout'
            if not is_loadout:continue
            if operation not in ('create','patch'):
                # The native engine has no deletion event. Do not pretend a
                # deletion frees a slot or bypasses the owner's live-use guard.
                raise Fault('UNSUPPORTED')
            data=c.get('data')
            if not isinstance(data,dict):raise Fault('INVALID')
            if operation=='patch':
                if identity not in loadouts or c.get('domain','loadout')!='loadout':raise Fault('DEPENDENCY')
                touched.add(loadouts[identity].get('holder'))
                loadouts[identity].update(deepcopy(data))
            else:
                if identity in loadouts:raise Fault('CONFLICT')
                loadouts[identity]=deepcopy(data)
            touched.add(loadouts[identity].get('holder'))
        if not touched:return
        # References may be introduced by the same admitted native event, but
        # a free-form item/holder string is never custody or actor authority.
        def domain(identity):
            if not isinstance(identity,str) or not identity:raise Fault('DEPENDENCY')
            row=self.engine.get(self.app.branch,identity)
            return row['domain'] if row else created.get(identity)
        for holder in touched:
            if domain(holder) not in ('character','faction','location'):raise Fault('DEPENDENCY')
        self.app.exploration.movement_clear(touched)
        slots=set();items=set()
        for data in loadouts.values():
            if domain(data.get('holder')) not in ('character','faction','location') or domain(data.get('item'))!='item':raise Fault('DEPENDENCY')
            # Native one_item_holder applies even to unequipped inventory.
            item=data['item']
            if item in items:raise Fault('DEPENDENCY')
            items.add(item)
            if data.get('equipped')!=1:continue
            slot=(data['holder'],data.get('slot'))
            if slot in slots:raise Fault('DEPENDENCY')
            slots.add(slot)
