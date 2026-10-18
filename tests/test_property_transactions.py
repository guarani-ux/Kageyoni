"""Native definition/rule/registry changes must obey their caller's boundary."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from kageyoni.engine import Engine,Rejected


class PropertyTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='kageyoni-property-uow-')
        self.path=Path(self.temp.name)/'world.sqlite';self.e=Engine(self.path)
        self.e.apply({'api_version':3,'branch':'main','request_id':'subject','expected_revision':0,
            'actor':'fixture','kind':'scene','narrative':'Disposable synthetic property subject.',
            'changes':[{'op':'create','domain':'character','id':'support','data':{'name':'Support fixture','entity_kind':'person'},
                'status':'proposed','visibility':'public','evidence':[{'note':'synthetic test only'}]}]})
        self.assertTrue(self.e.verify()['ok'])
        self.e.backup(Path(self.temp.name)/'before-property-maintenance.sqlite')

    def tearDown(self):self.e.close();self.temp.cleanup()

    def define(self,version=1):
        return self.e.define_property('fixture:capacity',version,'Capacity','Synthetic admitted load capacity','integer',['person'],{'min':0,'max':20},'active',unit='kg')

    def assignment(self,value,state='known'):
        return {'entity_id':'support','property_id':'fixture:capacity','definition_version':1,'state':state,
            'value':value,'unit':'kg','context':{},'epistemic_status':'reported','visibility':'public'}

    def assign_event(self,value,request_id):
        return self.e.apply({'api_version':3,'branch':'main','request_id':request_id,'expected_revision':self.e.branch('main')['revision'],
            'actor':'fixture','kind':'property_assignment','narrative':'Assign a synthetic typed base through its native event.',
            'changes':[],'properties':[self.assignment(value)]})

    def test_outer_interruption_rolls_back_definition_rule_registry_and_native_event(self):
        before=self.e.branch('main')['revision']
        with self.assertRaises(RuntimeError):
            with self.e.transaction():
                self.define()
                self.e.add_rule('fixture:support',1,'Can support 12 kg',['fixture:capacity'],[],True,
                    {'kind':'threshold','property':'fixture:capacity','threshold':12},[('fixture:capacity',1,'reads')])
                self.assign_event(15,'interrupted-property-event')
                raise RuntimeError('interrupt before outer receipt')
        self.assertEqual(self.e.branch('main')['revision'],before)
        for table in ('property_definitions','property_lifecycle','property_operations','property_values','rule_definitions','rule_dependencies'):
            self.assertEqual(self.e.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0,table)
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM registry_entries WHERE stable_id LIKE 'fixture:%'").fetchone())
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM events WHERE request_id='interrupted-property-event'").fetchone())
        self.assertTrue(self.e.verify()['ok'])

    def test_committed_native_consumer_and_reopen_retain_units_and_history(self):
        with self.e.transaction():
            self.define()
            self.e.add_rule('fixture:support',1,'Can support 12 kg',['fixture:capacity'],[],True,
                {'kind':'threshold','property':'fixture:capacity','threshold':12},[('fixture:capacity',1,'reads')])
            self.assign_event(10,'base-ten')
        self.assertFalse(self.e.evaluate_rule('fixture:support',1,'main','support')['output']['value'])
        self.assign_event(15,'base-fifteen')
        self.assertTrue(self.e.evaluate_rule('fixture:support',1,'main','support')['output']['value'])
        self.e.close();self.e=Engine(self.path)
        self.assertEqual(self.e.property_value('main','support','fixture:capacity',1)['value'],15)
        self.assign_event(10,'base-restored')
        self.assertFalse(self.e.evaluate_rule('fixture:support',1,'main','support')['output']['value'])
        self.assertTrue(self.e.verify()['ok'])
        self.assertIsNotNone(self.e.db.execute("SELECT 1 FROM events WHERE request_id='base-fifteen'").fetchone())

    def test_registration_failure_does_not_leave_half_defined_property_or_rule(self):
        with patch.object(self.e,'register_component',side_effect=RuntimeError('injected registry failure')):
            with self.assertRaises(RuntimeError):self.define()
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM property_definitions WHERE property_id='fixture:capacity'").fetchone())
        self.define()
        with patch.object(self.e,'register_component',side_effect=RuntimeError('injected registry failure')):
            with self.assertRaises(RuntimeError):
                self.e.add_rule('fixture:failed',1,'Must rollback',['fixture:capacity'],[],True,{'kind':'threshold','threshold':12},[('fixture:capacity',1,'reads')])
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id='fixture:failed'").fetchone())
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM rule_dependencies WHERE rule_id='fixture:failed'").fetchone())
        self.assertTrue(self.e.verify()['ok'])

    def test_revision_mapping_failure_preserves_old_definition_without_new_half(self):
        self.define()
        self.e.db.execute("CREATE TEMP TRIGGER fail_replacement BEFORE INSERT ON registry_dependencies WHEN NEW.relation='replaces' BEGIN SELECT RAISE(ABORT,'injected replacement failure'); END;")
        with self.assertRaises(sqlite3.IntegrityError):
            self.e.revise_property('fixture:capacity',1,2,label='Revised capacity',meaning='Synthetic new version',value_type='integer',applicability=['person'],constraints={'min':0},lifecycle='active',unit='kg')
        self.assertIsNotNone(self.e.db.execute("SELECT 1 FROM property_definitions WHERE property_id='fixture:capacity' AND definition_version=1").fetchone())
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM property_definitions WHERE property_id='fixture:capacity' AND definition_version=2").fetchone())
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM registry_entries WHERE stable_id='fixture:capacity' AND version='2'").fetchone())
        self.e.db.execute('DROP TRIGGER fail_replacement')
        self.assertTrue(self.e.verify()['ok'])

    def test_failed_nested_registry_cycle_rolls_back_only_failed_call(self):
        with self.e.transaction():
            for name in ('a','b','unrelated'):self.e.register_component('fixture',name,'1','synthetic:'+name)
            self.e.add_registry_dependency('fixture','a','1','fixture','b','1')
            with self.assertRaises(Rejected):self.e.add_registry_dependency('fixture','b','1','fixture','a','1')
            self.assertTrue(self.e.db.in_transaction)
            self.assertIsNotNone(self.e.db.execute("SELECT 1 FROM registry_entries WHERE stable_id='unrelated'").fetchone())
        self.assertEqual(self.e.db.execute("SELECT count(*) FROM registry_dependencies WHERE kind='fixture'").fetchone()[0],1)
        self.assertTrue(self.e.verify()['ok'])

    def test_admin_assignment_retirement_and_revision_still_obey_outer_rollback(self):
        self.define();self.assign_event(10,'original-base')
        before=self.e.branch('main')['revision']
        with self.assertRaises(RuntimeError):
            with self.e.transaction():
                self.e.set_property('main','support','fixture:capacity',1,'known',15,'kg',visibility='public')
                self.e.revise_property('fixture:capacity',1,2,label='New',meaning='New synthetic definition',value_type='integer',applicability=['person'],constraints={},lifecycle='active',unit='kg')
                self.e.retire_property('fixture:capacity',1,'synthetic rollback',replacement=('fixture:capacity',2))
                raise RuntimeError('interrupt all maintenance')
        self.assertEqual(self.e.property_value('main','support','fixture:capacity',1)['value'],10)
        self.assertEqual(self.e.db.execute("SELECT state FROM property_lifecycle WHERE property_id='fixture:capacity' AND definition_version=1 ORDER BY sequence DESC LIMIT 1").fetchone()[0],'active')
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM property_definitions WHERE property_id='fixture:capacity' AND definition_version=2").fetchone())
        self.assertEqual(self.e.branch('main')['revision'],before)
        self.assertTrue(self.e.verify()['ok'])

    def test_replacement_cycle_rejects_and_preserves_previous_definition(self):
        self.define()
        self.e.add_registry_dependency('property','fixture:capacity','1','property','fixture:capacity','2','synthetic forward reference')
        self.assertTrue(self.e.validate_registry()['ok'])
        with self.assertRaises(Rejected):
            self.e.revise_property('fixture:capacity',1,2,label='Revised',meaning='Synthetic revised definition',
                value_type='integer',applicability=['person'],constraints={},lifecycle='active',unit='kg')
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM property_definitions WHERE property_id='fixture:capacity' AND definition_version=2").fetchone())
        self.assertIsNone(self.e.db.execute("SELECT 1 FROM registry_entries WHERE stable_id='fixture:capacity' AND version='2'").fetchone())
        self.assertTrue(self.e.validate_registry()['ok'])
