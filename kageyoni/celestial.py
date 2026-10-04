"""
kageyoni.celestial: Unified Celestial Kernel.

Consolidates character models, state hydration, perspective-scoped observation,
local causal DAG epistemic reasoning, and persistent cryptographic evidence tracking
into a singular operative identity kernel.
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
    Unified operative participant kernel with situated causal reasoning
    and cryptographic continuity.
    """

    def __init__(
        self,
        character_id: str,
        name: str,
        db_path: Optional[Union[str, Path]] = None,
        conn: Optional[sqlite3.Connection] = None,
        role: str = "operative",
    ):
        self.character_id = character_id
        self.name = name
        self.role = role
        self.db_path = Path(db_path) if db_path is not None else None

        if conn is not None:
            self.conn = conn
        elif self.db_path is not None:
            self.conn = sqlite3.connect(str(self.db_path))
        else:
            self.conn = sqlite3.connect(":memory:")

        self.dag = CausalDAG()
        self.ledger = EvidenceLedger(self.conn)

    def observe(self, world_engine: Any, encounter_id: str) -> Dict[str, Any]:
        """
        Retrieves a perspective-scoped state observation from the world engine.
        Enforces viewer scoping strictly to this CelestialKernel's identity.
        """
        return world_engine.inspect("main", encounter_id, viewer=self.character_id)

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
    ) -> Dict[str, Any]:
        """
        Generates a canonical proposal packet compliant with EncounterActionDispatcher.
        """
        return {
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
        self.conn.close()
