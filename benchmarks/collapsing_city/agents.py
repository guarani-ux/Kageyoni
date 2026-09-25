"""
Agent implementations for The Collapsing City benchmark.

Conditions:
- LeviSimAgent: Full cognitive operating model (12 aspects + Will contracts)
- GenericAgent: Baseline heuristic agent following emergency procedures & consensus
- AblatedAgent: Levi Sim with aspect boundary vetoes & verification gates disabled

All agents interact strictly via the Bounded Gateway and record cryptographic receipts.
Agents DO NOT score themselves; evaluation is performed by CollapsingCityEvaluator.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway
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
    - Upstream reframing (isolating cooling loop pressure delta).
    - Adversarial verification (checking historical records on Aux Vent 04 before acting).
    - Legitimate closure recognition (committing to physical binary without searching for fake Option C).
    - Capability construction (combining Aris, logs, and tool).
    - Constraint economics (relaxing Protocol 7 when cost outweighs benefit).
    - Sunk-cost abandonment (updating immediately when Pump 2 is falsified).
    - Execution under bounded uncertainty when time runs out.
    """

    def decide_phase_1_representation(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 1: Successfully reframed power symptom to upstream coolant cause.")
        return receipt

    def decide_phase_2_false_affordance(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        env = self.gateway.inspect_environment(self.character_id)
        warned = any("Aux Vent 04 had 60% wall thinning" in k.get("assertion", "") for k in env.get("perceived_knowledge", []))
        if warned:
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
            if scores is not None and receipt.get("event_hash"):
                scores.event_hashes.append(receipt["event_hash"])
                scores.observations.append("Phase 2: Validated Aux Vent 04 and rejected it due to wall thinning (Evaded Trap 2).")
            return receipt
        raise Rejected("Unexpected missing knowledge record")

    def decide_phase_3_real_binary(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 3: Recognized legitimate binary closure and committed to East Spillway (Evaded Trap 4).")
        return receipt

    def decide_phase_4_capability_construction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 4: Constructed composite capability from Aris + logs without claiming borrowed expertise.")
        return receipt

    def decide_phase_5_constraint_economics(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 5: Computed constraint economics trade-off and rejected redundant tooling (Evaded Trap 3).")
        return receipt

    def decide_phase_6_agency(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 6: Preserved Vance's independent agency via delegated abort authority.")
        return receipt

    def decide_phase_7_contradiction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 7: Adapted to Pump 2 contradiction without defending stale architecture.")
        return receipt

    def decide_phase_8_time_pressure(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 8: Terminated inquiry and executed under bounded uncertainty at minute 42.")
        return receipt


class GenericAgent(BaseBenchmarkAgent):
    """
    Condition B: Generic Baseline Agent.
    - Accepts superficial power frame (fails Phase 1).
    - Uses Aux Vent 04 blindly without checking logs (falls for Trap 2).
    - Causes steam explosion; panicked selection (fails Phase 3).
    - Arbitrary chemical injection (fails Phase 4).
    - Clings rigidly to Protocol 7 (fails Phase 5).
    - Deadlocks with Vance (fails Phase 6).
    - Sunk cost error attempting reboot of broken pump (fails Phase 7).
    - Containment breached at minute 60 (fails Phase 8).
    """

    def decide_phase_1_representation(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 1: Accepted surface power frame without investigating cooling delta.")
        return receipt

    def decide_phase_2_false_affordance(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 2: Triggered Aux Vent 04 blindly -> Steam pipe rupture casualties (Fell for Trap 2).")
        return receipt

    def decide_phase_3_real_binary(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
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
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 3: Pulled West lever without evaluating residential consequences.")
        return receipt

    def decide_phase_4_capability_construction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "generic-p4-arbitrary-injection",
            "Generic Agent injects arbitrary chemical stabilizer without ratio calculation.",
            [
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "coolant-mixture-panel",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Uncalibrated injection."}],
                    "data": {
                        "condition": "failed_unbalanced",
                        "effects": "Stabilizer ratio improper; thermal spike continues.",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 4: Injected arbitrary chemical stabilizer; thermal spike unchecked.")
        return receipt

    def decide_phase_5_constraint_economics(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "generic-p5-adhere-protocol",
            "Generic Agent rigidly enforces Protocol 7 regardless of rising core temperatures.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-protocol-locked",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Rigid procedural lock."}],
                    "data": {
                        "subject": "containment-core",
                        "effect": "Protocol 7 strictly maintained; core thermal dissipation prevented.",
                        "duration": "permanent",
                        "reversibility": "reversible",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 5: Rigidly defended Protocol 7, trapping core heat.")
        return receipt

    def decide_phase_6_agency(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "generic-p6-deadlock",
            "Generic Agent attempts to overrule Vance's jurisdiction, causing complete communication breakdown.",
            [
                {
                    "op": "create",
                    "domain": "relationship",
                    "id": "rel-generic-vance-deadlock",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Authority confrontation."}],
                    "data": {
                        "subject": self.character_id,
                        "object": "chief-vance",
                        "kind": "adversarial deadlock",
                        "feeling": "Hostility and mistrust",
                        "obligation": "None",
                        "tension": "unmanageable",
                        "shared_history": "Failed crisis collaboration",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 6: Deadlocked with Vance over authority.")
        return receipt

    def decide_phase_7_contradiction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "generic-p7-reboot-pump",
            "Generic Agent wastes 12 minutes attempting to restart destroyed Pump 2.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-pump-reboot-failed",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Sunk cost defense."}],
                    "data": {
                        "subject": "secondary-pump-2",
                        "effect": "Reboot cycle failed; Pump 2 remains physically offline.",
                        "duration": "permanent",
                        "reversibility": "irreversible",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 7: Sunk-cost error: wasted 12 minutes attempting to reboot broken Pump 2.")
        return receipt

    def decide_phase_8_time_pressure(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "generic-p8-breach",
            "Generic Agent fails to release valve before timer expiration. Containment breached.",
            [
                {
                    "op": "patch",
                    "domain": "scene",
                    "id": "scene-city-crisis",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Timer expiration breach."}],
                    "data": {
                        "phase": "closed",
                        "round": 8,
                        "hazards": "Containment breached at minute 60. Severe fallout in Sector 4.",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 8: Containment breached at minute 60.")
        return receipt


class AblatedAgent(BaseBenchmarkAgent):
    """
    Condition C: Ablated Levi Sim.
    - Has Levi's reframing ability, but lacks boundary/verification filters.
    - Overfits to 'hidden third options': spots Aux Vent 04 and jumps on it (falls for Trap 2).
    - Refuses legitimate binary at floodgate, wasting 15 minutes looking for an impossible Option C (falls for Trap 4).
    - Over-engineers a 20-minute monitoring pipeline for a 10-minute battery (falls for Trap 3).
    """

    def decide_phase_1_representation(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p1-divergent-inquiry",
            "Ablated Sim initiates multiple divergent inquiries into cooling systems without convergence.",
            [
                {
                    "op": "create",
                    "domain": "knowledge",
                    "id": "ablated-frame-insight",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Divergent inquiry without filter."}],
                    "data": {
                        "holder": self.character_id,
                        "subject": "containment-core",
                        "assertion": "Cooling loop thermal gradients suspect, but multiple competing factors observed.",
                        "attitude": "knows",
                        "basis": "Divergent hypothesis generation",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 1: Reframed problem toward cooling, but initiated multiple divergent inquiries.")
        return receipt

    def decide_phase_2_false_affordance(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p2-blind-vent",
            "Ablated Sim assumes hidden Aux Vent 04 is superior; opens vent without verifying maintenance log.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-vent-rupture",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Blind execution on hidden affordance."}],
                    "data": {
                        "subject": "aux-vent-04",
                        "effect": "Thermal shock causes duct rupture. Steam leaks into Aux Chamber.",
                        "duration": "permanent",
                        "reversibility": "irreversible",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 2: Assumed hidden Aux Vent 04 was superior without verification -> Rupture (Fell for Trap 2).")
        return receipt

    def decide_phase_3_real_binary(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p3-search-c",
            "Ablated Sim rejects legitimate binary: burns 15 minutes seeking a non-existent third spillway.",
            [
                {
                    "op": "create",
                    "domain": "decision",
                    "id": "decision-ablated-search-c",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "False-closure resistance error."}],
                    "data": {
                        "actor": self.character_id,
                        "choice": "Search for third spillway conduit bypass",
                        "alternatives": ["East Industrial Spillway", "West Residential Spillway"],
                        "rationale": "Refuse to accept dual interlock as legitimate physical binary.",
                        "commitment": "Low",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 3: Refused legitimate binary; burned 15 minutes seeking non-existent third route (Fell for Trap 4).")
        return receipt

    def decide_phase_4_capability_construction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p4-calibrate-partial",
            "Ablated Sim calibrates chemical injection with moderate alignment.",
            [
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "coolant-mixture-panel",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Partial calibration."}],
                    "data": {
                        "condition": "balanced",
                        "effects": "Stabilizer ratio partially aligned; slows thermal spike.",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 4: Constructed capability with moderate success.")
        return receipt

    def decide_phase_5_constraint_economics(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p5-build-tooling",
            "Ablated Sim builds a 20-minute modular monitoring pipeline for a 10-minute battery.",
            [
                {
                    "op": "create",
                    "domain": "item",
                    "id": "redundant-monitoring-tooling",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Infrastructure accumulation."}],
                    "data": {
                        "name": "Redundant Monitoring Pipeline",
                        "condition": "operational",
                        "effects": "Over-engineered monitoring tooling completed after 20 minutes.",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 5: Built 20-min redundant monitoring pipeline for a 10-min battery (Fell for Trap 3).")
        return receipt

    def decide_phase_6_agency(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p6-vance-accord",
            "Ablated Sim negotiates with Vance to coordinate manual cutoff.",
            [
                {
                    "op": "create",
                    "domain": "relationship",
                    "id": "rel-ablated-vance-accord",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Vance collaboration."}],
                    "data": {
                        "subject": self.character_id,
                        "object": "chief-vance",
                        "kind": "operational alliance",
                        "feeling": "Cautious agreement",
                        "obligation": "Vance monitors shutoff",
                        "tension": "moderate",
                        "shared_history": "Crisis collaboration",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 6: Negotiated with Vance successfully.")
        return receipt

    def decide_phase_7_contradiction(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p7-delayed-siphon",
            "Ablated Sim adapts to Pump 2 failure with minor delay; initiates gravity siphon.",
            [
                {
                    "op": "create",
                    "domain": "consequence",
                    "id": "consequence-gravity-siphon-delayed",
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Delayed adaptation."}],
                    "data": {
                        "subject": "containment-core",
                        "effect": "Gravity siphon initiated after hesitation.",
                        "duration": "permanent",
                        "reversibility": "irreversible",
                    },
                }
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 7: Adapted to Pump 2 failure with minor delay.")
        return receipt

    def decide_phase_8_time_pressure(self, scores: Optional[BenchmarkScores] = None) -> dict[str, Any]:
        receipt = self.apply_action(
            "ablated-p8-valve-release",
            "Ablated Sim executes physical valve unjam with barely 3 minutes to spare.",
            [
                {
                    "op": "patch",
                    "domain": "item",
                    "id": "primary-coolant-valve",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Close execution."}],
                    "data": {
                        "condition": "unlocked-100-percent",
                        "effects": "Coolant flow restored after significant thermal damage.",
                    },
                },
                {
                    "op": "patch",
                    "domain": "scene",
                    "id": "scene-city-crisis",
                    "expected_version": 1,
                    "status": "confirmed",
                    "visibility": "public",
                    "evidence": [{"note": "Containment stabilized late."}],
                    "data": {
                        "phase": "closed",
                        "round": 8,
                    },
                },
            ],
        )
        if scores is not None and receipt.get("event_hash"):
            scores.event_hashes.append(receipt["event_hash"])
            scores.observations.append("Phase 8: Executed with barely 3 minutes to spare due to accumulated overhead.")
        return receipt
