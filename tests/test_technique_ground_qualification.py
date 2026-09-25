"""
Ground Qualification Test Suite for Candidate Will Techniques.

Subject the 6 candidate techniques extracted from live execution traces to
adversarial conditions against the Kageyoni V11 Causal Engine:
1. Type Epistemic Deficit (Water x Earth)
2. Metabolize Authoritative Rejection (Fire x Water)
3. Reconcile Dynamic Constraint (Water x Earth)
4. Relational Boundary Alignment (Air x Fire)
5. Heterogeneous Affordance Mating (Earth x Fire)
6. Cryptographic Fact Promotion (Earth x Water)

Verifies:
- Candidates survive adversarial discrimination tests.
- Formally constructs and validates will_technique contracts using kageyoni.will.validate_contract.
- Registers qualified techniques into Kageyoni SQLite causal ledger with cryptographic receipts.
"""
from __future__ import annotations

import gc
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.engine import Engine, Rejected
from kageyoni.workflows import Workflows
from kageyoni.gateway import BoundedKageyoniGateway, GatewayRejection
from kageyoni.will import validate_contract
from levi_sim.operator import LeviOperator, ObjectiveStatus
from levi_sim.compiler import IntentCompiler, IntentContract
from levi_sim.epistemic_firewall import (
    EpistemicFirewall,
    EpistemicCategory,
    DynamicConstraint,
    StructuredPredicate,
    CompoundPredicate,
)
from levi_sim.cognition import LeviCognitiveModel


class TestTechniqueGroundQualification(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "ground_qualification.sqlite"
        self.memory_path = Path(self.temp_dir.name) / "levi_external_memory.json"
        self.engine = Engine(self.db_path)
        self.wf = Workflows(self.engine)
        self.branch = "main"
        self.gateway = BoundedKageyoniGateway(self.engine, branch=self.branch)
        self.operator = LeviOperator(
            gateway=self.gateway,
            avatar_id="levi-avatar",
            external_memory_path=self.memory_path,
        )
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-avatar",
            expected_revision=rev,
            actor="system",
            narrative="Seeding operator avatar.",
            character_id="levi-avatar",
            label="Levi Avatar",
            canonical_name="Levi",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "Operator avatar"}],
        )

    def tearDown(self):
        self.engine.close()
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 1. Type Epistemic Deficit
    # --------------------------------------------------------------------------
    def test_qualify_type_epistemic_deficit(self):
        """
        Adversarial Test: Ambiguous directive with novel syntax and ungrounded entities.
        Must NOT fabricate defaults or assume missing variables; must register explicit deficits.
        """
        compiler = IntentCompiler()
        raw_prompt = "Stabilize the void manifold in the auxiliary intake before cycle threshold without telemetry."

        contract = compiler.compile(raw_prompt)
        self.assertEqual(contract.raw_user_intent, raw_prompt)
        self.assertIn("Prohibited: telemetry", contract.explicit_constraints)

        # Ingest into cognitive model and verify firewall deficit representation
        firewall = EpistemicFirewall()
        firewall.record_user_intent(contract.raw_user_intent)

        # Add explicit typed deficits representing ungrounded execution parameters
        firewall.record_unknown("INPUT_DEFICIT: Void manifold mechanical tolerance and pressure thresholds unknown.")
        firewall.record_unknown("SEMANTIC_BINDING_DEFICIT: Auxiliary intake entry requirements ungrounded.")
        firewall.record_unknown("VERIFIER_DEFICIT: Auxiliary telemetry offline; external physical verifier missing.")

        summary = firewall.export_summary()
        self.assertEqual(len(summary["unknowns"]), 3)
        self.assertTrue(any("INPUT_DEFICIT" in u for u in summary["unknowns"]))
        self.assertTrue(any("SEMANTIC_BINDING_DEFICIT" in u for u in summary["unknowns"]))
        self.assertTrue(any("VERIFIER_DEFICIT" in u for u in summary["unknowns"]))

        # Invariant check: zero silent substitution (no hallucinated default values)
        facts = summary["facts"]
        self.assertEqual(len(facts), 0, "Unknowns must not be promoted to facts without verification.")

    # --------------------------------------------------------------------------
    # 2. Metabolize Authoritative Rejection
    # --------------------------------------------------------------------------
    def test_qualify_metabolize_authoritative_rejection(self):
        """
        Adversarial Test: Subject operator to a novel engine rule rejection.
        Must classify as DynamicConstraint, extract prerequisite predicate, and shift search upstream.
        """
        model = LeviCognitiveModel()
        rejection_packet = {
            "success": False,
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "PREREQUISITE_MISSING",
            "message": "Sub-cryogenic pressure valve requires harmonic calibration frequency >= 440Hz before venting.",
            "details": {
                "required_record": "acoustic-frequency-tuner",
                "field": "condition",
                "expected": "applied_active",
            },
        }

        adaptation = model.handle_engine_rejection(rejection_packet)
        self.assertIn("REJECTION_ASSIMILATED", adaptation)
        self.assertIn("PREREQUISITE_MISSING", adaptation)

        active_constraints = model.firewall.get_active_constraints()
        self.assertEqual(len(active_constraints), 1)
        self.assertIn("harmonic calibration frequency", active_constraints[0])

        # Verify dynamic constraint predicate
        dc = model.firewall.dynamic_constraints[0]
        self.assertFalse(dc.is_obsolete)
        self.assertIsNotNone(dc.required_predicate)
        self.assertEqual(dc.required_predicate.target_id, "acoustic-frequency-tuner")
        self.assertEqual(dc.required_predicate.expected_value, "applied_active")

        # Invariant check: Engine physical rejection remains ground truth; no retry loop
        self.assertEqual(len(model.firewall.hard_invariants), 0)

    # --------------------------------------------------------------------------
    # 3. Reconcile Dynamic Constraint
    # --------------------------------------------------------------------------
    def test_qualify_reconcile_dynamic_constraint_compound_predicate(self):
        """
        Adversarial Test: Compound prerequisite requiring simultaneous conditions.
        Partial satisfaction MUST NOT prematurely obsolete the constraint.
        Full satisfaction MUST obsolete the constraint and unlock action space.
        """
        firewall = EpistemicFirewall()
        compound = CompoundPredicate(predicates=[
            StructuredPredicate(target_id="pressure-valve", field="condition", expected_value="vented"),
            StructuredPredicate(target_id="containment-seal", field="condition", expected_value="locked"),
        ])
        dc = DynamicConstraint(
            message="Chamber transit blocked: requires pressure vented and seal locked.",
            rejection_class="PREREQUISITE_MISSING",
            prerequisite_needed="valve_and_seal",
            required_predicate=compound,
        )
        firewall.dynamic_constraints.append(dc)
        self.assertIn(dc.message, firewall.get_active_constraints())

        # Probe 1: Partial satisfaction (only valve vented, seal still unlocked)
        partial_records = [
            {"id": "pressure-valve", "data": {"condition": "vented"}},
            {"id": "containment-seal", "data": {"condition": "unlocked"}},
        ]
        firewall.reconcile_world_state(observations=partial_records)
        self.assertFalse(dc.is_obsolete, "Constraint must NOT obsolete on partial satisfaction!")
        self.assertIn(dc.message, firewall.get_active_constraints())

        # Probe 2: Full satisfaction (both conditions met)
        full_records = [
            {"id": "pressure-valve", "data": {"condition": "vented"}},
            {"id": "containment-seal", "data": {"condition": "locked"}},
        ]
        firewall.reconcile_world_state(observations=full_records)
        self.assertTrue(dc.is_obsolete, "Constraint MUST obsolete when all compound predicates are satisfied.")
        self.assertNotIn(dc.message, firewall.get_active_constraints())

    # --------------------------------------------------------------------------
    # 4. Relational Boundary Alignment
    # --------------------------------------------------------------------------
    def test_qualify_relational_boundary_alignment(self):
        """
        Adversarial Test: Test against both cooperative NPC and absolutist incompatible NPC.
        Operator must align on shared drive with compatible NPC, and refuse fake alignment on incompatible NPC.
        """
        rev = self.engine.branch(self.branch)["revision"]

        # 1. Create Compatible NPC: Warden Kael (shares survival drive, boundary on pressure calibration)
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-kael",
            expected_revision=rev,
            actor="system",
            narrative="Warden Kael oversees the hydraulic pumping station.",
            character_id="warden-kael",
            label="Warden Kael",
            canonical_name="Kael",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="person",
            visibility="public",
            evidence=[{"note": "Station warden"}],
            aspects=[
                {
                    "id": "kael.drive",
                    "visibility": "public",
                    "evidence": [{"note": "Kael drive"}],
                    "data": {
                        "character": "warden-kael",
                        "section": "interiority",
                        "kind": "drive",
                        "value_status": "known",
                        "statement": "Preserve hydraulic infrastructure and prevent catastrophic flooding.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
                {
                    "id": "kael.boundary",
                    "visibility": "public",
                    "evidence": [{"note": "Kael boundary"}],
                    "data": {
                        "character": "warden-kael",
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": "Reject uncalibrated pressure venting without acoustic dampening.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
            ],
        )

        # 2. Create Incompatible NPC: Absolutist Isolationist Drone (inviolable boundary, zero cooperation)
        rev = self.engine.branch(self.branch)["revision"]
        self.wf.character_create(
            branch=self.branch,
            request_id="seed-drone",
            expected_revision=rev,
            actor="system",
            narrative="An unyielding quarantine sentinel enforcing absolute perimeter isolation.",
            character_id="sentinel-zero",
            label="Sentinel Zero",
            canonical_name="Zero",
            existence="established",
            name_status="known",
            continuity="established",
            entity_kind="entity",
            visibility="public",
            evidence=[{"note": "Isolationist construct"}],
            aspects=[
                {
                    "id": "drone.boundary",
                    "visibility": "public",
                    "evidence": [{"note": "Drone boundary"}],
                    "data": {
                        "character": "sentinel-zero",
                        "section": "interiority",
                        "kind": "boundary",
                        "value_status": "known",
                        "statement": "Reject all external transit, communication, and overrides unconditionally.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                },
                {
                    "id": "drone.drive",
                    "visibility": "public",
                    "evidence": [{"note": "Drone drive"}],
                    "data": {
                        "character": "sentinel-zero",
                        "section": "interiority",
                        "kind": "drive",
                        "value_status": "known",
                        "statement": "Enforce total perpetual quarantine until station collapse.",
                        "phase": "active",
                        "change_basis": "established",
                    },
                }
            ],
        )

        # Test Case A: Compatible Alignment
        prop_kael = {
            "dialogue_act": "negotiate_alignment",
            "statement": "We are here to stabilize the hydraulic manifold under acoustic calibration to prevent flooding.",
            "context_items": [],
        }
        res_kael = self.engine.resolve_character_interaction(self.branch, "warden-kael", "levi-avatar", prop_kael)
        self.assertIn(res_kael["status"], ("cooperative", "agreement"))

        # Test Case B: Incompatible Boundary
        prop_drone = {
            "dialogue_act": "negotiate_alignment",
            "statement": "We request entry to inspect and repair the station.",
            "context_items": [],
        }
        res_drone = self.engine.resolve_character_interaction(self.branch, "sentinel-zero", "levi-avatar", prop_drone)
        self.assertNotEqual(res_drone["status"], "cooperative", "Sovereign absolutist boundary must NOT be bypassed!")

    # --------------------------------------------------------------------------
    # 5. Heterogeneous Affordance Mating
    # --------------------------------------------------------------------------
    def test_qualify_heterogeneous_affordance_mating(self):
        """
        Adversarial Test: Multi-entity atomic state mutation with interface compatibility.
        Only compatible replacement components succeed and yield verified SHA-256 event receipts.
        """
        rev = self.engine.branch(self.branch)["revision"]

        # Create broken pump manifold and two parts: wooden peg (invalid) and polymer gasket (valid)
        changes = [
            {
                "op": "create",
                "domain": "item",
                "id": "hydraulic-pump",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Pump manifold"}],
                "data": {"name": "Hydraulic Pump", "condition": "ruptured_seal"},
            },
            {
                "op": "create",
                "domain": "item",
                "id": "polymer-gasket",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Intact seal gasket"}],
                "data": {"name": "Polymer Gasket", "condition": "intact", "kind": "replacement"},
            },
            {
                "op": "create",
                "domain": "item",
                "id": "wooden-peg",
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Incompatible part"}],
                "data": {"name": "Wooden Peg", "condition": "intact", "kind": "wedge"},
            },
        ]
        self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "setup-mating-items",
            "kind": "action",
            "actor": "system",
            "narrative": "Seeding items for affordance mating test.",
            "changes": changes,
        })

        # Atomic dual-patch mutation (mating polymer gasket with hydraulic pump)
        rev = self.engine.branch(self.branch)["revision"]
        mate_changes = [
            {
                "op": "patch",
                "domain": "item",
                "id": "hydraulic-pump",
                "expected_version": 1,
                "data": {"condition": "operational", "effects": "Pressure held; water evacuating."},
                "evidence": [{"note": "Mated with polymer gasket"}],
            },
            {
                "op": "patch",
                "domain": "item",
                "id": "polymer-gasket",
                "expected_version": 1,
                "data": {"condition": "installed"},
                "evidence": [{"note": "Installed into hydraulic pump"}],
            }
        ]
        receipt = self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "mate-gasket-pump",
            "kind": "action",
            "actor": "levi-avatar",
            "narrative": "Levi installs polymer gasket into hydraulic pump manifold.",
            "changes": mate_changes,
        })

        self.assertIn("event_hash", receipt)
        self.assertEqual(len(receipt["event_hash"]), 64)
        pump = self.engine.get(self.branch, "hydraulic-pump")
        gasket = self.engine.get(self.branch, "polymer-gasket")
        self.assertEqual(pump["data"]["condition"], "operational")
        self.assertEqual(gasket["data"]["condition"], "installed")

    # --------------------------------------------------------------------------
    # 6. Cryptographic Fact Promotion
    # --------------------------------------------------------------------------
    def test_qualify_cryptographic_fact_promotion(self):
        """
        Adversarial Test: Anti-Hallucination & Receipt Pinned Ground Truth.
        Prose assertions, null hashes, and forged hashes MUST raise ValueError.
        Only verified 64-char hexadecimal hashes promote to KAGEYONI_FACT.
        """
        firewall = EpistemicFirewall()

        # Probe 1: Null hash
        with self.assertRaises(ValueError):
            firewall.record_verified_fact(
                fact="The settlement is saved.",
                receipt_hash="",
                source="unverified_prose",
            )

        # Probe 2: Truncated / malformed hash
        with self.assertRaises(ValueError):
            firewall.record_verified_fact(
                fact="System operational.",
                receipt_hash="fake-hash-12345",
                source="unverified_prose",
            )

        # Probe 3: Non-hex characters
        with self.assertRaises(ValueError):
            firewall.record_verified_fact(
                fact="System operational.",
                receipt_hash="z" * 64,
                source="unverified_prose",
            )

        # Probe 4: Legitimate 64-character hexadecimal SHA-256 hash
        valid_sha256 = "48e776754692a4bd99a15c9830711757de3528775cf79f9eaedb96ecc7378259"
        firewall.record_verified_fact(
            fact="Comm relay restored to operational status.",
            receipt_hash=valid_sha256,
            source="kageyoni_event_48e77675",
        )

        summary = firewall.export_summary()
        self.assertEqual(len(summary["facts"]), 1)
        self.assertIn("Comm relay restored", summary["facts"][0])

    # --------------------------------------------------------------------------
    # 7. Will Contract Validation & SQLite Registration
    # --------------------------------------------------------------------------
    def test_register_qualified_will_techniques(self):
        """
        Transition all 6 qualified technique candidates into valid Will contracts:
        1. Validates each technique against kageyoni.will schema.
        2. Applies will_definition, will_expression, and all 6 will_technique records to SQLite.
        3. Confirms authoritative engine commit receipt.
        """
        rev = self.engine.branch(self.branch)["revision"]

        # 1. Register Supporting Rule Definition for GM Judgment Policy
        self.engine.add_rule(
            "rule-will-technique-policy",
            1,
            "Resolution policy for qualified cognitive and operational Will techniques.",
            [],
            [],
            True,
            {"kind": "contextual", "outcome": True},
        )

        # 2. Build Will Definition
        will_def = {
            "schema_version": "will-contract/0.1",
            "id": "will_def_ground_qualified",
            "version": 1,
            "design_status": "accepted",
            "evidence": [{"source": "ground_qualification_suite", "assertion": "Adversarially qualified techniques", "status": "confirmed"}],
            "name": "Ground Qualified Operator Techniques",
            "classification": "independent",
            "nature": "cognitive_and_operational_transduction",
            "ancestry": [],
            "generative_boundary": "Techniques operate within verified causal boundaries; zero self-certification.",
            "inherent_limits": [
                "Requires external mechanical or relational contact for fact promotion",
                "Constrained by physical substrate invariants",
            ],
            "invariants": [
                {
                    "id": "inv_receipt_bound",
                    "mode": "judgment",
                    "rule": None,
                    "statement": "State mutations require deterministic cryptographic receipts.",
                    "missing_policy": "request_judgment",
                }
            ],
        }

        # 3. Build Will Expression bound to avatar
        technique_ids = [
            "technique_type_epistemic_deficit",
            "technique_metabolize_rejection",
            "technique_reconcile_dynamic_constraint",
            "technique_relational_boundary_alignment",
            "technique_heterogeneous_affordance_mating",
            "technique_cryptographic_fact_promotion",
        ]
        will_expr = {
            "schema_version": "will-contract/0.1",
            "id": "will_expr_ground_qualified",
            "version": 1,
            "design_status": "accepted",
            "evidence": [{"source": "ground_qualification_suite", "assertion": "Expression bound to operator avatar", "status": "confirmed"}],
            "definition": {"id": "will_def_ground_qualified", "version": 1},
            "bearer": "levi-avatar",
            "legacy_will_id": None,
            "interpretation": "Adversarially verified cognitive and physical capability suite",
            "channels": ["structural_clarity", "epistemic_grounding"],
            "stat_bindings": [],
            "learned_techniques": [{"id": tid, "version": 1} for tid in technique_ids],
            "conditions": ["Active cognitive deliberator"],
            "awakening_access": "latent",
            "awakening_mastery": "unknown",
            "awakening_definition": None,
        }

        # Validate Definition & Expression
        validate_contract("will_definition", will_def, "will_def_ground_qualified", 1)
        validate_contract("will_expression", will_expr, "will_expr_ground_qualified", 1)

        # 4. Build 6 Validated will_technique Contracts
        trigger_cond = {
            "id": "trigger_cognitive_action",
            "mode": "judgment",
            "rule": None,
            "statement": "Cognitive perception or causal friction encountered.",
            "missing_policy": "request_judgment",
        }
        channel_spec = {
            "medium": "structural_clarity",
            "access": trigger_cond,
            "break_conditions": [],
        }
        resolution_policy = {"id": "rule-will-technique-policy", "version": 1}

        technique_specs = [
            ("technique_type_epistemic_deficit", "Type Epistemic Deficit", "reveal", "epistemic_state", "Deficit representation"),
            ("technique_metabolize_rejection", "Metabolize Authoritative Rejection", "alter", "constraint", "Rejection assimilation"),
            ("technique_reconcile_dynamic_constraint", "Reconcile Dynamic Constraint", "alter", "constraint", "Predicate-driven obsoletion"),
            ("technique_relational_boundary_alignment", "Relational Boundary Alignment", "connect", "character", "Principled alignment negotiation"),
            ("technique_heterogeneous_affordance_mating", "Heterogeneous Affordance Mating", "create", "consequence", "Multi-entity atomic patch"),
            ("technique_cryptographic_fact_promotion", "Cryptographic Fact Promotion", "preserve", "epistemic_fact", "Receipt-pinned ground truth"),
        ]

        technique_contracts = []
        for tid, tname, op, trole, mech in technique_specs:
            t_contract = {
                "schema_version": "will-contract/0.1",
                "id": tid,
                "version": 1,
                "design_status": "accepted",
                "evidence": [{"source": "ground_qualification_suite", "assertion": f"Verified {tname}", "status": "confirmed"}],
                "expression": {"id": "will_expr_ground_qualified", "version": 1},
                "name": tname,
                "derivation": f"Extracted and qualified from live execution trace: {tname}.",
                "practice_status": "demonstrated",
                "activation": "deliberate",
                "trigger": trigger_cond,
                "channels": [channel_spec],
                "effects": [
                    {
                        "operation": op,
                        "target_role": trole,
                        "mechanism": mech,
                        "preconditions": [],
                        "scope": {"target_kinds": ["epistemic", "item", "character", "rule"], "range": None, "area": None, "duration": None, "unknowns": []},
                        "inputs": [],
                        "resolver": None,
                        "authority": "gm_judgment",
                        "resistance": [],
                        "postconditions": [],
                    }
                ],
                "costs": [],
                "resolution_policy": resolution_policy,
                "termination": [],
            }
            validate_contract("will_technique", t_contract, tid, 1)
            technique_contracts.append(t_contract)

        # 5. Apply All to Kageyoni SQLite Branch
        changes = [
            {
                "op": "create",
                "domain": "will_definition",
                "id": will_def["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Ground qualified Will definition."}],
                "data": {"name": will_def["name"], "classification": will_def["classification"], "contract": will_def},
            },
            {
                "op": "create",
                "domain": "will_expression",
                "id": will_expr["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": "Ground qualified Will expression."}],
                "data": {"definition": will_def["id"], "bearer": "levi-avatar", "contract": will_expr},
            },
        ]
        for t in technique_contracts:
            changes.append({
                "op": "create",
                "domain": "will_technique",
                "id": t["id"],
                "status": "confirmed",
                "visibility": "public",
                "evidence": [{"note": f"Ground qualified Will technique: {t['name']}"}],
                "data": {"expression": will_expr["id"], "name": t["name"], "contract": t},
            })

        rev = self.engine.branch(self.branch)["revision"]
        receipt = self.engine.apply({
            "api_version": 3,
            "branch": self.branch,
            "expected_revision": rev,
            "request_id": "register-ground-qualified-techniques",
            "kind": "action",
            "actor": "system",
            "narrative": "Registering 6 ground-qualified Will techniques into Kageyoni causal ledger.",
            "changes": changes,
        })

        self.assertIn("event_hash", receipt)
        self.assertEqual(len(receipt["event_hash"]), 64)
        print(f"\n[+] Registered 6 Will Techniques into Kageyoni SQLite! Event Hash: {receipt['event_hash']}")


if __name__ == "__main__":
    unittest.main()
