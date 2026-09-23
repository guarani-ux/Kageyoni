"""
Topic Modeler (Pillars 3 & 7)

Constructs an objective topic model BEFORE audience strategy or creative framing is attempted.
Enforces information-value prioritization and stopping conditions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .claims import ClaimGraph, ClaimNode, EpistemicStatus


@dataclass
class TopicModel:
    topic_id: str
    subject_title: str
    core_state_of_affairs: str
    established_facts: List[Dict[str, Any]] = field(default_factory=list)
    concepts_and_relationships: List[Dict[str, Any]] = field(default_factory=list)
    chronology_and_causality: List[Dict[str, Any]] = field(default_factory=list)
    stakeholders_and_perspectives: List[Dict[str, Any]] = field(default_factory=list)
    disagreements_and_uncertainties: List[Dict[str, Any]] = field(default_factory=list)
    misconceptions: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    consequences: List[Dict[str, Any]] = field(default_factory=list)
    active_tensions: List[Dict[str, Any]] = field(default_factory=list)
    known_unknowns: List[str] = field(default_factory=list)
    information_value_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "subject_title": self.subject_title,
            "core_state_of_affairs": self.core_state_of_affairs,
            "established_facts_count": len(self.established_facts),
            "established_facts": self.established_facts,
            "concepts_and_relationships": self.concepts_and_relationships,
            "chronology_and_causality": self.chronology_and_causality,
            "stakeholders_and_perspectives": self.stakeholders_and_perspectives,
            "disagreements_and_uncertainties": self.disagreements_and_uncertainties,
            "misconceptions": self.misconceptions,
            "contradictions": self.contradictions,
            "consequences": self.consequences,
            "active_tensions": self.active_tensions,
            "known_unknowns": self.known_unknowns,
            "information_value_score": round(self.information_value_score, 3),
        }


class TopicModeler:
    """
    Builds the TopicModel from verified claim graphs without audience distortion.
    """

    @staticmethod
    def calculate_information_value(
        decision_relevance: float,    # 0.0 to 1.0 (will this alter the downstream choice?)
        evidentiary_confidence: float,# 0.0 to 1.0 (warrant and corroboration)
        audience_relevance: float,    # 0.0 to 1.0 (does this affect audience life/friction?)
        narrative_potential: float,   # 0.0 to 1.0 (presence of tension, stakes, or turn)
        novelty: float,               # 0.0 to 1.0 (is this surprising or poorly understood?)
    ) -> float:
        """
        Pillar 7 Formula:
        InfoValue = Decision Relevance * Confidence * Audience Relevance * Narrative Potential * Novelty
        Bounded between 0.0 and 1.0.
        """
        return float(
            max(0.0, min(1.0, decision_relevance)) *
            max(0.0, min(1.0, evidentiary_confidence)) *
            max(0.0, min(1.0, audience_relevance)) *
            max(0.0, min(1.0, narrative_potential)) *
            max(0.0, min(1.0, novelty))
        )

    @classmethod
    def evaluate_stopping_condition(
        cls,
        current_fact_count: int,
        unresolved_contradictions_count: int,
        marginal_information_gain: float,
        epsilon: float = 0.05,
    ) -> bool:
        """
        Stopping Condition:
        Returns True when additional research will only make the pile taller
        without altering the model structure.
        """
        # Cannot stop if we have zero facts or unresolved critical contradictions
        if current_fact_count == 0:
            return False
        if unresolved_contradictions_count > 0:
            return False
        # Stop if marginal information gain is below threshold epsilon
        return marginal_information_gain < epsilon

    @classmethod
    def build_topic_model(
        cls,
        topic_id: str,
        subject_title: str,
        core_state_of_affairs: str,
        graph: ClaimGraph,
        relationships: Optional[List[Dict[str, Any]]] = None,
        stakeholders: Optional[List[Dict[str, Any]]] = None,
        misconceptions: Optional[List[Dict[str, Any]]] = None,
        contradictions: Optional[List[Dict[str, Any]]] = None,
        active_tensions: Optional[List[Dict[str, Any]]] = None,
        known_unknowns: Optional[List[str]] = None,
    ) -> TopicModel:
        """
        Compiles the TopicModel ensuring all established facts trace back to ClaimGraph.
        """
        if not core_state_of_affairs or len(core_state_of_affairs.strip()) < 15:
            raise ValueError("TOPIC_DEFICIT: Topic model requires non-empty, detailed core_state_of_affairs.")

        facts = [
            {
                "claim_id": c.claim_id,
                "statement": c.statement,
                "sources": c.provenance_sources,
                "confidence": c.confidence_level,
            }
            for c in graph.get_established_facts()
        ]

        uncertainties = [
            {
                "claim_id": c.claim_id,
                "statement": c.statement,
                "epistemic_status": c.epistemic_status.value,
                "confidence": c.confidence_level,
                "falsification_condition": c.falsification_condition,
            }
            for c in graph.get_uncertain_claims()
        ]

        # Base score on factual density and structural friction
        info_score = cls.calculate_information_value(
            decision_relevance=0.9 if len(facts) >= 2 else 0.4,
            evidentiary_confidence=0.85 if len(facts) >= 2 else 0.5,
            audience_relevance=0.8,
            narrative_potential=0.85 if (active_tensions and len(active_tensions) > 0) else 0.3,
            novelty=0.75,
        )

        return TopicModel(
            topic_id=topic_id,
            subject_title=subject_title,
            core_state_of_affairs=core_state_of_affairs,
            established_facts=facts,
            concepts_and_relationships=relationships or [],
            chronology_and_causality=[],
            stakeholders_and_perspectives=stakeholders or [],
            disagreements_and_uncertainties=uncertainties,
            misconceptions=misconceptions or [],
            contradictions=contradictions or [],
            consequences=[],
            active_tensions=active_tensions or [],
            known_unknowns=known_unknowns or [],
            information_value_score=info_score,
        )
