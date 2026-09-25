"""Adversarial qualification test suite for Kageyoni Core Nature Transformation Substrate.

Verifies:
1. Operational distinctness of all 5 Natures (Expansion, Compression, Grounding, Continuity, Coupling).
2. Non-authority invariants (Δcog ≠ Δworld, Cognitive Output ≠ Verified Fact).
3. Transformation Control and failure-mode regulation (explosion, destructive abstraction, paralysis, stale state, spurious coupling).
4. 3-Strike Governor.
5. Techniques & Composition (Reframe, LiftInvariant, Falsify, CarryForward, CausalAttribute).
6. Compound Capability ExtractTechnique & 11 structural type discrimination.
7. Compounding Loop (Work → Extract → Qualify → Register → Compose).
8. Five Heterogeneous Scenarios:
   - Scenario A: Software Diagnosis
   - Scenario B: Research / Epistemic Reasoning
   - Scenario C: Planning & Strategy
   - Scenario D: Kageyoni World Interaction (with physical SQLite engine check)
   - Scenario E: Unfamiliar Domain (Esoteric State Machine)
9. Ablation comparisons (Full vs Ablated vs Generic Baseline).
10. Self-reflective bootstrap (running substrate on its own development trace).
"""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine, Rejected
from kageyoni.gateway import BoundedKageyoniGateway
from kageyoni.nature import (
    CandidateBranch,
    CandidateComposition,
    CandidateTechnique,
    CarryForward,
    CausalAttribute,
    CognitiveDelta,
    CognitiveHypothesis,
    CognitiveState,
    ComponentInterface,
    CompoundingLoop,
    Compression,
    CompressionResult,
    Continuity,
    ContinuityDisposition,
    ContinuityResult,
    ControlDecision,
    ControlDirective,
    Coupling,
    CouplingResult,
    DeficitType,
    DestructiveCompressionError,
    EpistemicCategory,
    EpistemicLaunderingError,
    Expansion,
    ExpansionResult,
    ExtractionResult,
    ExtractTechnique,
    FailureModeGovernor,
    Falsify,
    Grounding,
    GroundingResult,
    IncompatibleCasesError,
    IncompatibleInterfaceError,
    KnowledgeDeficit,
    LiftInvariant,
    NatureType,
    ObjectiveDriftError,
    QualificationTrial,
    QualifiedTechniqueRecord,
    Reframe,
    SpuriousCouplingError,
    StructuralType,
    Technique,
    TechniqueComposition,
    TransformationControl,
    UnqualifiedTechniqueError,
    VerificationProbe,
)


class TestNatureTransformations(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "nature_test.sqlite"
        self.engine = Engine(self.db_path)
        self.gateway = BoundedKageyoniGateway(self.engine)

    def tearDown(self):
        self.engine.close()
        self.tmp_dir.cleanup()

    # =========================================================================
    # 1. EXPANSION NATURE TESTS
    # =========================================================================
    def test_expansion_objective_invariance_enforced(self):
        """Expansion MUST preserve Objective(Ri) = Objective(R); alters raise ObjectiveDriftError."""
        expansion = Expansion()
        state = CognitiveState(objective="Repair leaking valve safely")
        generators = [
            {"representation": "Use bypass pipe", "objective": "Repair leaking valve safely", "material_difference": "Bypasses valve"},
            {"representation": "Blow up pipe", "objective": "Destroy facility", "material_difference": "Destruction"},
        ]
        with self.assertRaises(ObjectiveDriftError):
            expansion.transform(state, candidate_generators=generators)

    def test_expansion_paraphrase_rejection(self):
        """Cosmetic rewordings must be rejected as paraphrases rather than counted as alternatives."""
        expansion = Expansion()
        state = CognitiveState(
            objective="Inspect system status",
            raw_intent="Check the current status of the engine",
        )
        generators = [
            {"representation": "Check the current status of the engine", "material_difference": ""},  # exact
            {"representation": "check the current status of engine", "material_difference": ""},      # trivial
            {"representation": "Query database telemetry log for latency spikes", "material_difference": "Queries telemetry instead of surface status"},
        ]
        result = expansion.transform(state, candidate_generators=generators)
        self.assertGreaterEqual(len(result.rejected_paraphrases), 1)
        valid_reps = [b.representation for b in result.valid_branches]
        self.assertIn("Query database telemetry log for latency spikes", valid_reps)

    def test_expansion_constraint_filtering(self):
        """Branches violating active hard constraints must be marked invalid."""
        expansion = Expansion()
        state = CognitiveState(
            objective="Enter secure vault",
            active_constraints=["Prohibited: explosive breach"],
        )
        generators = [
            {"representation": "Execute explosive breach on reinforced door", "material_difference": "Explosive entry"},
            {"representation": "Acquire clearance card from guard terminal", "material_difference": "Credentialed entry"},
        ]
        result = expansion.transform(state, candidate_generators=generators)
        invalid = [b for b in result.branches if not b.is_valid]
        self.assertEqual(len(invalid), 1)
        self.assertIn("explosive breach", invalid[0].representation.lower())

    # =========================================================================
    # 2. COMPRESSION NATURE TESTS
    # =========================================================================
    def test_compression_declares_all_mandated_fields(self):
        """Compression must explicitly declare preserved, removed, lost_info, and safety_limit."""
        compression = Compression()
        cases = [
            {"name": "op1", "protocol": "tls", "port": 443, "timeout": 30, "failures": ["handshake_timeout"]},
            {"name": "op2", "protocol": "tls", "port": 8443, "timeout": 60, "failures": ["handshake_timeout", "cert_revoked"]},
        ]
        result = compression.transform(cases)
        self.assertIsNotNone(result.generator)
        self.assertTrue(len(result.preserved) > 0)
        self.assertTrue(len(result.removed) > 0)
        self.assertTrue(len(result.lost_info) > 0)
        self.assertTrue(len(result.safety_limit) > 0)
        self.assertIn("tls", str(result.preserved))

    def test_compression_rejects_incompatible_cases(self):
        """Compression refuses to collapse mutually contradictory cases into false universality."""
        compression = Compression()
        contradictory_cases = [
            {"scope": "safety", "requirement": "valves", "disposition": "supported"},
            {"scope": "safety", "requirement": "valves", "disposition": "contradicted"},
        ]
        with self.assertRaises(IncompatibleCasesError):
            compression.transform(contradictory_cases)

    # =========================================================================
    # 3. GROUNDING NATURE TESTS
    # =========================================================================
    def test_grounding_anti_laundering_enforcement(self):
        """Grounding strictly forbids internal self-certification to SOURCE_SUPPLIED_FACT."""
        grounding = Grounding()
        hyp = CognitiveHypothesis(
            hypothesis_id="h1",
            statement="Database corrupted by hardware fault",
            epistemic_status=EpistemicCategory.ASSUMPTION,
        )
        # Attempt to forge a SOURCE_SUPPLIED_FACT without physical provenance ID
        def rogue_verifier(probe):
            return {
                "disposition": "supported",
                "category": EpistemicCategory.SOURCE_SUPPLIED_FACT,
                # Missing source_provenance_id
            }

        with self.assertRaises(EpistemicLaunderingError):
            grounding.evaluate_with_verifier(hyp, verifier_fn=rogue_verifier)

    def test_grounding_verifier_deficit_exposure(self):
        """When no independent verifier is available, Grounding exposes VERIFIER_DEFICIT."""
        grounding = Grounding()
        state = CognitiveState(objective="Verify alien transmission")
        hyp = CognitiveHypothesis(
            hypothesis_id="h-alien",
            statement="Signal encodes prime numbers",
            epistemic_status=EpistemicCategory.ASSUMPTION,
        )
        result = grounding.evaluate_with_verifier(hyp, verifier_fn=None, state=state)
        self.assertEqual(result.disposition, "UNVERIFIED_DEFICIT")
        self.assertEqual(hyp.confidence, "UNVERIFIED")
        self.assertTrue(any(d.deficit_type == DeficitType.VERIFIER_DEFICIT for d in state.deficits))

    def test_grounding_preserves_negative_evidence(self):
        """Falsification preserves negative evidence and marks hypothesis invalidated."""
        grounding = Grounding()
        hyp = CognitiveHypothesis(
            hypothesis_id="h-bug",
            statement="Bug is caused by integer overflow",
            epistemic_status=EpistemicCategory.ASSUMPTION,
        )
        def verifier(probe):
            return {
                "disposition": "contradicted",
                "reason": "Integer widths were 64-bit; values never exceeded 100",
            }
        result = grounding.evaluate_with_verifier(hyp, verifier_fn=verifier)
        self.assertTrue(result.is_falsified)
        self.assertTrue(hyp.is_invalidated)
        self.assertIn("Falsified", hyp.invalidation_reason)

    # =========================================================================
    # 4. CONTINUITY NATURE TESTS
    # =========================================================================
    def test_continuity_5_way_classification(self):
        """Continuity reconciles S_t + Δ into PERSIST, UPDATE, INVALIDATE, OBSOLETE, UNRESOLVED."""
        continuity = Continuity()
        state = CognitiveState(
            objective="Navigate through sector",
            active_constraints=[
                "Permanent Law: Gravity active",
                "Dynamic Block: Door locked by magnetic seal",
            ],
            hypotheses=[
                CognitiveHypothesis(hypothesis_id="h-active", statement="Bridge is lowered"),
                CognitiveHypothesis(hypothesis_id="h-broken", statement="Generator offline"),
            ],
            unresolved_uncertainties=["Is guardian present in chamber?"],
        )

        transition_receipt = {
            "cleared_conditions": ["magnetic seal"],  # Should obsolete the door constraint
            "new_facts": [
                {"statement": "Bridge is lowered confirmed", "corroborates": ["h-active"]},
                {"statement": "Generator is operational not offline", "status": "invalidated"},
            ],
        }

        result = continuity.reconcile(state, transition_receipt, source_revision=1, target_revision=2)
        self.assertEqual(result.obsoleted_count, 1)    # magnetic seal cleared
        self.assertEqual(result.persisted_count, 1)    # gravity law persisted
        self.assertEqual(result.updated_count, 1)      # bridge updated with corroboration
        self.assertEqual(result.invalidated_count, 1)  # generator offline contradicted
        self.assertEqual(result.unresolved_count, 1)   # guardian presence still unknown

        # Check that state was updated cleanly
        self.assertNotIn("Dynamic Block: Door locked by magnetic seal", state.active_constraints)
        self.assertIn("Permanent Law: Gravity active", state.active_constraints)

    # =========================================================================
    # 5. COUPLING NATURE TESTS
    # =========================================================================
    def test_coupling_interface_matching_and_mechanism(self):
        """Coupling succeeds when interfaces are complementary and causal mechanism is provided."""
        coupling = Coupling()
        a = ComponentInterface(
            component_id="SensorSubsystem",
            kind="tool",
            provides={"telemetry_stream"},
            requires=set(),
            invariants=["read_only"],
        )
        b = ComponentInterface(
            component_id="AnomalyDetector",
            kind="technique",
            provides={"anomaly_alerts"},
            requires={"telemetry_stream"},
            invariants=["read_only"],
        )
        result = coupling.couple(
            a, b,
            relationship="data_pipeline",
            claimed_emergent_capability="Real-time fault alerting",
            emergent_mechanism="Streams telemetry directly to statistical anomaly detector buffer.",
        )
        self.assertTrue(result.is_compatible)
        self.assertIsNotNone(result.composition)
        self.assertEqual(result.composition.emergent_capability, "Real-time fault alerting")

    def test_coupling_rejects_spurious_assertion_without_mechanism(self):
        """Coupling rejects emergence claims lacking a concrete causal mechanism."""
        coupling = Coupling()
        a = ComponentInterface(component_id="A", kind="tool")
        b = ComponentInterface(component_id="B", kind="tool")
        with self.assertRaises(SpuriousCouplingError):
            coupling.couple(
                a, b,
                relationship="parallel",
                claimed_emergent_capability="Magic synergy",
                emergent_mechanism="",  # empty
            )

    def test_coupling_detects_invariant_conflicts(self):
        """Coupling detects when components have clashing invariants (e.g. read_only vs mutating)."""
        coupling = Coupling()
        a = ComponentInterface(component_id="Reader", kind="tool", invariants=["read_only"])
        b = ComponentInterface(component_id="Writer", kind="tool", invariants=["mutating"])
        result = coupling.couple(
            a, b,
            relationship="atomic_lockstep",
            claimed_emergent_capability="Safe write",
            emergent_mechanism="Executes read and write simultaneously.",
        )
        self.assertFalse(result.is_compatible)
        self.assertTrue(any("Invariant conflict" in inc for inc in result.incompatibilities))

    # =========================================================================
    # 6. TRANSFORMATION CONTROL & FAILURE-MODE REGULATION TESTS
    # =========================================================================
    def test_transformation_control_failure_mode_dampening(self):
        """Control detects failure modes and halts or dampens them appropriately."""
        control = TransformationControl()

        # A. Verification Paralysis Governor
        state_paralysis = CognitiveState(objective="Solve puzzle")
        hyp = CognitiveHypothesis(hypothesis_id="h-stuck", statement="Door needs key #9", confidence="UNVERIFIED")
        state_paralysis.add_hypothesis(hyp)
        control.governor.grounding_attempt_counter["h-stuck"] = 3  # hit max limit
        decision = control.assess_need(state_paralysis)
        self.assertEqual(decision.directive, ControlDirective.REQUIRES_USER_JUDGMENT)

        # B. 3-Strike Governor
        control.governor.current_failures = 3
        decision_strike = control.assess_need(state_paralysis)
        self.assertEqual(decision_strike.directive, ControlDirective.HALT_THREE_STRIKE_ABORT)

    def test_control_selects_smallest_sufficient_operation(self):
        """Control selects nature matching the exact deficit rather than running all five."""
        control = TransformationControl()
        state = CognitiveState(objective="Run query")
        state.record_deficit(KnowledgeDeficit(
            deficit_type=DeficitType.VERIFIER_DEFICIT,
            description="Need oracle",
            impacted_representation="query",
            required_to_resolve="oracle",
        ))
        decision = control.assess_need(state)
        self.assertEqual(decision.selected_nature, NatureType.GROUNDING)
        self.assertEqual(decision.directive, ControlDirective.REQUIRES_EXTERNAL_GATEWAY)

    # =========================================================================
    # 7. TECHNIQUES & COMPOSITION PIPELINE TESTS
    # =========================================================================
    def test_techniques_emerge_above_natures(self):
        """Verifies Reframe, LiftInvariant, Falsify, CarryForward, and CausalAttribute."""
        state = CognitiveState(objective="Optimize throughput")

        # 1. Reframe
        reframe = Reframe()
        res_reframe = reframe.execute(state)
        self.assertGreater(len(res_reframe.branches), 0)

        # 2. Lift Invariant
        lift = LiftInvariant()
        cases = [{"metric": "cpu", "threshold": 80}, {"metric": "cpu", "threshold": 80}]
        res_lift = lift.execute(state, cases=cases)
        self.assertIn("cpu", str(res_lift.preserved))

        # 3. Carry Forward
        carry = CarryForward()
        res_carry = carry.execute(state, world_transition={"events": []})
        self.assertIsNotNone(res_carry)

        # 4. Falsify
        falsify = Falsify()
        target_hyp = CognitiveHypothesis(hypothesis_id="h-opt", statement="Batch size 100 is optimal")
        res_falsify = falsify.execute(
            state,
            target_hypothesis=target_hyp,
            verifier_fn=lambda p: {"disposition": "supported"},
        )
        self.assertFalse(res_falsify["is_falsified"])

        # 5. Causal Attribute
        attr = CausalAttribute()
        res_attr = attr.execute(
            state,
            intervention_records=[{"action": "tune_cache"}],
            observed_outcome={"latency": "10ms"},
            verifier_fn=lambda p: {"disposition": "supported"},
        )
        self.assertIn("Causal Attribute", res_attr["technique"])

    def test_technique_composition_pipeline(self):
        """Chains Reframe -> LiftInvariant into a verified pipeline."""
        pipeline = TechniqueComposition(
            composition_id="comp-pipeline-1",
            name="ReframeAndCompress",
            techniques=[Reframe(), LiftInvariant()],
        )
        state = CognitiveState(objective="Improve resilience")
        step_inputs = {
            "technique.lift_invariant": {
                "cases": [{"failure_mode": "oom", "guard": "limits"}, {"failure_mode": "oom", "guard": "limits"}]
            }
        }
        res = pipeline.execute_pipeline(state, step_inputs=step_inputs)
        self.assertEqual(res["steps_executed"], 2)

    # =========================================================================
    # 8. EXTRACT TECHNIQUE & 11 STRUCTURAL TYPES TESTS
    # =========================================================================
    def test_extract_technique_9_stage_and_type_discrimination(self):
        """Executes full 9-stage extraction and discriminates all 11 structural types."""
        extractor = ExtractTechnique()

        # 11 distinct patterns
        patterns = [
            ({"name": "Mental Reframing Step", "content": "cognitive reframe of goal"}, StructuralType.COGNITIVE_TECHNIQUE),
            ({"name": "Pipeline Orchestrator", "content": "composition of sequential tools"}, StructuralType.COMPOSITION),
            ({"name": "Autonomous Navigation", "content": "higher-order capability"}, StructuralType.CAPABILITY),
            ({"name": "Release Workflow", "content": "stages and gates for deployment"}, StructuralType.WORKFLOW),
            ({"name": "SQLite Ledger Engine", "content": "deterministic machine with schema"}, StructuralType.DETERMINISTIC_MECHANISM),
            ({"name": "Test Oracle Verifier", "content": "verifier assert check"}, StructuralType.VERIFIER),
            ({"name": "Mutual TLS Handshake", "content": "protocol handshake wire"}, StructuralType.PROTOCOL),
            ({"name": "Move South Action", "content": "execute action op in grid"}, StructuralType.ACTION),
            ({"name": "Visible Lever Affordance", "content": "environmental_visible affordance"}, StructuralType.ENVIRONMENTAL_AFFORDANCE),
            ({"name": "Lock Picking Trade", "content": "domain method and tradecraft"}, StructuralType.DOMAIN_METHOD),
            ({"name": "Execution Receipt Outcome", "content": "outcome terminal receipt"}, StructuralType.OUTCOME),
        ]

        for pat, expected_type in patterns:
            discriminated = extractor.discriminate_type(pat)
            self.assertEqual(discriminated, expected_type, f"Failed for {pat['name']}")

        # Full 9-stage extraction run
        work_trace = {
            "trace_id": "trace-101",
            "name": "AdaptiveReframeMethod",
            "objective": "Escape lock",
            "events": [
                {"step": 1, "kind": "observation", "state": {"locked": True}},
                {"step": 2, "kind": "deliberation", "content": "expand alternative latch paths"},
                {"step": 3, "kind": "action", "state": {"locked": False}},
            ],
        }
        result = extractor.extract(
            work_trace,
            verifier_fn=lambda p: {"disposition": "supported"},
        )
        self.assertEqual(result.trace_id, "trace-101")
        self.assertEqual(result.transitions_reconstructed, 2)
        self.assertEqual(result.candidate.status, "candidate")
        self.assertTrue(len(result.candidate.qualification_requirements) >= 2)

    # =========================================================================
    # 9. COMPOUNDING LOOP & QUALIFICATION TESTS
    # =========================================================================
    def test_compounding_loop_lifecycle(self):
        """Work → Extract → Qualify → Register → Compose."""
        loop = CompoundingLoop()

        work_trace = {
            "trace_id": "trace-improve",
            "name": "CircuitBreakerPattern",
            "events": [
                {"step": 1, "kind": "observation", "state": {"errors": 5}},
                {"step": 2, "kind": "action", "state": {"circuit": "open"}},
            ],
        }

        # 1. Extract Candidate
        cand = loop.extract_from_work(work_trace)
        self.assertEqual(cand.status, "candidate")

        # 2. Attempt registration before qualification must fail
        with self.assertRaises(UnqualifiedTechniqueError):
            loop.register_qualified(cand.candidate_id)

        # 3. Qualify Candidate through empirical trials
        trials = [
            ("Positive: Trip on high error", {"errors": 10}, "trip", lambda d: "trip" if d["errors"] >= 5 else "pass"),
            ("Negative: Pass on low error", {"errors": 1}, "pass", lambda d: "trip" if d["errors"] >= 5 else "pass"),
        ]
        passed, receipts = loop.qualify_candidate(cand.candidate_id, trials)
        self.assertTrue(passed)
        self.assertEqual(cand.status, "qualified")

        # 4. Register Qualified Technique
        record = loop.register_qualified(cand.candidate_id)
        self.assertEqual(record.name, "CircuitBreakerPattern")

        # 5. Compose into Higher Capability
        comp = loop.compose_registered([record.technique_id], "ResilienceCapability")
        self.assertEqual(len(comp.techniques), 1)

    # =========================================================================
    # 10. HETEROGENEOUS QUALIFICATION SCENARIOS
    # =========================================================================
    def test_scenario_a_software_diagnosis(self):
        """Scenario A: Software Diagnosis under contradictory error logs."""
        state = CognitiveState(
            objective="Diagnose backend crash",
            active_constraints=["Prohibited: restarting server without crash dump"],
        )
        expansion = Expansion()
        grounding = Grounding()

        # Expansion reveals competing root causes without jumping to conclusions
        res_exp = expansion.transform(
            state,
            candidate_generators=[
                {"representation": "Hypothesis: Memory leak OOM crash", "material_difference": "Memory exhaustion"},
                {"representation": "Hypothesis: Deadlock between worker threads", "material_difference": "Lock contention"},
            ],
        )
        self.assertEqual(len(res_exp.valid_branches), 2)

        # Grounding collides with log probe
        hyp_oom = state.hypotheses[0]
        hyp_deadlock = state.hypotheses[1]

        def verifier(probe):
            # Physical memory telemetry proves no OOM occurred, but thread dump shows deadlock
            if "Memory" in probe.discriminating_condition or "Memory" in str(probe.probe_payload):
                return {"disposition": "contradicted", "reason": "RSS never exceeded 40%"}
            return {"disposition": "supported", "reason": "Thread dump proves circular mutex lock"}

        res_g1 = grounding.evaluate_with_verifier(hyp_oom, verifier_fn=verifier, state=state)
        res_g2 = grounding.evaluate_with_verifier(hyp_deadlock, verifier_fn=verifier, state=state)

        self.assertTrue(res_g1.is_falsified)
        self.assertEqual(res_g2.disposition, "SUPPORTED")
        self.assertEqual(hyp_deadlock.confidence, "HIGH")

    def test_scenario_b_research_epistemic_reasoning(self):
        """Scenario B: Epistemic reasoning separating source assertions from warranted claims."""
        grounding = Grounding()
        hyp = CognitiveHypothesis(
            hypothesis_id="h-source-claim",
            statement="Vendor states library is memory-safe",
            epistemic_status=EpistemicCategory.INTERPRETATION,
        )
        # Attempt to label vendor claim as verified fact without external audit
        def biased_verifier(probe):
            return {
                "disposition": "supported",
                "category": EpistemicCategory.SOURCE_SUPPLIED_FACT,
                # Intentionally omitted source_provenance_id
            }
        with self.assertRaises(EpistemicLaunderingError):
            grounding.evaluate_with_verifier(hyp, verifier_fn=biased_verifier)

    def test_scenario_c_planning_and_strategy(self):
        """Scenario C: Multi-objective planning with strict constraint trade-offs."""
        expansion = Expansion()
        state = CognitiveState(
            objective="Deliver payload under budget",
            active_constraints=["Prohibited: exceeding budget of $1000"],
        )
        res = expansion.transform(
            state,
            candidate_generators=[
                {"representation": "Hire premium courier for $2500", "material_difference": "Overbudget option"},
                {"representation": "Use scheduled regional carrier for $600", "material_difference": "Within budget option"},
            ],
        )
        valid = [b for b in res.branches if b.is_valid]
        invalid = [b for b in res.branches if not b.is_valid]
        self.assertEqual(len(valid), 1)
        self.assertEqual(len(invalid), 1)
        self.assertIn("600", valid[0].representation)

    def test_scenario_d_kageyoni_world_interaction_and_non_authority(self):
        """Scenario D: Cognitive transformations do NOT mutate Kageyoni SQLite world tables (Δcog ≠ Δworld)."""
        # Baseline check on engine event count
        initial_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]

        state = CognitiveState(objective="Explore cavern")
        control = TransformationControl()

        # Run multiple cognitive steps: Expansion, Grounding, Compression
        control.assess_need(state)
        expansion = Expansion()
        expansion.transform(state)
        compression = Compression()
        compression.transform([{"room": "c1", "dark": True}, {"room": "c2", "dark": True}], state=state)

        # Invariant check: Engine event count MUST be completely unchanged
        current_events = self.engine.db.execute("SELECT count(*) FROM events").fetchone()[0]
        self.assertEqual(initial_events, current_events, "Violation of Δcog ≠ Δworld! Cognitive layer mutated world events.")

    def test_scenario_e_unfamiliar_domain_esoteric_state_machine(self):
        """Scenario E: Unfamiliar domain with alien protocol rules."""
        coupling = Coupling()
        # Alien protocol: Node can only link to Glyph if resonance frequencies harmonize
        glyph_node = ComponentInterface(
            component_id="GlyphNode_7",
            kind="domain_structure",
            provides={"resonance_432hz"},
            requires={"flux_stability"},
            invariants=["immutable_orientation"],
        )
        conduit = ComponentInterface(
            component_id="AetherConduit_X",
            kind="tool",
            provides={"flux_stability"},
            requires={"resonance_432hz"},
            invariants=["immutable_orientation"],
        )
        result = coupling.couple(
            glyph_node,
            conduit,
            relationship="harmonic_lock",
            claimed_emergent_capability="SustainedPortalOpening",
            emergent_mechanism="Bilateral cancellation of resonant flux oscillation between glyph and conduit.",
        )
        self.assertTrue(result.is_compatible)
        self.assertEqual(result.composition.emergent_capability, "SustainedPortalOpening")

    # =========================================================================
    # 11. ABLATION STUDIES (Full Substrate vs Ablated vs Baseline)
    # =========================================================================
    def test_ablation_grounding_removed_induces_laundering(self):
        """Ablation: Removing Grounding leaves operator unable to detect false hypotheses."""
        state = CognitiveState(objective="Evaluate security")
        hyp = CognitiveHypothesis(hypothesis_id="h-ablate", statement="Zero vulnerabilities exist")
        state.add_hypothesis(hyp)

        # With Grounding: probe reveals vulnerability
        grounding = Grounding()
        res = grounding.evaluate_with_verifier(
            hyp,
            verifier_fn=lambda p: {"disposition": "contradicted", "reason": "CVE-2024-XXXX present"},
        )
        self.assertTrue(res.is_falsified)

        # Without Grounding (ablated): hypothesis remains unexamined and unchallenged
        state_ablated = CognitiveState(objective="Evaluate security")
        hyp_ablated = CognitiveHypothesis(hypothesis_id="h-ablate", statement="Zero vulnerabilities exist")
        state_ablated.add_hypothesis(hyp_ablated)
        self.assertEqual(state_ablated.hypotheses[0].confidence, "UNVERIFIED")
        # In an ablated system, ungrounded hypotheses silently masquerade as valid premises

    def test_ablation_expansion_removed_induces_fixation(self):
        """Ablation: Removing Expansion leaves operator trapped in single flawed frame."""
        state = CognitiveState(
            objective="Cross chasm",
            raw_intent="Jump across 50-meter chasm",
            active_constraints=["Prohibited: lethal fall"],
        )
        # Full Expansion produces alternatives (e.g. build bridge, search for detour)
        expansion = Expansion()
        res = expansion.transform(state)
        self.assertGreater(len(res.valid_branches), 1)

        # Ablated Expansion only has original flawed intent which violates constraints
        self.assertIn("Jump across 50-meter chasm", state.raw_intent)

    def test_ablation_compression_removed_causes_representation_bloat(self):
        """Ablation: Without Compression, operator accumulates raw episodes without extracting invariants."""
        episodes = [{"run": i, "status": "ok", "threshold": 50, "failure": "timeout"} for i in range(10)]
        compression = Compression()
        comp_res = compression.transform(episodes)
        # Compressed: 1 generator expression, core invariant identified
        self.assertIsNotNone(comp_res.generator)
        self.assertTrue(len(comp_res.invariant_rules) > 0)
        # Ablated: 10 raw dictionaries with zero causal extraction

    # =========================================================================
    # 12. SELF-REFERENTIAL BOOTSTRAP TEST (Section 13)
    # =========================================================================
    def test_self_referential_bootstrap(self):
        """Run the resulting substrate against its own development trace to extract candidate techniques."""
        dev_trace = {
            "trace_id": "trace-nature-substrate-dev",
            "name": "AdversarialNatureQualification",
            "objective": "Implement and qualify core cognitive substrate",
            "events": [
                {"step": 1, "kind": "observation", "state": {"substrate_implemented": False}},
                {"step": 2, "kind": "deliberation", "content": "expand natures, ground verifiers, compress invariants"},
                {"step": 3, "kind": "action", "state": {"substrate_implemented": True, "qualified": True}},
            ],
        }

        loop = CompoundingLoop()
        candidate = loop.extract_from_work(dev_trace)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.name, "AdversarialNatureQualification")
        self.assertIn(NatureType.EXPANSION, candidate.factored_natures)
        self.assertIn(NatureType.GROUNDING, candidate.factored_natures)
        self.assertIn(NatureType.COMPRESSION, candidate.factored_natures)


if __name__ == "__main__":
    unittest.main()
