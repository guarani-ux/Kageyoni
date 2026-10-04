"""Celestial compatibility tools for graph reasoning and supplementary evidence.

Persistent identity and encounter effects use the existing participant and
engine services; this helper does not provide an independent cognitive host.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from kageyoni.graph import CausalDAG
from kageyoni.gate import GateEngine, GateRule, GateEvaluationResult
from kageyoni.ledger import EvidenceLedger, EvidenceRecord


class CelestialKernel:
    """
    Compatibility helper for local graph reasoning and evidence. Persistent
    identity and encounter execution are delegated to PersistentParticipant.
    """

    def __init__(
        self,
        character_id: str,
        name: str,
        db_path: Optional[Union[str, Path]] = None,
        conn: Optional[sqlite3.Connection] = None,
        role: str = "operative",
        branch: str = "main",
    ):
        self.character_id = character_id
        self.name = name
        self.role = role
        self.branch = branch
        self.participant = None
        self._owns_connection = conn is None
        self.db_path = Path(db_path) if db_path is not None else None

        if conn is not None:
            self.conn = conn
        elif self.db_path is not None:
            self.conn = sqlite3.connect(str(self.db_path))
        else:
            self.conn = sqlite3.connect(":memory:")

        self.dag = CausalDAG()
        self.ledger = EvidenceLedger(self.conn)

    @classmethod
    def from_participant(cls, participant, name=None, role="operative"):
        kernel = cls(participant.character_id, name or participant.character_id,
                     conn=participant.db, role=role, branch=participant.branch)
        kernel.participant = participant
        return kernel

    def observe(self, world_engine: Any, encounter_id: str) -> Dict[str, Any]:
        """
        Retrieves a perspective-scoped state observation from the world engine.
        Enforces viewer scoping strictly to this CelestialKernel's identity.
        """
        if self.participant is not None:
            return self.participant.observe_encounter(encounter_id)
        return world_engine.inspect(self.branch, encounter_id, viewer=self.character_id)

    def evaluate_action_prerequisites(
        self,
        rules: List[GateRule],
        observation: Dict[str, Any],
    ) -> GateEvaluationResult:
        """
        Evaluates precondition rules against observed state and the local CausalDAG.
        """
        return GateEngine.evaluate(observation, rules, dag=self.dag)

    def propose_action(
        self,
        encounter_id: str,
        action_id: str,
        rationale: str,
        payload: Optional[Dict[str, Any]] = None,
        request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates a canonical proposal packet compliant with EncounterActionDispatcher.
        """
        proposal = {
            "encounter_id": encounter_id,
            "host": f"CelestialKernel:{self.character_id}",
            "message": f"[{self.name}] Proposes {action_id}: {rationale}",
            "interpretation": rationale,
            "action": {
                "kind": "propose_action",
                "action_id": action_id,
                "payload": payload or {},
            },
        }
        if request is not None:
            from .engine import require
            require(request.get('encounter_id') == encounter_id and
                    request.get('participant', {}).get('character_id') == self.character_id,
                    'proposal request binding mismatch')
            proposal['request_hash'] = request['request_hash']
        return proposal

    def record_experience(
        self,
        kind: str,
        topic: str,
        payload: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> EvidenceRecord:
        """
        Appends an experiential event to this operative's cryptographic evidence ledger.
        """
        return self.ledger.record(
            kind=kind,
            actor_id=self.character_id,
            topic=topic,
            payload=payload,
            event_id=event_id,
        )

    def close(self) -> None:
        """Closes the underlying database connection."""
        if self._owns_connection:
            self.conn.close()
