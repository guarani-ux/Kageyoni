"""
Idea Discovery & Qualification Engine for Vantage.
Evaluates video concepts against organizational contribution, audience demand,
evidence grounding, and production feasibility.
Explicitly rejects trend-chasing concepts that lack organizational or audience fit.
"""

from __future__ import annotations
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    IdeaCandidate,
    IdeaQualificationStatus,
    ProjectBrief,
)


class IdeaQualificationEngine:
    """
    Discovers, evaluates, and filters video concepts.
    Enforces that high-clickbait trends without substance are rejected.
    """

    MIN_ORG_CONTRIBUTION = 0.50
    MIN_AUDIENCE_RELEVANCE = 0.50
    MIN_EVIDENCE_GROUNDING = 0.40
    QUALIFICATION_THRESHOLD = 0.65

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_dict: Dict[str, Any],
        brief: ProjectBrief,
    ) -> IdeaCandidate:
        """
        Evaluates a single idea candidate against the project brief.
        Computes multi-dimensional scores and applies fail-closed qualification rules.
        """
        title = candidate_dict.get("title", "Untitled Concept")
        premise = candidate_dict.get("premise", "")
        hook = candidate_dict.get("hook", "")
        target_audience = candidate_dict.get("target_audience", brief.target_audience.get("segment", "General Public"))
        trend_name = candidate_dict.get("trend_alignment")

        # 1. Evaluate Organizational Contribution
        org_contribution_text = candidate_dict.get("organizational_contribution", "")
        org_score = candidate_dict.get("org_contribution_score")
        if org_score is None:
            # Score heuristically based on alignment with brief organizational goals
            matched_goals = [
                g for g in brief.organizational_goals
                if any(word.lower() in org_contribution_text.lower() or word.lower() in premise.lower()
                       for word in g.split() if len(word) > 4)
            ]
            org_score = min(1.0, 0.3 + 0.35 * len(matched_goals)) if org_contribution_text else 0.1

        # 2. Evaluate Audience Relevance & Demand
        aud_score = candidate_dict.get("audience_relevance_score")
        if aud_score is None:
            target_problem = brief.target_audience.get("problem", "").lower()
            if target_problem and any(w in premise.lower() or w in hook.lower() for w in target_problem.split() if len(w) > 3):
                aud_score = 0.85
            elif "audience" in candidate_dict and len(candidate_dict["audience"]) > 10:
                aud_score = 0.70
            else:
                aud_score = 0.35

        # 3. Evaluate Supporting Evidence & SME Grounding
        evidence = candidate_dict.get("supporting_evidence", [])
        ev_score = candidate_dict.get("evidence_grounding_score")
        if ev_score is None:
            matched_sme = [
                s for s in brief.subject_matter_notes
                if any(w in premise.lower() or w in str(evidence).lower() for w in s.get("fact", "").split() if len(w) > 4)
            ]
            ev_score = min(1.0, 0.2 + 0.3 * len(matched_sme) + 0.1 * len(evidence))

        # 4. Evaluate Production Feasibility
        prod_implications = candidate_dict.get("production_implications", "")
        prod_score = candidate_dict.get("production_feasibility_score", 0.75)
        # Check against available budget/resources
        budget_limit = brief.available_resources.get("budget_tier", "MEDIUM")
        if "high budget" in prod_implications.lower() and budget_limit == "LOW":
            prod_score = 0.30

        # 5. Evaluate Trend Authenticity vs Opportunism
        trend_score = 1.0
        if trend_name:
            # If concept aligns with a trend, check if the trend is substantively relevant
            trend_data = next((t for t in brief.trends if t.get("name") == trend_name or t.get("trend") == trend_name), None)
            if trend_data:
                trend_rel = trend_data.get("relevance_score", 0.5)
                trend_score = trend_rel

        # Composite calculation
        # Weights: Org (0.30), Audience (0.30), Evidence (0.25), Feasibility (0.15)
        composite = round(
            (org_score * 0.30) +
            (aud_score * 0.30) +
            (ev_score * 0.25) +
            (prod_score * 0.15),
            3
        )

        scores = {
            "org_contribution": round(org_score, 2),
            "audience_relevance": round(aud_score, 2),
            "evidence_grounding": round(ev_score, 2),
            "production_feasibility": round(prod_score, 2),
            "trend_authenticity": round(trend_score, 2),
            "composite": composite,
        }

        # Apply Hard Qualification Rules
        unresolved = list(candidate_dict.get("unresolved_questions", []))
        rejection_reason = None
        status = IdeaQualificationStatus.QUALIFIED

        # RULE 1: Trend Trap Check (Scenario 1)
        # An idea that fits a trend but lacks org or audience relevance MUST NOT PASS!
        if trend_name and (org_score < cls.MIN_ORG_CONTRIBUTION or aud_score < cls.MIN_AUDIENCE_RELEVANCE):
            status = IdeaQualificationStatus.REJECTED
            rejection_reason = (
                f"TREND_WITHOUT_ORGANIZATIONAL_OR_AUDIENCE_RELEVANCE: Concept chases trend '{trend_name}' "
                f"but fails organizational threshold ({org_score:.2f} < {cls.MIN_ORG_CONTRIBUTION:.2f}) "
                f"or audience need ({aud_score:.2f} < {cls.MIN_AUDIENCE_RELEVANCE:.2f}). "
                "Clicks without relevance erode institutional trust."
            )
        # RULE 2: Insufficient Evidence Grounding
        elif ev_score < cls.MIN_EVIDENCE_GROUNDING:
            status = IdeaQualificationStatus.REJECTED
            rejection_reason = (
                f"EVIDENCE_DEFICIT: Supporting evidence score ({ev_score:.2f}) is below minimum "
                f"threshold ({cls.MIN_EVIDENCE_GROUNDING:.2f}). Concept makes unverified assertions "
                "lacking SME source backing."
            )
        # RULE 3: Overall Composite Below Threshold
        elif composite < cls.QUALIFICATION_THRESHOLD:
            status = IdeaQualificationStatus.REJECTED
            rejection_reason = (
                f"INSUFFICIENT_COMPOSITE_FIT: Overall qualification score ({composite:.2f}) "
                f"does not meet threshold ({cls.QUALIFICATION_THRESHOLD:.2f})."
            )
        else:
            status = IdeaQualificationStatus.SHORTLISTED

        return IdeaCandidate(
            idea_id=candidate_dict.get("idea_id") or f"idea_{uuid.uuid4().hex[:8]}",
            title=title,
            premise=premise,
            hook=hook,
            target_audience=target_audience,
            organizational_contribution=org_contribution_text,
            supporting_evidence=evidence,
            production_implications=prod_implications,
            trend_alignment=trend_name,
            unresolved_questions=unresolved,
            scores=scores,
            status=status,
            rejection_reason=rejection_reason,
        )

    @classmethod
    def discover_and_qualify(
        cls,
        brief: ProjectBrief,
        provisional_ideas: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[IdeaCandidate], List[IdeaCandidate]]:
        """
        Discovers and qualifies ideas.
        Returns (shortlist, rejected_list).
        """
        candidates: List[Dict[str, Any]] = []

        if provisional_ideas:
            candidates.extend(provisional_ideas)

        # If no provisional ideas provided, synthesize baseline candidates from the brief
        if not candidates:
            # Idea 1: Grounded Explainer based on core SME facts and audience problem
            sme_facts = [s.get("fact", "") for s in brief.subject_matter_notes]
            org_goal_primary = brief.organizational_goals[0] if brief.organizational_goals else "Organizational Mission"
            candidates.append({
                "idea_id": "idea_grounded_explainer",
                "title": f"The Real Mechanism: {brief.working_title}",
                "premise": f"Deconstructs how the initiative actually solves {brief.target_audience.get('problem', 'the core challenge')} using proven field evidence.",
                "hook": f"What really happens when {sme_facts[0] if sme_facts else 'you change the system'}?",
                "target_audience": brief.target_audience.get("segment", "Target Community"),
                "organizational_contribution": f"Directly advances goal: '{org_goal_primary}' by demonstrating empirical efficacy.",
                "supporting_evidence": sme_facts[:3],
                "production_implications": "1-day location shoot with SME interview, macro b-roll, on-screen data verification.",
                "trend_alignment": None,
                "unresolved_questions": ["Confirm SME availability for on-camera demonstration."],
                "org_contribution_score": 0.88,
                "audience_relevance_score": 0.85,
                "evidence_grounding_score": 0.90,
                "production_feasibility_score": 0.85,
            })

            # Idea 2: Viral Trend Trap candidate (demonstrates rejection under pressure)
            if brief.trends:
                top_trend = brief.trends[0]
                candidates.append({
                    "idea_id": "idea_trend_trap",
                    "title": f"We Tried The 24-Hour {top_trend.get('trend', 'Viral')} Challenge!",
                    "premise": f"Staff take on a high-energy trending internet challenge completely disconnected from long-term institutional goals.",
                    "hook": "Can our team survive 24 hours locked in the facility?",
                    "target_audience": "Random YouTube Browsers",
                    "organizational_contribution": "Generates casual awareness but does not communicate any organizational capability or strategic mission.",
                    "supporting_evidence": [],
                    "production_implications": "24 hours continuous filming, overnight crew overtime, chaotic editing.",
                    "trend_alignment": top_trend.get("trend") or top_trend.get("name"),
                    "unresolved_questions": ["Why would our serious donors or partners care about this?"],
                    "org_contribution_score": 0.20,
                    "audience_relevance_score": 0.35,
                    "evidence_grounding_score": 0.15,
                    "production_feasibility_score": 0.50,
                })

            # Idea 3: Stakeholder Self-Congratulatory candidate (demonstrates low audience relevance)
            candidates.append({
                "idea_id": "idea_internal_gala",
                "title": f"Annual Stakeholder Milestone Celebration & Speeches",
                "premise": "Uncut speeches from organizational leadership detailing internal committee updates.",
                "hook": "Executive Director remarks at the annual departmental summit.",
                "target_audience": "Internal Staff & Board Members",
                "organizational_contribution": "Pleases internal committee leadership.",
                "supporting_evidence": ["Internal committee minutes"],
                "production_implications": "Multi-camera auditorium recording, basic podium audio.",
                "trend_alignment": None,
                "unresolved_questions": ["Will any external viewer watch past 15 seconds?"],
                "org_contribution_score": 0.50,
                "audience_relevance_score": 0.25,
                "evidence_grounding_score": 0.70,
                "production_feasibility_score": 0.90,
            })

        evaluated = [cls.evaluate_candidate(c, brief) for c in candidates]
        shortlist = [c for c in evaluated if c.status == IdeaQualificationStatus.SHORTLISTED]
        rejected = [c for c in evaluated if c.status == IdeaQualificationStatus.REJECTED]

        return shortlist, rejected
