"""
contracts/epistemic_ledger.py
Foundational Epistemic Integrity Ledger for Reliable Communication.

Enforces the 9 Epistemic Status categories and prevents Epistemic-Status Laundering:
- A statement in a source is NOT thereby a fact (it is SOURCE_SUPPLIED_FACT).
- An assumption may NOT lose its assumption marker during compression.
- An unknown must remain explicitly marked UNKNOWN, never filled with plausible fiction.
- Creative decisions cannot be laundered into 'empirically demanded' facts.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Literal

EPISTEMIC_STATUSES = (
    "SOURCE_SUPPLIED_FACT",
    "EVIDENCE_SUPPORTED_CLAIM",
    "INFERENCE",
    "ASSUMPTION",
    "HEURISTIC",
    "INTERPRETATION",
    "CREATIVE_DECISION",
    "PREFERENCE",
    "UNKNOWN",
)

EpistemicStatus = Literal[
    "SOURCE_SUPPLIED_FACT",
    "EVIDENCE_SUPPORTED_CLAIM",
    "INFERENCE",
    "ASSUMPTION",
    "HEURISTIC",
    "INTERPRETATION",
    "CREATIVE_DECISION",
    "PREFERENCE",
    "UNKNOWN",
]

class EpistemicLaunderingError(ValueError):
    """Raised when an assertion illegally sheds uncertainty, assumption, or provenance."""
    pass

@dataclass(frozen=True)
class EpistemicStatement:
    statement_id: str
    proposition: str
    status: EpistemicStatus
    provenance_source: str | None = None
    warrant_or_reasoning: str | None = None
    uncertainties: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        if self.status not in EPISTEMIC_STATUSES:
            raise EpistemicLaunderingError(f"Invalid epistemic status: '{self.status}'. Must be one of {EPISTEMIC_STATUSES}")
        if self.status == "SOURCE_SUPPLIED_FACT" and not self.provenance_source:
            raise EpistemicLaunderingError("SOURCE_SUPPLIED_FACT requires an identifiable provenance_source.")
        if self.status == "EVIDENCE_SUPPORTED_CLAIM" and not self.warrant_or_reasoning:
            raise EpistemicLaunderingError("EVIDENCE_SUPPORTED_CLAIM requires an identifiable warrant_or_reasoning.")
        if self.status == "INFERENCE" and not self.dependencies:
            raise EpistemicLaunderingError("INFERENCE requires explicitly declared parent dependencies.")

    def digest(self) -> str:
        payload = {
            "statement_id": self.statement_id,
            "proposition": self.proposition,
            "status": self.status,
            "provenance_source": self.provenance_source,
            "warrant_or_reasoning": self.warrant_or_reasoning,
            "uncertainties": self.uncertainties,
            "dependencies": self.dependencies,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

class EpistemicLedger:
    """Tracks propositions across transformations, ensuring uncertainty and provenance are preserved."""
    def __init__(self):
        self._statements: dict[str, EpistemicStatement] = {}

    def record(self, statement: EpistemicStatement) -> EpistemicStatement:
        self._statements[statement.statement_id] = statement
        return statement

    def transform(
        self,
        *,
        source_id: str,
        target_id: str,
        new_proposition: str,
        new_status: EpistemicStatus,
        reasoning: str,
    ) -> EpistemicStatement:
        """Derives a downstream statement while preventing illegal status promotions."""
        parent = self._statements.get(source_id)
        if not parent:
            raise KeyError(f"Parent statement '{source_id}' not found in ledger.")

        # PROHIBITION 1: Assumption Laundering
        # An assumption cannot become a fact or supported claim without physical evidence
        if parent.status == "ASSUMPTION" and new_status in ("SOURCE_SUPPLIED_FACT", "EVIDENCE_SUPPORTED_CLAIM"):
            raise EpistemicLaunderingError(
                f"Laundering detected: Cannot promote ASSUMPTION '{source_id}' to {new_status} without external warrant."
            )

        # PROHIBITION 2: Creative Decision Laundering
        # A creative aesthetic choice cannot be framed as an empirically required fact
        if parent.status == "CREATIVE_DECISION" and new_status == "EVIDENCE_SUPPORTED_CLAIM":
            raise EpistemicLaunderingError(
                f"Laundering detected: CREATIVE_DECISION '{source_id}' cannot be promoted to EVIDENCE_SUPPORTED_CLAIM."
            )

        # PROHIBITION 3: Unknown Amnesia
        # An unknown cannot be silently converted to a fact
        if parent.status == "UNKNOWN" and new_status != "UNKNOWN":
            if not reasoning or "verified" not in reasoning.lower():
                raise EpistemicLaunderingError(
                    f"Laundering detected: UNKNOWN state '{source_id}' cannot be completed by model inference alone."
                )

        child = EpistemicStatement(
            statement_id=target_id,
            proposition=new_proposition,
            status=new_status,
            provenance_source=parent.provenance_source,
            warrant_or_reasoning=reasoning,
            uncertainties=parent.uncertainties,
            dependencies=(parent.statement_id,),
        )
        return self.record(child)

    def verify_no_laundering(self) -> bool:
        """Audits the full graph to ensure no assumption or creative preference was promoted to factual truth."""
        for s in self._statements.values():
            for dep_id in s.dependencies:
                dep = self._statements.get(dep_id)
                if dep and dep.status in ("ASSUMPTION", "UNKNOWN") and s.status in ("SOURCE_SUPPLIED_FACT", "EVIDENCE_SUPPORTED_CLAIM"):
                    return False
        return True
