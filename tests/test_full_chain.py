"""AX.2: a single executed chain, checked through real saved outputs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from examples.full_chain import run
from kageyoni.application import Application
from kageyoni.engine import Engine, Rejected
from kageyoni.intelligence.network import Network
from kageyoni.intelligence.transfer import Transfers
from kageyoni.operations import Operations
from kageyoni.persistence.artifacts import Artifacts
from kageyoni.workspaces.contracts import checkpoint
from kageyoni.workspaces.pipeline import Pipelines
from kageyoni.workspaces.repository import Repository, tree_digest


class FullChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name) / 'connected'
        cls.report = run(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_recorded_journey_reaches_exact_repaired_and_delivered_output(self):
        report = json.loads((self.root / 'evidence' / 'full-chain-report.json').read_text(encoding='utf-8'))
        self.assertEqual(report, self.report)
        self.assertEqual(len(report['checks']), 20)
        self.assertTrue(all(report['checks'].values()))
        self.assertEqual(report['campaign_writes'], 0)
        engine = Engine(report['paths']['reopened_database'])
        try:
            app = Application(engine)
            self.assertEqual(checkpoint(engine, 'main'), report['checkpoint'])
            self.assertEqual(app.encounters.inspect('main', 'journey')['phase'], 'completed')
            self.assertEqual(engine.get('main', 'promise')['data']['phase'], 'open')
            self.assertEqual({row['id'] for row in engine.state('main') if row['domain'] == 'character'}, {'traveler', 'guard'})
            for item in report['documents']:
                self.assertEqual(app.nodes.read('main', item['character_id'])['node_id'], item['node_id'])
                transfer = Transfers(engine).read(item['transfer']['transfer_id'])
                self.assertEqual(transfer['status'], 'qualified')
                self.assertEqual(transfer['method_digest'], item['draft']['method_effect']['method_digest'])
                self.assertEqual(transfer['latest_trial']['trial_id'], item['draft']['method_effect']['trial_id'])
                self.assertTrue(transfer['source_current'])
                self.assertEqual(item['transition']['checkpoint'], report['checkpoint'])
            composed = Network(engine).read_composition('main', report['composition']['composition_id'])
            artifact = Artifacts(engine).read(composed['artifact']['artifact_id'])
            for body in composed['bodies']:
                self.assertIn(body['text'].encode(), artifact['content'])
            self.assertEqual(Path(report['paths']['relocated_output']).read_bytes(), artifact['content'])
            self.assertEqual((Path(report['paths']['relocated_repository']) / 'handoff.md').read_bytes(), artifact['content'])
            candidate = Repository(engine).read('main', report['repository']['promoted']['candidate_id'])
            self.assertEqual(tree_digest(report['paths']['relocated_repository']), candidate['candidate_digest'])
            self.assertEqual(candidate['attempts'][-1]['tests'], 3)
            self.assertEqual(candidate['attempts'][-1]['method_effect']['phase'], 'completed')
            flow = Pipelines(engine).read('main', report['pipeline']['pipeline_id'])
            self.assertEqual(flow['tasks']['read-synthesis']['attempts'][0]['composition_id'], composed['composition_id'])
            self.assertEqual(flow['tasks']['write-handoff']['resolved_config']['content'], artifact['content'].decode())
            self.assertEqual({key: len(value['attempts']) for key, value in flow['tasks'].items()},
                             {'check-repair': 1, 'read-synthesis': 1, 'write-handoff': 1})
            self.assertTrue(engine.verify()['ok'])
        finally:
            engine.close()

    def test_fresh_portable_import_preserves_bytes_but_cannot_use_original_roots(self):
        with zipfile.ZipFile(self.root / 'portable.zip') as archive:
            manifest = json.loads(archive.read('manifest.json'))
            self.assertEqual({item['service'] for item in manifest['external_dependencies']}, {'repository', 'pipelines'})
            self.assertFalse(any(name.startswith('repository-') or name.startswith('pipeline-output/') for name in archive.namelist()))
        restored = Operations.import_bundle(self.root / 'portable.zip', self.root / 'second-import')
        engine = Engine(restored['path'])
        original_output = Path(self.report['paths']['pipeline_output'])
        old_stat = original_output.stat()
        try:
            self.assertEqual(checkpoint(engine, 'main'), self.report['checkpoint'])
            for item in Artifacts(engine).manifest():
                raw = Artifacts(engine).read(item['artifact_id'])['content']
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['digest'])
            with self.assertRaisesRegex(Rejected, 'explicit root rebind'):
                Pipelines(engine).run('main', self.report['pipeline']['pipeline_id'])
            with self.assertRaisesRegex(Rejected, 'explicit root rebind'):
                Repository(engine).reconcile('main', self.report['repository']['promoted']['candidate_id'])
            self.assertEqual(original_output.stat().st_mtime_ns, old_stat.st_mtime_ns)
            self.assertFalse((self.root / 'second-import' / 'external').exists())
            self.assertTrue(engine.verify()['ok'])
        finally:
            engine.close()

    def test_corrupted_reopened_compilation_cannot_be_read_as_valid_evidence(self):
        engine = Engine(self.report['paths']['reopened_database'])
        artifact_id = self.report['composition']['artifact']['artifact_id']
        artifact = Artifacts(engine).read(artifact_id)
        path = Path(artifact['path'])
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\nUNRECORDED ALTERATION\n')
            with self.assertRaisesRegex(Rejected, 'corrupt'):
                Network(engine).read_composition('main', self.report['composition']['composition_id'])
        finally:
            path.write_bytes(original)
            engine.close()


if __name__ == '__main__':
    unittest.main()
