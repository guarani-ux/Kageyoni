"""
Vantage Studio Engine: Core coordinator and durable persistence layer.
Manages the end-to-end media development lifecycle on top of SQLite and Epistemic Graph.
"""

from __future__ import annotations
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from contracts.production_gates import ProductionGatekeeper, GateStatus, GateResult
from .graph import EpistemicDependencyGraph, GraphNode, InvalidationReceipt
from .models import (
    ApprovalStatus,
    CallSheet,
    EpistemicNodeStatus,
    IdeaCandidate,
    IdeaQualificationStatus,
    PerformanceAnalysis,
    PlatformPackaging,
    ProductionPlan,
    ProjectBrief,
    ShortsTreatment,
    StrategicProposal,
    ThumbnailDirection,
    TitleOption,
    TreatmentSection,
)
from .packaging import PackagingGenerator
from .performance import PerformanceAnalyzer
from .production import ProductionPlanner
from .proposal import ProposalGenerator
from .qualification import IdeaQualificationEngine


class VantageStudio:
    """
    Main organizational video development coordinator.
    Enforces epistemic integrity, durable persistence, non-destructive invalidation,
    and decision gatekeeping across the 6 lifecycle phases.
    """

    def __init__(self, db_path: str = "vantage_studio.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS vantage_projects (
                    project_id TEXT PRIMARY KEY,
                    working_title TEXT NOT NULL,
                    organization TEXT NOT NULL,
                    decision_owner TEXT NOT NULL,
                    approval_authority TEXT NOT NULL,
                    current_stage TEXT NOT NULL,
                    brief_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vantage_ideas (
                    idea_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS vantage_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    idea_id TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS vantage_production_plans (
                    plan_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS vantage_packaging (
                    packaging_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS vantage_performance (
                    analysis_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );

                CREATE TABLE IF NOT EXISTS vantage_graphs (
                    project_id TEXT PRIMARY KEY,
                    graph_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES vantage_projects(project_id)
                );
            """)

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    # -------------------------------------------------------------------------
    # STAGE 1: Intake & Brief Initialisation
    # -------------------------------------------------------------------------

    def create_project(self, brief_data: Dict[str, Any]) -> Tuple[ProjectBrief, EpistemicDependencyGraph]:
        brief = ProjectBrief.from_dict(brief_data)
        graph = EpistemicDependencyGraph()

        # Seed initial graph nodes
        graph.add_node("brief:org_goals", "INPUT", "Organizational Goals", payload={"goals": brief.organizational_goals})
        graph.add_node("brief:sme_claims", "INPUT", "Subject Matter Evidence", payload={"notes": brief.subject_matter_notes})
        
        # Check campaign priorities (Scenario 2: missing marketing information remains explicit UNKNOWN)
        campaign_status = EpistemicNodeStatus.VALID if brief.campaign_priorities else EpistemicNodeStatus.UNKNOWN
        graph.add_node("brief:campaign", "INPUT", "Campaign Priorities", status=campaign_status, payload={"campaigns": brief.campaign_priorities})

        # Logistics node
        logistics_data = {
            "shoot_date": brief.deadlines.get("shoot_date"),
            "location_name": brief.available_resources.get("location_name"),
            "location_address": brief.available_resources.get("location_address"),
        }
        logistics_status = EpistemicNodeStatus.VALID if (logistics_data["shoot_date"] and logistics_data["location_name"]) else EpistemicNodeStatus.UNKNOWN
        graph.add_node("brief:logistics", "INPUT", "Production Logistics", status=logistics_status, payload=logistics_data)

        # Persist project & graph
        now = time.time()
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_projects
                (project_id, working_title, organization, decision_owner, approval_authority, current_stage, brief_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    brief.project_id,
                    brief.working_title,
                    brief.organization,
                    brief.decision_owner,
                    brief.approval_authority,
                    "INTAKE_SCOPED",
                    json.dumps(brief.to_dict()),
                    now,
                    now,
                )
            )
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_graphs (project_id, graph_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (brief.project_id, json.dumps(graph.to_dict()), now)
            )

        return brief, graph

    # -------------------------------------------------------------------------
    # STAGE 2: Idea Discovery & Qualification
    # -------------------------------------------------------------------------

    def discover_and_qualify_ideas(
        self,
        project_id: str,
        custom_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[IdeaCandidate], List[IdeaCandidate]]:
        brief = self.get_project_brief(project_id)
        graph = self.get_project_graph(project_id)

        shortlist, rejected = IdeaQualificationEngine.discover_and_qualify(brief, custom_candidates)

        # Add ideas to graph
        for cand in shortlist + rejected:
            node_status = EpistemicNodeStatus.VALID if cand.status == IdeaQualificationStatus.SHORTLISTED else EpistemicNodeStatus.BLOCKED
            graph.add_node(
                node_id=f"idea:{cand.idea_id}",
                node_type="IDEA_CANDIDATE",
                title=cand.title,
                status=node_status,
                payload=cand.to_dict(),
                dependencies=["brief:org_goals", "brief:sme_claims"],
            )

            # Persist idea in SQLite
            with self.conn:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO vantage_ideas (idea_id, project_id, title, status, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cand.idea_id, project_id, cand.title, cand.status.value, json.dumps(cand.to_dict()), time.time())
                )

        self._save_graph(project_id, graph)
        return shortlist, rejected

    # -------------------------------------------------------------------------
    # STAGE 3: Proposal & Strategy Brief Generation
    # -------------------------------------------------------------------------

    def build_proposal_from_idea(self, project_id: str, idea_id: str) -> StrategicProposal:
        brief = self.get_project_brief(project_id)
        graph = self.get_project_graph(project_id)

        row = self.conn.execute("SELECT data_json FROM vantage_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
        if not row:
            raise KeyError(f"Idea '{idea_id}' not found.")
        idea = IdeaCandidate.from_dict(json.loads(row["data_json"]))

        proposal = ProposalGenerator.create_proposal(idea, brief)

        # Connect proposal in graph
        prop_node_id = f"proposal:{proposal.proposal_id}"
        graph.add_node(
            node_id=prop_node_id,
            node_type="STRATEGIC_PROPOSAL",
            title=proposal.working_title,
            status=EpistemicNodeStatus.VALID,
            approval_status=proposal.approval_status,
            content_hash=proposal.content_hash,
            payload=proposal.to_dict(),
            dependencies=[f"idea:{idea.idea_id}", "brief:org_goals", "brief:sme_claims"],
        )

        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_proposals
                (proposal_id, project_id, idea_id, approval_status, content_hash, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (proposal.proposal_id, project_id, idea.idea_id, proposal.approval_status.value, proposal.content_hash, json.dumps(proposal.to_dict()), time.time())
            )
            self.conn.execute(
                "UPDATE vantage_projects SET current_stage = ?, updated_at = ? WHERE project_id = ?",
                ("PROPOSAL_DRAFTED", time.time(), project_id)
            )

        self._save_graph(project_id, graph)
        return proposal

    def approve_proposal(self, project_id: str, proposal_id: str, approver_name: str) -> bool:
        graph = self.get_project_graph(project_id)
        node_id = f"proposal:{proposal_id}"
        node = graph.get_node(node_id)
        if not node:
            return False

        current_hash = node.content_hash
        success = graph.grant_approval(node_id, approver_name, current_hash)
        if success:
            with self.conn:
                row = self.conn.execute("SELECT data_json FROM vantage_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
                if row:
                    pdata = json.loads(row["data_json"])
                    pdata["approval_status"] = ApprovalStatus.APPROVED.value
                    pdata["approved_by"] = approver_name
                    pdata["approved_at"] = time.time()
                    self.conn.execute(
                        "UPDATE vantage_proposals SET approval_status = ?, data_json = ? WHERE proposal_id = ?",
                        (ApprovalStatus.APPROVED.value, json.dumps(pdata), proposal_id)
                    )
                self.conn.execute(
                    "UPDATE vantage_projects SET current_stage = ?, updated_at = ? WHERE project_id = ?",
                    ("PROPOSAL_APPROVED", time.time(), project_id)
                )
            self._save_graph(project_id, graph)
        return success

    # -------------------------------------------------------------------------
    # STAGE 4: Production Planning & Call Sheet
    # -------------------------------------------------------------------------

    def create_production_plan(
        self,
        project_id: str,
        proposal_id: str,
        logistics_override: Optional[Dict[str, Any]] = None,
    ) -> ProductionPlan:
        brief = self.get_project_brief(project_id)
        graph = self.get_project_graph(project_id)

        row = self.conn.execute("SELECT data_json FROM vantage_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
        if not row:
            raise KeyError(f"Proposal '{proposal_id}' not found.")
        proposal = StrategicProposal.from_dict(json.loads(row["data_json"]))

        plan = ProductionPlanner.generate_plan(proposal, brief, logistics_override)

        # 1. Granular Call Sheet node: depends strictly on logistics
        cs_node_id = f"call_sheet:{plan.call_sheet.call_sheet_id}"
        graph.add_node(
            node_id=cs_node_id,
            node_type="CALL_SHEET",
            title=f"Call Sheet: {proposal.working_title}",
            status=plan.status,
            payload=plan.call_sheet.to_dict(),
            dependencies=["brief:logistics"],
        )

        # 2. Granular Shot Plan node: depends on proposal treatment
        shot_node_id = f"shot_plan:{plan.plan_id}"
        graph.add_node(
            node_id=shot_node_id,
            node_type="SHOT_PLAN",
            title=f"Shot Plan: {proposal.working_title}",
            status=EpistemicNodeStatus.VALID,
            payload={"shots": plan.shot_plan},
            dependencies=[f"proposal:{proposal.proposal_id}"],
        )

        # 3. Overall production plan node
        plan_node_id = f"production_plan:{plan.plan_id}"
        graph.add_node(
            node_id=plan_node_id,
            node_type="PRODUCTION_PLAN",
            title=f"Production Plan: {proposal.working_title}",
            status=plan.status,
            payload=plan.to_dict(),
            dependencies=[cs_node_id, shot_node_id],
        )

        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_production_plans (plan_id, project_id, status, data_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (plan.plan_id, project_id, plan.status.value, json.dumps(plan.to_dict()), time.time())
            )
            stage = "SHOOT_PREPARED" if plan.status == EpistemicNodeStatus.VALID else "SHOOT_BLOCKED_PREREQUISITES"
            self.conn.execute(
                "UPDATE vantage_projects SET current_stage = ?, updated_at = ? WHERE project_id = ?",
                (stage, time.time(), project_id)
            )

        self._save_graph(project_id, graph)
        return plan

    # -------------------------------------------------------------------------
    # STAGE 5: Platform Packaging & Publication Preparation
    # -------------------------------------------------------------------------

    def create_platform_packaging(
        self,
        project_id: str,
        proposal_id: str,
        qc_override: Optional[Dict[str, Any]] = None,
    ) -> PlatformPackaging:
        brief = self.get_project_brief(project_id)
        graph = self.get_project_graph(project_id)

        row = self.conn.execute("SELECT data_json FROM vantage_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
        if not row:
            raise KeyError(f"Proposal '{proposal_id}' not found.")
        proposal = StrategicProposal.from_dict(json.loads(row["data_json"]))

        packaging = PackagingGenerator.generate_packaging(proposal, brief, qc_override)

        pkg_node_id = f"packaging:{packaging.packaging_id}"
        graph.add_node(
            node_id=pkg_node_id,
            node_type="PLATFORM_PACKAGING",
            title=f"Platform Packaging: {proposal.working_title}",
            status=packaging.status,
            approval_status=packaging.approval_status,
            payload=packaging.to_dict(),
            dependencies=[f"proposal:{proposal.proposal_id}"],
        )

        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_packaging (packaging_id, project_id, approval_status, status, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (packaging.packaging_id, project_id, packaging.approval_status.value, packaging.status.value, json.dumps(packaging.to_dict()), time.time())
            )
            self.conn.execute(
                "UPDATE vantage_projects SET current_stage = ?, updated_at = ? WHERE project_id = ?",
                ("PACKAGING_DRAFTED", time.time(), project_id)
            )

        self._save_graph(project_id, graph)
        return packaging

    # -------------------------------------------------------------------------
    # STAGE 6: Performance Telemetry & Learning Loop
    # -------------------------------------------------------------------------

    def analyze_performance(
        self,
        project_id: str,
        proposal_id: str,
        telemetry_export: Dict[str, Any],
        cadence_interval: str = "+7d",
    ) -> PerformanceAnalysis:
        graph = self.get_project_graph(project_id)
        row = self.conn.execute("SELECT data_json FROM vantage_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
        if not row:
            raise KeyError(f"Proposal '{proposal_id}' not found.")
        proposal = StrategicProposal.from_dict(json.loads(row["data_json"]))

        analysis = PerformanceAnalyzer.evaluate_performance(proposal, telemetry_export, cadence_interval)

        analysis_node_id = f"performance:{analysis.analysis_id}"
        graph.add_node(
            node_id=analysis_node_id,
            node_type="PERFORMANCE_ANALYSIS",
            title=f"Performance Telemetry ({cadence_interval}): {proposal.working_title}",
            status=EpistemicNodeStatus.VALID,
            payload=analysis.to_dict(),
            dependencies=[f"proposal:{proposal.proposal_id}"],
        )

        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO vantage_performance (analysis_id, project_id, data_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (analysis.analysis_id, project_id, json.dumps(analysis.to_dict()), time.time())
            )
            self.conn.execute(
                "UPDATE vantage_projects SET current_stage = ?, updated_at = ? WHERE project_id = ?",
                ("PERFORMANCE_EVALUATED", time.time(), project_id)
            )

        self._save_graph(project_id, graph)
        return analysis

    # -------------------------------------------------------------------------
    # CHANGE MANAGEMENT & TARGETED INVALIDATION (Pressure Tests 3 & 4)
    # -------------------------------------------------------------------------

    def update_sme_evidence(
        self,
        project_id: str,
        new_evidence: List[Dict[str, Any]],
        reason: str,
    ) -> InvalidationReceipt:
        """
        Scenario 3: New SME evidence conflicts with a concept.
        Invalidates proposal, treatment, and packaging; revokes approvals.
        Crucially preserves independent logistics and call sheets!
        """
        graph = self.get_project_graph(project_id)
        brief = self.get_project_brief(project_id)
        brief.subject_matter_notes = new_evidence
        brief.updated_at = time.time()

        sme_node = graph.get_node("brief:sme_claims")
        if sme_node:
            sme_node.payload = {"notes": new_evidence}

        receipt = graph.invalidate("brief:sme_claims", reason=reason, target_status=EpistemicNodeStatus.CONTESTED)

        # Update DB
        with self.conn:
            self.conn.execute(
                "UPDATE vantage_projects SET brief_json = ?, updated_at = ? WHERE project_id = ?",
                (json.dumps(brief.to_dict()), time.time(), project_id)
            )
            for node_id in receipt.affected_nodes:
                if node_id.startswith("proposal:"):
                    prop_id = node_id.split(":")[1]
                    self.conn.execute(
                        "UPDATE vantage_proposals SET approval_status = ? WHERE proposal_id = ?",
                        (ApprovalStatus.STALE.value, prop_id)
                    )

        self._save_graph(project_id, graph)
        return receipt

    def update_production_logistics(
        self,
        project_id: str,
        new_logistics: Dict[str, Any],
        reason: str,
    ) -> InvalidationReceipt:
        """
        Scenario 4: Changed location or date.
        Invalidates production documents (call sheet, schedule).
        Leaves strategic brief, script narrative, and YouTube titles completely VALID!
        """
        graph = self.get_project_graph(project_id)
        logistics_node = graph.get_node("brief:logistics")
        if logistics_node:
            logistics_node.payload = new_logistics

        receipt = graph.invalidate("brief:logistics", reason=reason, target_status=EpistemicNodeStatus.STALE)

        for node_id in receipt.affected_nodes:
            if node_id.startswith("production_plan:"):
                plan_id = node_id.split(":")[1]
                with self.conn:
                    self.conn.execute(
                        "UPDATE vantage_production_plans SET status = ? WHERE plan_id = ?",
                        (EpistemicNodeStatus.STALE.value, plan_id)
                    )

        self._save_graph(project_id, graph)
        return receipt

    # -------------------------------------------------------------------------
    # PERSISTENCE HELPERS
    # -------------------------------------------------------------------------

    def get_project_brief(self, project_id: str) -> ProjectBrief:
        row = self.conn.execute("SELECT brief_json FROM vantage_projects WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            raise KeyError(f"Project '{project_id}' not found.")
        return ProjectBrief.from_dict(json.loads(row["brief_json"]))

    def get_project_graph(self, project_id: str) -> EpistemicDependencyGraph:
        row = self.conn.execute("SELECT graph_json FROM vantage_graphs WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return EpistemicDependencyGraph()
        return EpistemicDependencyGraph.from_dict(json.loads(row["graph_json"]))

    def _save_graph(self, project_id: str, graph: EpistemicDependencyGraph) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE vantage_graphs SET graph_json = ?, updated_at = ? WHERE project_id = ?",
                (json.dumps(graph.to_dict()), time.time(), project_id)
            )

    def export_production_dossier_markdown(self, project_id: str, proposal_id: str) -> str:
        """Generates an inspectable Markdown production package for review."""
        brief = self.get_project_brief(project_id)
        p_row = self.conn.execute("SELECT data_json FROM vantage_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
        if not p_row:
            return "# Error: Proposal not found"
        proposal = StrategicProposal.from_dict(json.loads(p_row["data_json"]))

        plan_row = self.conn.execute("SELECT data_json FROM vantage_production_plans WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        plan = ProductionPlan.from_dict(json.loads(plan_row["data_json"])) if plan_row else None

        pkg_row = self.conn.execute("SELECT data_json FROM vantage_packaging WHERE project_id = ? ORDER BY created_at DESC LIMIT 1", (project_id,)).fetchone()
        pkg = PlatformPackaging.from_dict(json.loads(pkg_row["data_json"])) if pkg_row else None

        md = []
        md.append(f"# VANTAGE PRODUCTION DOSSIER: {proposal.working_title.upper()}")
        md.append(f"**Organization:** {brief.organization} | **Decision Owner:** {brief.decision_owner}")
        md.append(f"**Proposal Approval Status:** `{proposal.approval_status.value}` (Approved by: {proposal.approved_by or 'None'})\n")

        md.append("## 1. STRATEGIC RATIONALE (Why this video should exist)")
        for k, v in proposal.strategic_rationale.items():
            md.append(f"- **{k.replace('_', ' ').title()}:** {v}")
        md.append("")

        md.append("## 2. AUDIOVISUAL TREATMENT (What viewers see and hear)")
        md.append("| Timecode | Job / Function | Spoken Audio / Dialogue | Visual Scene & Proof |")
        md.append("| :--- | :--- | :--- | :--- |")
        for s in proposal.treatment_sections:
            clean_audio = s.audio_column.replace('\n', ' ')
            clean_video = s.video_column.replace('\n', ' ')
            md.append(f"| `{s.timecode_range}` | **{s.structural_function}** | {clean_audio} | {clean_video} |")
        md.append("")

        if plan:
            md.append("## 3. PRODUCTION PLAN & CALL SHEET")
            cs = plan.call_sheet
            md.append(f"- **Shoot Date:** `{cs.shoot_date or '[MISSING: Date unconfirmed]'}`")
            md.append(f"- **Location:** `{cs.location_name or '[MISSING: Location unconfirmed]'}`, {cs.location_address or '[MISSING: Address]'}")
            md.append(f"- **Call Time:** `{cs.call_time}`")
            md.append(f"- **Gate 3 Status:** `{plan.status.value}`\n")
            if cs.missing_prerequisites:
                md.append("### Explicit Missing Prerequisites (Fail-Closed):")
                for mp in cs.missing_prerequisites:
                    md.append(f"- [!] **{mp}**")
                md.append("")

        if pkg:
            md.append("## 4. PLATFORM PACKAGING DELIVERABLES (Drafts pending lock)")
            md.append("### YouTube Title Hypotheses (Multi-Angle):")
            for t in pkg.youtube_titles:
                md.append(f"- **[{t.angle_type}]** *\"{t.title}\"* — *{t.rationale}*")
            md.append("")
            md.append("### Thumbnail Visual Directives:")
            for td in pkg.thumbnail_directions:
                md.append(f"- **{td.concept_name}:** Focal: {td.focal_subject} | Copy: `{td.text_copy_max_3_words}` | *{td.mobile_legibility_notes}*")
            md.append("")
            md.append("### Derivative Shorts Plan (9:16 Vertical):")
            md.append(f"- **Hook (0-2s):** {pkg.shorts_treatment.hook_seconds_0_to_2}")
            md.append(f"- **Pre-shoot Instruction:** {pkg.shorts_treatment.pre_shoot_derivative_instructions}\n")

        return "\n".join(md)
