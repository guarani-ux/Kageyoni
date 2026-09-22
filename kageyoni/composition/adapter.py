from __future__ import annotations
from typing import Any
from ..engine import digest, require

DOMAIN_MAP = {
    'character': ('entity','actor'),
    'scene': ('situational','situation'),
    'location': ('environmental','location'),
    'environment': ('environmental','environment'),
    'world_rule': ('governing','world_rule'),
    'arc': ('governing','arc_pressure'),
    'relationship': ('relational','relationship_state'),
    'knowledge': ('epistemic','knowledge_state'),
    'will': ('configuration','orientation'),
    'ability': ('configuration','capability'),
    'capability': ('configuration','capability'),
    'experience': ('history','experience'),
    'historical_account': ('history','event'),
}

class EngineAspectAdapter:
    """Read-only bridge from v9.5 records into v10 Aspect packets."""
    def __init__(self, engine, branch='main'): self.engine=engine; self.branch=branch
    def record_aspect(self, record_id: str, *, compatible_slots=None, authority='mechanical') -> dict[str,Any]:
        r=self.engine.get(self.branch,record_id); require(r is not None,'aspect source record missing')
        require(r['domain'] in DOMAIN_MAP,f"record domain {r['domain']!r} has no composition mapping")
        family, typ=DOMAIN_MAP[r['domain']]
        
        owner = r['data'].get('bearer') or r['data'].get('holder') or r['data'].get('character')
        return {'aspect_id':f"record:{record_id}", 'type':typ,'family':family,'authority':authority,
                'compatible_slots':list(compatible_slots or []), 'properties':{'record_id':record_id,'domain':r['domain'],'status':r['status'],'data':r['data']},
                'scope':{'branch':self.branch}, 'lineage':({'entity_id':owner} if owner else {}),
                'semantic_key':f"record:{record_id}",
                'provenance':[{'kind':'world_record','ref':record_id,'version':r['version'],'updated_event':r['updated_event'],'branch':self.branch}]}
    def derived_aspect(self, aspect_id, typ, family, slots, reason, properties=None):
        return {'aspect_id':aspect_id,'type':typ,'family':family,'authority':'derived','compatible_slots':list(slots),
                'properties':properties or {},'provenance':[{'kind':'engine_derivation','ref':reason,'branch':self.branch,'revision':self.engine.branch(self.branch)['revision']}]}
    def mechanical_aspect(self, aspect_id, typ, family, slots, reason, properties=None):
        return {'aspect_id':aspect_id,'type':typ,'family':family,'authority':'mechanical','compatible_slots':list(slots),
                'properties':properties or {},'provenance':[{'kind':'engine_contract','ref':reason}]}
    def basis_manifest(self, aspects):
        records=[]; contracts=[]
        for a in aspects:
            for prov in a.get('provenance',[]):
                if prov.get('kind')=='world_record':
                    records.append({'record_id':prov['ref'],'version':prov['version'],'updated_event':prov.get('updated_event')})
                elif prov.get('kind') in ('engine_contract','engine_derivation'):
                    contracts.append(dict(prov))
        # De-duplicate while preserving exact expected versions.
        unique={(r['record_id'],r['version'],r.get('updated_event')):r for r in records}
        return {'branch':self.branch,'records':sorted(unique.values(),key=lambda r:r['record_id']),
                'contracts':sorted(contracts,key=lambda x:(x.get('kind',''),x.get('ref','')))}
    def binding_hash(self, aspects):
        return digest(self.basis_manifest(aspects))
    def narrative_scene(self, scene_id: str, participant_ids: list[str]) -> tuple[list[dict],dict]:
        scene=self.engine.get(self.branch,scene_id); require(scene and scene['domain']=='scene','scene unavailable')
        aspects=[]; bindings={}
        def bind(slot,a): aspects.append(a);bindings.setdefault(slot,[]).append(a['aspect_id'])
        # Governing rules are world-level mechanical context.
        rules=[r for r in self.engine.state(self.branch) if r['domain']=='world_rule']
        require(rules,'no world rules available')
        for r in rules: bind('governing.context',self.record_aspect(r['id'],compatible_slots=['governing.context']))
        for pid in participant_ids: bind('scene.participants',self.record_aspect(pid,compatible_slots=['scene.participants']))
        bind('scene.situation',self.record_aspect(scene_id,compatible_slots=['scene.situation']))
        loc=scene['data'].get('location'); require(loc,'scene location unavailable')
        bind('scene.environment',self.record_aspect(loc,compatible_slots=['scene.environment']))
        for pid in participant_ids:
            configs=[r for r in self.engine.state(self.branch) if r['domain'] in ('will','ability','capability') and (r['data'].get('bearer')==pid or r['data'].get('holder')==pid or r['data'].get('character')==pid)]
            for r in configs: bind('actor.configuration',self.record_aspect(r['id'],compatible_slots=['actor.configuration']))
            knows=[r for r in self.engine.state(self.branch) if r['domain']=='knowledge' and r['data'].get('holder')==pid]
            for r in knows: bind('actor.epistemic',self.record_aspect(r['id'],compatible_slots=['actor.epistemic']))
        if len(participant_ids)>1:
            pset=set(participant_ids)
            rels=[r for r in self.engine.state(self.branch) if r['domain']=='relationship' and {r['data'].get('subject'),r['data'].get('object')} <= pset]
            for r in rels: bind('actor.relationships',self.record_aspect(r['id'],compatible_slots=['actor.relationships']))
        bind('scene.action_space',self.mechanical_aspect('engine:world-action-api','operation','action',['scene.action_space'],'Engine.apply api_version=3'))
        bind('scene.consequence_contract',self.mechanical_aspect('engine:event-consequence-contract','consequence_contract','consequence',['scene.consequence_contract'],'Engine.apply validates and atomically records consequences'))
        return aspects,bindings
