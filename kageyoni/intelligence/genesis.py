"""Explicit character introduction; sparse input never creates inferred mastery."""
from copy import deepcopy
import json
from uuid import uuid4

from .. import characters
from ..engine import require, digest, encoded
from ..persistence.unit_of_work import UnitOfWork
from .contracts import text, integer
from .nodes import Nodes


def _profile(value):
    allowed = {'label', 'character_id', 'canonical_name', 'entity_kind', 'existence', 'visibility', 'audience',
               'motivation', 'communication', 'stats', 'abilities', 'named_will', 'primordial_will', 'innate_will', 'basis'}
    require(isinstance(value, dict) and set(value) <= allowed, 'unsupported profile field')
    result = deepcopy(value); text(result.get('label'), 'working character label')
    result.setdefault('existence', 'provisional'); result.setdefault('entity_kind', 'unknown')
    result.setdefault('visibility', 'gm'); result.setdefault('audience', [])
    result.setdefault('basis', 'Explicitly supplied character draft; unspecified details remain unknown.')
    text(result['basis'], 'profile basis')
    require(result['existence'] in ('provisional', 'established', 'alleged'), 'invalid existence status')
    require(result['visibility'] in ('gm', 'public', 'restricted'), 'invalid profile visibility')
    require(isinstance(result['audience'], list) and all(isinstance(x,str) and x for x in result['audience']), 'invalid audience')
    require(result['visibility'] != 'restricted' or bool(result['audience']), 'restricted profile needs audience')
    for key in ('motivation', 'communication', 'innate_will'):
        result.setdefault(key, {'status': 'unknown', 'statement': None})
        item = result[key]
        require(isinstance(item, dict) and set(item) == {'status', 'statement'}, 'invalid ' + key)
        require(item['status'] in ('known', 'unknown', 'proposed'), 'invalid profile epistemic status')
        if item['status'] == 'unknown':
            require(item['statement'] is None, 'unknown field cannot contain an asserted value')
        else:
            text(item['statement'], key + ' statement')
    result.setdefault('stats', []); result.setdefault('abilities', [])
    require(isinstance(result['stats'], list) and len(result['stats']) <= 64, 'invalid stats')
    require(isinstance(result['abilities'], list) and len(result['abilities']) <= 64, 'invalid abilities')
    for stat in result['stats']:
        require(isinstance(stat, dict) and set(stat) == {'property_id', 'definition_version', 'status', 'value', 'unit', 'basis'}, 'invalid stat declaration')
        text(stat['property_id'], 'property id'); integer(stat['definition_version'], 'property version'); text(stat['basis'], 'stat basis')
        require(stat['status'] in ('known', 'unknown', 'proposed'), 'invalid stat status')
        require(stat['status'] != 'unknown' or stat['value'] is None, 'unknown stat must have null value')
    require(len({(s['property_id'],s['definition_version']) for s in result['stats']}) == len(result['stats']), 'duplicate stat')
    for ability in result['abilities']:
        require(isinstance(ability, dict) and set(ability) == {'ability_id', 'status', 'basis'}, 'invalid ability declaration')
        text(ability['ability_id'], 'ability id'); text(ability['basis'], 'ability basis')
        require(ability['status'] in ('known', 'unknown', 'proposed'), 'invalid ability status')
    result.setdefault('named_will', {'status': 'unknown', 'name': None, 'interpretation': None})
    named = result['named_will']
    require(isinstance(named, dict) and set(named) == {'status', 'name', 'interpretation'}, 'invalid named Will interpretation')
    require(named['status'] in ('known', 'proposed', 'unknown'), 'invalid named Will status')
    if named['status'] == 'unknown':
        require(named['name'] is None and named['interpretation'] is None, 'unknown named Will has no asserted interpretation')
    else:
        text(named['name'], 'named Will name'); text(named['interpretation'], 'bearer interpretation')
    result.setdefault('primordial_will', {'status': 'unknown', 'definition_ref': None, 'basis': None})
    primordial = result['primordial_will']
    require(isinstance(primordial, dict) and set(primordial) == {'status', 'definition_ref', 'basis'}, 'invalid primordial declaration')
    require(primordial['status'] in ('known', 'proposed', 'unknown'), 'invalid primordial status')
    if primordial['status'] == 'unknown':
        require(primordial['definition_ref'] is None, 'unknown primordial Will cannot identify a definition')
    else:
        ref = primordial['definition_ref']
        require(isinstance(ref,dict) and set(ref)=={'id','version'}, 'primordial definition needs exact reference')
        text(ref['id'], 'primordial definition id'); integer(ref['version'], 'primordial version'); text(primordial['basis'], 'primordial basis')
    encoded(result)
    return result


class Genesis:
    def __init__(self, engine):
        self.engine, self.db = engine, engine.db

    def introduce(self, branch, request_id, expected_revision, profile, viewer=None):
        require(viewer is None, 'owner view required to introduce characters')
        require(self.db.execute("SELECT 1 FROM engine_versions WHERE component='encounter_interface' AND version='1'").fetchone(), 'encounter interface not installed')
        text(request_id, 'request id'); integer(expected_revision, 'expected revision', 0)
        profile = _profile(profile)
        payload = dict(branch=branch, request_id=request_id, expected_revision=expected_revision, profile=profile)
        with UnitOfWork(self.db):
            old = self.db.execute('SELECT payload_hash,receipt_json FROM genesis_profiles WHERE request_id=?', (request_id,)).fetchone()
            if old:
                require(old['payload_hash'] == digest(payload), 'genesis request reused with different payload')
                return dict(json.loads(old['receipt_json']), replayed=True)
            require(self.engine.branch(branch)['revision'] == expected_revision, 'stale branch revision')
            cid = profile.get('character_id') or 'character:' + uuid4().hex
            text(cid, 'character id')
            primordial = profile['primordial_will']
            if primordial['definition_ref'] is not None:
                ref = primordial['definition_ref']
                r = self.engine.get(branch, ref['id'])
                require(r and r['domain']=='will_definition' and r['version']==ref['version']
                        and r['data']['classification']=='primordial', 'primordial definition unavailable')
                self.engine.get_will_contract(branch, 'will_definition', ref['id'], ref['version'])
            for stat in profile['stats']:
                definition = self.engine._definition(stat['property_id'], stat['definition_version'])
                self.engine._property_value_parts(definition, 'unknown' if stat['status']=='unknown' else 'known', stat['value'], stat['unit'])
            for declaration in profile['abilities']:
                r = self.engine.get(branch, declaration['ability_id'])
                require(r and r['domain']=='ability', 'declared ability unavailable')
            aspects=[]
            for key, section, kind in (('motivation','interiority','drive'),('communication','condition','communication')):
                item=profile[key]
                aspects.append(dict(id=cid+'.'+key, status='proposed' if item['status']=='proposed' else 'unknown' if item['status']=='unknown' else 'confirmed',
                    data=dict(section=section,kind=kind,value_status='unknown' if item['status']=='unknown' else 'known',
                              statement=item['statement'],phase='active',change_basis='established' if item['status']=='known' else 'unknown')))
            receipt = characters.create(self.engine, branch=branch, request_id='genesis-character:'+request_id,
                expected_revision=expected_revision, actor='owner', narrative='Introduce explicitly supplied character profile',
                character_id=cid, label=profile['label'], existence=profile['existence'], entity_kind=profile['entity_kind'],
                evidence=[{'note':profile['basis']}], visibility=profile['visibility'], audience=profile['audience'],
                canonical_name=profile.get('canonical_name'), name_status='known' if profile.get('canonical_name') else 'unknown', aspects=aspects)
            common=dict(op='create',visibility=profile['visibility'],audience=profile['audience'],evidence=[{'note':profile['basis']}])
            changes=[]; assignments=[]
            for stat in profile['stats']:
                if stat['status']=='proposed':
                    continue
                assignments.append(dict(entity_id=cid,property_id=stat['property_id'],definition_version=stat['definition_version'],
                    state=stat['status'],value=stat['value'],unit=stat['unit'],context={'audience':profile['audience'],'basis':stat['basis']},
                    epistemic_status='authored' if stat['status']=='known' else 'unknown',visibility=profile['visibility']))
            for idx, ability in enumerate(profile['abilities']):
                if ability['status']=='known':
                    changes.append(dict(common,domain='capability',id=cid+'.capability.'+str(idx),status='reported',
                        data=dict(character=cid,ability=ability['ability_id'],mastery='unknown',demonstrated_use=None,condition=ability['basis'])))
            named=profile['named_will']
            if named['status']!='unknown':
                changes.append(dict(common,domain='will',id=cid+'.named-will',status='reported' if named['status']=='known' else 'proposed',
                    data=dict(name=named['name'],bearer=cid,principles=named['interpretation'],expression='Bearer interpretation; primordial identity is recorded separately.')))
            if changes or assignments:
                receipt=self.engine.apply(dict(api_version=3,branch=branch,request_id='genesis-details:'+request_id,
                    expected_revision=self.engine.branch(branch)['revision'],kind='action',actor='owner',
                    narrative='Record supplied traits without inferred mastery or primordial identity',changes=changes,properties=assignments))
            node=Nodes(self.engine).bind(branch,cid,'genesis-node:'+request_id,self.engine.branch(branch)['revision'],{'note':profile['basis']})
            result=dict(genesis_interface='1',character_id=cid,node_id=node['node_id'],branch=branch,
                        world_revision=self.engine.branch(branch)['revision'],receipt=receipt,
                        existence=profile['existence'],unknowns=[k for k in ('motivation','communication','innate_will','named_will','primordial_will') if profile[k]['status']=='unknown']
                            +(['stats'] if not profile['stats'] else [])+(['abilities'] if not profile['abilities'] else []),replayed=False)
            self.db.execute('INSERT INTO genesis_profiles VALUES(?,?,?,?,?,?,?)', (branch,cid,node['node_id'],request_id,encoded(profile),digest(payload),encoded(result)))
            return result

    def read(self, branch, character_id, viewer=None):
        with UnitOfWork(self.db):
            world=characters.read(self.engine,branch,character_id,viewer=viewer)
            row=self.db.execute('SELECT * FROM genesis_profiles WHERE branch=? AND character_id=?',(branch,character_id)).fetchone()
            require(row is not None,'genesis profile unavailable')
            profile=json.loads(row['profile_json'])
            if viewer is not None:
                require(self.engine._visible(profile,viewer),'genesis profile unavailable')
                visible={r['id'] for r in self.engine.context(branch,viewer=viewer)['records']}
                refs=[a['ability_id'] for a in profile['abilities']]
                if profile['primordial_will']['definition_ref']:refs.append(profile['primordial_will']['definition_ref']['id'])
                require(all(ref in visible for ref in refs),'genesis profile unavailable')
                profile.pop('audience',None);profile.pop('basis',None)
                for stat in profile['stats']:stat.pop('basis',None)
                for ability in profile['abilities']:ability.pop('basis',None)
                profile['primordial_will'].pop('basis',None)
            return dict(genesis_interface='1',character_id=character_id,node_id=row['node_id'],profile=profile,world=world,
                        limits='Profile declarations do not infer mastery, intelligence ranking, or executable Will powers.')
