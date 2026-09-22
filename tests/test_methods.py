"""V2 source, scope and durability boundaries using synthetic data only."""
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kageyoni.engine import Engine, Rejected, digest
from kageyoni.intelligence.methods import Methods, verify_methods
from kageyoni.intelligence.nodes import Nodes
from kageyoni.persistence.migrations import install_methods
from kageyoni.persistence.unit_of_work import UnitOfWork


class MethodTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'methods.sqlite'
        self.engine = Engine(self.path)
        changes = [dict(op='create', domain='character', id=id, status='proposed', visibility=visibility,
                        evidence=[{'note': 'Synthetic fixture'}], data={'name': id, 'entity_kind': 'person'})
                   for id, visibility in [('a', 'public'), ('viewer', 'public'), ('secret', 'gm')]]
        for id, visibility in [('source', 'public'), ('private-source', 'gm')]:
            changes.append(dict(op='create', domain='ability', id=id, status='proposed', visibility=visibility,
                                evidence=[{'note': 'OWNER_EVIDENCE_CANARY'}],
                                data={'name': id, 'function': 'Synthetic comparison exercise'}))
        self.engine.apply(dict(api_version=3, branch='main', expected_revision=0, request_id='fixture',
                               kind='action', actor='fixture', narrative='Synthetic fixture only', changes=changes))
        install_methods(self.engine)
        self.node = Nodes(self.engine).bind('main', 'a', 'bind', 1, {'note': 'Synthetic node'})['node_id']
        self.methods = Methods(self.engine)

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def definition(self, **updates):
        result = dict(name='Fixture comparison', operation={'kind': 'constraint_rank', 'params': {
                      'criteria': [{'field': 'quality', 'weight': 1, 'direction': 'maximize'}]}},
                      rationale='Owner proposes this operation from a synthetic comparison episode.',
                      domains=['fixture.choice'], preconditions=['task_domain_matches', 'sources_current'],
                      failure_conditions=['missing_support'], checking_procedure=['recompute_scores'],
                      roles=['candidate', 'criterion'],
                      relationships=[{'source': 'candidate', 'relation': 'evaluated_by', 'target': 'criterion'}],
                      visibility='public')
        result.update(updates)
        return result

    def refs(self, id='source'):
        record = self.engine.get('main', id)
        return [dict(domain=record['domain'], id=id, record_revision=record['version'], snapshot_hash=digest(record))]

    def create(self, request='create', **overrides):
        args = dict(branch='main', node_id=self.node, request_id=request,
                    expected_world_revision=self.engine.branch('main')['revision'],
                    method=self.definition(), source_refs=self.refs())
        args.update(overrides)
        return self.methods.create(**args)

    def assign(self, method, request='assign', **overrides):
        args = dict(branch='main', node_id=self.node, method_id=method['method_id'], method_revision=method['revision'],
                    request_id=request, expected_world_revision=self.engine.branch('main')['revision'],
                    qualification='experimental', rationale='Operator-approved synthetic trial only.')
        args.update(overrides)
        return self.methods.assign(**args)

    def patch(self, id, **changes):
        record = self.engine.get('main', id)
        change = dict(op='patch', id=id, expected_version=record['version'], evidence=[{'note': 'Synthetic revision'}])
        change.update(changes)
        return self.engine.apply(dict(api_version=3, branch='main', expected_revision=self.engine.branch('main')['revision'],
                               request_id='patch:' + id + ':' + str(record['version']), kind='correction', actor='fixture',
                               narrative='Synthetic correction', causes=[record['updated_event']], changes=[change]))

    def test_persistence_and_no_story_mutation(self):
        created = self.create(); self.assign(created)
        before = self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer')
        self.assertEqual(len(before), 1)
        self.assertEqual(before[0]['revision'], 1)
        self.assertIn('not established mastery', before[0]['qualification_limit'])
        self.assertNotIn('OWNER_EVIDENCE_CANARY', json.dumps(before))
        self.engine.close(); self.engine = Engine(self.path); self.methods = Methods(self.engine)
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer'), before)
        self.assertEqual(self.engine.branch('main')['revision'], 1)
        self.assertEqual(self.engine.db.execute('SELECT count(*) FROM events').fetchone()[0], 1)
        self.assertEqual(verify_methods(self.engine)['methods'], 1)

    def test_explicit_qualification_and_exact_domain(self):
        created = self.create()
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice'), [])
        self.assign(created, qualification='proposed')
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice'), [])
        self.assign(created, request='authorize', expected_assignment_revision=1)
        self.assertEqual(len(self.methods.eligible('main', 'a', 'fixture.choice')), 1)
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture'), [])
        self.assertEqual(self.methods.eligible('main', 'a', 'medicine'), [])
        with self.assertRaises(Rejected):
            self.assign(created, request='mastery', expected_assignment_revision=2, qualification='mastered')

    def test_request_replay_and_revoke_do_not_reactivate(self):
        created = self.create(); duplicate = self.create()
        self.assertTrue(duplicate['replayed']); self.assertEqual(duplicate['method_id'], created['method_id'])
        with self.assertRaises(Rejected):
            self.create(method=self.definition(name='Conflicting payload'))
        assignment = self.assign(created)
        self.assign(created, request='revoke', qualification='revoked', expected_assignment_revision=1)
        replay = self.assign(created)
        self.assertTrue(replay['replayed']); self.assertEqual(replay['assignment_revision'], assignment['assignment_revision'])
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice'), [])
        self.assertEqual(verify_methods(self.engine)['assignments'], 2)

    def test_revision_is_immutable_and_assignment_pins_version(self):
        one = self.create(); self.assign(one)
        two = self.methods.revise('main', self.node, one['method_id'], 1, 'revise', 1,
                                  self.definition(name='A decorative rename', visibility='gm'), self.refs())
        self.assertEqual(two['revision'], 2)
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer')[0]['revision'], 1)
        self.assign(two, request='adopt', expected_assignment_revision=1)
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer'), [])
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice')[0]['revision'], 2)
        self.assertEqual(self.methods.read('main', one['method_id'], 1)['definition']['name'], 'Fixture comparison')
        for table in ('method_revisions', 'node_method_assignments', 'method_events'):
            with self.assertRaises(sqlite3.IntegrityError):
                self.engine.db.execute('DELETE FROM ' + table)
        with self.assertRaises(Rejected):
            self.methods.revise('main', self.node, one['method_id'], 1, 'stale', 1, self.definition(), self.refs())
        self.assertEqual(verify_methods(self.engine)['revisions'], 2)

    def test_current_and_historical_source_visibility(self):
        created = self.create(); self.assign(created)
        self.patch('source', visibility='gm')
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer'), [])
        self.assertFalse(self.methods.read('main', created['method_id'])['source_fresh'])
        with self.assertRaises(Rejected):
            self.methods.read('main', created['method_id'], viewer='viewer')
        private = self.create(request='private', source_refs=self.refs('private-source'))
        self.assign(private, request='private-assign')
        self.patch('private-source', visibility='public')
        with self.assertRaises(Rejected):
            self.methods.read('main', private['method_id'], viewer='viewer')

    def test_stale_source_revision_and_digest_block_use(self):
        created = self.create(); self.assign(created)
        original = self.refs()
        self.patch('source', data={'function': 'Changed causal context'})
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice'), [])
        with self.assertRaises(Rejected):
            self.create(request='stale-source', source_refs=original)
        with self.assertRaises(Rejected):
            self.assign(created, request='reapprove-stale', expected_assignment_revision=1)
        # Even an illicit same-version projection change cannot bypass digest freshness.
        refreshed = self.create(request='refreshed'); self.assign(refreshed, request='refreshed-assign')
        self.engine.db.execute("UPDATE ability SET function='Illicit mutation' WHERE branch='main' AND id='source'")
        self.assertEqual(self.methods.eligible('main', 'a', 'fixture.choice'), [])

    def test_restricted_audience_identifiers_are_not_disclosed(self):
        created = self.create(method=self.definition(visibility='restricted', audience=['viewer', 'secret']))
        self.assign(created)
        view = self.methods.read('main', created['method_id'], viewer='viewer')
        self.assertNotIn('audience', view['definition'])
        self.assertNotIn('secret', json.dumps(view))
        self.assertEqual(len(self.methods.eligible('main', 'a', 'fixture.choice', viewer='viewer')), 1)
        with self.assertRaises(Rejected):
            self.methods.read('main', created['method_id'], viewer='a')

    def test_branch_and_workspace_do_not_inherit_methods(self):
        created = self.create(); self.assign(created)
        self.engine.fork('main', 'other', 1)
        Nodes(self.engine).bind('other', 'a', 'bind-other', 0, {'note': 'Explicit identity only'}, node_id=self.node)
        self.assertEqual(self.methods.eligible('other', 'a', 'fixture.choice'), [])
        with self.assertRaises(Rejected):
            self.methods.read('other', created['method_id'])
        with self.assertRaises(Rejected):
            self.methods.read('main', created['method_id'], workspace_id='world:other')
        with self.assertRaises(Rejected):
            self.methods.assign('other', self.node, created['method_id'], 1, 'inherit', 0, 'experimental', 'Cannot inherit implicitly')
        other_source = self.engine.get('other', 'source')
        child = self.create(request='child-method', branch='other', expected_world_revision=0,
                            source_refs=[dict(domain='ability', id='source', record_revision=other_source['version'], snapshot_hash=digest(other_source))])
        self.assertNotEqual(child['method_id'], created['method_id'])
        self.assertEqual(verify_methods(self.engine)['methods'], 2)

    def test_wrong_owner_and_invalid_contracts_leave_no_rows(self):
        for overrides in ({'viewer': 'viewer'}, {'expected_world_revision': True},
                          {'source_refs': [{'domain': 'ability', 'id': 'source', 'record_revision': True}]},
                          {'method': self.definition(domains=['fixture.choice', 'fixture.choice'])},
                          {'method': self.definition(operation={'kind': 'x', 'params': {'weight': float('nan')}})},
                          {'method': self.definition(relationships=[{'source': 'unknown', 'relation': 'requires', 'target': 'candidate'}])}):
            with self.assertRaises(Rejected):
                self.create(**overrides)
        self.assertEqual(self.engine.db.execute('SELECT count(*) FROM method_revisions').fetchone()[0], 0)

    def test_outer_rollback_keeps_world_and_methods_atomic(self):
        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.engine.db):
                created = self.create(); self.assign(created)
                self.patch('source', data={'function': 'Rolled back'})
                raise RuntimeError('Synthetic interruption')
        self.assertEqual(self.methods.list('main', 'a'), [])
        self.assertEqual(self.engine.branch('main')['revision'], 1)
        self.assertEqual(verify_methods(self.engine)['methods'], 0)

    def test_assignment_cas_and_no_cross_node_adoption(self):
        created = self.create(); self.assign(created)
        with self.assertRaises(Rejected):
            self.assign(created, request='stale-assignment')
        other_node = Nodes(self.engine).bind('main', 'viewer', 'bind-viewer', 1, {'note': 'Synthetic second node'})['node_id']
        with self.assertRaises(Rejected):
            self.assign(created, request='steal-method', node_id=other_node)
        self.assertEqual(verify_methods(self.engine)['assignments'], 1)


if __name__ == '__main__':
    unittest.main()
