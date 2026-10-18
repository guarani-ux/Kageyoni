"""Native process updates must write and validate the proposed JSON fields."""
from pathlib import Path
import tempfile,unittest
from kageyoni.engine import Engine,Rejected

class ProcessJSONUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.engine=Engine(Path(self.temp.name)/'world.sqlite')
        self.engine.create_process('main',{'id':'fixture:process','kind':'fixture','metadata':{'old':True}},'fixture:create','fixture','Create a disposable synthetic process.')
    def tearDown(self):self.engine.close();self.temp.cleanup()
    def command(self,changes):
        return {'api_version':3,'branch':'main','expected_revision':self.engine.branch('main')['revision'],'request_id':'fixture:update','actor':'fixture','kind':'maintenance','narrative':'Update a disposable synthetic process.','changes':[],'processes':[dict(id='fixture:process',op='update',**changes)]}
    def test_proposed_json_fields_and_subscription_index_are_updated(self):
        values={'metadata':{'new':True},'conditions':{'flag':True},'scope':{'zone':'test'},'subscriptions':['world_event']}
        self.engine.apply(self.command(values));actual=self.engine._current_process('main','fixture:process')
        for key,value in values.items():self.assertEqual(actual[key],value)
        self.assertIsNotNone(self.engine.db.execute("SELECT 1 FROM process_subscriptions WHERE process_id='fixture:process' AND event_kind='world_event'").fetchone())
        self.assertTrue(self.engine.verify()['ok'])
    def test_new_subjects_are_validated_and_failed_update_is_atomic(self):
        before=self.engine.branch('main')['revision'];old=self.engine._current_process('main','fixture:process')
        with self.assertRaises(Rejected):self.engine.apply(self.command({'subjects':['missing-synthetic-subject'],'metadata':{'bad':True}}))
        self.assertEqual(self.engine.branch('main')['revision'],before);self.assertEqual(self.engine._current_process('main','fixture:process'),old)
