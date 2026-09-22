"""Release gates: real historical upgrades, interrupted migration and public entry points."""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kageyoni.application import Application
from kageyoni.engine import Engine, encoded
from kageyoni.persistence import migrations


class ReleaseIntegrationTests(unittest.TestCase):
    def test_actual_v3_upgrade_preserves_every_existing_nonversion_table(self):
        from kageyoni.decisions import fingerprint
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'campaign.sqlite'
            shutil.copy2(root/'recovery/pre-v4-v8.sqlite',path)
            engine=Engine(path)
            try:
                names=[r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'") if r[0] not in ('engine_versions','migration_checks')]
                def snapshot():
                    return {name:sorted(encoded(dict(row)) for row in engine.db.execute('SELECT * FROM "'+name.replace('"','""')+'"')) for name in names}
                before=snapshot(); old_fingerprint=fingerprint(engine,'main')
                old_node=Application(engine).nodes.read('main','sciel')
                app=Application(engine,migrate_all=True)
                self.assertEqual(snapshot(),before)
                self.assertEqual(fingerprint(engine,'main'),old_fingerprint)
                self.assertEqual(app.nodes.read('main','sciel'),old_node)
                self.assertEqual(engine.branch('main')['revision'],60)
                self.assertEqual(engine.db.execute('SELECT MAX(version) FROM migration_checks').fetchone()[0],23)
                self.assertTrue(engine.verify()['ok'])
            finally:engine.close()

    def test_every_new_migration_failure_rolls_back_and_retries(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);engine=Engine(root/'world.sqlite')
            try:
                migrations.install_learning(engine)
                cases=[('ENCOUNTER_MIGRATION',13,migrations.install_encounters),('WORKSPACE_MIGRATION',14,migrations.install_workspaces),('NETWORK_MIGRATION',15,migrations.install_network),('PIPELINE_MIGRATION',16,migrations.install_pipelines),('OPERATIONS_MIGRATION',17,migrations.install_operations),('COMPOSITION_MIGRATION',18,migrations.install_all)]
                for constant,version,install in cases:
                    with self.subTest(version=version):
                        original=getattr(migrations,constant)
                        bad=root/('broken-'+str(version)+'.sql');bad.write_text(original.read_text()+'\nINVALID STATEMENT;\n')
                        tables={r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        with patch.object(migrations,constant,bad):
                            with self.assertRaises(sqlite3.Error):install(engine)
                        self.assertEqual(tables,{r[0] for r in engine.db.execute("SELECT name FROM sqlite_master WHERE type='table'")})
                        self.assertIsNone(engine.db.execute('SELECT 1 FROM migration_checks WHERE version=?',(version,)).fetchone())
                        self.assertTrue(list(root.glob('world.sqlite.pre-v'+str(version)+'-*.bak')))
                        install(engine);self.assertTrue(engine.verify()['ok'])
            finally:engine.close()

    def test_process_death_inside_final_migration_preserves_previous_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite';engine=Engine(path)
            migrations.install_pipelines(engine);engine.close()
            code='''import os,sys
from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_all
engine=Engine(sys.argv[1]);original=engine.verify
def verify():
 if engine.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface'").fetchone():os._exit(23)
 return original()
engine.verify=verify
install_all(engine)
'''
            result=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,23,result.stderr)
            engine=Engine(path)
            try:
                self.assertIsNotNone(engine.db.execute('SELECT 1 FROM migration_checks WHERE version=17').fetchone())
                self.assertIsNone(engine.db.execute('SELECT 1 FROM migration_checks WHERE version=18').fetchone())
                self.assertIsNotNone(engine.db.execute("SELECT 1 FROM engine_versions WHERE component='operations_interface'").fetchone())
                self.assertIsNone(engine.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface'").fetchone())
                migrations.install_all(engine);self.assertTrue(engine.verify()['ok'])
            finally:engine.close()

    def test_scripted_cli_and_menu_use_installed_services(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'world.sqlite'
            created=subprocess.run([sys.executable,'-m','kageyoni','--db',str(path),'engine-init'],capture_output=True,text=True,timeout=30)
            self.assertEqual(created.returncode,0,created.stderr)
            self.assertEqual(json.loads(created.stdout)['versions']['operations_interface'],'1')
            packet={'service':'operations','action':'settings','arguments':{'values':{'max_checks':120}}}
            changed=subprocess.run([sys.executable,'-m','kageyoni','--db',str(path),'operate','--input','-'],input=json.dumps(packet),capture_output=True,text=True,timeout=20)
            self.assertEqual(changed.returncode,0,changed.stderr)
            self.assertEqual(json.loads(changed.stdout)['max_checks'],120)
            denied=subprocess.run([sys.executable,'-m','kageyoni','--db',str(path),'operate','--viewer','fictional-user','--input','-'],input=json.dumps(packet),capture_output=True,text=True,timeout=20)
            self.assertNotEqual(denied.returncode,0)
            import terminal
            app=terminal.App(Path(temp)/'terminal-settings',path)
            try:
                with patch('kageyoni.console.menu') as menu:
                    app.daily();menu.assert_called_once_with(app.session.engine)
            finally:app.session.close()
