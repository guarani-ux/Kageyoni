"""
Competing Story Model Generator (Pillar 6) - Hardened (Gate G4).

Evaluates the 9 structural story archetypes dynamically against the TopicModel, AudienceModel,
and communication objective. Explicitly labels scoring formulas as heuristics, and establishes
the Mandatory Flip Condition for each treatment candidate.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
from .topic_modeler import TopicModel


class StoryArchetype(Enum):
    EXPLANATORY = "EXPLANATORY"                  # Mechanism, clarification, conceptual model
    INVESTIGATIVE = "INVESTIGATIVE"              # Uncovering hidden reality, gap, or disparity
    CHARACTER_DRIVEN = "CHARACTER_DRIVEN"        # Personal agency, emotional obstacle, change
    PROBLEM_SOLUTION = "PROBLEM_SOLUTION"        # Explicit diagnosis, friction reduction, remedy
    HISTORICAL = "HISTORICAL"                    # Evolution over time, path dependency, legacy
    EXPERIENTIAL = "EXPERIENTIAL"                # Sensory immersion, atmospheric presence
    ARGUMENTATIVE = "ARGUMENTATIVE"              # Defending a thesis against counter-arguments
    PROCESS_ORIENTED = "PROCESS_ORIENTED"        # Step-by-step demystification of a workflow
    TENSION_REVELATION = "TENSION_REVELATION"    # Unresolved question, dramatic delay, payoff turn


@dataclass
class CompetingTreatment:
    archetype: StoryArchetype
    hypothesis: str
    strengths: List[str]
    vulnerabilities: List[str]
    evidence_warrant_score: float   # 0.0 to 1.0 (How well does evidence support this format?)
    audience_fit_score: float       # 0.0 to 1.0 (Does this match audience need/attention?)
    objective_fit_score: float      # 0.0 to 1.0 (Does it solve the communication problem?)
    medium_feasibility_score: float # 0.0 to 1.0 (Can it be realized visually/sonically?)
    composite_score: float = 0.0
    mandatory_flip_condition: str = ""
    is_heuristic: bool = True       # Explicit heuristic label (Rule: Epistemic Integrity)
    heuristic_warrant: str = "Evaluated via multi-factor heuristic assessment against topic and audience models."

    def calculate_composite(self) -> float:
        """
        Pillar 6 Heuristic Formula:
        Composite = Evidence Warrant * Audience Fit * Objective Fit * Medium Feasibility
        """
        self.composite_score = round(
            self.evidence_warrant_score *
            self.audience_fit_score *
            self.objective_fit_score *
            self.medium_feasibility_score,
            4
        )
        return self.composite_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archetype": self.archetype.value,
            "hypothesis": self.hypothesis,
            "strengths": self.strengths,
            "vulnerabilities": self.vulnerabilities,
            "is_heuristic": self.is_heuristic,
            "heuristic_warrant": self.heuristic_warrant,
            "scores": {
                "evidence_warrant": self.evidence_warrant_score,
                "audience_fit": self.audience_fit_score,
                "objective_fit": self.objective_fit_score,
                "medium_feasibility": self.medium_feasibility_score,
                "composite": self.composite_score,
            },
            "mandatory_flip_condition": self.mandatory_flip_condition,
        }


class TreatmentGenerator:
    """
    Generates and dynamically scores all 9 competing story archetypes.
    """

    @classmethod
    def evaluate_all_archetypes(
        cls,
        topic: TopicModel,
        audience_need: str,
        communication_objective: str,
    ) -> List[CompetingTreatment]:
        """
        Evaluates the 9 canonical story models dynamically against the topic reality.
        """
        title = topic.subject_title or "Subject Matter"
        state = topic.core_state_of_affairs or "Current conditions"
        
        num_facts = len(topic.established_facts)
        num_tensions = len(topic.active_tensions)
        num_stakeholders = len(topic.stakeholders_and_perspectives)
        num_causality = len(topic.chronology_and_causality)
        num_misconceptions = len(topic.misconceptions)
        num_contradictions = len(topic.contradictions)

        stakeholder_names = [s.get("name", "participant") for s in topic.stakeholders_and_perspectives]
        primary_stakeholder = stakeholder_names[0] if stakeholder_names else "impacted participant"

        # Heuristic scoring derivations
        # 1. Problem-Solution
        ps_warrant = min(1.0, 0.5 + (0.1 * min(num_facts, 3)) + (0.1 if num_misconceptions > 0 else 0.0))
        ps_hyp = f"Diagnose friction points in {title} and present a verifiable structural remedy for {primary_stakeholder}."
        ps_flip = f"If viewer engagement drops during solution steps or remedy lacks physical evidence, flip to character struggle."

        # 2. Character-Driven
        cd_warrant = min(1.0, 0.4 + (0.2 * min(num_stakeholders, 3)))
        cd_hyp = f"Follow {primary_stakeholder} directly confronting obstacles in {title} created by {state}."
        cd_flip = f"If authentic participant testimony or consent cannot be secured for {primary_stakeholder}, abandon character-driven model."

        # 3. Tension-Revelation
        tr_warrant = min(1.0, 0.4 + (0.25 * min(num_tensions + num_contradictions, 3)))
        tension_desc = topic.active_tensions[0].get("description", "apparent contradiction") if topic.active_tensions else "unresolved divergence"
        tr_hyp = f"Open on the core paradox in {title} ({tension_desc}), delaying the resolution until evidence reveals the underlying mechanism."
        tr_flip = f"If revelation under-delivers on opening curiosity or feels sensationalist, restructure as straightforward explanatory."

        # 4. Explanatory
        ex_warrant = min(1.0, 0.5 + (0.15 * min(num_facts + num_causality, 3)))
        ex_hyp = f"Deconstruct the systemic architecture, concepts, and causal dependencies governing {title}."
        ex_flip = f"If audience retention analysis flags cognitive overload or academic fatigue, blend with experiential pacing."

        # 5. Investigative
        inv_warrant = min(1.0, 0.4 + (0.2 * min(num_contradictions + num_tensions, 3)))
        inv_hyp = f"Expose the structural gap between declared institutional intent and physical outcomes in {title}."
        inv_flip = f"If primary source documentation cannot withstand adversarial scrutiny, terminate investigative line."

        # 6. Process-Oriented
        po_warrant = min(1.0, 0.4 + (0.2 * min(num_causality, 3)))
        po_hyp = f"Walk through the physical end-to-end procedural workflow required to navigate {title}."
        po_flip = f"If workflow is flagged as transactional or dry by audience panels, infuse stakeholder stakes."

        # 7. Experiential
        exp_warrant = min(1.0, 0.4 + (0.15 * min(num_stakeholders, 3)))
        exp_hyp = f"Provide an atmospheric, observational immersion into the physical environment and daily texture of {title}."
        exp_flip = f"If communication objective requires measurable conversion or explicit cognitive takeaway, reject experiential."

        # 8. Argumentative
        arg_warrant = min(1.0, 0.4 + (0.2 * min(num_misconceptions + len(topic.disagreements_and_uncertainties), 3)))
        arg_hyp = f"Defend a rigorous thesis resolving active disputes regarding {title}, systematically refuting prevalent misconceptions."
        arg_flip = f"If counter-evidence undermines core premises, pivot to open investigative inquiry."

        # 9. Historical
        hist_warrant = min(1.0, 0.4 + (0.15 * min(num_causality, 3)))
        hist_hyp = f"Trace the institutional, technological, and social lineage of {title} that produced {state} over time."
        hist_flip = f"If audience demands immediate contemporary intervention, demote historical lineage to background context."

        treatments = [
            CompetingTreatment(
                archetype=StoryArchetype.PROBLEM_SOLUTION,
                hypothesis=ps_hyp,
                strengths=["High practical utility", "Direct audience action", "Low cognitive resistance"],
                vulnerabilities=["Can feel dry or transactional if emotional stakes are omitted"],
                evidence_warrant_score=round(ps_warrant, 2),
                audience_fit_score=0.90,
                objective_fit_score=0.95,
                medium_feasibility_score=0.90,
                mandatory_flip_condition=ps_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.CHARACTER_DRIVEN,
                hypothesis=cd_hyp,
                strengths=["High emotional empathy", "Strong narrative transportation", "Relatable identification"],
                vulnerabilities=["Requires willing participant consent and authentic access"],
                evidence_warrant_score=round(cd_warrant, 2),
                audience_fit_score=0.92,
                objective_fit_score=0.85,
                medium_feasibility_score=0.80,
                mandatory_flip_condition=cd_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.TENSION_REVELATION,
                hypothesis=tr_hyp,
                strengths=["High hook retention", "Curiosity-driven engagement", "Memorable cognitive turn"],
                vulnerabilities=["Risk of anticlimax if revelation is self-evident"],
                evidence_warrant_score=round(tr_warrant, 2),
                audience_fit_score=0.88,
                objective_fit_score=0.85,
                medium_feasibility_score=0.85,
                mandatory_flip_condition=tr_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.EXPLANATORY,
                hypothesis=ex_hyp,
                strengths=["Authoritative and credible", "High educational utility"],
                vulnerabilities=["Risks passive lecture tone if stakes are unclear"],
                evidence_warrant_score=round(ex_warrant, 2),
                audience_fit_score=0.75,
                objective_fit_score=0.80,
                medium_feasibility_score=0.85,
                mandatory_flip_condition=ex_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.INVESTIGATIVE,
                hypothesis=inv_hyp,
                strengths=["Journalistic rigor", "Exposes hidden disparities"],
                vulnerabilities=["Requires high evidentiary threshold and legal review"],
                evidence_warrant_score=round(inv_warrant, 2),
                audience_fit_score=0.70,
                objective_fit_score=0.65,
                medium_feasibility_score=0.75,
                mandatory_flip_condition=inv_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.PROCESS_ORIENTED,
                hypothesis=po_hyp,
                strengths=["Procedural clarity", "Step-by-step repeatability"],
                vulnerabilities=["Lacks dramatic momentum"],
                evidence_warrant_score=round(po_warrant, 2),
                audience_fit_score=0.80,
                objective_fit_score=0.80,
                medium_feasibility_score=0.90,
                mandatory_flip_condition=po_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.EXPERIENTIAL,
                hypothesis=exp_hyp,
                strengths=["High aesthetic immersion", "Atmospheric resonance"],
                vulnerabilities=["Low information density; difficult to measure conversion"],
                evidence_warrant_score=round(exp_warrant, 2),
                audience_fit_score=0.55,
                objective_fit_score=0.60,
                medium_feasibility_score=0.85,
                mandatory_flip_condition=exp_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.ARGUMENTATIVE,
                hypothesis=arg_hyp,
                strengths=["Intellectual provocation", "Refutes persistent myths"],
                vulnerabilities=["Can alienate skeptical or polarized audiences"],
                evidence_warrant_score=round(arg_warrant, 2),
                audience_fit_score=0.70,
                objective_fit_score=0.70,
                medium_feasibility_score=0.80,
                mandatory_flip_condition=arg_flip,
            ),
            CompetingTreatment(
                archetype=StoryArchetype.HISTORICAL,
                hypothesis=hist_hyp,
                strengths=["Deep context", "Longitudinal perspective"],
                vulnerabilities=["Low immediate urgency for contemporary problems"],
                evidence_warrant_score=round(hist_warrant, 2),
                audience_fit_score=0.45,
                objective_fit_score=0.50,
                medium_feasibility_score=0.80,
                mandatory_flip_condition=hist_flip,
            ),
        ]

        # Calculate scores and sort descending
        for t in treatments:
            t.calculate_composite()

        treatments.sort(key=lambda x: x.composite_score, reverse=True)
        return treatments
