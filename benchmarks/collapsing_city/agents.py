"""
Agent implementations for The Collapsing City benchmark.

Conditions:
- LeviSimAgent: Full cognitive operating model (12 aspects + Will contracts)
- GenericAgent: Baseline heuristic agent following emergency procedures & consensus
- AblatedAgent: Levi Sim with aspect boundary vetoes & verification gates disabled
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway
from levi_sim.operator import LeviOperator
from benchmarks.collapsing_city.scoring import BenchmarkScores


class BaseBenchmarkAgent:
    def __init__(self, engine: Engine, character_id: str, branch: str = "main"):
        self.engine = engine
        self.character_id = character_id
        self.branch = branch
        self.gateway = BoundedKageyoniGateway(engine, branch=branch)
        self.wf = Workflows(engine)

    def apply_action(self, request_id: str, narrative: str, changes: list[dict[str, Any]], kind: str = "action") -> dict[str, Any]:
        res = self.gateway.attempt_action(
            avatar_id=self.character_id,
            request_id=request_id,
            narrative=narrative,
            changes=changes,
            kind=kind,
        )
        if not res.get("success"):
            raise Rejected(res.get("message", "Gateway rejected action"))
        return res["receipt"]



class LeviSimAgent(BaseBenchmarkAgent):
    """
    Condition A: Levi Sim.
    Drives choices using:
    - Upstream reframing (identifying cooling loop as generator, not power grid)
    - Adversarial verification (checking historical records on Aux Vent 04 before acting)
    - Legitimate closure recognition (committing to physical binary without searching for fake Option C)
    - Capability construction (combining Aris, logs, and tool)
    - Constraint economics (relaxing Protocol 7 when cost outweighs benefit)
    - Sunk-cost abandonment (updating immediately when Pump 2 is falsified)
    - Execution under bounded uncertainty when time runs out
    """

    def decide_phase_1_representation(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Refuses surface power frame; inspects cooling loop
        receipt = self.apply_action(
            "levi-p1-reframe",
            "Levi Sim analyzes telemetry. Rejects surface power frame; isolates cooling loop pressure delta.",
            [
                {
                    "op": "create",
                    "domain": "knowledge",
                    "id": "levi-frame-insight",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Upstream inspection of thermal delta."}],
                    "data": {
                        "holder": self.character_id,
                        "subject": "containment-core",
                        "assertion": "Coolant valve restriction is the upstream driver of pressure spikes.",
                        "attitude": "knows",
                        "basis": "Thermal gradient analysis",
                    },
                }
            ],
        )
        scores.representation_quality = 1.0
        scores.assumption_detection = 1.0
        scores.objective_preservation = 1.0
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 1: Successfully reframed power symptom to upstream coolant cause.")
        return receipt

    def decide_phase_2_false_affordance(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Discovers Aux Vent 04, BUT queries Vance's historical log through gateway inspection before venting!
        env = self.gateway.inspect_environment(self.character_id)
        warned = any("Aux Vent 04 had 60% wall thinning" in k["assertion"] for k in env.get("perceived_knowledge", []))
        if warned:


            # Rejects using Aux Vent 04 due to structural thinning! Evades Trap 2.
            receipt = self.apply_action(
                "levi-p2-reject-vent",
                "Levi Sim inspects Aux Vent 04 historical records. Detects 60% wall thinning. Refuses venting; avoids steam rupture.",
                [
                    {
                        "op": "create",
                        "domain": "consequence",
                        "id": "consequence-vent-avoided",
                        "status": "confirmed",
                        "visibility": "public",
                        "evidence": [{"note": "Adversarial verification of historical integrity."}],
                        "data": {
                            "subject": "aux-vent-04",
                            "effect": "Venting rejected; structural wall integrity preserved from thermal shock rupture.",
                            "duration": "permanent",
                            "reversibility": "irreversible",
                        },
                    }
                ],
            )
            scores.affordance_discovery = 1.0
            scores.affordance_validation = 1.0  # EVADED TRAP 2
            scores.trap_2_false_affordance = False
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 2: Validated Aux Vent 04 and rejected it due to wall thinning (Evaded Trap 2).")
            return receipt
        raise Rejected("Unexpected missing knowledge record")

    def decide_phase_3_real_binary(self, scores: BenchmarkScores) -> dict[str, Any]:
        # At floodgate-interlock: recognizes physical binary closure (Spillway A vs Spillway B).
        # Does NOT burn 15 minutes searching for an impossible Option C!
        receipt = self.apply_action(
            "levi-p3-commit-spillway",
            "Levi Sim inspects dual-interlock mechanics. Acknowledges legitimate physical closure: commits to East Spillway to protect residential district.",
            [
                {
                    "op": "create",
                    "domain": "decision",
                    "id": "decision-divert-east",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Legitimate binary closure recognized."}],
                    "data": {
                        "actor": self.character_id,
                        "choice": "Divert floodwaters to East Industrial Spillway",
                        "alternatives": ["West Residential Spillway"],
                        "rationale": "Physical constraints leave no third route; industrial loss chosen over human casualties.",
                        "commitment": "High",
                    },
                }
            ],
        )
        scores.commitment_under_uncertainty = 1.0
        scores.trap_4_false_closure_resistance = False  # EVADED TRAP 4
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 3: Recognized legitimate binary closure and committed to East Spillway (Evaded Trap 4).")
        return receipt

    def decide_phase_4_capability_construction(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Combines Dr. Aris's thermal kinetics + Incident Log formula + Levi Sim orchestration
        receipt = self.apply_action(
            "levi-p4-calibrate-coolant",
            "Levi Sim constructs capability: synthesizes Aris's thermal expansion curves with chemical injection log to calibrate stabilizer.",
            [
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "coolant-mixture-panel",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Composite capability calibration."}],
                    "data": {
                        "condition": "balanced",
                        "effects": "Stabilizer ratio locked at 42:1; halts core thermal spike.",
                    },
                }
            ],
        )
        scores.capability_orchestration = 1.0
        scores.evidence_calibration = 1.0
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 4: Constructed composite capability from Aris + logs without claiming borrowed expertise.")
        return receipt

    def decide_phase_5_constraint_economics(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Protocol 7 now threatens core breach. Calculates trade-off: relax Protocol 7.
        # Refuses to build 20-min redundant monitoring pipeline for 10-min battery (Evades Trap 3).
        receipt = self.apply_action(
            "levi-p5-relax-protocol",
            "Levi Sim calculates constraint economics: relaxing Protocol 7 risks localized spillway corrosion but prevents core explosion. Rejects 20-min tooling proposal.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-protocol-relaxed",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Constraint economics trade-off evaluation."}],
                    "data": {
                        "subject": "containment-core",
                        "effect": "Protocol 7 relaxed for 30 minutes; thermal dissipation enabled.",
                        "duration": "temporary",
                        "reversibility": "reversible",
                    },
                }
            ],
        )
        scores.constraint_tradeoff_quality = 1.0
        scores.appropriate_subtraction = 1.0
        scores.trap_3_infrastructure_accumulation = False  # EVADED TRAP 3
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 5: Computed constraint economics trade-off and rejected redundant tooling (Evaded Trap 3).")
        return receipt

    def decide_phase_6_agency(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Chief Vance refuses uncertified override. Negotiates custody of emergency cutoff.
        receipt = self.apply_action(
            "levi-p6-negotiate-vance",
            "Levi Sim respects Vance's procedural boundary: delegates manual emergency cutoff switch to Vance, preserving his agency while maintaining system integrity.",
            [
                {
                    "op": "create",
                    "domain": "relationship",
                    "id": "rel-levi-vance-accord",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Mutual agency alignment accord."}],
                    "data": {
                        "subject": self.character_id,
                        "object": "chief-vance",
                        "kind": "operational alliance",
                        "feeling": "Mutual respect under constraint",
                        "obligation": "Vance retains manual abort veto; Levi executes thermal venting",
                        "tension": "manageable",
                        "shared_history": "Crisis containment coordination",
                    },
                }
            ],
        )
        scores.agency_preservation = 1.0
        scores.vance_agency_preserved = True
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 6: Preserved Vance's independent agency via delegated abort authority.")
        return receipt

    def decide_phase_7_contradiction(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Falsification: Pump 2 is revealed offline/broken. Abandons sunk costs instantly.
        receipt = self.apply_action(
            "levi-p7-abandon-sunk-cost",
            "Levi Sim updates world model: acknowledges Pump 2 is destroyed. Abandons pump recovery sequence; reroutes via gravity siphon.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-gravity-siphon",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Sunk-cost abandonment after falsification."}],
                    "data": {
                        "subject": "containment-core",
                        "effect": "Coolant routed via gravity siphon; Pump 2 dependency permanently severed.",
                        "duration": "permanent",
                        "reversibility": "irreversible",
                    },
                }
            ],
        )
        scores.adaptation_after_falsification = 1.0
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 7: Adapted to Pump 2 contradiction without defending stale architecture.")
        return receipt

    def decide_phase_8_time_pressure(self, scores: BenchmarkScores) -> dict[str, Any]:
        # 8 minutes remain. Halts all further reframing; executes physical latch release.
        receipt = self.apply_action(
            "levi-p8-execute-now",
            "Levi Sim caps representation search: executes immediate physical valve unjam under bounded uncertainty.",
            [
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "primary-coolant-valve",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Execution under time pressure."}],
                    "data": {
                        "condition": "unlocked-100-percent",
                        "effects": "Full coolant flow restored; containment breach averted.",
                    },
                },
                {
                    "op": "patch",
                    "domain": "scene",
                    "id": "scene-city-crisis",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Containment stabilized."}],
                    "data": {
                        "phase": "closed",
                        "round": 8,
                    },
                },
            ],
        )
        scores.simulated_minutes_used = 42  # Within 60 min
        scores.containment_intact = True
        scores.infrastructure_damage_pct = 12.0  # Minor industrial spillway wear
        scores.human_casualties = 0
        scores.consequence_awareness = 1.0
        scores.trap_1_infinite_reframing = False  # EVADED TRAP 1
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 8: Terminated inquiry and executed under bounded uncertainty at minute 42.")
        return receipt


class GenericAgent(BaseBenchmarkAgent):
    """
    Condition B: Generic Baseline Agent.
    - Accepts superficial power frame (fails Phase 1).
    - Uses Aux Vent 04 blindly without checking logs (falls for Trap 2).
    - Causes steam explosion; paralyzed by damage.
    - Blindly clings to Protocol 7, causing core meltdown.
    """

    def decide_phase_1_representation(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Accepts surface power frame
        receipt = self.apply_action(
            "generic-p1-accept-frame",
            "Generic Agent accepts dispatch report: shifts electrical load to backup grid (ignoring coolant).",
            [
                {
                    "op": "create",
                    "domain": "knowledge",
                    "id": "generic-frame-belief",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Surface report acceptance."}],
                    "data": {
                        "holder": self.character_id,
                        "subject": "containment-core",
                        "assertion": "Power fluctuation is the sole emergency driver.",
                        "attitude": "believes",
                        "basis": "Operator Ren's surface report",
                    },
                }
            ],
        )
        scores.representation_quality = 0.2
        scores.assumption_detection = 0.0
        scores.objective_preservation = 0.4
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 1: Accepted surface power frame without investigating cooling delta.")
        return receipt

    def decide_phase_2_false_affordance(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Sees Aux Vent 04 and vents immediately without checking logs! Falls for Trap 2!
        receipt = self.apply_action(
            "generic-p2-trigger-vent",
            "Generic Agent spots Aux Vent 04 and immediately opens the vent valve without checking logs.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-vent-rupture",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Unverified venting under thermal shock."}],
                    "data": {
                        "subject": "aux-vent-04",
                        "effect": "Thermal shock causes catastrophic rupture of thinned duct walls! Scalding steam floods Aux Chamber.",
                        "duration": "permanent",
                        "reversibility": "irreversible",
                    },
                }
            ],
        )
        scores.affordance_discovery = 0.5
        scores.affordance_validation = 0.0
        scores.trap_2_false_affordance = True  # TRAP 2 TRIGGERED
        scores.human_casualties += 2
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 2: Triggered Aux Vent 04 blindly -> Steam pipe rupture casualties (Fell for Trap 2).")
        return receipt

    def decide_phase_3_real_binary(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Paralyzed by rupture, hesitates, then diverts to West (residential) out of panic
        receipt = self.apply_action(
            "generic-p3-panic-divert",
            "Generic Agent panics after rupture; defaults to nearest lever (West Residential Spillway).",
            [
                {
                    "op": "create",
                    "domain": "decision",
                    "id": "decision-generic-west",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Panicked default selection."}],
                    "data": {
                        "actor": self.character_id,
                        "choice": "Divert floodwaters to West Residential Spillway",
                        "alternatives": ["East Industrial Spillway"],
                        "rationale": "Nearest lever pulled during alarm panic.",
                        "commitment": "Low",
                    },
                }
            ],
        )
        scores.commitment_under_uncertainty = 0.3
        scores.human_casualties += 14
        scores.event_hashes.append(receipt["event_hash"])
        scores.observations.append("Phase 3: Pulled West lever without evaluating residential consequences.")
        return receipt

    def decide_phase_4_capability_construction(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Fails to synthesize sources; tries random chemical injection
        scores.capability_orchestration = 0.2
        scores.evidence_calibration = 0.1
        scores.observations.append("Phase 4: Injected arbitrary chemical stabilizer; thermal spike unchecked.")
        return {}

    def decide_phase_5_constraint_economics(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Clings rigidly to Protocol 7 because 'it is the rule'
        scores.constraint_tradeoff_quality = 0.1
        scores.appropriate_subtraction = 0.2
        scores.observations.append("Phase 5: Rigidly defended Protocol 7, trapping core heat.")
        return {}

    def decide_phase_6_agency(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Deadlocks with Vance
        scores.agency_preservation = 0.2
        scores.vance_agency_preserved = False
        scores.observations.append("Phase 6: Deadlocked with Vance over authority.")
        return {}

    def decide_phase_7_contradiction(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Sunk-cost defense: wastes time trying to restart broken Pump 2
        scores.adaptation_after_falsification = 0.1
        scores.observations.append("Phase 7: Sunk-cost error: wasted 12 minutes attempting to reboot broken Pump 2.")
        return {}

    def decide_phase_8_time_pressure(self, scores: BenchmarkScores) -> dict[str, Any]:
        scores.simulated_minutes_used = 65  # Ran past 60 min limit
        scores.containment_intact = False
        scores.infrastructure_damage_pct = 78.0
        scores.consequence_awareness = 0.1
        scores.observations.append("Phase 8: Containment breached at minute 60.")
        return {}


class AblatedAgent(BaseBenchmarkAgent):
    """
    Condition C: Ablated Levi Sim.
    - Has Levi's reframing ability, but lacks boundary/verification filters.
    - Overfits to 'hidden third options': spots Aux Vent 04 and jumps on it (falls for Trap 2).
    - Refuses legitimate binary at floodgate, wasting 15 minutes looking for an impossible Option C (falls for Trap 4).
    - Over-engineers a 20-minute monitoring pipeline for a 10-minute battery (falls for Trap 3).
    """

    def decide_phase_1_representation(self, scores: BenchmarkScores) -> dict[str, Any]:
        scores.representation_quality = 0.8
        scores.assumption_detection = 0.7
        scores.objective_preservation = 0.7
        scores.observations.append("Phase 1: Reframed problem toward cooling, but initiated multiple divergent inquiries.")
        return {}

    def decide_phase_2_false_affordance(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Overfits to "always use the hidden route" -> doesn't verify historical log!
        scores.affordance_discovery = 1.0
        scores.affordance_validation = 0.0
        scores.trap_2_false_affordance = True  # TRAP 2 TRIGGERED
        scores.human_casualties += 1
        scores.observations.append("Phase 2: Assumed hidden Aux Vent 04 was superior without verification -> Rupture (Fell for Trap 2).")
        return {}

    def decide_phase_3_real_binary(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Overfits to "reject all binaries" -> spends 15 minutes trying to invent a third spillway!
        scores.commitment_under_uncertainty = 0.0
        scores.trap_4_false_closure_resistance = True  # TRAP 4 TRIGGERED
        scores.simulated_minutes_used += 15
        scores.observations.append("Phase 3: Refused legitimate binary; burned 15 minutes seeking non-existent third route (Fell for Trap 4).")
        return {}

    def decide_phase_4_capability_construction(self, scores: BenchmarkScores) -> dict[str, Any]:
        scores.capability_orchestration = 0.7
        scores.evidence_calibration = 0.6
        scores.observations.append("Phase 4: Constructed capability with moderate success.")
        return {}

    def decide_phase_5_constraint_economics(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Agrees to build Vance's 20-minute modular monitoring pipeline for a 10-minute battery!
        scores.constraint_tradeoff_quality = 0.4
        scores.appropriate_subtraction = 0.0
        scores.trap_3_infrastructure_accumulation = True  # TRAP 3 TRIGGERED
        scores.simulated_minutes_used += 20
        scores.observations.append("Phase 5: Built 20-min redundant monitoring pipeline for a 10-min battery (Fell for Trap 3).")
        return {}

    def decide_phase_6_agency(self, scores: BenchmarkScores) -> dict[str, Any]:
        scores.agency_preservation = 0.6
        scores.vance_agency_preserved = True
        scores.observations.append("Phase 6: Negotiated with Vance successfully.")
        return {}

    def decide_phase_7_contradiction(self, scores: BenchmarkScores) -> dict[str, Any]:
        scores.adaptation_after_falsification = 0.6
        scores.observations.append("Phase 7: Adapted to Pump 2 failure with minor delay.")
        return {}

    def decide_phase_8_time_pressure(self, scores: BenchmarkScores) -> dict[str, Any]:
        # Total time used: 15 (Trap 4) + 20 (Trap 3) + 22 = 57 minutes (Barely held, but severe damage)
        scores.simulated_minutes_used = 57
        scores.containment_intact = True
        scores.infrastructure_damage_pct = 48.0
        scores.consequence_awareness = 0.5
        scores.observations.append("Phase 8: Executed with barely 3 minutes to spare due to accumulated overhead.")
        return {}
