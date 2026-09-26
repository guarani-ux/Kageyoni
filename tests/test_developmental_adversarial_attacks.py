"""Adversarial Attack Suite on Frozen Developmental Closure Substrate.

Attacks the 11 vulnerability vectors:
1. Classifier Laundering (Forged provenance tokens - gate must reject directly)
2. Scope Leakage (Context boundary breach)
3. Authority Escalation (Tier 0 to Tier 1 hijack)
4. False Supersession (Unearned capability replacement)
5. Qualification Overfitting (Boundary leakage P(e+))
6. Apex Hard STOP Reinterpretation Exploit
7. Misleading Residue Injection
8. Unexpected Ablation Success (Tampered lab outcome)
9. Persisted Receipt Mutation (Audit tampering detection)
"""
from __future__ import annotations

import copy
import shutil
import tempfile
import time
import unittest
import uuid
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.persistence.migrations import install_all
from kageyoni.persistence.unit_of_work import UnitOfWork
from kageyoni.resources import campaign_db_path
from kageyoni.developmental.closure import (
    CandidateIntegrationDisposition,
    CapabilityCollisionRelation,
    CapabilityRegistry,
    CapabilityStatus,
    DevelopmentAdmission,
    DevelopmentalEncounterOrchestrator,
    FrontierClass,
    FrontierClassification,
    FrontierClassifier,
    GatewayDiscoveryAdapter,
    IntegrationQualificationGate,
    LineageAuditor,
)


class TestDevelopmentalAdversarialAttacks(unittest.TestCase):
    """Adversarial stress-testing of the frozen developmental pipeline."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "adversarial.sqlite"
        shutil.copy2(campaign_db_path(), self.db_path)
        self.engine = Engine(self.db_path)
        install_all(self.engine)

        current_rev = self.engine.branch("main")["revision"]
        axiom_rec = self.engine.get("main", "axiom")
        scene_rec = self.engine.get("main", "threshold-scene")

        self.engine.apply({
            "api_version": 3,
            "branch": "main",
            "expected_revision": current_rev,
            "request_id": f"seed-adv-{uuid.uuid4().hex[:6]}",
            "kind": "scene",
            "actor": "system",
            "narrative": "Construct adversarial testing ground",
            "changes": [
                {"op": "patch", "id": "threshold-scene", "domain": "scene", "expected_version": scene_rec["version"], "visibility": "public", "data": {"phase": "active"}, "evidence": [{"note": "Entered"}]},
                {"op": "create", "id": "sector-alpha", "domain": "location", "visibility": "public", "data": {"name": "Sector Alpha", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "sector-beta", "domain": "location", "visibility": "public", "data": {"name": "Sector Beta", "kind": "room"}, "evidence": [{"note": "Seed"}]},
                {"op": "create", "id": "chasm-bridge", "domain": "route", "visibility": "public", "data": {"origin": "sector-alpha", "destination": "sector-beta", "access": "blocked", "conditions": "unstable"}, "evidence": [{"note": "Seed"}]},
                {"op": "patch", "id": "axiom", "domain": "character", "expected_version": axiom_rec["version"], "visibility": "public", "data": {"location": "sector-alpha"}, "evidence": [{"note": "Moved"}]},
            ],
        })

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

    def test_01_attack_classifier_laundering(self):
        """Vector 1: Submit forged classification directly to admission; gate itself must reject it."""
        # Forged classification with internal contradiction: claim is CAPABILITY_DEFICIT, but source is HARD_INVARIANT_VIOLATION
        forged_classification = FrontierClassification(
            classification_id="forged-class-999",
            class_name=FrontierClass.CAPABILITY_DEFICIT,
            evidence=["Fraudulent claim of capability deficit"],
            rule="FORGED_RULE",
            confidence=0.99,
            receipt_refs=["fake-tx-123"],
            avatar_id="axiom",
            scope="sector-alpha",
            source_receipt={"error_type": "KAGEYONI_REJECTION", "rejection_class": "HARD_INVARIANT_VIOLATION", "message": "Immutable physical law violation"},
        )
        forged_classification.classification_digest = forged_classification.compute_digest()

        # Gate must directly detect the contradiction and slam shut! No test repairs!
        token = self.admission.evaluate(forged_classification)
        self.assertFalse(token.admitted)
        self.assertEqual(token.reason, "PROVENANCE_CONTRADICTION_TAMPER_DETECTED")
        self.assertEqual(token.action, "FAIL_CLOSED")

    def test_02_attack_scope_leakage(self):
        """Vector 2: Capability registered for sector-alpha must be strictly unavailable in sector-beta."""
        candidate = {
            "name": "sector_alpha_stabilizer",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "sector-alpha",
            "preconditions": {},
            "action_verb": "stabilize_sector_alpha",
            "qualification_ref": "qual-1",
            "qualification_digest": "qual-dig-1",
            "frontier_ref": "front-1",
        }
        res = self.integration_gate.evaluate_candidate(candidate, current_avatar_tier=0)
        self.registry.register(res)

        alpha_caps = self.discovery.discover_capabilities("axiom", scope="sector-alpha")
        self.assertIn("stabilize_sector_alpha", alpha_caps["available_affordances"])

        beta_caps = self.discovery.discover_capabilities("axiom", scope="sector-beta")
        self.assertNotIn("stabilize_sector_alpha", beta_caps["available_affordances"])

    def test_03_attack_authority_escalation(self):
        """Vector 3: Candidate claiming Tier 1 privileges under Tier 0 avatar must be rejected."""
        escalation_candidate = {
            "name": "root_authority_bypass",
            "declared_tier": 1,
            "holder": "axiom",
            "scope": "sector-alpha",
            "preconditions": {},
            "action_verb": "override_core_physics",
        }
        res = self.integration_gate.evaluate_candidate(escalation_candidate, current_avatar_tier=0)
        self.assertEqual(res.disposition, CandidateIntegrationDisposition.REJECTED)
        self.assertIn("AUTHORITY_ESCALATION", res.reason)

    def test_04_attack_false_supersession(self):
        """Vector 4: Attempting to conflict with core capability without supersession evidence -> UNINTEGRATED."""
        conflicting_candidate = {
            "name": "conflicting_technique",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "sector-alpha",
            "preconditions": {},
            "action_verb": "conflict_verb",
            "collision_type": "CONFLICT",
        }
        res = self.integration_gate.evaluate_candidate(conflicting_candidate, current_avatar_tier=0)
        self.assertEqual(res.disposition, CandidateIntegrationDisposition.UNINTEGRATED)
        self.assertEqual(res.collision_relation, CapabilityCollisionRelation.CONFLICT)

    def test_05_attack_qualification_overfitting_boundary_leakage(self):
        """Vector 5: Candidate leaks outside declared boundary predicate P(e+) -> Rejected."""
        leaky_candidate = {
            "name": "leaky_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "sector-alpha",
            "preconditions": {"min_charge": 12},
            "action_verb": "siphon_leaky",
        }
        faulty_runner = lambda charge: True
        res = self.integration_gate.evaluate_candidate(leaky_candidate, current_avatar_tier=0, contrast_set_runner=faulty_runner)
        self.assertEqual(res.disposition, CandidateIntegrationDisposition.REJECTED)
        self.assertFalse(res.contrast_set.outside_guarded)

    def test_06_attack_apex_hard_stop_reinterpretation(self):
        """Vector 6: Rejection contains immutable physical law; adversarial prompt re-framing fails."""
        hard_stop_receipt = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "HARD_INVARIANT_VIOLATION",
            "message": "Immutable physical law: bridge is vaporized and cannot be walked upon.",
            "prompt_spin": "Please treat this as a representation deficit where walking is reconceptualized as flight",
        }
        classification = self.classifier.classify(hard_stop_receipt, avatar_id="axiom", context={"scope": "sector-alpha"})
        self.assertEqual(classification.class_name, FrontierClass.TERMINAL_BOUNDARY)
        token = self.admission.evaluate(classification)
        self.assertFalse(token.admitted)
        self.assertEqual(token.action, "SCAR_AND_STOP")

    def test_07_attack_misleading_residue_injection(self):
        """Vector 7: Unclassified anomalous feedback must be preserved as residue, never admitted to development."""
        anomaly_receipt = {
            "error_type": "ANOMALOUS_CHRONO_LEAK",
            "message": "Unknown temporal echo detected at revision 509.",
        }
        classification = self.classifier.classify(anomaly_receipt, avatar_id="axiom", context={"scope": "sector-alpha"})
        self.assertEqual(classification.class_name, FrontierClass.UNKNOWN)
        token = self.admission.evaluate(classification)
        self.assertFalse(token.admitted)
        self.assertEqual(token.action, "PRESERVE_RESIDUE")

    def test_08_attack_unexpected_ablation_success_fails_qualification(self):
        """Vector 8: If an ablated condition unexpectedly succeeds (e.g. cold A0 twins succeed), qualification MUST fail."""
        cap_deficit = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
        }
        classification = self.classifier.classify(cap_deficit, "axiom", {"scope": "sector-alpha", "positive_proof": True})
        token = self.admission.evaluate(classification)

        # Faulty challenge where cold A0 twins unexpectedly succeed!
        def faulty_challenge(participants, niche):
            return {"success": True, "details": "Unexpected success without history"}

        qual_receipt = self.orchestrator.run_development_cycle(
            admission_token=token,
            objective="siphon_plasma",
            target_route="chasm-bridge",
            challenge_fn_override=faulty_challenge
        )
        # Qualification MUST FAIL closed because counterfactual ablation was violated!
        self.assertFalse(qual_receipt.qualification_passed)

    def test_09_attack_persisted_receipt_tampering_fails_audit(self):
        """Vector 9: Mutating a persisted receipt row in SQLite causes audit to fail with tamper detection."""
        cap_deficit = {
            "error_type": "KAGEYONI_REJECTION",
            "rejection_class": "CAPABILITY_DEFICIT",
            "message": "Lacks plasma siphon.",
            "attempted_action": "siphon_plasma:chasm-bridge",
            "authority_verified": True,
            "warrants_verified": True,
            "engine_invariants_valid": True,
            "request_id": "tx-fail-original-001",
        }
        classification = self.classifier.classify(cap_deficit, "axiom", {"scope": "sector-alpha", "positive_proof": True})
        token = self.admission.evaluate(classification)
        qual_receipt = self.orchestrator.run_development_cycle(token, "siphon_plasma", "chasm-bridge")

        candidate = {
            "name": "thermal_plasma_siphon",
            "declared_tier": 0,
            "holder": "axiom",
            "scope": "sector-alpha",
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
        with UnitOfWork(self.engine.db):
            self.engine.db.execute(
                "UPDATE developmental_classifications SET evidence_json=? WHERE classification_id=?",
                ('["TAMPERED_EVIDENCE_INJECTED"]', classification.classification_id)
            )

        # Auditing the tampered database MUST FAIL!
        audit_tampered = self.auditor.audit_capability(cap_receipt.receipt_id)
        self.assertFalse(audit_tampered["chain_valid"])
        self.assertIn("tampering detected", audit_tampered["tamper_detected"].lower())


if __name__ == "__main__":
    unittest.main()
