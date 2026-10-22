"""Pure parser/compiler checks: no Engine construction, DB or native fixture.

Run with the real current28 samsara and native18 sources on PYTHONPATH.
Only note-only synthetic records use Engine._validate_record(None, image).
An audit fence rejects database/process effects; no replacement model exists.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

FORBIDDEN = []


def audit(event, args):
    if event in ('sqlite3.connect', 'subprocess.Popen', 'os.system', 'os.posix_spawn'):
        FORBIDDEN.append(event)
        raise AssertionError('pure test attempted ' + event)


sys.addaudithook(audit)
from kageyoni.engine import Engine, Rejected
from kageyoni.model import DOMAINS
from samsara.protocol import Fault, digest
from samsara.contentsets import ContentSets

MODULE = Path(__file__).resolve().parents[1] / 'samsara' / 'exhibition_profiles.py'
loader = importlib.util.spec_from_file_location('samsara.exhibition_profiles', MODULE)
leaf = importlib.util.module_from_spec(loader)
loader.loader.exec_module(leaf)
P = 'synthetic:f3a:'
EVIDENCE = [{'note': 'New source-only synthetic parser test; not native history.'}]


def native_validate(image):
    # Actual native method, no self/Engine/DB, only this note-only equipment.
    Engine._validate_record(None, image)


def rid(name): return P + name
def role(name): return {'$role': name}
def local(name): return {'$encounter': name}


def create(name, domain, data, *, episode=False):
    return dict(op='create', id=local(name) if episode else rid(name), domain=domain,
                data=data, status='proposed', visibility='public', evidence=copy.deepcopy(EVIDENCE))


def patch(record, data):
    return dict(op='patch', id=record, data=data, evidence=copy.deepcopy(EVIDENCE))


def req(record, field, value): return dict(record_id=record, field=field, equals=value)


def action(actor, next_state, changes=(), requirements=()):
    return dict(label='Synthetic ' + next_state, actor_role=actor, kind='event',
                payload={'changes': copy.deepcopy(list(changes))}, requirements=copy.deepcopy(list(requirements)),
                resolve_loops=[], next_state=next_state)


def state(actions=(), *, outcome='unresolved'):
    return dict(phase='active' if outcome=='unresolved' else 'completed', outcome=outcome, actions=list(actions))


def geometry():
    return [create('scene','scene',dict(name='Synthetic bounded work space', location=rid('site'), phase='active', round=0),episode=True)] + [
        create('participant-'+r,'participation',dict(scene=local('scene'),character=role(r),position='near',actions_remaining=1),episode=True)
        for r in ('left','right')]


def cleanup():
    return [dict(patch(local('scene'),{'phase':'closed'}), domain='scene')] + [
        dict(patch(local('participant-'+r),dict(position='outside',actions_remaining=0,active_effects=None)),domain='participation')
        for r in ('left','right')]


def report(name, actor):
    return create(name,'historical_account',dict(author=role(actor),assertion='Synthetic personal choice only.'),episode=True)


def gear_requirements(actor):
    return [req(rid('tool-loadout-'+actor),'holder',role(actor)), req(rid('tool-loadout-'+actor),'item',rid('tool-'+actor)),
            req(rid('tool-loadout-'+actor),'equipped',1), req(rid('tool-'+actor),'condition','sound')]


def encounter(name, spec):
    return dict(id=rid(name),version=1,spec=spec,binding={'left':rid('left'),'right':rid('right')},
                site_id=rid('site'),ordinary_alternative='Decline and pursue ordinary life without award or debt.')


def fixture():
    records=[create('site','location',dict(name='New synthetic workshop',kind='room')),
             create('left','character',dict(name='Synthetic left',entity_kind='person',location=rid('site'))),
             create('right','character',dict(name='Synthetic right',entity_kind='person',location=rid('site'))),
             create('pool','resource',dict(name='Synthetic award pieces',holder=rid('site'),quantity=2,unit='piece')),
             create('marker','item',dict(name='Synthetic scoring flag',condition='ready'))]
    for r in ('left','right'):
        records += [create('award-'+r,'resource',dict(name='Synthetic entrant pieces',holder=rid(r),quantity=0,unit='piece')),
                    create('incorporated-'+r,'resource',dict(name='Synthetic target material',holder=rid(r),quantity=0,unit='piece')),
                    create('exertion-'+r,'resource',dict(name='Synthetic effort',holder=rid(r),quantity=2,unit='step')),
                    create('tool-'+r,'item',dict(name='Synthetic hand tool',condition='sound')),
                    create('tool-loadout-'+r,'loadout',dict(item=rid('tool-'+r),holder=rid(r),slot='hand',equipped=1)),
                    create('target-'+r,'item',dict(name='Synthetic split fitting',condition='split')),
                    create('target-loadout-'+r,'loadout',dict(item=rid('target-'+r),holder=rid(r),slot='bench',equipped=0))]
    clear=cleanup()
    spec=dict(title='New synthetic opposed flag exhibition',roles=['left','right'],visibility='public',initial_state='offer',loops=[],
              states={'offer':state(['advance','withdraw0','evade0']),
                      'reply':state(['counter','yield','withdraw1','evade1']),
                      'finish':state(['finish','withdraw2','evade2']),
                      'leftwin':state(outcome='achieved'),'rightwin':state(outcome='achieved'),
                      'withdrawn':state(outcome='not_achieved'),'evaded':state(outcome='partly_achieved')},
              actions={},ending=dict(label='Stop synthetic exhibition',next_state='withdrawn',changes=copy.deepcopy(clear)))
    spec['actions']={
        'advance':action('left','reply',geometry()+[patch(rid('exertion-left'),{'quantity':1})],
                         [req(rid('exertion-left'),'quantity',2)]+gear_requirements('left')),
        'counter':action('right','rightwin',[patch(rid('exertion-right'),{'quantity':1}),patch(rid('marker'),{'condition':'right touch'})]+clear,
                         [req(rid('exertion-right'),'quantity',2)]+gear_requirements('right')),
        'yield':action('right','finish',[patch(rid('exertion-right'),{'quantity':1})],[req(rid('exertion-right'),'quantity',2)]+gear_requirements('right')),
        'finish':action('left','leftwin',[patch(rid('exertion-left'),{'quantity':0}),patch(rid('marker'),{'condition':'left touch'})]+clear,
                        [req(rid('exertion-left'),'quantity',1)]+gear_requirements('left'))}
    for n,actor,clearance in [(0,'left',[]),(1,'right',clear),(2,'left',clear)]:
        spec['actions']['withdraw'+str(n)]=action(actor,'withdrawn',clearance)
        spec['actions']['evade'+str(n)]=action(actor,'evaded',clearance)
    repairs=[]
    for beneficiary,helper in [('left','right'),('right','left')]:
        required=[req(rid('award-'+beneficiary),'quantity',1),req(rid('incorporated-'+beneficiary),'quantity',0),
                  req(rid('target-'+beneficiary),'condition','split'),
                  req(rid('target-loadout-'+beneficiary),'item',rid('target-'+beneficiary)),
                  req(rid('target-loadout-'+beneficiary),'holder',rid(beneficiary))]+gear_requirements(helper)
        repair_spec=dict(title='Separate synthetic '+beneficiary+' repair',roles=['left','right'],visibility='public',
             initial_state='helper_offer',loops=[],
             states={'helper_offer':state(['accept','decline']),'accepted':state(['setup','stop0']),
                     'work':state(['material','stop1']),'repaired':state(outcome='achieved'),'declined':state(outcome='not_achieved')},
             actions={'accept':action(helper,'accepted',[report('helper-accepted',helper)]),
                      'decline':action(helper,'declined',[report('helper-declined',helper)]),
                      'setup':action(beneficiary,'work',geometry()),'stop0':action(beneficiary,'declined'),
                      'material':action(beneficiary,'repaired',[
                          patch(rid('award-'+beneficiary),{'quantity':0}),
                          patch(rid('incorporated-'+beneficiary),{'quantity':1}),
                          patch(rid('target-'+beneficiary),{'condition':'repaired'})]+clear,required),
                      'stop1':action(beneficiary,'declined',clear)},
             ending=dict(label='Stop synthetic repair',next_state='declined',changes=copy.deepcopy(clear)))
        repairs.append(dict(encounter=encounter('repair:'+beneficiary,repair_spec),beneficiary_role=beneficiary,helper_role=helper,
                   target_id=rid('target-'+beneficiary),target_loadout_id=rid('target-loadout-'+beneficiary),
                   award_id=rid('award-'+beneficiary),incorporated_id=rid('incorporated-'+beneficiary),
                   tool_id=rid('tool-'+helper),tool_loadout_id=rid('tool-loadout-'+helper),
                   material_action='material',helper_accept_action='accept',helper_decline_action='decline'))
    return dict(format=leaf.FORMAT,id=rid('profile:small'),version=1,canonical=False,
                provenance=dict(not_recovered_history=True,participant_authorlore=False),existing_refs=[],native_records=records,
                exhibition=encounter('exhibition:small',spec),
                award=dict(amount=1,unit='piece',pool_id=rid('pool'),destinations={r:rid('award-'+r) for r in ('left','right')},
                           eligible_actions={'finish':'left','counter':'right'},boundary=leaf.BOUNDARY),repairs=repairs)


def blob(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


class CompilerTests(unittest.TestCase):
    def validate(self,p,anchors=None):
        return leaf.validate_profile(blob(p),anchor_images=anchors or {},validate_native_record=native_validate)

    def invalid(self,change):
        p=fixture();change(p)
        with self.assertRaises(Fault):self.validate(p)

    def record(self,p,name):return next(r for r in p['native_records'] if r['id']==rid(name))
    def repair(self,p):return p['repairs'][0]['encounter']['spec']

    def test_positive_actual_source_equipment_and_deepcopy(self):
        p=fixture();before=copy.deepcopy(p);out=self.validate(p)
        self.assertEqual(p,before);out['native_records'][0]['data']['name']='changed'
        self.assertEqual(p,before)
        encounters=leaf.authored_encounters(self.validate(p))
        self.assertEqual([e['kind'] for e in encounters],['battle','life','life'])
        self.assertEqual([e['id'] for e in encounters[1:]],[rid('repair:left'),rid('repair:right')])
        self.assertEqual(set(encounters[0]),set(leaf.ENCOUNTER)|{'kind'})
        encounters[0]['binding']['left']='mutated';self.assertEqual(p,before)
        compiled=ContentSets.compiled_spec(p['exhibition'])
        self.assertIn(req(role('left'),'location',rid('site')),compiled['actions']['finish']['requirements'])
        self.assertFalse(FORBIDDEN)

    def test_exact_anchor_full_image_and_revision(self):
        p=fixture();site=p['native_records'].pop(0)
        image=leaf._image(site,'pure-test-branch');image['updated_event']='pure-test-not-history'
        p['existing_refs']=[dict(id=image['id'],domain=image['domain'],record_revision=1,snapshot_hash=digest(image))]
        anchors={image['id']:copy.deepcopy(image)}
        self.validate(p,anchors)
        anchors[image['id']]['updated_event']='different-metadata'
        with self.assertRaises(Fault):self.validate(p,anchors)
        anchors[image['id']]=image;p['existing_refs'][0]['record_revision']=2
        with self.assertRaises(Fault):self.validate(p,anchors)

    def test_strict_json(self):
        for raw in [b'{"id":1,"id":2}',b'{"x":NaN}',b'{"x":Infinity}',b'\xff',b'[]',b'{',b'']:
            with self.subTest(raw=raw),self.assertRaises(Fault):
                leaf.validate_profile(raw,anchor_images={},validate_native_record=native_validate)
        deep=b'['*34+b'0'+b']'*34
        with self.assertRaises(Fault):leaf.validate_profile(deep,anchor_images={},validate_native_record=native_validate)

    def test_exact_shapes_namespace_and_no_recovery(self):
        for change in [lambda p:p.update(extra=1),lambda p:p.update(canonical=True),
                       lambda p:p.update(id='synthetic:f1:old'),lambda p:p.update(version=True),
                       lambda p:p['exhibition'].update(kind='battle'),lambda p:p['exhibition'].update(recovery=True),
                       lambda p:p['exhibition'].update(id='synthetic:f1:old-practice'),
                       lambda p:p['repairs'][0].update(extra=1),lambda p:p['provenance'].update(participant_authorlore=True)]:
            with self.subTest(change=change):self.invalid(change)

    def test_create_only_no_native_contest_facts_or_external_policy(self):
        for change in [lambda p:self.record(p,'marker').update(op='patch'),
                       lambda p:self.record(p,'marker').update(domain='contest_terms'),
                       lambda p:self.record(p,'marker').update(domain='will_process'),
                       lambda p:self.record(p,'marker').update(domain='personality_profile'),
                       lambda p:self.record(p,'marker')['data'].update(unknown=1),
                       lambda p:p['native_records'].append(copy.deepcopy(p['native_records'][0]))]:
            with self.subTest(change=change):self.invalid(change)

    def test_reference_closure_and_native_relational_constraints(self):
        for change in [lambda p:self.record(p,'left')['data'].update(location='missing'),
                       lambda p:self.record(p,'site')['data'].update(parent=rid('site')),
                       lambda p:self.record(p,'incorporated-left')['data'].update(holder=rid('target-left')),
                       lambda p:self.record(p,'tool-loadout-right')['data'].update(item=rid('tool-left')),
                       lambda p:self.record(p,'target-loadout-left')['data'].update(slot='hand',equipped=1),
                       lambda p:self.record(p,'target-left').update(visibility='restricted',audience=[]),
                       lambda p:self.record(p,'tool-left')['data'].update(condition=True)]:
            with self.subTest(change=change):self.invalid(change)

    def test_award_exact_native_constraints(self):
        for change in [lambda p:p['award'].update(amount=True),lambda p:p['award'].update(amount=0),
                       lambda p:p['award'].update(amount=0.5),lambda p:p['award'].update(boundary='award'),
                       lambda p:p['award']['eligible_actions'].update(withdraw0='left'),
                       lambda p:p['award']['destinations'].update(left=rid('award-right')),
                       lambda p:self.record(p,'award-left')['data'].update(holder=rid('right')),
                       lambda p:self.record(p,'award-left')['data'].update(quantity=1),
                       lambda p:self.record(p,'pool')['data'].update(quantity=0),
                       lambda p:self.record(p,'pool')['data'].update(quantity=1.5),
                       lambda p:self.record(p,'award-left')['data'].update(unit='other')]:
            with self.subTest(change=change):self.invalid(change)

    def test_competition_protected_writes_refunds_and_cost_types(self):
        for target in ['pool','award-left','incorporated-left','target-left']:
            self.invalid(lambda p,target=target:p['exhibition']['spec']['actions']['finish']['payload']['changes'].append(
                patch(rid(target),{'condition':'repaired'} if target=='target-left' else {'quantity':0})))
        for change in [lambda p:p['exhibition']['spec']['actions']['advance']['payload']['changes'][-1]['data'].update(quantity=3),
                       lambda p:p['exhibition']['spec']['actions']['advance']['payload']['changes'][-1]['data'].update(quantity=True),
                       lambda p:p['exhibition']['spec']['actions']['advance']['requirements'][0].update(equals=True),
                       lambda p:p['exhibition']['spec']['ending']['changes'].append(patch(rid('exertion-left'),{'quantity':2}))]:
            with self.subTest(change=change):self.invalid(change)

    def test_compile_rejects_non_event_unreachable_ambiguous_and_fake_geometry(self):
        for change in [lambda p:p['exhibition']['spec']['actions']['advance'].update(kind='will'),
                       lambda p:p['exhibition']['spec']['states'].update(unreachable=state(outcome='not_achieved')),
                       lambda p:p['exhibition']['spec']['states']['offer']['actions'].append('counter'),
                       lambda p:p['exhibition']['spec']['actions']['advance']['payload']['changes'][0].update(id=rid('not-local')),
                       lambda p:p['exhibition']['spec']['actions']['counter']['payload']['changes'].pop(),
                       lambda p:p['exhibition']['spec']['actions']['advance']['requirements'].append(req(local('scene'),'phase','active'))]:
            with self.subTest(change=change):self.invalid(change)

    def test_helper_offer_exact_two_no_geometry_material_tool_observation_costs(self):
        for change in [lambda p:self.repair(p)['states']['helper_offer']['actions'].append('setup'),
                       lambda p:self.repair(p)['states']['helper_offer'].update(actions=['accept']),
                       lambda p:self.repair(p)['actions']['accept'].update(actor_role='left'),
                       lambda p:self.repair(p)['actions']['accept'].update(next_state='repaired'),
                       lambda p:self.repair(p)['actions']['decline'].update(next_state='accepted'),
                       lambda p:self.repair(p)['actions']['accept']['payload'].update(changes=geometry()),
                       lambda p:self.repair(p)['actions']['accept']['payload'].update(changes=[patch(rid('tool-right'),{'condition':'worn'})]),
                       lambda p:self.repair(p)['actions']['accept']['payload'].update(changes=[patch(rid('award-left'),{'quantity':0})]),
                       lambda p:self.repair(p)['actions']['accept']['payload']['changes'].append(report('extra','right')),
                       lambda p:self.repair(p)['actions']['accept']['payload']['changes'][0]['data'].update(author=role('left')),
                       lambda p:self.repair(p)['actions']['accept']['payload'].update(observations=[dict(id=local('obs'),observer_id=role('right'),subject_id=role('left'),assertion='observed',certainty='reported',visibility='public')])]:
            with self.subTest(change=change):self.invalid(change)
        p=fixture();self.repair(p)['actions']['accept']['payload']={'changes':[]};self.validate(p)

    def test_material_dominated_by_helper_real_free_acceptance(self):
        def bypass(p):
            s=self.repair(p);s['actions']['stop0']['next_state']='work'
            # A postaccept edge is fine; the attempted bypass is a new initial edge.
            s['states']['helper_offer']['actions'].append('material')
        self.invalid(bypass)
        self.invalid(lambda p:self.repair(p)['actions']['decline'].update(next_state='work'))

    def test_material_exact_atomic_conservation_and_tool_requirements(self):
        for change in [lambda p:self.repair(p)['actions']['material']['payload']['changes'][0]['data'].update(quantity=1),
                       lambda p:self.repair(p)['actions']['material']['payload']['changes'][1]['data'].update(quantity=True),
                       lambda p:self.repair(p)['actions']['material']['payload']['changes'][2]['data'].update(condition='healed'),
                       lambda p:self.repair(p)['actions']['material']['payload']['changes'].pop(1),
                       lambda p:self.repair(p)['actions']['material']['requirements'].pop(),
                       lambda p:self.repair(p)['actions']['material']['requirements'][0].update(equals=True),
                       lambda p:self.repair(p)['actions']['material'].update(actor_role='right'),
                       lambda p:self.repair(p)['actions']['setup']['payload']['changes'].append(patch(rid('target-left'),{'condition':'repaired'})),
                       lambda p:self.record(p,'tool-loadout-right')['data'].update(equipped=0),
                       lambda p:self.record(p,'target-left')['data'].update(condition='sound'),
                       lambda p:self.record(p,'incorporated-left')['data'].update(quantity=1),
                       lambda p:p['repairs'][1].update(incorporated_id=rid('incorporated-left')),
                       lambda p:p['repairs'].pop()]:
            with self.subTest(change=change):self.invalid(change)

    def test_equipment_errors_are_not_success_or_masked_integrity(self):
        def broken(image):raise RuntimeError('actual equipment failure')
        with self.assertRaisesRegex(RuntimeError,'actual equipment failure'):
            leaf.validate_profile(blob(fixture()),anchor_images={},validate_native_record=broken)

    def test_terminal_same_event_geometry_cannot_survive(self):
        def extra(p):
            s=p['exhibition']['spec']
            s['actions']['finish']['payload']['changes'].extend([
                create('late-scene','scene',dict(name='Late active geometry',location=rid('site'),phase='active',round=0),episode=True),
                create('late-participant','participation',dict(scene=local('late-scene'),character=role('left'),position='near',actions_remaining=1),episode=True)])
            s['ending']['changes'].extend([
                dict(patch(local('late-scene'),{'phase':'closed'}),domain='scene'),
                dict(patch(local('late-participant'),dict(position='outside',actions_remaining=0,active_effects=None)),domain='participation')])
        self.invalid(extra)

    def test_incorporated_holder_matches_target_legal_access(self):
        self.invalid(lambda p:self.record(p,'incorporated-left')['data'].update(holder=rid('right')))
        self.invalid(lambda p:self.record(p,'target-loadout-left')['data'].update(holder=rid('right')))
        p=fixture()
        for name in ('incorporated-left','target-loadout-left'):
            self.record(p,name)['data']['holder']=rid('site')
        for requirement in self.repair(p)['actions']['material']['requirements']:
            if requirement['record_id']==rid('target-loadout-left') and requirement['field']=='holder':
                requirement['equals']=rid('site')
        self.validate(p)

    def test_terminal_created_geometry_is_checked_as_postimage(self):
        # Complete lowered geometry is permitted; only the live postimage fails.
        p=fixture();s=p['exhibition']['spec']
        s['actions']['finish']['payload']['changes'].extend([
            create('late-scene','scene',dict(name='Already lowered geometry',location=rid('site'),phase='closed',round=0),episode=True),
            create('late-participant','participation',dict(scene=local('late-scene'),character=role('left'),position='outside',actions_remaining=0,active_effects=None),episode=True)])
        s['ending']['changes'].extend([
            dict(patch(local('late-scene'),{'phase':'closed'}),domain='scene'),
            dict(patch(local('late-participant'),dict(position='outside',actions_remaining=0,active_effects=None)),domain='participation')])
        self.validate(p)
        s['actions']['finish']['payload']['changes'][-1]['data']['actions_remaining']=1
        with self.assertRaises(Fault):self.validate(p)

    def test_future_created_subject_cannot_be_observed_early(self):
        def future(p):
            s=p['exhibition']['spec']
            s['actions']['finish']['payload']['changes'].append(report('future','left'))
            s['actions']['advance']['payload']['observations']=[dict(id=local('observation'),observer_id=role('left'),
                subject_id=local('future'),assertion='Cannot preobserve future report',certainty='reported',visibility='public')]
        self.invalid(future)

    def test_future_created_native_field_reference_cannot_be_used_early(self):
        def future(p):
            s=p['exhibition']['spec']
            s['actions']['advance']['payload']['changes'][1]['data']['scene']=local('future-scene')
            s['actions']['finish']['payload']['changes'].append(create('future-scene','scene',
                dict(name='Future already closed scene',location=rid('site'),phase='closed',round=0),episode=True))
            s['ending']['changes'].append(dict(patch(local('future-scene'),{'phase':'closed'}),domain='scene'))
        self.invalid(future)

    def test_testimony_and_maintenance_cleanup_alone_cannot_award(self):
        self.invalid(lambda p:p['exhibition']['spec']['actions']['finish']['payload'].update(changes=cleanup()+[report('win-claim','left')]))
        def different_metadata(p):
            changes=cleanup()
            for c in changes:
                c.pop('domain');c['evidence']=[{'note':'Different notes are still only cleanup.'}]
            p['exhibition']['spec']['actions']['finish']['payload']['changes']=changes
        self.invalid(different_metadata)

    def test_coherently_authored_nonlowering_ending_is_native_rejected(self):
        # Root countercase: changing both ending and every terminal patch
        # cannot bypass actual compiled_spec -> native _validate equipment.
        mutations=[('scene',{'phase':'active'}),('scene',{'phase':'closed','context':'changed'}),
                   ('participant-left',dict(position='outside',actions_remaining=1,active_effects=None)),
                   ('participant-left',dict(position='outside',actions_remaining=False,active_effects=None)),
                   ('participant-left',dict(position='outside',actions_remaining=0,active_effects='new effect'))]
        for suffix,data in mutations:
            with self.subTest(suffix=suffix,data=data):
                p=fixture();encounters=[p['exhibition']]+[r['encounter'] for r in p['repairs']]
                for enc in encounters:
                    spec=enc['spec']
                    for c in spec['ending']['changes']:
                        if c['id']==local(suffix):c['data']=copy.deepcopy(data)
                    for a in spec['actions'].values():
                        for c in a['payload']['changes']:
                            if c['op']=='patch' and c['id']==local(suffix):c['data']=copy.deepcopy(data)
                    with self.assertRaises(Rejected):leaf._validate(spec)
                    with self.assertRaises(Rejected):ContentSets.compiled_spec(enc)
                with self.assertRaises(Fault):self.validate(p)


if __name__=='__main__':
    unittest.main(verbosity=2)
