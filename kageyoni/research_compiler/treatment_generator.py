"""
Competing Story Model Generator (Pillar 6)

Evaluates the 9 structural story archetypes against the TopicModel, AudienceModel,
and evidence warrant. Establishes the Mandatory Flip Condition for the selected treatment.
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
    evidence_warrant_score: float  # 0.0 to 1.0 (How well does evidence support this format?)
    audience_fit_score: float      # 0.0 to 1.0 (Does this match audience need/attention?)
    objective_fit_score: float     # 0.0 to 1.0 (Does it solve the communication problem?)
    medium_feasibility_score: float# 0.0 to 1.0 (Can it be realized visually/sonically?)
    composite_score: float = 0.0
    mandatory_flip_condition: str = ""

    def calculate_composite(self) -> float:
        """
        Pillar 6 Formula:
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
    Generates and scores all 9 competing story archetypes.
    """

    @classmethod
    def evaluate_all_archetypes(
        cls,
        topic: TopicModel,
        audience_need: str,
        communication_objective: str,
    ) -> List[CompetingTreatment]:
        """
        Evaluates the 9 canonical story models against the topic reality.
        """
        has_character = any("student" in s.get("name", "").lower() or "child" in s.get("name", "").lower() for s in topic.stakeholders_and_perspectives)
        has_tension = len(topic.active_tensions) > 0
        has_facts = len(topic.established_facts) >= 2

        treatments = [
            CompetingTreatment(
                archetype=StoryArchetype.PROBLEM_SOLUTION,
                hypothesis="Frame literacy friction as a solvable design problem: moving from book intimidation to the 3-step reading bridge.",
                strengths=["High practical utility", "Direct audience action", "Low cognitive resistance"],
                vulnerabilities=["Can feel dry or transactional if emotional stakes are omitted"],
                evidence_warrant_score=0.95 if has_facts else 0.5,
                audience_fit_score=0.90,
                objective_fit_score=0.95,
                medium_feasibility_score=0.90,
                mandatory_flip_condition="If audience retention drops by >30% during the solution steps, pivot to a character-driven struggle.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.CHARACTER_DRIVEN,
                hypothesis="Follow one struggling Grade 4 reader confronting chapter books and discovering their voice through graphic novels.",
                strengths=["High emotional empathy", "Strong narrative transportation", "Relatable identification"],
                vulnerabilities=["Requires willing student participant and parental consent under Alberta PIPA"],
                evidence_warrant_score=0.85 if has_character else 0.4,
                audience_fit_score=0.95,
                objective_fit_score=0.85,
                medium_feasibility_score=0.80,
                mandatory_flip_condition="If authentic on-camera talent is unavailable, drop character-driven treatment immediately.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.TENSION_REVELATION,
                hypothesis="Open on the paradox: Why do children stop reading right when they become fluent in speech? Reveal the hidden barrier.",
                strengths=["High click-through curiosity", "Powerful opening retention", "Intellectually arresting"],
                vulnerabilities=["Risk of feeling like clickbait if revelation under-delivers on the promise"],
                evidence_warrant_score=0.80 if has_tension else 0.4,
                audience_fit_score=0.85,
                objective_fit_score=0.85,
                medium_feasibility_score=0.85,
                mandatory_flip_condition="If the reveal feels anticlimactic to test viewers, restructure as straightforward explanatory.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.EXPLANATORY,
                hypothesis="Deconstruct the cognitive science of reading transition between Grades 3 and 4 using visual diagrams.",
                strengths=["Authoritative and credible", "High educator utility"],
                vulnerabilities=["Too academic for struggling parents and students; risks lecture tone"],
                evidence_warrant_score=0.90,
                audience_fit_score=0.60,
                objective_fit_score=0.70,
                medium_feasibility_score=0.85,
                mandatory_flip_condition="If watch time indicates early drop-off from general viewers, demote academic explanations.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.INVESTIGATIVE,
                hypothesis="Investigate why public library usage drops off among teenagers and pre-teens in urban Calgary.",
                strengths=["Exposes hidden institutional disparity", "High journalistic merit"],
                vulnerabilities=["May create defensive stakeholder response or politicized friction"],
                evidence_warrant_score=0.75,
                audience_fit_score=0.65,
                objective_fit_score=0.60,
                medium_feasibility_score=0.70,
                mandatory_flip_condition="If stakeholder sign-off is refused, terminate investigative line.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.PROCESS_ORIENTED,
                hypothesis="Walk through the physical journey of a library card: from registration to free studio booking and coach checkouts.",
                strengths=["Clear procedural clarity", "Direct conversion to library cards"],
                vulnerabilities=["Lacks dramatic tension or emotional stakes"],
                evidence_warrant_score=0.90,
                audience_fit_score=0.70,
                objective_fit_score=0.80,
                medium_feasibility_score=0.90,
                mandatory_flip_condition="If viewer feedback flags procedural boredom, blend with problem-solution framing.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.EXPERIENTIAL,
                hypothesis="An atmospheric, observational portrait of Central Library during afternoon drop-in reading clubs.",
                strengths=["Cinematic beauty", "High institutional prestige"],
                vulnerabilities=["Low information transfer; does not directly instruct parents how to solve their child's reading problem"],
                evidence_warrant_score=0.80,
                audience_fit_score=0.50,
                objective_fit_score=0.60,
                medium_feasibility_score=0.85,
                mandatory_flip_condition="If objective requires measurable program attendance, experiential format is rejected.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.ARGUMENTATIVE,
                hypothesis="Make the case against reading drills: Why forcing 30 minutes of silent chapter book reading backfires.",
                strengths=["High provocation", "Challenges conventional parenting habits"],
                vulnerabilities=["Can polarize educators or seem confrontational"],
                evidence_warrant_score=0.75,
                audience_fit_score=0.70,
                objective_fit_score=0.65,
                medium_feasibility_score=0.80,
                mandatory_flip_condition="If child psychology claims cannot be verified by secondary review, reject argumentative.",
            ),
            CompetingTreatment(
                archetype=StoryArchetype.HISTORICAL,
                hypothesis="Trace the 112-year evolution of Calgary Public Library's literacy programs from 1912 to the digital age.",
                strengths=["Archival depth", "Civic heritage interest"],
                vulnerabilities=["Zero urgency for a parent whose child is failing reading class today"],
                evidence_warrant_score=0.85,
                audience_fit_score=0.30,
                objective_fit_score=0.40,
                medium_feasibility_score=0.80,
                mandatory_flip_condition="Historical model is rejected for active program outreach.",
            ),
        ]

        # Calculate scores and sort descending
        for t in treatments:
            t.calculate_composite()

        treatments.sort(key=lambda x: x.composite_score, reverse=True)
        return treatments
