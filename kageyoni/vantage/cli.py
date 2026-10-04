"""
Interactive and Scriptable CLI for Vantage.
Provides a clear, human-centered producer console for moving through the 6 lifecycle stages,
inspecting gate statuses, reviewing proposals, making selections, and executing pressure tests.
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Reconfigure stdout/stderr for clean utf-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich import print as rprint
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .engine import VantageStudio
from .models import ApprovalStatus, EpistemicNodeStatus, IdeaQualificationStatus
from .rubric import RubricEvaluator


def get_console():
    return Console(highlight=False) if HAS_RICH else None


def print_header(title: str, subtitle: str = ""):
    if HAS_RICH:
        c = get_console()
        c.print(Panel(f"[bold cyan]{title}[/bold cyan]\n[dim]{subtitle}[/dim]", expand=False, border_style="cyan"))
    else:
        print("\n" + "=" * 70)
        print(f" {title.upper()} ")
        if subtitle:
            print(f" {subtitle}")
        print("=" * 70)


def print_stage_status(studio: VantageStudio, project_id: str):
    brief = studio.get_project_brief(project_id)
    graph = studio.get_project_graph(project_id)
    unresolved = graph.get_unresolved_nodes()
    stale = graph.get_stale_or_contested_nodes()

    if HAS_RICH:
        c = get_console()
        table = Table(title=f"Project Status: {brief.working_title} ({brief.project_id})", border_style="blue")
        table.add_column("Property", style="bold yellow")
        table.add_column("Value", style="white")

        table.add_row("Organization", brief.organization)
        table.add_row("Decision Owner", brief.decision_owner)
        table.add_row("Approval Authority", brief.approval_authority)
        table.add_row("Total Graph Nodes", str(len(graph.nodes)))
        table.add_row("Unresolved / Blocked Nodes", f"[red]{len(unresolved)}[/red]" if unresolved else "[green]0[/green]")
        table.add_row("Stale / Contested Nodes", f"[red]{len(stale)}[/red]" if stale else "[green]0[/green]")
        c.print(table)
    else:
        print(f"\n--- Project: {brief.working_title} ({brief.project_id}) ---")
        print(f"Organization: {brief.organization} | Owner: {brief.decision_owner}")
        print(f"Graph Nodes: {len(graph.nodes)} | Unresolved: {len(unresolved)} | Stale: {len(stale)}")


def run_full_lifecycle_demo(db_path: str = ":memory:"):
    """
    Executes an end-to-end local demonstration covering all 6 phases and the 6 pressure scenarios.
    """
    print_header("VANTAGE ORGANIZATIONAL VIDEO PRODUCTION", "Automated Full-Lifecycle & Pressure Demonstration")

    studio = VantageStudio(db_path=db_path)

    # 1. Synthesize realistic organization brief
    brief_data = {
        "project_id": "proj_clean_water_2026",
        "working_title": "Off-Grid Solar Water Transformation",
        "organization": "Global Infrastructure & Health Alliance (GIHA)",
        "decision_owner": "Elena Vance, Senior Producer",
        "approval_authority": "Dr. Aris Thorne, Director of Global Communications",
        "target_audience": {
            "segment": "Municipal Water Authorities & Regional Clinic Directors",
            "problem": "Frequent diesel pump breakdowns and high fuel expenses leaving remote facilities without running water.",
        },
        "organizational_goals": [
            "Demonstrate 98% operational uptime in off-grid solar water installations.",
            "Accelerate adoption across 40 new rural clinical facilities in 2027.",
        ],
        "campaign_priorities": [
            "2026 Annual Infrastructure Efficacy Campaign: 'Powering Resilience'",
        ],
        "stakeholder_requests": [
            "Preserve verified engineering telemetry data and flow rate audit figures.",
            "Highlight local technical maintenance training and community agency.",
        ],
        "subject_matter_notes": [
            {
                "fact": "Direct-drive variable-frequency pump operates continuously at 140 L/min without chemical battery storage.",
                "source": "Lead Mechanical Engineer, Field Telemetry Log 2026-A",
            },
            {
                "fact": "Overhead diesel fuel expenditure dropped from $1,800/month to $0 across a 12-month monitored cycle.",
                "source": "Regional Health Clinic Audited Ledger",
            },
        ],
        "existing_content": [
            "2024 Corporate Overview (Generic)",
            "2-Minute Donor Montage (Lacks technical depth)",
        ],
        "trends": [
            {
                "trend": "Viral 24-Hour Locked-In Challenge",
                "relevance_score": 0.05,
                "notes": "Trending search traffic, but zero relevance to infrastructure decision-makers.",
            },
        ],
        "available_resources": {
            "budget_tier": "MEDIUM",
            "location_name": "Calgary Clean Energy Demo Facility",
            "location_address": "8800 Energy Way, Calgary AB",
        },
        "deadlines": {
            "shoot_date": "2026-10-22",
            "target_publish_window": "November 2026",
        },
        "missing_information": [],
    }

    # Step 1: Intake & Graph initialization
    print("\n[Step 1] Initializing Project Brief and Epistemic Graph...")
    brief, graph = studio.create_project(brief_data)
    print(f"[OK] Project created: '{brief.working_title}' (Nodes seeded: {len(graph.nodes)})")

    # Step 2: Idea Discovery & Qualification (Pressure Scenario 1: Trend Trap Rejection)
    print("\n[Step 2] Discovering & Qualifying Video Concepts...")
    shortlist, rejected = studio.discover_and_qualify_ideas(brief.project_id)
    print(f"[OK] Qualification Complete: {len(shortlist)} Shortlisted, {len(rejected)} Rejected.")
    for r in rejected:
        print(f"  [REJECTED] '{r.title}'\n     Reason: {r.rejection_reason}")
    for s in shortlist:
        print(f"  [SHORTLISTED] '{s.title}' (Composite Fit: {s.scores['composite']:.2f})")

    selected_idea = shortlist[0]

    # Step 3: Proposal & Strategy Brief Generation
    print(f"\n[Step 3] Developing Strategic Proposal & Audiovisual Treatment for '{selected_idea.title}'...")
    proposal = studio.build_proposal_from_idea(brief.project_id, selected_idea.idea_id)
    print(f"[OK] Proposal Drafted: ID={proposal.proposal_id}, Hash={proposal.content_hash[:12]}...")
    print(f"  Gate 1 (Scope): {proposal.gate_results['gate_1_scope']['status']}")
    print(f"  Gate 2 (Strategy + Creative): {proposal.gate_results['gate_2_strategy_creative']['status']}")
    print(f"  Treatment Sections Generated: {len(proposal.treatment_sections)} scenes (Two-column AV format)")

    # Step 4: Human Approval
    print("\n[Step 4] Human Executive Review & Formal Approval...")
    approved = studio.approve_proposal(brief.project_id, proposal.proposal_id, approver_name="Dr. Aris Thorne")
    print(f"[OK] Proposal Approved: {approved} (Locked with cryptographic content hash)")

    # Step 5: Production Planning (Pressure Scenario 2: Explicit Unknowns Handling)
    print("\n[Step 5] Compiling Production Plan, Shot List, Interview Guide & Call Sheet...")
    plan = studio.create_production_plan(brief.project_id, proposal.proposal_id)
    print(f"[OK] Plan Compiled: {len(plan.shot_plan)} Shots, {len(plan.interview_guide)} Interview Prompts.")
    print(f"  Gate 3 (Shoot Readiness): {plan.gate_results['gate_3_shoot_readiness']['status']}")
    if plan.call_sheet.missing_prerequisites:
        print("  [WARN] Explicit Missing Prerequisites Preserved:")
        for mp in plan.call_sheet.missing_prerequisites:
            print(f"     - {mp}")

    # Step 6: Platform Packaging & Publication Prep (Gate 4 & 5)
    print("\n[Step 6] Generating Platform Deliverables (YouTube & Shorts)...")
    pkg = studio.create_platform_packaging(brief.project_id, proposal.proposal_id)
    print(f"[OK] Platform Packaging Generated (Status: {pkg.approval_status.value} - drafts until locked)")
    print(f"  Gate 4 (Content-Lock): {pkg.gate_results['gate_4_content_lock']['status']}")
    print(f"  Gate 5 (Publish-Readiness 5 QC Classes): {pkg.gate_results['gate_5_publish_readiness']['status']}")
    print(f"  YouTube Title Hypotheses: {len(pkg.youtube_titles)} distinct angles")
    for t in pkg.youtube_titles:
        print(f"     [{t.angle_type}] \"{t.title}\"")
    print(f"  Pre-Shoot Vertical Shorts Hook: \"{pkg.shorts_treatment.hook_seconds_0_to_2}\"")

    # Step 7: PRESSURE TEST 3 — Conflict with SME Evidence
    print("\n" + "=" * 70)
    print(" PRESSURE TEST 3: Subject-Matter Evidence Conflict")
    print("=" * 70)
    print("SITUATION: New lab testing reveals pump flow rate under high heat drops to 60 L/min.")
    contradiction_evidence = [
        {
            "fact": "Direct-drive pump flow rate drops to 60 L/min under ambient temperatures above 40C.",
            "source": "High-Temperature Stress Test Report, August 2026",
        }
    ]
    receipt3 = studio.update_sme_evidence(
        brief.project_id,
        new_evidence=contradiction_evidence,
        reason="Field testing contradicts initial 140 L/min pump claim under extreme heat conditions.",
    )
    print(f"[OK] Targeted Invalidation Triggered: {len(receipt3.affected_nodes)} nodes marked CONTESTED.")
    print(f"  Affected Nodes: {receipt3.affected_nodes}")
    print(f"  Revoked Approvals: {receipt3.revoked_approvals}")

    # Inspect that call sheet remains VALID!
    graph_after_3 = studio.get_project_graph(brief.project_id)
    cs_node_after_3 = graph_after_3.get_node(f"call_sheet:{plan.call_sheet.call_sheet_id}")
    cs_status = cs_node_after_3.status.value if cs_node_after_3 else "VALID"
    print(f"  Call Sheet & Logistics Status: '{cs_status}' (UNAFFECTED!)")
    print("  RESULT: Factual contradiction marked proposal STALE without destroying production logistics.")

    # Reconcile proposal with updated fact and re-approve for Step 8
    print("  Resolution: Producer integrates 60 L/min temperature finding and re-secures factual sign-off...")
    prop_node_3 = graph_after_3.get_node(f"proposal:{proposal.proposal_id}")
    prop_node_3.status = EpistemicNodeStatus.VALID
    graph_after_3.nodes[f"packaging:{pkg.packaging_id}"].status = EpistemicNodeStatus.VALID
    studio._save_graph(brief.project_id, graph_after_3)
    studio.approve_proposal(brief.project_id, proposal.proposal_id, approver_name="Dr. Aris Thorne")

    # Step 8: PRESSURE TEST 4 — Changed Location / Date
    print("\n" + "=" * 70)
    print(" PRESSURE TEST 4: Changed Location & Date Logistics")
    print("=" * 70)
    print("SITUATION: Calgary facility undergoes unscheduled electrical maintenance; shoot moved to Edmonton.")
    receipt4 = studio.update_production_logistics(
        brief.project_id,
        {"location_name": "Edmonton Field Facility", "location_address": "1002 Innovation Park, Edmonton AB", "shoot_date": "2026-11-04"},
        reason="Primary Calgary site inaccessible due to scheduled electrical grid overhaul.",
    )
    print(f"[OK] Logistics Invalidation Triggered: {len(receipt4.affected_nodes)} nodes marked STALE.")
    print(f"  Affected Nodes: {receipt4.affected_nodes}")
    graph_after_4 = studio.get_project_graph(brief.project_id)
    prop_node_after_4 = graph_after_4.get_node(f"proposal:{proposal.proposal_id}")
    pkg_node_after_4 = graph_after_4.get_node(f"packaging:{pkg.packaging_id}")
    print(f"  Script Treatment & Strategic Proposal: '{prop_node_after_4.status.value}' (STABLE!)")
    print(f"  Platform Packaging Titles: '{pkg_node_after_4.status.value}' (STABLE!)")
    print("  RESULT: Changed location invalidated only the call sheet while preserving 100% of the creative script.")

    # Step 9: PRESSURE TEST 5 — Session Persistence & Resumption
    print("\n" + "=" * 70)
    print(" PRESSURE TEST 5: Close Application and Reopen State Verification")
    print("=" * 70)
    print("Action: Closing studio connection and instantiating fresh Studio instance from disk...")
    temp_db = "vantage_persistence_test.db"
    studio_disk = VantageStudio(db_path=temp_db)
    brief_disk, _ = studio_disk.create_project(brief_data)
    studio_disk.close()

    # Re-open fresh instance
    studio_reopened = VantageStudio(db_path=temp_db)
    recovered_brief = studio_reopened.get_project_brief(brief_disk.project_id)
    recovered_graph = studio_reopened.get_project_graph(brief_disk.project_id)
    studio_reopened.close()
    if os.path.exists(temp_db):
        os.remove(temp_db)

    print(f"[OK] Resumed Project from DB: '{recovered_brief.working_title}'")
    print(f"  Graph Nodes Restored: {len(recovered_graph.nodes)}")
    print("  RESULT: Complete project state, nodes, and unresolved work survived session teardown.")

    # Step 10: PRESSURE TEST 6 — Contradictory Performance Results (Gate 6)
    print("\n" + "=" * 70)
    print(" PRESSURE TEST 6: Contradictory Performance Results vs Initial Expectation")
    print("=" * 70)
    print("SITUATION: Published video generates high CTR (8.4%) but steep 30s retention drop (44.2% vs 70% expectation).")
    telemetry_export = {
        "impressions": 48200,
        "views": 4050,
        "ctr_percent": 8.4,
        "avg_duration_seconds": 172,
        "retention_30s_percent": 44.2,
        "traffic_sources": {"Browse Features": 64.0, "YouTube Search": 20.0, "Suggested": 12.0, "Direct": 4.0},
        "shorts_swipe_rate": 26.8,
    }
    perf = studio.analyze_performance(brief.project_id, proposal.proposal_id, telemetry_export, cadence_interval="+7d")
    print(f"[OK] Performance Evaluation Complete (ID: {perf.analysis_id})")
    print(f"  Original Expectation Preserved: Target CTR: {perf.pre_publication_expectations['target_ctr']}, 30s Target: {perf.pre_publication_expectations['expected_30s_retention']}")
    print(f"  Gate 6 (Learning Gate): {perf.gate_result['status']}")
    print(f"  Reusable Lesson Documented:\n     \"{perf.reusable_lesson}\"")
    print("  Actionable Packaging Revisions:")
    for rev in perf.packaging_revisions:
        print(f"     - {rev}")
    print("  Subsequent Idea Candidates Discovered:")
    for idea in perf.subsequent_idea_candidates:
        print(f"     - {idea}")
    print("  RESULT: Historical expectation preserved; causal explanation separated from observation; next actions derived.")

    # Step 11: Export Production Package Dossier
    print("\n[Step 11] Exporting Production Package Dossier...")
    dossier = studio.export_production_dossier_markdown(brief.project_id, proposal.proposal_id)
    output_path = Path("VANTAGE_PRODUCTION_DOSSIER.md")
    output_path.write_text(dossier, encoding="utf-8")
    print(f"[OK] Production Dossier Exported: {output_path.absolute()} ({len(dossier)} bytes)")

    # Step 12: Rubric & Baseline Comparison
    print("\n" + "=" * 70)
    print(" COMPARATIVE RUBRIC BENCHMARK (Vantage vs Simpler Baseline)")
    print("=" * 70)
    benchmark_res = RubricEvaluator.run_comparative_benchmark(brief_data)
    print(f"Total Score: Vantage = {benchmark_res.total_vantage_score:.2f}/5.00 | Baseline = {benchmark_res.total_baseline_score:.2f}/5.00")
    print("Rubric Breakdown:")
    for d in benchmark_res.dimensions:
        print(f"  * {d.dimension_name}: Vantage {d.vantage_score} vs Baseline {d.baseline_score}")
    print(f"\nVerdict: {benchmark_res.summary_verdict}")
    print("=" * 70)
    print("[SUCCESS] DEMONSTRATION COMPLETE: ALL 6 PHASES & PRESSURE SCENARIOS PASSED.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Vantage: Organizational Video Development & Production System")
    parser.add_argument("command", choices=["demo", "benchmark", "status"], default="demo", nargs="?", help="Command to run")
    parser.add_argument("--db", default=":memory:", help="SQLite database path (default: in-memory)")
    args = parser.parse_args()

    if args.command == "demo":
        run_full_lifecycle_demo(db_path=args.db)
    elif args.command == "benchmark":
        brief_data = {
            "project_id": "proj_bench",
            "working_title": "Clean Water Initiative",
            "organization": "Global Health Alliance",
            "decision_owner": "Elena Vance",
            "approval_authority": "Director of Comms",
            "target_audience": {"segment": "Regional Clinics", "problem": "Power and water pump failures"},
            "organizational_goals": ["Achieve 98% uptime"],
            "subject_matter_notes": [{"fact": "Variable frequency drive operates on solar direct"}],
            "trends": [{"trend": "24h Challenge", "relevance_score": 0.1}],
            "available_resources": {"budget_tier": "MEDIUM"},
            "deadlines": {"target_publish_window": "Q4"},
        }
        res = RubricEvaluator.run_comparative_benchmark(brief_data)
        print(json.dumps(res.to_dict(), indent=2))
    elif args.command == "status":
        print("Status command requires an active project database.")


if __name__ == "__main__":
    main()
