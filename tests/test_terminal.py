import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from terminal import Session, App, clone_database, parse_value, atomic_json, safe
from kageyoni.engine import Engine, Rejected
from examples.personality_journey import setup

class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.path=self.root/'world.sqlite'
        e=Engine(self.path); setup(e); e.close()
        self.s=Session(self.path)
    def tearDown(self):self.s.close(); self.temp.cleanup()
    def test_preview_commit_reopen_replay(self):
        before=self.s.engine.state()
        cmd=self.s.patch('mira','voice','Quiet and precise','Fixture editorial change')
        self.s.stage(cmd)
        self.assertEqual(before,self.s.engine.state())
        cmd['changes'][0]['data']['voice']='tampered after preview'
        self.s.commit()
        self.s.close();self.s=Session(self.path)
        self.assertEqual(self.s.engine.get('main','mira')['data']['voice'],'Quiet and precise')
        self.assertEqual(self.s.engine.replay('main')['records'],self.s.engine.state())
    def test_stale_commit_and_invalid_preview(self):
        self.s.stage(self.s.patch('mira','voice','pending','test'))
        other=Session(self.path)
        try:
            other.stage(other.patch('mira','motives','changed','test'));other.commit()
            with self.assertRaises(Rejected):self.s.commit()
        finally:other.close()
        before=self.s.engine.state()
        with self.assertRaises(Rejected):self.s.stage(self.s.patch('mira','entity_kind','not-a-kind','test'))
        self.assertIsNone(self.s.pending)
        self.assertEqual(before,self.s.engine.state())
    def test_viewer_blocks_authorship_and_filters(self):
        self.s.viewer='mira'
        self.assertNotIn('SECRET_FACTION_ORDER',json.dumps(self.s.records()))
        with self.assertRaises(Rejected):self.s.patch('mira','voice','bad','test')
        with self.assertRaises(Rejected):self.s.commit()
    def test_clone_never_overwrites_and_rejects_nonengine(self):
        with self.assertRaises(FileExistsError):clone_database(self.path,self.path)
        target=self.root/'copy.sqlite';clone_database(self.path,target)
        copied=Session(target);self.assertEqual(copied.engine.state(),self.s.engine.state());copied.close()
        junk=self.root/'junk';junk.write_text('not sqlite')
        with self.assertRaises(Exception):clone_database(junk,self.root/'bad.sqlite')
        self.assertFalse((self.root/'bad.sqlite').exists())
    def test_missing_path_does_not_create_database(self):
        with self.assertRaises(ValueError):Session(self.root/'missing.sqlite')
        self.assertFalse((self.root/'missing.sqlite').exists())
    def test_no_commit_without_preview_or_wrong_branch(self):
        with self.assertRaises(Rejected):self.s.commit()
        cmd=self.s.patch('mira','voice','new','test');cmd['branch']='other'
        with self.assertRaises(Rejected):self.s.stage(cmd)
    def test_typed_values_and_terminal_escaping(self):
        for raw in ('true','NaN','Infinity'):
            with self.assertRaises(ValueError):parse_value(raw,'number')
        with self.assertRaises(ValueError):parse_value('1.5','integer')
        self.assertEqual(parse_value('3','integer'),3)
        self.assertNotIn('\x1b',safe('\x1b[2Jsecret'))
    def test_settings_persist_and_menu_exits(self):
        data=self.root/'app'; app=App(data)
        with patch('builtins.input',side_effect=['1','35']):app.settings_menu()
        self.assertEqual(App(data).settings['page_size'],35)
        with patch('builtins.input',side_effect=['0']):app.run()
        atomic_json(data/'settings.json',{'page_size':0})
        with self.assertRaises(ValueError):App(data)

if __name__=='__main__':unittest.main()
