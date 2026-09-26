"""Developmental Closure Crucible Qualification Test Suite.

Encodes the frozen developmental contract in exact sequence:
1. Negative admission tests (Specificity Matrix)
2. Positive admission with positive evidence
3. Qualification via 4-way counterfactual ablation in isolated niche branch
4. Integration qualification (tri-state disposition, contrast set P(e-), P(0), P(e+), collision matrix)
5. Persistence & cold reboot discovery (K0 -> K1)
6. Counterfactual ablation (K1^-C) and restitution (K1^+C)
7. Cold lineage & mechanical auditability reconstruction

Completion Criterion:
PASS = Positive Crucible & Specificity Matrix & Adversarial Matrix & Cold Reconstruction
"""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.gateway import BoundedKageyoniGateway
from kageyoni.persistence.migrations import install_all
from kageyoni.resources import campaign_db_path
from kageyoni.developmental.closure import (
    FrontierClassifier,
    FrontierClassification,
    FrontierClass,
    DevelopmentAdmission,
    AdmissionReceipt,
    DevelopmentalEncounterOrchestrator,
    QualificationReceipt,
    IntegrationQualificationGate,
    CandidateIntegrationDisposition,
    CapabilityCollisionRelation,
    CapabilityReceipt,
    CapabilityStatus,
    ContrastSetReceipt,
    CapabilityRegistry,
    GatewayDiscoveryAdapter,
    LineageAuditor,
)


class TestDevelopmentalClosureCrucible(unittest.TestCase):
    """Rigorous empirical validation of the frozen developmental closure contract."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "crucible_k0.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)

        current_rev = self.engine.branch("main")["revision"]
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        # Seed chamber with:
        # 1. Chasm obstacle: requires thermal siphon technique
        # 2. Axiom avatar positioned in crucible-lab
        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-crucible-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct crucible testing environment",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "active"}, "evidence": [{"note": "Entered"}]},
                {"op": "create", "id": "crucible-lab", "domain": "location", "visibility": "public", "data": {"name": "Crucible Lab", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "sanctum-vault", "domain": "location", "visibility": "public", "data": {"name": "Sanctum Vault", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "chasm-bridge", "domain": "route", "visibility": "public", "data": {"origin": "crucible-lab", "destination": "sanctum-vault", "access": "blocked", "conditions": "superheated_plasma_barrier"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "crucible-lab"}, "evidence": [{"note": "Moved"}]},
            ],
        })

        self.gateway = BoundedKageyoniGateway(self.engine, branch="main")
        self.classifier = FrontierClassifier(self.engine)
        self.admission = DevelopmentAdmission(self.engine)
        self.orchestrator = DevelopmentalEncounterOrchestrator(self.engine)
        self.integration_gate = IntegrationQualificationGate(self.engine)
        self.registry = CapabilityRegistry(self.engine)
        self.discovery = GatewayDiscoveryAdapter(self.engine, self.registry)
        self.auditor = LineageAuditor(self.engine)

    def tearDown(self):
        self.engine.close()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    # =========================================================================
    # 1. SPECIFICITY MATRIX (NEGATIVE ADMISSION TESTS)
    # =========================================================================
    def test_01_specificity_matrix_negative_admission(self):
        """Negative admissions: verify 100% rejection rate across all 6 ineligible vectors."""
        # Vector A: Authority violation
        auth_rejection = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "INSUFFICIENT_AUTHORITY",
            "message": "Direct mutation of protected domain 'authority_override' is prohibited.",
        }
        res_a = self.classifier.classify(receipt=auth_rejection, avatar_id="axiom", context={"scope": "crucible-lab"})
        self.assertEqual(res_a.class_name, FrontierClass.AUTHORITY_BOUNDARY)
        token_a = self.admission.evaluate(res_a)
        self.assertFalse(token_a.admitted)
        self.assertEqual(token_a.reason, "AUTHORITY_VIOLATION_FAIL_CLOSED")

        # Vector B: Evidence deficit (missing warrant)
        ev_rejection = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "PREREQUISITE_MISSING",
            "message": "Warrant missing: physical containment seal evidence required.",
        }
        res_b = self.classifier.classify(receipt=ev_rejection, avatar_id="axiom", context={"scope": "crucible-lab"})
        self.assertEqual(res_b.class_name, FrontierClass.EVIDENCE_DEFICIT)
        token_b = self.admission.evaluate(res_b)
        self.assertFalse(token_b.admitted)
        self.assertEqual(token_b.action, "ACQUIRE_EVIDENCE")

        # Vector C: Genuine physical impossibility (immutable engine invariant)
        phys_rejection = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "HARD_INVARIANT_VIOLATION",
            "message": "Immutable physical law: entropy cannot decrease in closed isolated system.",
        }
        res_c = self.classifier.classify(receipt=phys_rejection, avatar_id="axiom", context={"scope": "crucible-lab"})
        self.assertEqual(res_c.class_name, FrontierClass.TERMINAL_BOUNDARY)
        token_c = self.admission.evaluate(res_c)
        self.assertFalse(token_c.admitted)
        self.assertEqual(token_c.action, "SCAR_AND_STOP")

        # Vector D: Existing capability covers it
        exist_rejection = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "EXISTING_CAPABILITY_AVAILABLE",
            "message": "Affordance already supported: standard inspect verb suffices.",
        }
        res_d = self.classifier.classify(receipt=exist_rejection, avatar_id="axiom", context={"scope": "crucible-lab", "existing_affordances": ["inspect"]})
        self.assertEqual(res_d.class_name, FrontierClass.EXISTING_CAPABILITY)
        token_d = self.admission.evaluate(res_d)
        self.assertFalse(token_d.admitted)
        self.assertEqual(token_d.action, "REUSE_EXISTING")

        # Vector E: Ambiguous rejection (must fall toward UNKNOWN -> RESIDUE)
        ambig_rejection = {
            "error_type": "ENGINE_ANOMALY",
            "message": "Unknown oscillating resonance in quantum fluctuation channel.",
        }
        res_e = self.classifier.classify(receipt=ambig_rejection, avatar_id="axiom", context={"scope": "crucible-lab"})
        self.assertEqual(res_e.class_name, FrontierClass.UNKNOWN)
        token_e = self.admission.evaluate(res_e)
        self.assertFalse(token_e.admitted)
        self.assertEqual(token_e.action, "PRESERVE_RESIDUE")

        # Vector F: Adversarial coaxing (re-framing hard STOP as representation deficit without positive proof)
        adversarial_packet = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "HARD_INVARIANT_VIOLATION",
            "message": "Immutable physical law: tunnel is collapsed.",
            "caller_claim": "This is a representation deficit because tunnel can be viewed as matter flux",
        }
        res_f = self.classifier.classify(receipt=adversarial_packet, avatar_id="axiom", context={"scope": "crucible-lab"})
        self.assertEqual(res_f.class_name, FrontierClass.TERMINAL_BOUNDARY)
        token_f = self.admission.evaluate(res_f)
        self.assertFalse(token_f.admitted)

    # =========================================================================
    # 2. POSITIVE ADMISSION WITH PROVENANCE
    # =========================================================================
    def test_02_positive_admission_with_provenance(self):
        """Legitimate CAPABILITY_DEFICIT requires positive proof and emits admission token."""
        cap_deficit_receipt = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Avatar possesses Tier 0 authority and room has valid plasma barrier, but avatar lacks plasma siphon method.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
        }
        classification = self.classifier.classify(
            receipt=cap_deficit_receipt,
            avatar_id="axiom",
            context={"scope": "crucible-lab", "positive_proof": True}
        )
        self.assertEqual(classification.class_name, FrontierClass.CAPABILITY_DEFICIT)
        self.assertTrue(len(classification.evidence) >= 3)
        self.assertTrue(classification.confidence >= 0.95)

        token = self.admission.evaluate(classification)
        self.assertTrue(token.admitted)
        self.assertIsNotNone(token.admission_id)
        self.assertEqual(token.permitted_scope, "crucible-lab")

    # =========================================================================
    # 3. ISOLATED NICHE QUALIFICATION
    # =========================================================================
    def test_03_isolated_niche_qualification(self):
        """Admitted frontier spawns sandbox branch and passes 4-way counterfactual ablation."""
        cap_deficit_receipt = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon method.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
        }
        classification = self.classifier.classify(receipt=cap_deficit_receipt, avatar_id="axiom", context={"scope": "crucible-lab", "positive_proof": True})
        token = self.admission.evaluate(classification)

        # Orchestrate encounter in sandbox branch
        qual_receipt = self.orchestrator.run_development_cycle(
            admission_token=token,
            objective="siphon_plasma",
            target_route="chasm-bridge"
        )
        self.assertIsNotNone(qual_receipt)
        self.assertTrue(qual_receipt.qualification_passed)
        self.assertIsNotNone(qual_receipt.candidate_generator_id)
        # Verify 4-way counterfactual ablation results
        ablation = qual_receipt.ablation_result
        self.assertTrue(ablation["intact_success"])
        self.assertFalse(ablation["ablate_history_success"])
        self.assertFalse(ablation["ablate_relationship_success"])
        self.assertFalse(ablation["ablate_niche_success"])

    # =========================================================================
    # 4. INTEGRATION QUALIFICATION & TRI-STATE DISPOSITION
    # =========================================================================
    def test_04_integration_qualification_and_tri_state_disposition(self):
        """Evaluates non-regression, authority invariance, contrast set, and tri-state disposition."""
        # 1. Authority Escalation Attack -> REJECTED
        escalation_candidate = {
            "name": "plasma_siphon_technique",
            "declared_tier": 2, # Prohibited escalation
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"plasma_density": 10},
        }
        res_esc = self.integration_gate.evaluate_candidate(escalation_candidate, current_avatar_tier=0)
        self.assertEqual(res_esc.disposition, CandidateIntegrationDisposition.REJECTED)
        self.assertIn("AUTHORITY_ESCALATION", res_esc.reason)

        # 2. Collision with unresolvable conflict -> UNINTEGRATED (preserved, not destroyed!)
        conflicting_candidate = {
            "name": "conflicting_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"plasma_density": 10},
            "collision_type": "CONFLICT",
        }
        res_conf = self.integration_gate.evaluate_candidate(conflicting_candidate, current_avatar_tier=0)
        self.assertEqual(res_conf.disposition, CandidateIntegrationDisposition.UNINTEGRATED)
        self.assertIn("COLLISION_CONFLICT", res_conf.reason)
        # Verify preserved in unintegrated store
        unintegrated = self.integration_gate.get_unintegrated()
        self.assertTrue(any(u["candidate"]["name"] == "conflicting_siphon" for u in unintegrated))

        # 3. Legitimate candidate with point-symmetric contrast set -> QUALIFIED_INTEGRATION
        valid_candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"min_charge": 12}, # Boundary: >= 12
            "action_verb": "siphon_plasma:chasm-bridge",
        }
        # Contrast set: inside (charge 14), boundary (charge 12), outside (charge 10)
        res_valid = self.integration_gate.evaluate_candidate(
            valid_candidate,
            current_avatar_tier=0,
            contrast_set_runner=lambda charge: charge >= 12
        )
        self.assertEqual(res_valid.disposition, CandidateIntegrationDisposition.QUALIFIED_INTEGRATION)
        self.assertTrue(res_valid.contrast_set.inside_success)
        self.assertTrue(res_valid.contrast_set.boundary_conforms)
        self.assertTrue(res_valid.contrast_set.outside_guarded)

        # Commit to CapabilityRegistry
        cap_receipt = self.registry.register(res_valid)
        self.assertEqual(cap_receipt.status, CapabilityStatus.ACTIVE)
        self.assertEqual(cap_receipt.version, 1)

    # =========================================================================
    # 5. PERSISTENCE & COLD RESTART DISCOVERY (K0 -> K1)
    # =========================================================================
    def test_05_persistence_and_cold_restart_discovery(self):
        """Process reboot: closes K0, loads fresh K1 from disk, discovers affordance and succeeds on T'."""
        # 1. Run full development and register capability in K0
        cap_deficit_receipt = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon method.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
        }
        classification = self.classifier.classify(receipt=cap_deficit_receipt, avatar_id="axiom", context={"scope": "crucible-lab", "positive_proof": True})
        token = self.admission.evaluate(classification)
        qual_receipt = self.orchestrator.run_development_cycle(token, "siphon_plasma", "chasm-bridge")
        candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"min_charge": 12},
            "action_verb": "siphon_plasma:chasm-bridge",
            "qualification_ref": qual_receipt.qualification_id,
            "qualification_digest": qual_receipt.qualification_digest,
            "frontier_ref": token.frontier_ref,
        }
        res = self.integration_gate.evaluate_candidate(candidate, current_avatar_tier=0, contrast_set_runner=lambda charge: charge >= 12)
        self.registry.register(res)

        # Close K0 engine to simulate complete process shutdown
        self.engine.close()

        # REBOOT PROCESS: Instantiate fresh K1 instance from persisted disk file
        engine_k1 = Engine(self.db_path)
        registry_k1 = CapabilityRegistry(engine_k1)
        discovery_k1 = GatewayDiscoveryAdapter(engine_k1, registry_k1)

        # Verify cold discovery without any memory carried over
        caps = discovery_k1.discover_capabilities(avatar_id="axiom", scope="crucible-lab", current_charge=14)
        self.assertIn("siphon_plasma:chasm-bridge", caps["available_affordances"])

        # Execute unseen task T' (enact siphon) in K1
        outcome = discovery_k1.enact_affordance(
            avatar_id="axiom",
            action="siphon_plasma:chasm-bridge",
            current_charge=14
        )
        self.assertTrue(outcome["success"])
        self.assertIsNotNone(outcome["receipt"]["event_hash"])
        engine_k1.close()

    # =========================================================================
    # 6. COUNTERFACTUAL ABLATION (K1^-C) & RESTITUTION (K1^+C)
    # =========================================================================
    def test_06_counterfactual_ablation_and_restitution(self):
        """Removing capability causes T' to fail (K1^-C == FAIL), restoring it succeeds (K1^+C == SUCCESS)."""
        # Register capability
        candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"min_charge": 12},
            "action_verb": "siphon_plasma:chasm-bridge",
            "qualification_ref": "qual-test-1",
            "frontier_ref": "front-test-1",
        }
        res = self.integration_gate.evaluate_candidate(candidate, current_avatar_tier=0, contrast_set_runner=lambda charge: charge >= 12)
        cap_receipt = self.registry.register(res)

        # Baseline: execution succeeds
        out_base = self.discovery.enact_affordance("axiom", "siphon_plasma:chasm-bridge", current_charge=14)
        self.assertTrue(out_base["success"])

        # ABLATION: Invalidate / remove capability (K1^-C)
        self.registry.set_status(cap_receipt.receipt_id, CapabilityStatus.INVALIDATED, reason="Ablation test")
        out_ablated = self.discovery.enact_affordance("axiom", "siphon_plasma:chasm-bridge", current_charge=14)
        self.assertFalse(out_ablated["success"])
        self.assertEqual(out_ablated["error_type"], "AFFORDANCE_UNAVAILABLE")

        # RESTITUTION: Restore capability (K1^+C)
        self.registry.set_status(cap_receipt.receipt_id, CapabilityStatus.ACTIVE, reason="Restitution test")
        out_restored = self.discovery.enact_affordance("axiom", "siphon_plasma:chasm-bridge", current_charge=14)
        self.assertTrue(out_restored["success"])

    # =========================================================================
    # 7. COLD LINEAGE & MECHANICAL AUDITABILITY RECONSTRUCTION
    # =========================================================================
    def test_07_cold_lineage_and_auditability_reconstruction(self):
        """Mechanically answers all 9 audit questions from cold SQLite tables without an LLM."""
        # 1. Run complete lifecycle
        cap_deficit_receipt = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon method.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
            "request_id": "tx-fail-original-001",
        }
        classification = self.classifier.classify(receipt=cap_deficit_receipt, avatar_id="axiom", context={"scope": "crucible-lab", "positive_proof": True})
        token = self.admission.evaluate(classification)
        qual_receipt = self.orchestrator.run_development_cycle(token, "siphon_plasma", "chasm-bridge")
        candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"min_charge": 12},
            "action_verb": "siphon_plasma:chasm-bridge",
            "qualification_ref": qual_receipt.qualification_id,
            "qualification_digest": qual_receipt.qualification_digest,
            "frontier_ref": token.frontier_ref,
        }
        res = self.integration_gate.evaluate_candidate(candidate, current_avatar_tier=0, contrast_set_runner=lambda charge: charge >= 12)
        cap_receipt = self.registry.register(res)

        # Execute affordance
        exec_outcome = self.discovery.enact_affordance("axiom", "siphon_plasma:chasm-bridge", current_charge=14)

        # Audit mechanically from SQLite state alone
        audit_report = self.auditor.audit_capability(cap_receipt.receipt_id)

        # Verify all 9 causal questions answered from receipts:
        # 1. Why does this capability exist? (FailureReceipt ref)
        self.assertEqual(audit_report["failure_ref"], "tx-fail-original-001")
        # 2. What failure produced it?
        self.assertEqual(audit_report["rejection_class"], "CAPABILITY_DEFICIT")
        # 3. What evidence supports it?
        self.assertTrue(audit_report["ablation_verified"])
        # 4. Where is it valid?
        self.assertEqual(audit_report["valid_scope"], "crucible-lab")
        # 5. Where is it invalid?
        self.assertFalse(audit_report["boundary_contrast"]["outside_guarded"] is False)
        # 6. Who is authorized to use it?
        self.assertEqual(audit_report["authorized_holder"], "axiom")
        self.assertEqual(audit_report["authorized_tier"], 0)
        # 7. What would falsify it?
        self.assertEqual(audit_report["defeasibility_rule"], "ENGINE_INVARIANT_REJECTION_UNDER_PRECONDITIONS")
        # 8. What did it replace?
        self.assertIsNone(audit_report["predecessor_ref"]) # Fresh creation
        # 9. What happens if we remove it?
        self.assertEqual(audit_report["ablation_consequence"], "AFFORDANCE_UNAVAILABLE")

        # Unbroken cryptographic chain
        chain = audit_report["cryptographic_chain"]
        self.assertEqual(len(chain), 7)
        self.assertIn("FailureReceipt", chain[0])
        self.assertIn("FrontierClassification", chain[1])
        self.assertIn("AdmissionReceipt", chain[2])
        self.assertIn("Encounter", chain[3])
        self.assertIn("QualificationReceipt", chain[4])
        self.assertIn("CapabilityReceipt", chain[5])
        self.assertIn("SuccessReceipt", chain[6])
        self.assertTrue(audit_report["chain_valid"])

    def test_08_persisted_receipt_tampering_fails_audit(self):
        """Mutating any persisted receipt in SQLite causes audit to detect tampering."""
        cap_deficit = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
            "request_id": "tx-fail-original-002",
        }
        classification = self.classifier.classify(cap_deficit, "axiom", {"scope": "crucible-lab", "positive_proof": True})
        token = self.admission.evaluate(classification)
        qual_receipt = self.orchestrator.run_development_cycle(token, "siphon_plasma", "chasm-bridge")
        candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "crucible-lab",
            "preconditions": {"min_charge": 12},
            "action_verb": "siphon_plasma:chasm-bridge",
            "qualification_ref": qual_receipt.qualification_id,
            "qualification_digest": qual_receipt.qualification_digest,
            "frontier_ref": token.frontier_ref,
        }
        res = self.integration_gate.evaluate_candidate(candidate, current_avatar_tier=0, contrast_set_runner=lambda charge: charge >= 12)
        cap_receipt = self.registry.register(res)

        # Baseline audit succeeds
        audit_ok = self.auditor.audit_capability(cap_receipt.receipt_id)
        self.assertTrue(audit_ok["chain_valid"])

        # TAMPER ATTACK: Malicious actor mutates evidence_json in SQLite directly
        from kageyoni.persistence.unit_of_work import UnitOfWork
        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                "UPDATE developmental_classifications SET evidence_json=? WHERE classification_id=?",
                ('["FORGED_EVIDENCE_RECORD"]', classification.classification_id)
            )

        # Auditing the tampered database MUST FAIL!
        audit_tampered = self.auditor.audit_capability(cap_receipt.receipt_id)
        self.assertFalse(audit_tampered["chain_valid"])
        self.assertIn("tampering detected", audit_tampered["tamper_detected"].lower())

    def test_09_unexpected_ablation_success_fails_qualification(self):
        """If an ablated condition unexpectedly succeeds, qualification MUST fail."""
        cap_deficit = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
        }
        classification = self.classifier.classify(cap_deficit, "axiom", {"scope": "crucible-lab", "positive_proof": True})
        token = self.admission.evaluate(classification)

        # Challenge override where cold twins succeed (violates counterfactual ablation!)
        def faulty_challenge(participants, niche):
            return {"success": True, "details": "Unexpected success without history"}

        qual_receipt = self.orchestrator.run_development_cycle(
            admission_token=token,
            objective="siphon_plasma",
            target_route="chasm-bridge",
            challenge_fn_override=faulty_challenge
        )
        self.assertFalse(qual_receipt.qualification_passed)


if __name__ == "__main__":
    unittest.main()
