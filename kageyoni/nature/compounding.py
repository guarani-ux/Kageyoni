"""9. COMPOUNDING LOOP & EMPIRICAL QUALIFICATION

Purpose:
Realize the self-improving compounding cycle:
WORK
→ OBSERVE
→ EXTRACT
→ QUALIFY
→ REGISTER
→ COMPOSE
→ APPLY
→ OBSERVE AGAIN

Experience → Reusable Intelligence → Better Future Experience
WITHOUT allowing:
Experience → Self-Certified Dogma

A candidate technique emitted by Extract Technique CANNOT enter the registered library
unless it undergoes external adversarial qualification trials.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .core import (
    CognitiveDelta,
    CognitiveState,
    DeficitType,
    KnowledgeDeficit,
    NatureType,
)
from .extraction import CandidateTechnique, ExtractTechnique
from .techniques import Technique, TechniqueComposition


class UnqualifiedTechniqueError(ValueError):
    """Raised when an uncertified candidate attempts to register into the authoritative library."""
    pass


@dataclass
class QualificationTrial:
    """An empirical trial testing a candidate technique under adversarial conditions."""
    trial_id: str
    candidate_id: str
    scenario_name: str
    input_data: dict[str, Any]
    expected_outcome: Any
    observed_outcome: Any
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "candidate_id": self.candidate_id,
            "scenario_name": self.scenario_name,
            "input_data": self.input_data,
            "expected_outcome": self.expected_outcome,
            "observed_outcome": self.observed_outcome,
            "passed": self.passed,
        }


@dataclass
class QualifiedTechniqueRecord:
    """An authorized, registered technique available for composition and situated work."""
    technique_id: str
    name: str
    candidate: CandidateTechnique
    qualification_receipts: list[QualificationTrial]
    registered_at: float = field(default_factory=lambda: 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "technique_id": self.technique_id,
            "name": self.name,
            "candidate": self.candidate.to_dict(),
            "qualification_receipts": [t.to_dict() for t in self.qualification_receipts],
            "registered_at": self.registered_at,
        }


class CompoundingLoop:
    """Orchestrates the compounding lifecycle of operator intelligence."""

    def __init__(self, extractor: Optional[ExtractTechnique] = None):
        self.extractor = extractor or ExtractTechnique()
        self.registered_library: dict[str, QualifiedTechniqueRecord] = {}
        self.candidate_ledger: dict[str, CandidateTechnique] = {}
        self.trial_history: list[QualificationTrial] = []

    def extract_from_work(
        self,
        work_trace: dict[str, Any],
        state: Optional[CognitiveState] = None,
    ) -> CandidateTechnique:
        """Step 1 & 2: Extract candidate technique from observed work trace."""
        existing_summaries = [
            {"name": rec.name, "candidate_id": rec.technique_id}
            for rec in self.registered_library.values()
        ]
        result = self.extractor.extract(
            work_trace=work_trace,
            existing_library=existing_summaries,
            state=state,
        )
        cand = result.candidate
        self.candidate_ledger[cand.candidate_id] = cand
        return cand

    def qualify_candidate(
        self,
        candidate_id: str,
        evaluation_trials: Sequence[tuple[str, dict[str, Any], Any, Callable[[dict[str, Any]], Any]]],
    ) -> tuple[bool, list[QualificationTrial]]:
        """Step 3: Adversarially test the candidate against empirical trials.

        Trials must include at least:
        - One positive case (should succeed).
        - One adversarial/negative case (should detect failure/constraint).
        All trials must pass without synthetic skips.
        """
        if candidate_id not in self.candidate_ledger:
            raise ValueError(f"Candidate {candidate_id} not found in candidate ledger.")

        candidate = self.candidate_ledger[candidate_id]
        trials_recorded: list[QualificationTrial] = []
        all_passed = True

        for scenario, inp, expected, runner in evaluation_trials:
            tid = f"trial-{uuid.uuid4().hex[:8]}"
            observed = runner(inp)
            passed = (observed == expected)
            if not passed:
                all_passed = False
            trial = QualificationTrial(
                trial_id=tid,
                candidate_id=candidate_id,
                scenario_name=scenario,
                input_data=inp,
                expected_outcome=expected,
                observed_outcome=observed,
                passed=passed,
            )
            trials_recorded.append(trial)
            self.trial_history.append(trial)

        if all_passed and len(trials_recorded) >= 2:
            candidate.status = "qualified"
        else:
            candidate.status = "rejected"

        return all_passed, trials_recorded

    def register_qualified(
        self,
        candidate_id: str,
    ) -> QualifiedTechniqueRecord:
        """Step 4: Promote an empirically qualified candidate to the persistent library.

        Fails if candidate is not qualified.
        """
        if candidate_id not in self.candidate_ledger:
            raise ValueError(f"Candidate {candidate_id} not found in candidate ledger.")

        candidate = self.candidate_ledger[candidate_id]
        if candidate.status != "qualified":
            raise UnqualifiedTechniqueError(
                f"Candidate '{candidate.name}' ({candidate_id}) cannot be registered: "
                f"Status is '{candidate.status}'. Must pass qualification trials first."
            )

        # Retrieve relevant trials
        receipts = [t for t in self.trial_history if t.candidate_id == candidate_id and t.passed]

        record = QualifiedTechniqueRecord(
            technique_id=f"tech-{candidate.candidate_id[5:]}",
            name=candidate.name,
            candidate=candidate,
            qualification_receipts=receipts,
        )
        self.registered_library[record.technique_id] = record
        return record

    def compose_registered(
        self,
        technique_ids: Sequence[str],
        composition_name: str,
    ) -> TechniqueComposition:
        """Step 5: Compose qualified registered techniques into higher-order capabilities."""
        techniques: list[Technique] = []
        for tid in technique_ids:
            if tid not in self.registered_library:
                raise ValueError(f"Cannot compose: Technique '{tid}' is not registered.")
            rec = self.registered_library[tid]

            # Wrap into executable Technique adapter
            class QualifiedAdapter(Technique):
                def __init__(self, record):
                    self.technique_id = record.technique_id
                    self.name = record.name
                    self.underlying_natures = record.candidate.factored_natures

                def execute(self, state, **kwargs):
                    return {
                        "executed_technique": self.name,
                        "generator": record.candidate.invariant_generator,
                        "status": "applied",
                    }

            techniques.append(QualifiedAdapter(rec))

        return TechniqueComposition(
            composition_id=f"comp-{uuid.uuid4().hex[:8]}",
            name=composition_name,
            techniques=techniques,
        )
