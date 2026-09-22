from __future__ import annotations
import json
from .service import SituationService
from .storage import SQLiteSituationStore

class KageyoniSituationAdapter:
    """Bridge Situation Architecture to existing Kageyoni state/services."""
    def __init__(self, engine):
        self.engine=engine
        self.db=engine.db

    def service(self):
        return SituationService(
            SQLiteSituationStore(self.db),
            participant_evidence_resolver=self.participant_evidence,
        )

    def workspace_context(self, workspace_id, viewer=None):
        from kageyoni.workspaces.registry import Registry
        return Registry(self.engine).read(workspace_id,viewer=viewer)["context"]

    def evidence(self, ref, run=None):
        if not isinstance(ref,str) or ":" not in ref:
            return False
        kind,value=ref.split(":",1)
        if kind=="event":
            return self.db.execute("SELECT 1 FROM events WHERE id=?",(value,)).fetchone() is not None
        if kind=="artifact":
            return self.db.execute("SELECT 1 FROM artifacts WHERE artifact_id=?",(value,)).fetchone() is not None
        if kind=="method":
            return self.db.execute("SELECT 1 FROM method_revisions WHERE method_id=?",(value,)).fetchone() is not None
        if kind=="pipeline":
            row=self.db.execute("SELECT payload_json FROM pipeline_runs WHERE pipeline_id=?",(value,)).fetchone()
            return bool(row and json.loads(row[0]).get("phase")=="completed")
        if kind=="v11-execution":
            return self.db.execute("SELECT 1 FROM v11_execution_receipts WHERE receipt_id=?",(value,)).fetchone() is not None
        return False

    def participant_evidence(self, participant_id, ref, situation_id):
        if not isinstance(ref,str) or ":" not in ref:
            return False
        kind,value=ref.split(":",1)
        if kind=="method":
            return self.db.execute(
                """SELECT 1
                   FROM node_method_assignments a
                   LEFT JOIN node_bindings b ON b.node_id=a.node_id
                   WHERE a.method_id=? AND (a.node_id=? OR b.character_id=?)
                     AND a.qualification!='revoked'
                   LIMIT 1""",
                (value,participant_id,participant_id),
            ).fetchone() is not None
        if kind=="event":
            return self.db.execute(
                "SELECT 1 FROM events WHERE id=? AND actor=?",
                (value,participant_id),
            ).fetchone() is not None
        return False
