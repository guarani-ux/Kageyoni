"""
Comprehensive Automated Test Suite for Vantage Organizational Video System.
Verifies mechanical behaviors, gate enforcements, dependency invalidations,
and the 6 pressure scenarios.
"""

import json
import os
import pytest
from contracts.production_gates import GateStatus
from kageyoni.vantage.engine import VantageStudio
from kageyoni.vantage.models import (
    ApprovalStatus,
    EpistemicNodeStatus,
    IdeaQualificationStatus,
    ProjectBrief,
)
from kageyoni.vantage.qualification import IdeaQualificationEngine
from kageyoni.vantage.rubric import RubricEvaluator


@pytest.fixture
def sample_brief_data():
    return {
        "project_id": "proj_test_01",
        "working_title": "Clean Energy Microgrid Explainer",
        "organization": "Renewable Resilience Institute",
        "decision_owner": "Sarah Jenkins",
        "approval_authority": "VP Communications",
        "target_audience": {
            "segment": "Municipal Power Directors",
            "problem": "Frequent blackout events during severe winter storms",
        },
        "organizational_goals": [
            "Demonstrate 99.9% winter grid reliability",
            "Drive 25 municipal feasibility audits in 2027",
        ],
        "campaign_priorities": [
            "Winter Grid Resilience Campaign 2026",
        ],
        "stakeholder_requests": [
            "Ensure battery cold-weather discharge telemetry is verified",
        ],
        "subject_matter_notes": [
            {
                "fact": "Sodium-ion storage retains 91% capacity at -30 Celsius without external heating.",
                "source": "Cold-Weather Field Lab Report",
            },
        ],
        "existing_content": ["General Solar 101 Video"],
        "trends": [
            {
                "trend": "Viral Sub-Zero Frozen Challenge",
                "relevance_score": 0.05,
            },
        ],
        "available_resources": {
            "budget_tier": "MEDIUM",
            "location_name": "Canmore Alpine Research Facility",
            "location_address": "1200 Mountain Way, Canmore AB",
        },
        "deadlines": {
            "shoot_date": "2026-11-12",
            "target_publish_window": "December 2026",
        },
        "missing_information": [],
    }


def test_scenario_1_trend_trap_rejection(sample_brief_data):
    """
    Scenario 1: An idea fits a trend but lacks organizational or audience relevance.
    It should NOT pass qualification merely because it may attract clicks.
    """
    brief = ProjectBrief.from_dict(sample_brief_data)
    shortlist, rejected = IdeaQualificationEngine.discover_and_qualify(brief)

    # Must have rejected the trend trap
    trend_rejections = [r for r in rejected if r.trend_alignment == "Viral Sub-Zero Frozen Challenge"]
    assert len(trend_rejections) == 1
    tr = trend_rejections[0]
    assert tr.status == IdeaQualificationStatus.REJECTED
    assert "TREND_WITHOUT_ORGANIZATIONAL_OR_AUDIENCE_RELEVANCE" in tr.rejection_reason
    assert tr.scores["org_contribution"] < 0.50

    # The substantive engineering concept must be shortlisted
    assert len(shortlist) >= 1
    assert shortlist[0].status == IdeaQualificationStatus.SHORTLISTED
    assert shortlist[0].scores["composite"] >= 0.65


def test_scenario_2_missing_marketing_info_allows_independent_prep(sample_brief_data):
    """
    Scenario 2: Marketing information is missing.
    Independent preparation should continue; campaign-dependent claims should remain unresolved.
    """
    # Remove campaign priorities
    brief_data = dict(sample_brief_data)
    brief_data["campaign_priorities"] = []

    studio = VantageStudio(db_path=":memory:")
    brief, graph = studio.create_project(brief_data)

    # Campaign node must be UNKNOWN
    campaign_node = graph.get_node("brief:campaign")
    assert campaign_node.status == EpistemicNodeStatus.UNKNOWN

    # Independent creative & production steps should continue smoothly
    shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
    proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)
    plan = studio.create_production_plan(brief.project_id, proposal.proposal_id)

    # Shot plan and interview guide are generated
    assert len(plan.shot_plan) > 0
    assert len(plan.interview_guide) > 0

    # Unresolved campaign notice must remain explicit
    assert any("marketing campaign" in item.lower() for item in plan.unresolved_items)


def test_scenario_3_sme_conflict_invalidates_concept_and_preserves_logistics(sample_brief_data):
    """
    Scenario 3: New SME evidence conflicts with a selected concept.
    The conflict, affected decisions, and approval implications become visible without rewriting unrelated work.
    """
    studio = VantageStudio(db_path=":memory:")
    brief, graph = studio.create_project(sample_brief_data)
    shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
    proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)
    approved = studio.approve_proposal(brief.project_id, proposal.proposal_id, "Sarah Jenkins")
    assert approved is True

    plan = studio.create_production_plan(brief.project_id, proposal.proposal_id)
    pkg = studio.create_platform_packaging(brief.project_id, proposal.proposal_id)

    # Contradict the battery claim
    new_sme = [{"fact": "Sodium-ion battery freezes and ceases output at -20C without active thermal blanket."}]
    receipt = studio.update_sme_evidence(
        brief.project_id,
        new_evidence=new_sme,
        reason="Field test proves battery freezes without active heating."
    )

    # Invalidation checks
    assert f"proposal:{proposal.proposal_id}" in receipt.affected_nodes
    assert f"proposal:{proposal.proposal_id}" in receipt.revoked_approvals
    assert f"packaging:{pkg.packaging_id}" in receipt.affected_nodes

    # The call sheet logistics must be UNAFFECTED
    graph_after = studio.get_project_graph(brief.project_id)
    cs_node = graph_after.get_node(f"call_sheet:{plan.call_sheet.call_sheet_id}")
    assert cs_node is not None
    assert cs_node.status != EpistemicNodeStatus.CONTESTED
    # Proposal node must be CONTESTED and approval revoked to STALE
    prop_node = graph_after.get_node(f"proposal:{proposal.proposal_id}")
    assert prop_node.status == EpistemicNodeStatus.CONTESTED
    assert prop_node.approval_status == ApprovalStatus.STALE


def test_scenario_4_logistics_change_invalidates_call_sheet_and_preserves_script(sample_brief_data):
    """
    Scenario 4: A changed location or date affects production documents.
    Dependent information should update consistently, and missing arrangements stay explicit.
    """
    studio = VantageStudio(db_path=":memory:")
    brief, graph = studio.create_project(sample_brief_data)
    shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
    proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)
    studio.approve_proposal(brief.project_id, proposal.proposal_id, "Sarah Jenkins")
    plan = studio.create_production_plan(brief.project_id, proposal.proposal_id)
    pkg = studio.create_platform_packaging(brief.project_id, proposal.proposal_id)

    # Change location
    receipt = studio.update_production_logistics(
        brief.project_id,
        {"location_name": "Nordic Testing Center", "location_address": "400 Glacier Rd", "shoot_date": "2026-11-20"},
        reason="Canmore facility snowed out."
    )

    # Call sheet is invalidated
    assert f"call_sheet:{plan.call_sheet.call_sheet_id}" in receipt.affected_nodes

    # Proposal, treatment, and packaging remain strictly VALID
    graph_after = studio.get_project_graph(brief.project_id)
    prop_node = graph_after.get_node(f"proposal:{proposal.proposal_id}")
    pkg_node = graph_after.get_node(f"packaging:{pkg.packaging_id}")
    assert prop_node.status == EpistemicNodeStatus.VALID
    assert prop_node.approval_status == ApprovalStatus.APPROVED
    assert pkg_node.status == EpistemicNodeStatus.VALID


def test_scenario_5_session_persistence_roundtrip(sample_brief_data, tmp_path):
    """
    Scenario 5: The application is closed and reopened.
    Relevant project state and unresolved work should survive.
    """
    db_file = str(tmp_path / "test_persistence.db")
    studio1 = VantageStudio(db_path=db_file)
    brief1, _ = studio1.create_project(sample_brief_data)
    shortlist1, _ = studio1.discover_and_qualify_ideas(brief1.project_id)
    prop1 = studio1.build_proposal_from_idea(brief1.project_id, shortlist1[0].idea_id)
    plan1 = studio1.create_production_plan(brief1.project_id, prop1.proposal_id)
    studio1.close()

    # Reopen fresh instance
    studio2 = VantageStudio(db_path=db_file)
    brief2 = studio2.get_project_brief(brief1.project_id)
    graph2 = studio2.get_project_graph(brief1.project_id)

    assert brief2.working_title == sample_brief_data["working_title"]
    assert len(graph2.nodes) > 0
    assert f"proposal:{prop1.proposal_id}" in graph2.nodes
    assert f"production_plan:{plan1.plan_id}" in graph2.nodes

    # Unresolved prerequisites survived
    plan_row = studio2.conn.execute("SELECT data_json FROM vantage_production_plans WHERE plan_id = ?", (plan1.plan_id,)).fetchone()
    recovered_plan_data = json.loads(plan_row["data_json"])
    assert len(recovered_plan_data["unresolved_items"]) > 0
    studio2.close()


def test_scenario_6_contradictory_performance_telemetry(sample_brief_data):
    """
    Scenario 6: Performance results contradict the original expectation.
    The system should preserve original expectation and propose a justified next action—not rewrite history into success.
    """
    studio = VantageStudio(db_path=":memory:")
    brief, _ = studio.create_project(sample_brief_data)
    shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
    proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)

    # Ingest contradictory metrics (High CTR, steep drop-off at 30s)
    telemetry = {
        "impressions": 50000,
        "views": 4200,
        "ctr_percent": 8.4,
        "avg_duration_seconds": 150,
        "retention_30s_percent": 41.0,  # Below 70% expectation
    }
    perf = studio.analyze_performance(brief.project_id, proposal.proposal_id, telemetry, cadence_interval="+7d")

    # Original expectation must be preserved
    assert "target_ctr" in perf.pre_publication_expectations
    assert "expected_30s_retention" in perf.pre_publication_expectations

    # Observations and Explanations must be separated
    assert len(perf.observations) >= 4
    assert len(perf.explanations) >= 2
    for exp in perf.explanations:
        assert "correlation_vs_causation_caution" in exp
        assert "hypothesis" in exp

    # Actionable revisions & next ideas must be generated
    assert len(perf.packaging_revisions) >= 1
    assert len(perf.subsequent_idea_candidates) >= 1
    assert perf.gate_result["status"] == GateStatus.PASSED.value


def test_content_modification_revokes_unearned_approval(sample_brief_data):
    """
    Invariant: Editing a document must not silently create or maintain an approval.
    """
    studio = VantageStudio(db_path=":memory:")
    brief, graph = studio.create_project(sample_brief_data)
    shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
    proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)
    studio.approve_proposal(brief.project_id, proposal.proposal_id, "Sarah Jenkins")

    # Verify initially approved
    graph1 = studio.get_project_graph(brief.project_id)
    prop_node = graph1.get_node(f"proposal:{proposal.proposal_id}")
    assert prop_node.approval_status == ApprovalStatus.APPROVED

    # Invalidate upstream SME
    studio.update_sme_evidence(brief.project_id, [{"fact": "Altered fact"}], reason="Fact altered")

    # Status must automatically become STALE
    graph2 = studio.get_project_graph(brief.project_id)
    prop_node2 = graph2.get_node(f"proposal:{proposal.proposal_id}")
    assert prop_node2.approval_status == ApprovalStatus.STALE


def test_rubric_evaluator_comparative_benchmark(sample_brief_data):
    """
    Verifies the declared review rubric and comparative baseline execution.
    """
    res = RubricEvaluator.run_comparative_benchmark(sample_brief_data)
    assert res.total_vantage_score > res.total_baseline_score
    assert res.mechanical_metrics["vantage_fabrications_detected"] == 0
    assert res.mechanical_metrics["baseline_fabrications_detected"] > 0
    assert len(res.dimensions) == 5
