"""
Adversarial Research Auditor (Pillar 5)

Executes the adversarial research circuit before creative lock:
"What would make our understanding wrong?"
Probes for contradictory evidence, missing stakeholders, selection bias, and falsifications.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any
from .claims import ClaimGraph, ClaimNode, EpistemicStatus
from .topic_modeler import TopicModel


@dataclass
class AdversarialFinding:
    category: str  # CONTRADICTORY_EVIDENCE | MISSING_STAKEHOLDER | SELECTION_BIAS | OUTDATED_ASSUMPTION | ALTERNATIVE_EXPLANATION
    probe_question: str
    finding: str
    impact_on_model: str
    severity: str  # BLOCKER | MAJOR | MINOR


@dataclass
class AdversarialAuditResult:
    topic_id: str
    audit_passed: bool
    vulnerability_rating: str  # 1/10 to 10/10
    findings: List[AdversarialFinding] = field(default_factory=list)
    counter_evidence_claims: List[str] = field(default_factory=list)
    falsification_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "audit_passed": self.audit_passed,
            "vulnerability_rating": self.vulnerability_rating,
            "findings_count": len(self.findings),
            "findings": [
                {
                    "category": f.category,
                    "probe_question": f.probe_question,
                    "finding": f.finding,
                    "impact_on_model": f.impact_on_model,
                    "severity": f.severity,
                }
                for f in self.findings
            ],
            "counter_evidence_claims": self.counter_evidence_claims,
            "falsification_summary": self.falsification_summary,
        }


class AdversarialAuditor:
    """
    Simulates adversarial probing against the TopicModel and ClaimGraph.
    """

    @classmethod
    def audit_topic(
        cls,
        topic: TopicModel,
        graph: ClaimGraph,
        simulated_counter_evidence: List[Dict[str, Any]] = None,
    ) -> AdversarialAuditResult:
        findings: List[AdversarialFinding] = []
        counter_evidence_ids: List[str] = []

        # 1. Probe: Selection Bias (Did we only look at successful programs?)
        if len(topic.established_facts) > 0 and len(topic.disagreements_and_uncertainties) == 0:
            findings.append(AdversarialFinding(
                category="SELECTION_BIAS",
                probe_question="Why are there zero recorded disagreements or uncertainties in this model?",
                finding="The research exhibits confirmation bias by only logging positive outcome evidence.",
                impact_on_model="Force logging of at least one friction or barrier in the topic model.",
                severity="MAJOR",
            ))

        # 2. Probe: Missing Stakeholders (Are essential voices excluded?)
        if len(topic.stakeholders_and_perspectives) == 0:
            findings.append(AdversarialFinding(
                category="MISSING_STAKEHOLDER",
                probe_question="Why are there zero recorded stakeholders in this topic model?",
                finding="The topic model contains zero stakeholder perspectives.",
                impact_on_model="Must document primary audience and stakeholder perspectives.",
                severity="MAJOR",
            ))
        else:
            recorded_stakeholders = {s.get("name", "").lower() for s in topic.stakeholders_and_perspectives}
            for essential_group in ["struggling students", "non-cardholders", "esl families", "parents"]:
                if not any(essential_group in s for s in recorded_stakeholders):
                    findings.append(AdversarialFinding(
                        category="MISSING_STAKEHOLDER",
                        probe_question=f"Where is the voice or perspective of '{essential_group}'?",
                        finding=f"The topic model does not account for the perspective of '{essential_group}'.",
                        impact_on_model=f"Must represent '{essential_group}' before creative treatment lock.",
                        severity="MAJOR",
                    ))

        # 3. Probe: Injected counter-evidence
        if simulated_counter_evidence:
            for ce in simulated_counter_evidence:
                findings.append(AdversarialFinding(
                    category="CONTRADICTORY_EVIDENCE",
                    probe_question=ce.get("question", "What contradicts our thesis?"),
                    finding=ce.get("statement", "Contradictory evidence found."),
                    impact_on_model=ce.get("impact", "Weakens core assumption."),
                    severity=ce.get("severity", "MAJOR"),
                ))
                if "affected_claim_id" in ce:
                    graph.invalidate_claim(ce["affected_claim_id"], ce.get("statement"))
                    counter_evidence_ids.append(ce["affected_claim_id"])

        blockers = [f for f in findings if f.severity == "BLOCKER"]
        passed = len(blockers) == 0

        vulnerability = min(10, 2 + len(findings) * 2)

        return AdversarialAuditResult(
            topic_id=topic.topic_id,
            audit_passed=passed,
            vulnerability_rating=f"{vulnerability}/10",
            findings=findings,
            counter_evidence_claims=counter_evidence_ids,
            falsification_summary=(
                "Adversarial probes complete. " +
                (f"{len(blockers)} blocking contradictions found." if blockers else "No unhandled blocking contradictions. Safe for treatment generation.")
            ),
        )
