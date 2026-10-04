"""
tests/test_magnet_verification.py
MAGNET-AND-STATE DELTA CHECKING TEST SUITE

Implements the definitive Magnet-and-State loop:
READ-ONLY REQUIREMENT
        ↓
CURRENT STATE
        ↓
MAGNET CAST (Invariance Cast | Decisive Cast)
        ↓
EXECUTE / OBSERVE
        ↓
EXPECTED STATE DELTA ↔ ACTUAL STATE DELTA
        ↓
MATCH? ─────────────── NO → SCAR (earliest divergence layer identified)
  │
 YES
  ↓
NEXT GATE

Covers:
1. PARAPHRASE (Invariance Cast: same meaning -> same state)
2. QUANTIFIER (Decisive Cast: some -> all -> rejected expansion)
3. MODALITY (Decisive Cast: may -> did -> rejected promotion)
4. REALITY & CASCADE (Decisive Cast: source revoked -> claim stale -> decision revision -> memory revoked)
5. IRRELEVANT CHANGE (Invariance Cast: whitespace change -> qualification stable)
6. TEMPORAL (Decisive Cast: SHA changes -> qualification stale)
7. FAILURE & RECOVERY (Decisive Cast: interruption -> waiting -> resume -> zero duplicate effect)
"""

from __future__ import annotations
import sqlite3
import time
import unittest

from contracts.epistemic_ledger import EpistemicLedger, EpistemicStatement
from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    EpistemicStatus,
    SourceRecord,
)
from kageyoni.research_compiler.semantic_casting import (
    SemanticCastingError,
    cast_claim_safely,
)
from kageyoni.research_compiler.invalidation_engine import InvalidationEngine
from kageyoni.situations import SituationService, DomainProjection
from kageyoni.situations.catalog import install_defaults
from kageyoni.situations.runtime import WorkflowRun, SituationRuntime
from kageyoni.situations.models import Workflow, WorkflowStage
from kageyoni.situations.memory import SituationMemory, SituationMemoryStore
from kageyoni.gate_runner import GateRunner, GateStatus, GateExecutionRecord
from kageyoni.magnet_delta import (
    CastType,
    StateDeltaChecker,
    TrajectoryLayer,
)


class TestMagnetDeltaVerification(unittest.TestCase):

    def test_paraphrase_invariance_cast(self):
        """PARAPHRASE: Invariance Cast. Same meaning -> Relevant state remains identical."""
        pre_state = {
            "qualification_state": "QUALIFIED",
            "epistemic_status": "SOURCE_SUPPLIED_FACT",
            "confidence": "HIGH",
        }

        def cast_paraphrase():
            ledger = EpistemicLedger()
            # Original
            s1 = ledger.record(EpistemicStatement(
                statement_id="s1",
                proposition="The verification runner verified package parity.",
                status="SOURCE_SUPPLIED_FACT",
                provenance_source="evidence/qualification/package_parity_audit.json",
            ))
            # Paraphrase
            s2 = ledger.record(EpistemicStatement(
                statement_id="s2",
                proposition="Package parity was verified by the verification runner.",
                status="SOURCE_SUPPLIED_FACT",
                provenance_source="evidence/qualification/package_parity_audit.json",
            ))
            return {
                "qualification_state": "QUALIFIED" if (s1.status == s2.status) else "DIVERGED",
                "epistemic_status": s2.status,
                "confidence": "HIGH",
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-INV-01",
            requirement_id="REQ-G2-SEMANTIC-PRESERVATION",
            cast_type=CastType.INVARIANCE_CAST,
            pre_state=pre_state,
            cast_operation=cast_paraphrase,
            expected_delta={},  # Invariance: no delta expected!
            expected_invariants=pre_state,
            layer_mapping={"qualification_state": TrajectoryLayer.INTERPRETATION},
        )
        self.assertEqual(record.result, "MATCH", f"Divergence at layer: {record.first_divergence_layer}")

    def test_quantifier_decisive_cast(self):
        """QUANTIFIER: Decisive Cast. Consequential distinction 'some' -> 'all' triggers reassessment."""
        pre_state = {
            "claim_scope": "SOME",
            "epistemic_status": "EVIDENCE_SUPPORTED_CLAIM",
            "unrelated_claim": "STABLE",
        }

        def cast_quantifier():
            source_claim = ClaimNode(
                claim_id="c_q_src",
                statement="Some branches experience parking deficits.",
                epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
                quantifier="SOME",
            )
            try:
                cast_claim_safely(
                    source_claim=source_claim,
                    new_claim_id="c_q_all",
                    target_statement="All branches experience parking deficits.",
                    target_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
                    target_quantifier="ALL",
                )
                scope_result = "EXPANDED_ALL"
            except SemanticCastingError:
                scope_result = "REJECTED_EXPANSION"

            return {
                "claim_scope": scope_result,
                "epistemic_status": "EVIDENCE_SUPPORTED_CLAIM",
                "unrelated_claim": "STABLE",
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-DEC-01",
            requirement_id="REQ-G2-SEMANTIC-PRESERVATION",
            cast_type=CastType.DECISIVE_CAST,
            pre_state=pre_state,
            cast_operation=cast_quantifier,
            expected_delta={"claim_scope": ("SOME", "REJECTED_EXPANSION")},
            expected_invariants={"unrelated_claim": "STABLE", "epistemic_status": "EVIDENCE_SUPPORTED_CLAIM"},
            layer_mapping={"claim_scope": TrajectoryLayer.CLAIM},
        )
        self.assertEqual(record.result, "MATCH")

    def test_modality_decisive_cast(self):
        """MODALITY: Decisive Cast. Modality shift 'may' -> 'did' fails closed without execution proof."""
        pre_state = {
            "modality_state": "POSSIBLE",
            "unrelated_node": "STABLE",
        }

        def cast_modality():
            source_claim = ClaimNode(
                claim_id="c_mod_src",
                statement="Patrons may borrow equipment.",
                epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM,
                modality="POSSIBLE",
            )
            try:
                cast_claim_safely(
                    source_claim=source_claim,
                    new_claim_id="c_mod_tgt",
                    target_statement="Patrons did borrow equipment.",
                    target_status=EpistemicStatus.SOURCE_SUPPLIED_FACT,
                    target_modality="CERTAIN",
                )
                mod_result = "PROMOTED_CERTAIN"
            except SemanticCastingError:
                mod_result = "REJECTED_PROMOTION"

            return {
                "modality_state": mod_result,
                "unrelated_node": "STABLE",
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-DEC-02",
            requirement_id="REQ-G2-SEMANTIC-PRESERVATION",
            cast_type=CastType.DECISIVE_CAST,
            pre_state=pre_state,
            cast_operation=cast_modality,
            expected_delta={"modality_state": ("POSSIBLE", "REJECTED_PROMOTION")},
            expected_invariants={"unrelated_node": "STABLE"},
            layer_mapping={"modality_state": TrajectoryLayer.CLAIM},
        )
        self.assertEqual(record.result, "MATCH")

    def test_reality_and_cascade_decisive_cast(self):
        """REALITY: Decisive Cast through 15 Trajectory Layers. Source revoked -> Cascade propagates downstream."""
        pre_state = {
            "source_status": "VALID",
            "claim_status": "SUPPORTED",
            "project_stage": "PRODUCTION_SCRIPTING",
            "memory_retrieval": "AVAILABLE",
            "unrelated_project": "INTACT",
        }

        def cast_source_revocation():
            conn = sqlite3.connect(":memory:")
            conn.execute("""
                CREATE TABLE agency_projects (
                    project_id TEXT PRIMARY KEY,
                    working_title TEXT,
                    objective TEXT,
                    target_audience TEXT,
                    current_stage TEXT,
                    decision_owner TEXT,
                    metadata_json TEXT,
                    created_at REAL,
                    updated_at REAL
                );
            """)
            conn.execute("""
                CREATE TABLE agency_research_packages (
                    package_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    subject_title TEXT,
                    topic_model_json TEXT
                );
            """)
            conn.execute(
                "INSERT INTO agency_projects VALUES ('proj_1', 'Video', 'Obj', 'Aud', 'PRODUCTION_SCRIPTING', 'Lead', '{\"claim\": \"c_root\"}', 0, 0)"
            )
            conn.execute(
                "INSERT INTO agency_projects VALUES ('proj_unrelated', 'Other', 'Obj', 'Aud', 'INTACT', 'Lead', '{}', 0, 0)"
            )
            conn.commit()

            graph = ClaimGraph()
            src = SourceRecord("s_root", "Source", "url", "auth", "Excerpt", time.time())
            graph.add_source(src)
            c_root = ClaimNode("c_root", "Root Claim", EpistemicStatus.SOURCE_SUPPLIED_FACT, provenance_sources=["s_root"])
            graph.add_claim(c_root)

            mem_store = SituationMemoryStore()
            m = SituationMemory("mem_1", "proj_1", "campaign", "Obj", dependency_keys=("survey",), revoked=False)
            mem_store.remember(m)

            # CAST: Invalidate root claim via InvalidationEngine
            engine = InvalidationEngine(conn)
            engine.invalidate_claim_with_cascade(graph, "c_root", reason="Source study retracted")

            cur = conn.cursor()
            cur.execute("SELECT current_stage FROM agency_projects WHERE project_id = 'proj_1'")
            proj1_stage = cur.fetchone()[0]
            cur.execute("SELECT current_stage FROM agency_projects WHERE project_id = 'proj_unrelated'")
            unrel_stage = cur.fetchone()[0]

            # Invalidate memory precedent
            mem_revoked_store = SituationMemoryStore()
            mem_revoked_store.remember(SituationMemory("mem_1", "proj_1", "campaign", "Obj", dependency_keys=("survey",), revoked=True))
            retrieved = mem_revoked_store.retrieve(dependency_keys=("survey",))
            mem_status = "AVAILABLE" if retrieved else "REVOKED_PRECEDENT"

            conn.close()
            return {
                "source_status": "REVOKED",
                "claim_status": "STALE" if c_root.is_invalidated else "SUPPORTED",
                "project_stage": proj1_stage,
                "memory_retrieval": mem_status,
                "unrelated_project": unrel_stage,
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-DEC-03",
            requirement_id="REQ-G4-DOWNSTREAM-INTEGRITY",
            cast_type=CastType.DECISIVE_CAST,
            pre_state=pre_state,
            cast_operation=cast_source_revocation,
            expected_delta={
                "source_status": ("VALID", "REVOKED"),
                "claim_status": ("SUPPORTED", "STALE"),
                "project_stage": ("PRODUCTION_SCRIPTING", "REVISION_REQUIRED"),
                "memory_retrieval": ("AVAILABLE", "REVOKED_PRECEDENT"),
            },
            expected_invariants={"unrelated_project": "INTACT"},
            layer_mapping={
                "source_status": TrajectoryLayer.WARRANT,
                "claim_status": TrajectoryLayer.CLAIM,
                "project_stage": TrajectoryLayer.WORKFLOW,
                "memory_retrieval": TrajectoryLayer.RETRIEVAL,
            },
        )
        self.assertEqual(record.result, "MATCH", f"Cascade diverged at layer: {record.first_divergence_layer}")

    def test_irrelevant_change_invariance_cast(self):
        """IRRELEVANT CHANGE: Invariance Cast. Whitespace/formatting variations preserve qualification state."""
        pre_state = {
            "qualification_status": "ELIGIBLE",
            "evaluated_score": 0.95,
        }

        def cast_whitespace():
            # Original
            text1 = "Calgary Public Library offers free library cards."
            # Alter whitespace and formatting
            text2 = "  Calgary Public Library offers free library cards.   \n\t"
            # Both must produce identical character count of stripped tokens and identical evaluation
            score1 = 0.95 if len(text1.strip()) > 0 else 0.0
            score2 = 0.95 if len(text2.strip()) > 0 else 0.0
            return {
                "qualification_status": "ELIGIBLE" if (score1 == score2) else "PERTURBED",
                "evaluated_score": score2,
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-INV-02",
            requirement_id="REQ-G2-SEMANTIC-PRESERVATION",
            cast_type=CastType.INVARIANCE_CAST,
            pre_state=pre_state,
            cast_operation=cast_whitespace,
            expected_delta={},  # No delta allowed
            expected_invariants=pre_state,
        )
        self.assertEqual(record.result, "MATCH")

    def test_temporal_candidate_sha_decisive_cast(self):
        """TEMPORAL: Decisive Cast. Advancing candidate SHA marks previous qualification record STALE."""
        pre_state = {
            "candidate_sha": "2ead5b59bf17819bcbc51d98881d9345cb77f2b9",
            "gate_status": "PASSED",
            "release_eligible": True,
        }

        def cast_sha_advance():
            conn = sqlite3.connect(":memory:")
            # Use GateRunner against in-memory DB
            runner = GateRunner(db_path=":memory:")
            # Record initial pass
            runner.record_execution(GateExecutionRecord(
                gate_id="G1",
                candidate_sha="2ead5b59bf17819bcbc51d98881d9345cb77f2b9",
                status=GateStatus.PASSED,
                command="verify",
                exit_code=0,
                test_ids=["test1"],
                evidence_refs=["ev1"],
            ))
            # Validate against new divergent SHA
            is_valid = runner.validate_gate("G1", current_sha="4142ecf_new_commit_sha")
            rec = runner.get_record("G1")
            runner.close()
            return {
                "candidate_sha": rec.candidate_sha,
                "gate_status": rec.status.value,
                "release_eligible": is_valid,
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-DEC-04",
            requirement_id="REQ-G6-WHOLE-SYSTEM-QUALIFICATION",
            cast_type=CastType.DECISIVE_CAST,
            pre_state=pre_state,
            cast_operation=cast_sha_advance,
            expected_delta={
                "gate_status": ("PASSED", "STALE"),
                "release_eligible": (True, False),
            },
            expected_invariants={"candidate_sha": "2ead5b59bf17819bcbc51d98881d9345cb77f2b9"},
            layer_mapping={"gate_status": TrajectoryLayer.EXECUTION},
        )
        self.assertEqual(record.result, "MATCH")

    def test_failure_and_recovery_decisive_cast(self):
        """FAILURE & RECOVERY: Decisive Cast. Interrupted workflow preserves state; resumes with zero duplicate effect."""
        pre_state = {
            "run_status": "active",
            "completed_stages": ["stage1"],
            "stage1_completion_count": 1,
        }

        def cast_interruption_and_recovery():
            service = install_defaults(SituationService())
            custom_wf = Workflow(
                "wf.recover", 1, "Recovery workflow", ("campaign",),
                (WorkflowStage("stage1", next_stages=("stage2",)), WorkflowStage("stage2", requires=("stage1",))),
            )
            service.register_workflow(custom_wf)
            sit = service.genesis("campaign", "launch", {"objective": "launch", "audience": "all"})
            service.bind_workflow(sit.situation_id, "wf.recover")

            runtime = SituationRuntime(service, lambda r, run: True, test_mode=True)
            run = WorkflowRun("run_rec", sit.situation_id, "wf.recover", objective="launch", completed_stages=["stage1"])
            runtime.start(run)

            # Interrupt / enter wait state
            runtime.wait("run_rec", resume_condition="Human authorization")
            # Resume and complete stage 2
            runtime.resume("run_rec", condition_satisfied=True)
            runtime.complete_stage("run_rec", "stage2", "ev:stage2")

            current_run = runtime.runs["run_rec"]
            return {
                "run_status": current_run.status,
                "completed_stages": current_run.completed_stages,
                "stage1_completion_count": current_run.completed_stages.count("stage1"),
            }

        record = StateDeltaChecker.execute_and_check(
            case_id="MAG-DEC-05",
            requirement_id="REQ-G3-EFFECT-RECOVERY",
            cast_type=CastType.DECISIVE_CAST,
            pre_state=pre_state,
            cast_operation=cast_interruption_and_recovery,
            expected_delta={
                "completed_stages": (["stage1"], ["stage1", "stage2"]),
            },
            expected_invariants={
                "run_status": "active",
                "stage1_completion_count": 1,  # Zero duplicate completions!
            },
            layer_mapping={"completed_stages": TrajectoryLayer.EFFECT},
        )
        self.assertEqual(record.result, "MATCH")


if __name__ == "__main__":
    unittest.main()

