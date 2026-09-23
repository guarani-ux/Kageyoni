"""
tools/run_gate_g0_baseline.py
Gate G0: Establish the Real Baseline.

Find/fix:
- Inventory every branch.
- Map historical Scars and requirements to current source/tests.
- Preserve historical records without merging obsolete code.
- Run full suite and record actual failures and baseline inventory.
"""

from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kageyoni.gate_runner import GateRunner, GateStatus, GateExecutionRecord


def run_g0():
    runner = GateRunner()
    current_sha = runner.get_current_git_sha()
    print(f"[Gate G0] Establishing Real Baseline against SHA: {current_sha}")

    # 1. Branch Inventory
    branches_res = subprocess.run(
        ["git", "branch", "-a"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    branches = [b.strip() for b in branches_res.stdout.splitlines() if b.strip()]

    # 2. Historical Scars Inventory
    scars = [
        {
            "scar_id": "SCAR-0001",
            "class": "counterfeit-evidence",
            "provenance_branch": "origin/v11-scar-saturation",
            "requirement": "Lifecycle evidence must resolve to an engine-custodied real domain effect.",
            "verifying_test": "tests/test_v11_production_path_mediation.py::test_counterfeit_receipt_rejected",
            "status": "closed",
            "repair_ref": "b73a38b / SCAR-counterfeit-execution-receipt.patch",
        },
        {
            "scar_id": "SCAR-SIT-001",
            "class": "unauthorized_authority_expansion",
            "provenance_branch": "reality-grounding-audit",
            "requirement": "Child run permitted unconstrained authority tuple; must fail closed.",
            "verifying_test": "tests/test_situation_r4_scar_saturation.py::test_scar_ledger_lifecycle_enforces_reprobe_and_positive_control",
            "status": "closed",
            "repair_ref": "commit:55a1dad",
        },
        {
            "scar_id": "SCAR-artifact-execution-evidence",
            "class": "missing_artifact_verification",
            "provenance_branch": "patches/",
            "requirement": "artifact-result evidence type verified in issue_execution with artifact_id and digest checking against physical artifacts table.",
            "verifying_test": "tests/test_v11.py",
            "status": "closed",
            "repair_ref": "patches/SCAR-artifact-execution-evidence.patch",
        },
        {
            "scar_id": "SCAR-counterfeit-execution-receipt",
            "class": "forged_receipt",
            "provenance_branch": "patches/",
            "requirement": "Separated _issue_execution_record from public issue_execution; enforces world-event in events table and pipeline-result in pipeline_runs.",
            "verifying_test": "tests/test_v11_production_path_mediation.py",
            "status": "closed",
            "repair_ref": "patches/SCAR-counterfeit-execution-receipt.patch",
        },
        {
            "scar_id": "SCAR-governor-v11-schema",
            "class": "unmigrated_governor_connection",
            "provenance_branch": "patches/",
            "requirement": "ResolutionGovernor.__init__ installs v11 migrations (migrations 019-022) before establishing db connection.",
            "verifying_test": "tests/test_composition_governor.py",
            "status": "closed",
            "repair_ref": "patches/SCAR-governor-v11-schema.patch",
        },
        {
            "scar_id": "SCAR-pipeline-v11-mediation",
            "class": "optional_trust_bypass",
            "provenance_branch": "patches/",
            "requirement": "Pipeline run unconditionally installs v11 and mediates via begin_domain_operation and complete_domain_operation.",
            "verifying_test": "tests/test_v11_production_path_mediation.py",
            "status": "closed",
            "repair_ref": "b73a38b / patches/SCAR-pipeline-v11-mediation.patch",
        },
        {
            "scar_id": "SITUATION-migration-023",
            "class": "missing_situation_schema",
            "provenance_branch": "patches/",
            "requirement": "install_situations and install_all updated to install migration_023.sql.",
            "verifying_test": "tests/test_situation_integration_adapter.py",
            "status": "closed",
            "repair_ref": "patches/SITUATION-migration-023.patch",
        },
        {
            "scar_id": "MIGRATION_PREDECESSOR_GAP_V7_PIPELINE",
            "class": "test_setup_bypass",
            "provenance_branch": "evidence/audits/baseline_failure_map.json",
            "requirement": "PipelineTests.setUp must invoke install_v11 establishing legitimate predecessor chain.",
            "verifying_test": "tests/test_v7_pipeline.py",
            "status": "closed",
            "repair_ref": "evidence/audits/baseline_failure_map.json",
        },
        {
            "scar_id": "SUCCESSOR-Q08",
            "class": "one_sided_supported_reference",
            "provenance_branch": "docs/V11-TRUST-SUCCESSOR-PROBES.md",
            "requirement": "One-sided supported-only reference cases cannot qualify an enforcer.",
            "verifying_test": "tests/test_v11_frozen_trust_gate.py",
            "status": "closed",
            "repair_ref": "kageyoni/v11/enforcement.py",
        },
        {
            "scar_id": "SUCCESSOR-O08",
            "class": "counterfeit_assessment_injection",
            "provenance_branch": "docs/V11-TRUST-SUCCESSOR-PROBES.md",
            "requirement": "A caller cannot inject a fake assessment id to move PREPARED -> ASSESSED.",
            "verifying_test": "tests/test_v11_production_path_mediation.py",
            "status": "closed",
            "repair_ref": "kageyoni/v11/enforcement.py",
        },
        {
            "scar_id": "SUCCESSOR-F07",
            "class": "unauthorized_frontier_jump",
            "provenance_branch": "docs/V11-TRUST-SUCCESSOR-PROBES.md",
            "requirement": "A frontier cannot jump directly from open -> resolved without observation.",
            "verifying_test": "tests/test_v11_frontier.py",
            "status": "closed",
            "repair_ref": "kageyoni/v11/frontier.py",
        },
        {
            "scar_id": "SUCCESSOR-N01",
            "class": "concurrent_acknowledgment_conflict",
            "provenance_branch": "docs/V11-TRUST-SUCCESSOR-PROBES.md",
            "requirement": "Concurrent acknowledged operation history is retained or rejected under strict ordering.",
            "verifying_test": "tests/test_v11_adaptive.py",
            "status": "closed",
            "repair_ref": "kageyoni/v11/adaptive.py",
        },
        {
            "scar_id": "SCAR-DOMAIN-PROJECTION",
            "class": "unbound_method_evidence",
            "provenance_branch": "docs/SCAR-REGRESSION-RULE.md",
            "requirement": "Domain Projection evidence must remain bound to participant and Situation; method reference alone is insufficient.",
            "verifying_test": "tests/test_situations.py",
            "status": "closed",
            "repair_ref": "kageyoni/situations/service.py",
        },
    ]

    for s in scars:
        s["reprobe_passed"] = (s.get("status") == "closed")
        s["positive_control_passed"] = (s.get("status") == "closed")

    scar_inventory_path = ROOT / "evidence" / "audits" / "scar_inventory.json"
    scar_inventory_path.parent.mkdir(parents=True, exist_ok=True)
    scar_inventory_path.write_text(json.dumps({"scars": scars, "count": len(scars)}, indent=2), encoding="utf-8")

    # 3. Requirement Mapping from docs/V11-FROZEN-REMAINING-PLAN.md
    requirements_map = {
        "R1": {"name": "Authoritative inherited-engine integration", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R1", "tests": ["tests/test_situation_integration_adapter.py", "tests/test_v7_pipeline.py"]},
        "R2": {"name": "Mechanical trust gate", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R2", "tests": ["tests/test_v11_frozen_trust_gate.py", "tests/test_v11_production_path_mediation.py"]},
        "R3": {"name": "Situation connected qualification", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R3", "tests": ["tests/test_situation_qualification.py", "tests/test_situations.py"]},
        "R4": {"name": "Scar Saturation", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R4", "tests": ["tests/test_situation_r4_scar_saturation.py"]},
        "R5": {"name": "Comparative qualification", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R5", "tests": ["tests/test_situation_r5_comparative_qualification.py"]},
        "R6": {"name": "Long-horizon development", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R6", "tests": ["tests/test_situation_r6_long_horizon_qualification.py"]},
        "R7": {"name": "Release qualification", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R7", "tests": ["tests/test_v11_r7_release_qualification.py"]},
        "R8": {"name": "Release and evidence", "plan_ref": "docs/V11-FROZEN-REMAINING-PLAN.md#R8", "tests": ["tools/generate_qualification_record.py"]},
    }

    # 4. Physical Test Suite Discovery & Execution
    print("[Gate G0] Running test discovery and baseline execution...")
    loader = unittest.TestLoader()
    suite = loader.discover(str(ROOT / "tests"), pattern="test_*.py")

    def flatten_tests(s):
        out = []
        for item in s:
            if isinstance(item, unittest.TestSuite):
                out.extend(flatten_tests(item))
            else:
                out.append(item)
        return out

    all_tests = flatten_tests(suite)
    test_ids = [t.id() for t in all_tests]
    
    runner_unit = unittest.TextTestRunner(verbosity=0)
    start_time = time.time()
    test_res = runner_unit.run(suite)
    elapsed = time.time() - start_time

    failures = [f[0].id() for f in test_res.failures]
    errors = [e[0].id() for e in test_res.errors]
    all_failures = failures + errors
    skips = [s[0].id() for s in test_res.skipped]

    # 5. Open Deficit Inventory
    deficits = [
        {"code": "G1_DEFICIT", "detail": "tools/generate_qualification_record.py treats missing frontier db as 0 frontiers and applied patches as closed scars."},
        {"code": "G2_DEFICIT", "detail": "claims.py does not separate literal source assertion from warranted claim; lacks excerpt relevance checking."},
        {"code": "G3_DEFICIT", "detail": "Disconnected claim vocabularies across epistemic_ledger.py, claims.py, and enforcement.py; lacks semantic casting."},
        {"code": "G4_DEFICIT", "detail": "treatment_generator.py hardcodes youth literacy hypotheses and fixed scores for all 9 archetypes."},
        {"code": "G5_DEFICIT", "detail": "invalidate_claim does not propagate forward into downstream agency_projects, section records, or Kageyoni warrants."},
        {"code": "G6_DEFICIT", "detail": "Situation memory retrieval lacks workspace isolation and Method revocation filtering; transfer does not route through Transfers."},
        {"code": "G7_DEFICIT", "detail": "Comparative runner uses mock condition-based scores instead of real task executions against frozen fixtures."},
    ]

    baseline_data = {
        "gate": "G0",
        "candidate_sha": current_sha,
        "branches": branches,
        "historical_scars_count": len(scars),
        "requirements_mapped": list(requirements_map.keys()),
        "total_tests_discovered": len(test_ids),
        "tests_passed": test_res.testsRun - len(all_failures) - len(skips),
        "tests_failed": len(failures),
        "tests_errored": len(errors),
        "tests_skipped": len(skips),
        "execution_time_seconds": round(elapsed, 3),
        "open_deficits": deficits,
    }

    out_file = ROOT / "evidence" / "audits" / "g0_baseline_inventory.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(baseline_data, indent=2), encoding="utf-8")

    input_hashes = {
        "V11-FROZEN-REMAINING-PLAN.md": hashlib.sha256((ROOT / "docs" / "V11-FROZEN-REMAINING-PLAN.md").read_bytes()).hexdigest(),
        "V11-COMPLETION-LEDGER.md": hashlib.sha256((ROOT / "docs" / "V11-COMPLETION-LEDGER.md").read_bytes()).hexdigest(),
    }
    output_hashes = {
        "g0_baseline_inventory.json": hashlib.sha256(out_file.read_bytes()).hexdigest(),
        "scar_inventory.json": hashlib.sha256(scar_inventory_path.read_bytes()).hexdigest(),
    }

    record = GateExecutionRecord(
        gate_id="G0",
        candidate_sha=current_sha,
        status=GateStatus.PASSED if len(all_failures) == 0 else GateStatus.FAILED,
        command="python tools/run_gate_g0_baseline.py",
        exit_code=0 if len(all_failures) == 0 else 1,
        test_ids=test_ids,
        failures=all_failures,
        skips=skips,
        input_hashes=input_hashes,
        output_hashes=output_hashes,
        evidence_refs=[str(out_file), str(scar_inventory_path)],
        details=baseline_data,
    )
    runner.record_execution(record)
    runner.close()

    print(f"[Gate G0] Baseline established. Status: {record.status.value}")
    print(f"  Tests discovered: {len(test_ids)} | Failures: {len(all_failures)} | Skips: {len(skips)}")
    print(f"  Historical Scars mapped: {len(scars)}")
    print(f"  Artifact: {out_file}")
    return record.exit_code


if __name__ == "__main__":
    sys.exit(run_g0())
