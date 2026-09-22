"""Authored V4 journey and failure cases; every database is synthetic and temporary."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from examples.v4_demo import setup, record
from kageyoni.application import Application
from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.genesis import Genesis
from kageyoni.persistence.migrations import install_encounters
from kageyoni.workspaces.world import Encounters, verify_encounters


class GenesisTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.e=Engine(Path(self.tmp.name)/'world.sqlite');install_encounters(self.e)
        self.genesis=Genesis(self.e)
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def test_sparse_unicode_identity_unknowns_and_replay(self):
        args=dict(branch='main',request_id='sparse',expected_revision=0,profile={'label':'Sciel・シエル','visibility':'public'})
        result=self.genesis.introduce(**args);view=self.genesis.read('main',result['character_id'])
        self.assertEqual(view['profile']['stats'],[])
        self.assertEqual(view['profile']['innate_will']['status'],'unknown')
        self.assertEqual(view['profile']['primordial_will']['definition_ref'],None)
        self.assertEqual(view['world']['character']['data']['name'],'Sciel・シエル')
        self.assertEqual(self.e.properties('main',entity_id=result['character_id']),[])
        self.assertTrue(self.genesis.introduce(**args)['replayed'])
        self.assertEqual(verify_encounters(self.e)['profiles'],1)
    def test_proposed_stats_do_not_become_power_and_wrong_units_are_atomic(self):
        self.e.define_property('fixture',1,'Resource','Authored fixture','number',['character'],{'min':0,'max':10},lifecycle='active',unit='points')
        stat=dict(property_id='fixture',definition_version=1,status='proposed',value=9,unit='points',basis='Unaccepted draft value')
        result=self.genesis.introduce('main','draft',0,{'label':'Draft','stats':[stat]})
        self.assertEqual(self.e.properties('main',entity_id=result['character_id']),[])
        before=self.e.state();revision=self.e.branch('main')['revision']
        stat['status']='known';stat['unit']='days'
        with self.assertRaises(Rejected):self.genesis.introduce('main','bad',revision,{'label':'Bad','stats':[stat]})
        self.assertEqual(self.e.state(),before)
    def test_named_interpretation_and_underlying_definition_can_disagree(self):
        self.e.close();self.e=Engine(Path(self.tmp.name)/'second.sqlite')
        f=setup(self.e);genesis=Genesis(self.e)
        profile=dict(label='Different interpretation',named_will={'status':'known','name':'Endings','interpretation':'The bearer believes this power severs all connections.'},
            primordial_will={'status':'known','definition_ref':{'id':'root-will','version':1},'basis':'Explicit synthetic world declaration.'})
        result=genesis.introduce('main','opposite',self.e.branch('main')['revision'],profile)
        saved=genesis.read('main',result['character_id'])['profile']
        self.assertEqual(saved['named_will']['name'],'Endings')
        self.assertEqual(saved['primordial_will']['definition_ref']['id'],'root-will')
        self.assertEqual(self.e.get('main','root-will')['data']['name'],'Primordial Preservation')
        self.assertFalse(any(r['domain']=='will_expression' and r['data']['bearer']==result['character_id'] for r in self.e.state()))


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'world.sqlite';self.e=Engine(self.path)
        self.f=setup(self.e);self.world=self.f['app'].encounters
        self.world.start('main','passage',1,'journey','start',self.e.branch('main')['revision'],self.f['participants'])
    def tearDown(self):self.e.close();self.tmp.cleanup()
    def act(self,action,request=None,**kw):
        return self.world.act('main','journey',action,request or 'act-'+action,self.e.branch('main')['revision'],**kw)
    def play_to_reply(self):
        for action in ('bridge','offer','shield'):self.act(action)
    def focus(self):return next(p['value'] for p in self.e.properties('main',entity_id='traveler') if p['property_id']=='fixture.focus')
    def event(self,changes):
        revision=self.e.branch('main')['revision']
        return self.e.apply(dict(api_version=3,branch='main',request_id='fixture-'+str(revision),expected_revision=revision,actor='fixture',narrative='Synthetic fixture change',kind='action',changes=changes))
    def test_route_dialogue_will_restart_and_consequence(self):
        self.act('ferry');self.assertEqual(self.e.get('main','clock')['data']['tick'],2)
        offered=self.act('offer');open_state=self.world.inspect('main','journey')
        self.assertEqual(open_state['loops']['dialogue']['phase'],'open')
        self.assertEqual([a['action_id'] for a in open_state['next_actions']],['shield'])
        shield=self.act('shield');self.assertEqual(self.focus(),2)
        self.assertEqual(self.e.get('main','guard')['data']['condition'],'sheltered')
        self.assertEqual(self.world.inspect('main','journey')['loops']['dialogue']['phase'],'open')
        before=self.world.inspect('main','journey');self.e.close();self.e=Engine(self.path);self.world=Encounters(self.e)
        self.assertEqual(self.world.inspect('main','journey'),before)
        self.assertEqual({a['actor_id'] for a in before['next_actions']},{'guard'})
        self.act('accept');self.act('depart')
        done=self.world.inspect('main','journey')
        self.assertEqual(done['phase'],'completed');self.assertEqual(done['next_actions'],[])
        self.assertEqual(done['continuations'],[{'loop_id':'promise','record_id':'promise'}])
        self.assertEqual(self.e.get('main','promise')['data']['phase'],'open')
        replay=self.world.act('main','journey','shield','act-shield',offered['world_revision'])
        self.assertTrue(replay['replayed']);self.assertEqual(self.focus(),2)
        self.assertEqual(self.e.get('main','objective')['data']['phase'],'completed')
        self.assertTrue(self.e.verify()['ok'])
    def test_waiting_choice_invalid_stale_and_valid_resume(self):
        self.play_to_reply();self.act('refuse');wait=self.act('judge')
        before=self.world.inspect('main','journey');head=self.e.branch('main')['revision']
        self.assertEqual(wait['phase'],'waiting')
        self.e.close();self.e=Engine(self.path);self.world=Encounters(self.e)
        self.assertEqual(self.world.inspect('main','journey'),before)
        with self.assertRaises(Rejected):self.act('judge','invalid',fields={'choice_id':'invented','rationale':'No such branch'})
        self.assertEqual(self.world.inspect('main','journey'),before);self.assertEqual(self.e.branch('main')['revision'],head)
        with self.assertRaises(Rejected):self.world.act('main','journey','judge','stale',head-1,fields={'choice_id':'withdraw','rationale':'Choose explicitly'})
        fields={'choice_id':'withdraw','rationale':'Choose withdrawal; make no claim that trust improved.'}
        result=self.act('judge','resume',fields=fields)
        replay=self.world.act('main','journey','judge','resume',head,fields=fields)
        self.assertTrue(replay['replayed']);self.assertEqual(result['world_revision'],head+1)
        self.assertEqual(self.world.inspect('main','journey')['current_state'],'settle')
    def test_unknown_action_preserves_world_and_known_actions_can_resume(self):
        head=self.e.branch('main')['revision'];wait=self.act('teleport')
        self.assertEqual(wait['phase'],'waiting');self.assertEqual(self.e.branch('main')['revision'],head)
        self.assertEqual({x['action_id'] for x in self.world.inspect('main','journey')['next_actions']},{'bridge','ferry'})
        self.act('bridge');self.assertEqual(self.world.inspect('main','journey')['current_state'],'offer')
    def test_required_child_prevents_premature_parent_closure(self):
        spec=deepcopy(self.f['spec'])
        spec['actions']['bridge']['next_state']='closed'
        self.world.define('premature',1,spec,'define-premature')
        self.world.start('main','premature',1,'premature','start-premature',self.e.branch('main')['revision'],self.f['participants'])
        state=self.e.state()
        with self.assertRaisesRegex(Rejected,'required encounter loop'):
            self.world.act('main','premature','bridge','early-end',self.e.branch('main')['revision'])
        self.assertEqual(self.e.state(),state)
    def test_nested_parent_cannot_resolve_before_required_child(self):
        spec=deepcopy(self.f['spec']);spec['loops'].append(dict(id='parent',kind='interaction',required=True,depends_on=[],continuable=False))
        spec['loops'][0]['parent']='parent';spec['actions']['bridge']['resolve_loops']=['parent']
        self.world.define('nested',1,spec,'define-nested');self.world.start('main','nested',1,'nested','start-nested',self.e.branch('main')['revision'],self.f['participants'])
        with self.assertRaisesRegex(Rejected,'required nested child'):
            self.world.act('main','nested','bridge','close-parent',self.e.branch('main')['revision'])
    def test_terminal_entry_cannot_skip_required_obligations(self):
        spec=deepcopy(self.f['spec']);spec['initial_state']='closed'
        head=self.e.branch('main')['revision']
        with self.assertRaisesRegex(Rejected,'begin in an active state'):
            self.world.define('already-done',1,spec,'already-done')
        self.assertEqual(self.e.branch('main')['revision'],head)
    def test_requirement_distinguishes_zero_from_false_and_hidden_from_null(self):
        self.event([record('resource','gate',holder='traveler',name='Gate',quantity=0,unit='fixture')])
        spec=deepcopy(self.f['spec'])
        spec['actions']['bridge']['requirements']=[{'record_id':'gate','field':'quantity','equals':False}]
        spec['actions']['ferry']['requirements']=[{'record_id':'gate','field':'quantity','equals':0}]
        self.world.define('typed',1,spec,'typed');self.world.start('main','typed',1,'typed','typed-start',self.e.branch('main')['revision'],self.f['participants'])
        self.assertEqual([a['action_id'] for a in self.world.inspect('main','typed')['next_actions']],['ferry'])
        self.event([record('character','hidden-holder',name='Private',entity_kind='person'),record('resource','private-gate',holder='hidden-holder',name='Gate',quantity=1,unit='fixture')])
        self.event([dict(op='patch',id='hidden-holder',expected_version=1,visibility='gm',data={},evidence=[{'note':'Restrict fixture holder'}])])
        spec['actions']['bridge']['requirements']=[{'record_id':'private-gate','field':'holder','equals':None}]
        self.world.define('redacted',1,spec,'redacted');self.world.start('main','redacted',1,'redacted','redacted-start',self.e.branch('main')['revision'],self.f['participants'])
        self.assertEqual([a['action_id'] for a in self.world.inspect('main','redacted',viewer='traveler')['next_actions']],['ferry'])
    def test_late_failure_rolls_back_will_effect_and_loop_but_keeps_prepared_roll(self):
        self.act('bridge');self.act('offer');head=self.e.branch('main')['revision'];before=self.world.inspect('main','journey')
        with patch.object(self.world,'_write',side_effect=RuntimeError('Synthetic interruption after world apply')):
            with self.assertRaises(RuntimeError):self.act('shield')
        self.assertEqual(self.focus(),3);self.assertEqual(self.e.branch('main')['revision'],head)
        self.assertEqual(self.world.inspect('main','journey'),before)
        roll=self.e.db.execute("SELECT result FROM rolls WHERE id='journey:shield-roll'").fetchone()[0]
        self.act('shield');self.assertEqual(self.focus(),2)
        self.assertEqual(self.e.db.execute("SELECT result FROM rolls WHERE id='journey:shield-roll'").fetchone()[0],roll)
    def test_other_actor_cannot_spend_cost_or_steal_speaker(self):
        self.act('bridge')
        with self.assertRaises(Rejected):self.act('offer',viewer='guard')
        self.act('offer',viewer='traveler')
        turn=self.e.get('main','journey:turn:act-offer')
        self.assertEqual(turn['data']['speaker'],'traveler')
        with self.assertRaises(Rejected):self.act('shield',viewer='guard')
        self.assertEqual(self.focus(),3)
    def test_cycle_budget_blocks_without_fabricated_success(self):
        spec=deepcopy(self.f['spec']);spec['max_steps']=2;spec['actions']['bridge']['next_state']='route'
        self.world.define('cycle',1,spec,'cycle-def');self.world.start('main','cycle',1,'cycle','cycle-start',self.e.branch('main')['revision'],self.f['participants'])
        for index in range(2):self.world.act('main','cycle','bridge','cycle-'+str(index),self.e.branch('main')['revision'])
        head=self.e.branch('main')['revision'];result=self.world.act('main','cycle','bridge','cycle-limit',head)
        self.assertEqual(result['phase'],'blocked');self.assertEqual(result['outcome'],'unresolved');self.assertEqual(self.e.branch('main')['revision'],head)
    def test_finished_choice_is_not_reoffered_and_new_episode_needs_new_evidence(self):
        self.play_to_reply();self.act('accept');self.act('depart')
        with self.assertRaises(Rejected):self.act('accept','again')
        with self.assertRaises(Rejected):self.world.start('main','passage',1,'follow-up','follow-up',self.e.branch('main')['revision'],self.f['participants'],continuation_of='journey')
        self.event([record('knowledge','new-evidence',holder='traveler',assertion='A new messenger arrived after departure.',attitude='believes')])
        r=self.e.get('main','new-evidence');ref=dict(domain=r['domain'],id=r['id'],record_revision=r['version'],snapshot_hash=digest(r))
        self.world.start('main','passage',1,'follow-up','follow-up',self.e.branch('main')['revision'],self.f['participants'],continuation_of='journey',evidence_refs=[ref])
        self.assertEqual(self.world.inspect('main','journey')['phase'],'completed')
        self.assertEqual(self.world.inspect('main','follow-up')['continuation_of'],'journey')
    def test_projection_tamper_is_detected(self):
        self.e.db.execute("UPDATE encounter_instances SET state_json='{}'")
        with self.assertRaisesRegex(Rejected,'projection'):verify_encounters(self.e)
    def test_participant_projection_cannot_replace_pinned_speaker(self):
        self.e.db.execute('UPDATE encounter_instances SET participants_json=? WHERE encounter_id=?',
            (json.dumps({'traveler':'guard','guard':'traveler'}),'journey'))
        with self.assertRaisesRegex(Rejected,'pinned start'):self.world.inspect('main','journey')
        with self.assertRaisesRegex(Rejected,'pinned start'):verify_encounters(self.e)

    def test_same_primordial_will_different_evidenced_methods_without_changed_rules(self):
        from kageyoni.intelligence.expression import Expression
        from kageyoni.intelligence.methods import Methods
        from kageyoni.intelligence.nodes import Nodes
        old=self.e.get('main','expression')['data']['contract'];other=deepcopy(old)
        other.update(id='guard-expression',bearer='guard',legacy_will_id=None,learned_techniques=[])
        changes=[record('will_expression','guard-expression',definition='root-will',bearer='guard',contract=other),
                 record('knowledge','traveler-experience',holder='traveler',assertion='A prior fixture journey made time conservation relevant.',attitude='believes'),
                 record('knowledge','guard-experience',holder='guard',assertion='A prior fixture review made checks relevant.',attitude='believes')]
        for rid,amount in [('fast-time',1),('fast-checks',1),('thorough-time',3),('thorough-checks',5)]:
            changes.append(record('resource',rid,holder='traveler',name=rid,quantity=amount,unit='fixture'))
        self.event(changes);expression=Expression(self.e);methods=Methods(self.e)
        for character,field,direction in [('traveler','time','minimize'),('guard','checks','maximize')]:
            definition=dict(name='Experience-linked comparison',rationale='Explicit fixture interpretation of the recorded experience.',domains=['fixture.planning'],
                operation={'kind':'constraint_rank','params':{'criteria':[{'field':field,'weight':1,'direction':direction}]}},
                preconditions=['sources_current'],failure_conditions=['stale_source'],checking_procedure=['recompute_scores'],visibility='public')
            node=Nodes(self.e).read('main',character)['node_id']
            method=methods.create('main',node,character+'-method',self.e.branch('main')['revision'],definition,[expression.source_ref('main',character+'-experience')])
            methods.assign('main',node,method['method_id'],1,character+'-assign',self.e.branch('main')['revision'],'experimental','Bounded synthetic trial')
        task=dict(task_id='same-question',revision=1,domain='fixture.planning',objective='Compare recorded candidate values',candidates=[],source_refs=[])
        for candidate in ('fast','thorough'):
            claims={}
            for field in ('time','checks'):
                rid=candidate+'-'+field;ref=expression.source_ref('main',rid);task['source_refs'].append(ref)
                claims[field]={'value':self.e.get('main',rid)['data']['quantity'],'evidence':[{'source_ref':ref,'field_path':['data','quantity']}]}
            task['candidates'].append({'id':candidate,'claims':claims})
        rules=[tuple(r) for r in self.e.db.execute('SELECT * FROM rule_definitions')]
        choices=[]
        for character in ('traveler','guard'):
            result=expression.execute('main',character,task)
            choices.append(result['artifact']['content']['results'][0]['result']['ranked'][0]['candidate_id'])
        self.assertEqual(choices,['fast','thorough'])
        self.assertEqual(self.e.get('main','expression')['data']['definition'],self.e.get('main','guard-expression')['data']['definition'])
        self.assertEqual([tuple(r) for r in self.e.db.execute('SELECT * FROM rule_definitions')],rules)


if __name__=='__main__':unittest.main()
