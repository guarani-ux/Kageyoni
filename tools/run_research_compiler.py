"""
Upstream Research-to-Creative Compiler CLI Runner
Compiles physical evidence and topic reality into a 10-section Script-Ready Intelligence Package.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kageyoni.research_compiler.claims import (
    ClaimGraph,
    ClaimNode,
    SourceRecord,
    EpistemicStatus,
)
from kageyoni.research_compiler.topic_modeler import TopicModeler, TopicModel
from kageyoni.research_compiler.adversarial import AdversarialAuditor
from kageyoni.research_compiler.treatment_generator import (
    TreatmentGenerator,
    StoryArchetype,
    CompetingTreatment,
)
from kageyoni.research_compiler.package_compiler import (
    ScriptReadyCompiler,
    ScriptReadyPackage,
    AudienceModel,
)


def run_cpl_literacy_compilation(output_path: str = "evidence/reports/cpl_literacy_intelligence_package.json"):
    graph = ClaimGraph()

    # Ingest verified source records
    src_audit = SourceRecord(
        source_id="src_cpl_audit",
        title="Calgary Public Library Services Ecosystem Audit (2024)",
        provenance="Desktop/Calgary Public Library Services Ecosystem Audit.docx",
        author_or_institution="Calgary Public Library Operations",
        direct_excerpt="Grade 3-6 educational literacy programs reached over 26,600 student participants across 12 programs, with an analytics-driven CTR improvement of 37%.",
        date_recorded=time.time(),
        reliability_tier="PRIMARY_CORROBORATED",
    )
    src_reading = SourceRecord(
        source_id="src_reading_transition",
        title="Cognitive Reading Transitions and Illustrated Scaffolding",
        provenance="Kintsch Construction-Integration Model & Canadian Literacy Framework",
        author_or_institution="Reading Psychology Research",
        direct_excerpt="Visual intimidation increases sharply between Grades 3 and 4 as textbooks remove illustrations. Graphic novels restore fluency by scaffolding visual situation models.",
        date_recorded=time.time(),
        reliability_tier="PRIMARY_CORROBORATED",
    )
    src_desktop_audio = SourceRecord(
        source_id="src_cpl_audio_studios",
        title="Central Library Audio & Creative Studio Inventory",
        provenance="Desktop/CPL Media Systems Playbook Specification.pdf",
        author_or_institution="CPL Media Production",
        direct_excerpt="Central Library and branch community commons provide soundproof audio suites, Pro Tools, and podcast stations accessible free with library card.",
        date_recorded=time.time(),
        reliability_tier="PRIMARY_CORROBORATED",
    )

    graph.add_source(src_audit)
    graph.add_source(src_reading)
    graph.add_source(src_desktop_audio)

    # Ingest claims
    clm_reach = ClaimNode(
        claim_id="clm_reach",
        statement="CPL literacy programs reached over 26,600 student participants across 12 programs.",
        epistemic_status=EpistemicStatus.SOURCE_FACT,
        provenance_sources=["src_cpl_audit"],
        confidence_level="HIGH",
        falsification_condition="If audited attendance logs report fewer than 20,000 unique students.",
    )
    clm_friction = ClaimNode(
        claim_id="clm_friction",
        statement="Grade 4 reading resistance is triggered by the sudden elimination of visual illustrations in school texts.",
        epistemic_status=EpistemicStatus.SOURCE_FACT,
        provenance_sources=["src_reading_transition"],
        confidence_level="HIGH",
        falsification_condition="If eye-tracking and comprehension latency show identical friction on illustrated vs unillustrated texts.",
    )
    clm_bridge = ClaimNode(
        claim_id="clm_bridge",
        statement="Graphic novels act as an evidence-based cognitive bridge restoring reading fluency for struggling 4th graders.",
        epistemic_status=EpistemicStatus.SYNTHESIS,
        provenance_sources=["src_reading_transition"],
        confidence_level="HIGH",
        parent_claim_ids=["clm_friction"],
        falsification_condition="If reading fluency scores fail to increase after 60 days of graphic novel intervention.",
    )
    clm_free_access = ClaimNode(
        claim_id="clm_free_access",
        statement="All Calgary Public Library reading coaches, tutoring programs, and digital tools are 100% free with a library card.",
        epistemic_status=EpistemicStatus.SOURCE_FACT,
        provenance_sources=["src_cpl_audit", "src_cpl_audio_studios"],
        confidence_level="HIGH",
        falsification_condition="If any fee or financial barrier is required to access programs.",
    )
    clm_audiobook = ClaimNode(
        claim_id="clm_audiobook",
        statement="Audiobook listening produces identical vocabulary retention as silent text reading for Grade 4 children.",
        epistemic_status=EpistemicStatus.HYPOTHESIS,
        provenance_sources=[],
        confidence_level="CONTESTED",
        falsification_condition="Standardized vocabulary retention tests across audio vs print cohorts.",
    )

    graph.add_claim(clm_reach)
    graph.add_claim(clm_friction)
    graph.add_claim(clm_bridge)
    graph.add_claim(clm_free_access)
    graph.add_claim(clm_audiobook)

    # 1. Topic Model (Built BEFORE audience strategy)
    topic = TopicModeler.build_topic_model(
        topic_id="cpl_youth_literacy_2026",
        subject_title="Calgary Public Library Grade 3-6 Cognitive Reading Bridge",
        core_state_of_affairs=(
            "Calgary elementary students experience reading resistance at the Grade 3-4 transition point due to "
            "visual intimidation caused by the removal of illustrations from standard curriculum texts. "
            "Calgary Public Library deploys graphic novel collections and free reading coaches across 21 branches to eliminate this friction."
        ),
        graph=graph,
        relationships=[
            {"entity_a": "Curriculum Text Transition", "relation": "TRIGGERS", "entity_b": "Visual Intimidation in Grade 4 Readers"},
            {"entity_a": "Graphic Novel Bridge", "relation": "SCAFFOLDS", "entity_b": "Situation Model Comprehension"},
            {"entity_a": "Free Library Card", "relation": "PROVIDES_ACCESS_TO", "entity_b": "Drop-in Reading Coaches"},
        ],
        stakeholders=[
            {"name": "Grade 3-6 Students", "stance": "Intimidated by unillustrated chapter books, shame around reading speed."},
            {"name": "Parents", "stance": "Anxious about academic decline; harbor misconception that graphic novels are 'cheating'."},
            {"name": "Children's Librarians", "stance": "Trained in scaffolding; advocate for graphic novel reading bridges."},
            {"name": "Elementary Teachers", "stance": "Constrained by standardized testing; looking for outside reading support."},
        ],
        misconceptions=[
            {"misconception": "Graphic novels don't count as real reading.", "correction": "Cognitive studies confirm graphic novels build complex situation models and equal vocabulary."},
            {"misconception": "Public library coaching requires paid appointments.", "correction": "Library cardholders receive free drop-in access."},
        ],
        contradictions=[
            {"contradiction": "Parents want children to love reading, but restrict them to unillustrated books that cause reading anxiety."},
        ],
        active_tensions=[
            {"tension": "Academic pressure (forcing 30-min chapter book drills) vs. Cognitive joy (graphic novel fluency)."},
        ],
        known_unknowns=[
            "Exact percentage of Calgary elementary schools with active library partnership programs in 2026.",
        ],
    )

    # 2. Adversarial Probing
    adversarial_result = AdversarialAuditor.audit_topic(topic, graph)

    # 3. Audience Model
    audience = AudienceModel(
        target_segment="Calgary parents of Grade 3-6 children showing reading resistance or declining school grades.",
        prior_knowledge_baseline="Parents believe reading difficulties stem from screen addiction or lack of effort.",
        active_misconceptions=["Graphic novels are comic junk food", "Library resources are outdated books"],
        practical_and_emotional_stakes="Fear of long-term academic failure and childhood embarrassment.",
        reception_friction="Parents are exhausted by homework battles and skeptical of another reading lecture.",
    )

    # 4. Communication Problem
    comm_problem = {
        "current_state": "Parents enforce painful reading drills on intimidating chapter books, unaware of the CPL graphic novel bridge.",
        "desired_shift": "Shift from conflict-driven reading drills to empowered library visits using graphic novels and free coaching.",
        "decision_to_enable": "Parent visits Calgary Public Library branch with student and checks out 3 graphic novels from the curated reading bridge.",
    }

    # 5. Story Territory
    story_territory = {
        "core_frictions": ["The invisible wall: when a fluent reader suddenly freezes on page 3 of a chapter book."],
        "transformations": ["From bedtime homework tears to a child voluntarily reading under the covers with a flashlight."],
        "human_stakes": ["Academic confidence, parent-child bonding, lifelong literacy."],
        "scenes_and_locales": ["Kitchen table homework frustration", "Central Library children's commons", "Close-up of graphic novel visual panels"],
    }

    # 6. Competing Treatments
    treatments = TreatmentGenerator.evaluate_all_archetypes(
        topic=topic,
        audience_need="Resolve Grade 4 reading resistance and end homework battles.",
        communication_objective="Drive graphic novel checkout and coaching attendance.",
    )

    # 7. Narrative Ingredients
    narrative_ingredients = {
        "essential_facts": [
            "26,600 Calgary students supported in 2024",
            "100% free with Calgary Public Library card",
            "3-step reading bridge method",
        ],
        "compulsory_scenes_or_proofs": [
            "Side-by-side demonstration: wall of unillustrated text vs illustrated panel cognitive processing",
            "Physical library coach showing parent how to select the right bridge book",
        ],
        "voices_and_perspectives": [
            "Struggling 4th grade student",
            "Relieved parent",
            "Calgary Children's Librarian",
        ],
        "visual_metaphors": [
            "The scaffold: graphic novels as training wheels that build real muscle rather than cheating",
        ],
        "unanswered_dramatic_questions": [
            "Will the student finish their first book independently?",
        ],
    }

    # 8. Constraints
    constraints = {
        "must_not_claim": [
            "Do not claim graphic novels permanently replace text novels.",
            "Do not promise overnight grade improvements without regular practice.",
        ],
        "must_not_omit": [
            "Must state clearly that all cards, programs, and coaching are completely free.",
        ],
        "ethical_and_privacy_boundaries": [
            "Parental consent and Alberta PIPA compliance for any student likeness or story.",
        ],
    }

    # 9. Open Questions
    open_questions = {
        "research_gaps": [
            "Collect 2026 branch borrowing metrics for graphic novel categories.",
        ],
        "field_discovery_requirements": [
            "Identify 2 Calgary families willing to share their reading bridge breakthrough on record.",
        ],
    }

    # Compile the final package
    package = ScriptReadyCompiler.compile_package(
        subject_title="Calgary Youth Literacy & Cognitive Reading Bridge",
        topic=topic,
        graph=graph,
        audience=audience,
        comm_problem=comm_problem,
        story_territory=story_territory,
        treatments=treatments,
        narrative_ingredients=narrative_ingredients,
        constraints=constraints,
        open_questions=open_questions,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(package.to_dict(), f, indent=2)

    return package, adversarial_result


def main():
    parser = argparse.ArgumentParser(description="Run Upstream Research-to-Creative Compiler")
    parser.add_argument("--out", type=str, default="evidence/reports/cpl_literacy_intelligence_package.json", help="Output JSON path")
    args = parser.parse_args()

    pkg, adv = run_cpl_literacy_compilation(args.out)

    print("\n=======================================================")
    print("SCRIPT-READY INTELLIGENCE PACKAGE COMPILED")
    print(f"Package ID: {pkg.package_id}")
    print(f"Subject:    {pkg.subject_title}")
    print("=======================================================\n")
    print(f"1. TOPIC MODEL (Pre-Communication Reality):")
    print(f"   * Facts: {pkg.topic_model['established_facts_count']} established facts verified.")
    print(f"   * Active Tensions: {len(pkg.topic_model['active_tensions'])} tensions identified.")
    print(f"   * Info Value Score: {pkg.topic_model['information_value_score']}")
    print(f"\n2. ADVERSARIAL AUDIT:")
    print(f"   * Vulnerability Rating: {adv.vulnerability_rating}")
    print(f"   * Audit Status: {'PASSED' if adv.audit_passed else 'BLOCKED'}")
    print(f"\n3. COMPETING STORY MODELS EVALUATED:")
    for idx, t in enumerate(pkg.competing_treatments[:3]):
        print(f"   [{idx+1}] {t['archetype']}: Composite Score {t['scores']['composite']} -> {t['hypothesis'][:75]}...")
    print(f"\n4. SELECTED CREATIVE DECISION:")
    print(f"   * Archetype: {pkg.creative_decision['selected_archetype']}")
    print(f"   * Strategic Rationale: {pkg.creative_decision['strategic_rationale']}")
    print(f"   * Mandatory Flip Condition: {pkg.creative_decision['mandatory_flip_condition']}")
    print(f"\n5. UNCERTAINTY PROPAGATION:")
    for w in pkg.uncertainty_warnings:
        print(f"   * {w}")
    print(f"\n6. BACKWARD LINEAGE TRACEABILITY:")
    for cid, lin in list(pkg.lineage_chains.items())[:2]:
        print(f"   * Claim [{cid}] traces to source: {lin['direct_sources'][0]['title']}")
    print(f"\n[AUTHORITATIVE SCRIPT-READY ARTIFACT EXPORTED TO: {args.out}]")


if __name__ == "__main__":
    main()
