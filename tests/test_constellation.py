"""
Comprehensive qualification tests for Kageyōni Constellation Substrate:
Summon, Alchemy (Transmute), Joy Boy Reground, Constellation-Chef-Beast lifecycle,
and the 30 Coordinates & 5 Koans.
"""

import json
import pytest
import time
from kageyoni.constellation import (
    Beast,
    CandidateTechnique,
    ConstellationElement,
    ConstellationField,
    DerivationStatus,
    EpistemicStatus,
    SummonScarError,
    TransmuteScarError,
    reground,
    summon,
    transmute,
)
from kageyoni.vantage.engine import VantageStudio
from kageyoni.vantage.models import ProjectBrief


class TestConstellationTechniques:

    def test_summon_consequential_co_presence(self):
        """
        Technique I: Summon changes what becomes consequentially co-present.
        Binds previously separated elements into mutual visibility.
        """
        field = ConstellationField("global_pantry")
        elem1 = ConstellationElement(
            id="org_brief_01",
            element_type="artifact",
            payload={"org": "GIHA", "goal": "Demonstrate off-grid uptime"},
            epistemic_status=EpistemicStatus.OBSERVED,
        )
        elem2 = ConstellationElement(
            id="tool_vantage_compiler",
            element_type="tool",
            payload={"version": "1.0.0", "capabilities": ["proposal", "treatment"]},
            epistemic_status=EpistemicStatus.OBSERVED,
        )
        field.add_element(elem1)
        field.add_element(elem2)

        # Summon into a focused sub-field
        co_present_field = summon(
            field,
            target_ids=["org_brief_01", "tool_vantage_compiler", "missing_actor_01"],
            intent="strategic_video_formulation",
        )

        # Verify co-presence
        assert "org_brief_01" in co_present_field.elements
        assert "tool_vantage_compiler" in co_present_field.elements
        # Missing elements are marked UNKNOWN rather than hallucinated
        assert co_present_field.elements["missing_actor_01"].epistemic_status == EpistemicStatus.UNKNOWN

        # Verify candidate relation established
        relations = co_present_field.relations
        assert len(relations) >= 1
        assert relations[0]["status"] == EpistemicStatus.CANDIDATE_RELATION.value
        assert relations[0]["proven_lineage"] is False

    def test_summon_scar_observed_relation_not_proven_lineage(self):
        """
        Summon Scar: Observed relation != proven lineage.
        Attempting to claim proven lineage on an unverified co-presence must fail closed.
        """
        field = ConstellationField("test_field")
        field.add_element(ConstellationElement(id="a", element_type="artifact", payload={}))
        field.add_element(ConstellationElement(id="b", element_type="artifact", payload={}))

        with pytest.raises(SummonScarError):
            field.add_relation(
                source_id="a",
                target_id="b",
                relation_type="derives_from",
                status=EpistemicStatus.CANDIDATE_RELATION,
                proven_lineage=True,  # INVARIANT VIOLATION: Cannot claim proven lineage without verified observation
            )

    def test_transmute_grounded_derivation(self):
        """
        Alchemy: Transmute creates a grounded new form from co-present elements.
        Enforces that CREATIVE_PROPOSAL cannot claim to be SOURCE_FACT.
        """
        source = ConstellationElement(
            id="org_fact_diesel_breakdown",
            element_type="evidence",
            payload={"fact": "Frequent diesel pump breakdowns leave clinics without running water"},
            epistemic_status=EpistemicStatus.OBSERVED,
            derivation_status=DerivationStatus.SOURCE_FACT,
        )

        def derive_video_opportunity(elements):
            return {
                "core_conflict": elements[0].payload["fact"],
                "video_format": "Demonstration / Mechanical Breakdown",
                "target_duration_sec": 480,
            }

        # Successful transmutation into a CREATIVE_PROPOSAL
        derived_element = transmute(
            source_elements=[source],
            target_form="video_opportunity",
            derivation_fn=derive_video_opportunity,
            declared_status=DerivationStatus.CREATIVE_PROPOSAL,
        )

        assert derived_element.element_type == "video_opportunity"
        assert derived_element.derivation_status == DerivationStatus.CREATIVE_PROPOSAL
        assert derived_element.payload["video_format"] == "Demonstration / Mechanical Breakdown"
        assert "org_fact_diesel_breakdown" in derived_element.provenance

    def test_transmute_scar_generated_possibility_not_established_reality(self):
        """
        Transmute Scar: Generated possibility != established reality.
        A derived element cannot falsely declare itself as a SOURCE_FACT or unearned AUTHORIZED.
        """
        source = ConstellationElement(
            id="fact_01",
            element_type="evidence",
            payload={"data": "test"},
            derivation_status=DerivationStatus.SOURCE_FACT,
        )

        # Violation 1: Claiming derivation is a SOURCE_FACT
        with pytest.raises(TransmuteScarError, match="Transmute cannot emit a SOURCE_FACT"):
            transmute(
                source_elements=[source],
                target_form="claim",
                derivation_fn=lambda els: {"falsified": True},
                declared_status=DerivationStatus.SOURCE_FACT,
            )

        # Violation 2: Claiming AUTHORIZED without an authorizer
        with pytest.raises(TransmuteScarError, match="without an explicit sovereign authorizer"):
            transmute(
                source_elements=[source],
                target_form="claim",
                derivation_fn=lambda els: {"approved": True},
                declared_status=DerivationStatus.AUTHORIZED,
                authorizer=None,
            )

    def test_reground_frame_release_and_scar_preservation(self):
        """
        Joy Boy Reground:
        Releases accumulated path, framing, and representation privilege
        while strictly preserving objective, scars, receipts, and active capabilities.
        """
        prior_state = {
            "objective": "Build high-integrity solar water video dossier",
            "narrative_fluff": "We are entering a glorious new epoch...",
            "path_traversed": ["step1", "step2", "step3_redundant"],
            "active_capabilities": ["proposal_compilation", "gate_validation"],
            "unresolved_residue": ["Unclear clinic electrical grounding specs"],
        }
        active_scars = [
            {"scar_id": "scar_01", "rule": "Never film without location permit"},
            {"scar_id": "scar_02", "rule": "Observed relation != proven lineage"},
        ]
        receipts = [
            {"tx_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        ]

        regrounded = reground(
            current_state=prior_state,
            preserved_invariants=["3_tier_matrix", "sufficiency_law"],
            active_scars=active_scars,
            receipts=receipts,
        )

        # Narrative fluff and path history are stripped
        assert "narrative_fluff" not in regrounded
        assert "path_traversed" not in regrounded
        # Scars, invariants, and objective are strictly preserved
        assert len(regrounded["preserved_scars"]) == 2
        assert len(regrounded["immutable_receipts"]) == 1
        assert regrounded["objective"] == prior_state["objective"]
        assert regrounded["framing_status"] == "CLEAN_SLATE_RECONSTRUCTED"

    def test_constellation_chef_beast_lifecycle(self):
        """
        Constellation / Chef / Beast:
        Beast is an ephemeral configuration that executes bounded actions within ActionHorizon,
        then dissolves cleanly upon completion.
        """
        field = ConstellationField("pantry")
        field.add_element(ConstellationElement(id="tool_run", element_type="tool", payload={}))

        action_horizon = {"compile_dossier", "run_gate_check"}

        # Instantiate Beast context
        with Beast("video_production_beast", field, action_horizon) as beast:
            assert beast.is_active is True
            # Allowed action succeeds
            receipt = beast.act("compile_dossier", {"project_id": "proj_01"})
            assert receipt["status"] == "COMPLETED"

            # Action outside ActionHorizon fails closed and forges a scar
            with pytest.raises(PermissionError, match="outside the Beast's ActionHorizon"):
                beast.act("unauthorized_cloud_deploy", {"target": "aws"})

        # Upon exit, Beast dissolves
        assert beast.is_active is False
        assert len(beast.execution_log) == 1
        assert len(beast.scars_forged) == 1
        assert beast.scars_forged[0]["invariant_violated"] == "ACTION_HORIZON_EXCEEDED"

    def test_ten_qualification_criteria_enforcement(self):
        """
        Verifies that candidate techniques conform to the 10 invariant qualification criteria
        and require multi-case trials before becoming qualified.
        """
        technique = CandidateTechnique(
            name="strategic_concept_transmutation",
            object_type="organizational_brief -> video_proposal",
            input_state="ProjectBrief with target_audience and organizational_goals",
            operation="Synthesize mechanical demonstration concept matching stakeholder constraints",
            output_state="StrategicProposal with explicit hypothesis angles",
            conservation="Source facts and constraints preserved invariant",
            authority="Proposal creation is Tier 0; production authorization requires Tier 1",
            failure_signature="Hallucinating budget or permits not in brief",
            null_case="Emit NULL_DELTA when brief lacks verifiable audience friction",
            evidence="8/8 Vantage pressure scenario test passes",
            carrier="kageyoni/vantage/proposal.py",
        )

        assert technique.is_qualified is False

        # Attempting qualification with only 1 disposition class fails
        technique.qualify(["PASS", "PASS"])
        assert technique.is_qualified is False

        # Qualification succeeds with at least 2 distinct disposition classes (e.g. PASS and REJECT_INVALID)
        success = technique.qualify(["PASS", "REJECT_INVALID", "PASS"])
        assert success is True
        assert technique.is_qualified is True

    def test_elc_arc_haiku_23_fail_closed_call_sheet(self):
            """
            Tests Haiku 23 ("The call sheet is clean. No one has reserved the room. The crew waits outside.")
            In VantageStudio, Gate 3 (pre-production) fails closed when permits or releases are missing.
            """
            brief_data = {
                "project_id": "p_elc_23",
                "working_title": "Off-Grid Solar Water Transformation",
                "organization": "GIHA",
                "decision_owner": "Elena Vance",
                "approval_authority": "Dr. Aris Thorne",
                "target_audience": {
                    "segment": "Municipal Water Authorities",
                    "problem": "Frequent diesel pump breakdowns",
                },
                "organizational_goals": ["Demonstrate 98% uptime"],
                "campaign_priorities": ["Winter Resilience 2026"],
                "subject_matter_notes": [{"fact": "Variable frequency drive matches pump curve dynamically"}],
                "available_resources": {
                    "budget_tier": "MEDIUM",
                    "location_name": "Calgary Demo Facility",
                    "location_address": "8800 Energy Way, Calgary AB",
                },
            }
            studio = VantageStudio(db_path=":memory:")
            brief, graph = studio.create_project(brief_data)
            shortlist, _ = studio.discover_and_qualify_ideas(brief.project_id)
            proposal = studio.build_proposal_from_idea(brief.project_id, shortlist[0].idea_id)
            studio.approve_proposal(brief.project_id, proposal.proposal_id, "Elena Vance")
    
            # Generate production plan without confirming permits / talent releases
            plan = studio.create_production_plan(brief.project_id, proposal.proposal_id)
    
            # Haiku 23 Verification: Gate 3 must be BLOCKED because talent release and permit are missing
            assert plan.status.value == "BLOCKED"
            gate_3 = plan.gate_results.get("gate_3_shoot_readiness", {})
            assert gate_3.get("passed") is False
            assert len(plan.call_sheet.missing_prerequisites) >= 2
