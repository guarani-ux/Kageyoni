import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_pipelines
from kageyoni.workspaces.pipeline import Pipelines


class PipelineV11MandatoryMediationTests(unittest.TestCase):
    def test_run_installs_v11_before_execution(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/"engine.sqlite"
            engine=Engine.create(db,seed=17)
            try:
                install_pipelines(engine)
                self.assertIsNone(engine.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v11_operations'").fetchone())
                p=Pipelines(engine).create("main","req:mandatory-v11",[{"id":"manual","kind":"manual","dependencies":[],"config":{"instruction":"bounded"}}],viewer="owner")
                Pipelines(engine).run("main",p["pipeline_id"],viewer="owner")
                self.assertIsNotNone(engine.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v11_operations'").fetchone())
                row=engine.db.execute("SELECT scope,state FROM v11_operations WHERE scope='pipeline' ORDER BY created_at DESC LIMIT 1").fetchone()
                self.assertIsNotNone(row)
            finally:
                engine.close()

if __name__=="__main__": unittest.main()
