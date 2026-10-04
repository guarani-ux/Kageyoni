import json
import shutil
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.resources import fixture_path
from kageyoni.persistence.migrations import install_composition
from kageyoni.composition import Compiler, CompositionRegistry, EngineAspectAdapter, ResolutionGovernor

ROOT = Path(__file__).resolve().parents[2]
BASE_DB = fixture_path('campaign-v11.sqlite')


class CompositionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'candidate.sqlite'
        shutil.copy2(BASE_DB, self.db_path)
        self.engine = Engine(self.db_path)
        self.before = {
            'revision': self.engine.branch('main')['revision'],
            'records': len(self.engine.state('main')),
            'events': self.engine.db.execute("SELECT count(*) FROM events WHERE branch='main'").fetchone()[0],
        }
        install_composition(self.engine)
        self.registry = CompositionRegistry(self.engine)

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def test_migration_preserves_campaign_state(self):
        self.assertEqual(self.before['revision'], self.engine.branch('main')['revision'])
        self.assertEqual(self.before['records'], len(self.engine.state('main')))
        self.assertEqual(self.before['events'], self.engine.db.execute("SELECT count(*) FROM events WHERE branch='main'").fetchone()[0])
        self.assertTrue(self.engine.verify()['ok'])
        self.assertEqual({x['frame_id'] for x in self.registry.list_frames()}, {'content_development.v1','narrative_scene.v1'})

    def test_current_sciel_scene_compiles_from_actual_campaign_state(self):
        adapter = EngineAspectAdapter(self.engine)
        aspects, bindings = adapter.narrative_scene('lucretia-voss-recall-scene', ['sciel'])
        result = Compiler(self.registry.frame('narrative_scene.v1'), aspects).compile(bindings)
        self.assertTrue(result['runnable'], result)
        self.assertEqual(result['participant_count'], 1)

    def test_two_actor_scene_fails_closed_without_relationship_state(self):
        adapter = EngineAspectAdapter(self.engine)
        aspects, bindings = adapter.narrative_scene('lucretia-voss-recall-scene', ['sciel','environmental-admiral'])
        result = Compiler(self.registry.frame('narrative_scene.v1'), aspects).compile(bindings)
        self.assertFalse(result['runnable'])
        rel = next(x for x in result['slots'] if x['slot_id']=='actor.relationships')
        self.assertEqual(rel['status'],'UNKNOWN')

    def test_content_frame_uses_same_compiler(self):
        frame = self.registry.frame('content_development.v1')
        slots = {s['slot_id']:s for s in frame['slots']}
        aspects=[];bindings={}
        for sid, slot in slots.items():
            if slot['requirement']=='conditional' and sid!='audience.intent':
                continue
            aid='test:'+sid
            authority=slot['authority_policy'][0]
            aspects.append({'aspect_id':aid,'type':slot['accepts'][0],'family':slot['family'],'authority':authority,
                            'compatible_slots':[sid],'properties':{},'provenance':[{'kind':'test','ref':sid}]})
            bindings[sid]=[aid]
        result=Compiler(frame,aspects).compile(bindings)
        self.assertTrue(result['runnable'],result)
        # The audience-intent condition is tied to audience.entities, not a narrative participant counter.
        missing=dict(bindings); missing.pop('audience.intent')
        blocked=Compiler(frame,aspects).compile(missing)
        self.assertFalse(blocked['runnable'])
        intent=next(x for x in blocked['slots'] if x['slot_id']=='audience.intent')
        self.assertEqual(intent['status'],'UNKNOWN')

    def test_governor_preview_commit_verifies_existing_engine_transition(self):
        adapter=EngineAspectAdapter(self.engine)
        aspects,bindings=adapter.narrative_scene('lucretia-voss-recall-scene',['sciel'])
        compilation=Compiler(self.registry.frame('narrative_scene.v1'),aspects).compile(bindings)
        basis_manifest=adapter.basis_manifest(aspects)
        revision=self.engine.branch('main')['revision']
        command={'api_version':3,'branch':'main','expected_revision':revision,'request_id':'v10-test-failed-action',
                 'kind':'failed_action','actor':'sciel','narrative':'Disposable v10 governor integration probe','changes':[]}
        governor=ResolutionGovernor(self.engine)
        prepared=governor.prepare(compilation,command,basis_manifest=basis_manifest)
        self.assertEqual(prepared['status'],'prepared')
        self.assertEqual(self.engine.branch('main')['revision'],revision)
        committed=governor.commit(prepared,compilation,command)
        self.assertEqual(committed['status'],'committed')
        self.assertEqual(self.engine.branch('main')['revision'],revision+1)
        self.assertTrue(committed['verification']['ok'])

    def test_governor_rejects_changed_command_after_preview(self):
        adapter=EngineAspectAdapter(self.engine)
        aspects,bindings=adapter.narrative_scene('lucretia-voss-recall-scene',['sciel'])
        compilation=Compiler(self.registry.frame('narrative_scene.v1'),aspects).compile(bindings)
        basis_manifest=adapter.basis_manifest(aspects);revision=self.engine.branch('main')['revision']
        command={'api_version':3,'branch':'main','expected_revision':revision,'request_id':'v10-test-tamper',
                 'kind':'failed_action','actor':'sciel','narrative':'Probe','changes':[]}
        governor=ResolutionGovernor(self.engine);prepared=governor.prepare(compilation,command,basis_manifest=basis_manifest)
        changed=dict(command);changed['narrative']='Tampered after preview'
        with self.assertRaises(Rejected): governor.commit(prepared,compilation,changed)
        self.assertEqual(self.engine.branch('main')['revision'],revision)


if __name__=='__main__': unittest.main()

