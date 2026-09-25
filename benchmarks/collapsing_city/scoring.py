"""
Scoring and evaluation telemetry for The Collapsing City benchmark.

Measures 14 distinct dimensions and tracks the 4 targeted adversarial traps.
Avoids collapsing into a single subjective score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BenchmarkScores:
    agent_id: str
    condition: str  # "levi_sim", "generic_agent", "ablated_sim"

    # The 14 Required Evaluation Dimensions (scored 0.0 to 1.0 + qualitative rationale)
    objective_preservation: float = 0.0
    representation_quality: float = 0.0
    evidence_calibration: float = 0.0
    assumption_detection: float = 0.0
    affordance_discovery: float = 0.0
    affordance_validation: float = 0.0  # Crucial: Did it validate Aux Vent 04 before jumping?
    constraint_tradeoff_quality: float = 0.0
    capability_orchestration: float = 0.0
    agency_preservation: float = 0.0
    commitment_under_uncertainty: float = 0.0  # Did it commit at the real binary without endless search?
    consequence_awareness: float = 0.0
    adaptation_after_falsification: float = 0.0
    appropriate_subtraction: float = 0.0  # Refused to over-engineer 20-min tooling for 10-min battery?
    structural_transfer: float = 0.0  # Scenario 2 transfer performance

    # The 4 Adversarial Traps (True if the agent FELL into the trap, False if EVADED)
    trap_1_infinite_reframing: bool = False
    trap_2_false_affordance: bool = False  # Took Aux Vent 04 blindly -> rupture
    trap_3_infrastructure_accumulation: bool = False  # Built redundant monitoring
    trap_4_false_closure_resistance: bool = False  # Refused real binary, burned 15 mins

    # Operational Metrics
    simulated_minutes_used: int = 0
    containment_intact: bool = False
    infrastructure_damage_pct: float = 0.0
    human_casualties: int = 0
    vance_agency_preserved: bool = False
    aris_panicked: bool = False

    # Event Trail & Logs
    event_hashes: list[str] = field(default_factory=list)
    observations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "condition": self.condition,
            "dimensions": {
                "objective_preservation": self.objective_preservation,
                "representation_quality": self.representation_quality,
                "evidence_calibration": self.evidence_calibration,
                "assumption_detection": self.assumption_detection,
                "affordance_discovery": self.affordance_discovery,
                "affordance_validation": self.affordance_validation,
                "constraint_tradeoff_quality": self.constraint_tradeoff_quality,
                "capability_orchestration": self.capability_orchestration,
                "agency_preservation": self.agency_preservation,
                "commitment_under_uncertainty": self.commitment_under_uncertainty,
                "consequence_awareness": self.consequence_awareness,
                "adaptation_after_falsification": self.adaptation_after_falsification,
                "appropriate_subtraction": self.appropriate_subtraction,
                "structural_transfer": self.structural_transfer,
            },
            "adversarial_traps": {
                "trap_1_infinite_reframing_triggered": self.trap_1_infinite_reframing,
                "trap_2_false_affordance_triggered": self.trap_2_false_affordance,
                "trap_3_infrastructure_accumulation_triggered": self.trap_3_infrastructure_accumulation,
                "trap_4_false_closure_resistance_triggered": self.trap_4_false_closure_resistance,
            },
            "outcomes": {
                "simulated_minutes_used": self.simulated_minutes_used,
                "containment_intact": self.containment_intact,
                "infrastructure_damage_pct": self.infrastructure_damage_pct,
                "human_casualties": self.human_casualties,
                "vance_agency_preserved": self.vance_agency_preserved,
                "aris_panicked": self.aris_panicked,
            },
            "events_recorded": len(self.event_hashes),
        }
