"""Test Suite: 20-Control SSL Control-to-Behavior Contract.

Mechanically verifies the 20 SSL controls specified in the Control-to-Behavior Contract:
Every single control (1 to 20) has:
1. An expected-effect test (control active changes behavior as specified).
2. An absence-of-effect test (control bypassed/inactive leaves signal unchanged or fails closed).
"""
import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from kageyoni.ninshu.ageing import SSLBoardAgeingEngine
from kageyoni.ninshu.circuits import (
    FourBandEQ,
    IngressTrimExceededError,
    PreampIngressTrim,
    ScopeFilter,
    VCADynamicsCompressor,
    apply_phase_invert,
    compare_phase,
)
from kageyoni.ninshu.console import ActiveConsole, ChannelStripConfig, canonical_digest
from kageyoni.ninshu.modulator import (
    PredicateTransductionError,
    SubstrateModulator,
    validate_predicate_observation,
)
from kageyoni.ninshu.process_supervisor import (
    ExpiredRunTokenError,
    ProcessSupervisor,
    TokenCancelledError,
)
from kageyoni.ninshu.scars import SCAR_REGISTRY, ScarFeedbackMatrix, ScarImpedanceTransformer
from kageyoni.ninshu.shaper import SSLMixingSession


class TestControl01_DiscoveryRoute(unittest.TestCase):
    """Control 1: Discovery / route (Candidate selection and relevance, not authorization)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl01",
            "channel_strips": [
                {
                    "ch": 1,
                    "name": "AdversaryDiscriminator",
                    "carrier": "kageyoni/ninshu/adversary.py",
                    "entrypoint": "ConsoleAdversaryBridge.audit_channel",
                    "tier": 0,
                },
                {
                    "ch": 2,
                    "name": "SovereignGate",
                    "carrier": "kageyoni/ninshu/power_system.py",
                    "entrypoint": "PowerSystem.gate_sovereign",
                    "tier": 2,
                },
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Active discovery resolves module path, callable symbol, schemas, and execution tier."""
        res = self.console.resolve_route(channel_number=1, max_tier=2)
        self.assertEqual(res["status"], "RESOLVED")
        self.assertTrue(res["is_executable"])
        self.assertEqual(res["module_path"], "kageyoni/ninshu/adversary.py")
        self.assertEqual(res["callable_symbol"], "ConsoleAdversaryBridge.audit_channel")
        self.assertEqual(res["execution_tier"], 0)
        self.assertIn("dict", res["input_schema"])
        self.assertFalse(res["universal_absence"])

    def test_absence_of_effect(self):
        """Incompatible execution tier remains non-executing; no-match does not assert universal absence."""
        # Channel 2 requires Tier 2, but max_tier constraint is Tier 0
        incompatible = self.console.resolve_route(channel_number=2, max_tier=0)
        self.assertEqual(incompatible["status"], "INCOMPATIBLE")
        self.assertFalse(incompatible["is_executable"])
        self.assertIn("exceeds authorized max_tier", incompatible["reason"])

        # Nonexistent channel query returns NO_MATCH without universal absence claim
        no_match = self.console.resolve_route(query="non_existent_symbol", max_tier=2)
        self.assertEqual(no_match["status"], "NO_MATCH")
        self.assertFalse(no_match["is_executable"])
        self.assertFalse(no_match["universal_absence"])


class TestControl02_PatchBusMembership(unittest.TestCase):
    """Control 2: Patch / bus membership (Typed execution graph and dataflow)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl02",
            "channel_strips": [
                {"ch": 1, "name": "StripA", "carrier": "modA", "entrypoint": "fnA", "tier": 0, "bus_id": "BUS_A"},
                {"ch": 2, "name": "StripB", "carrier": "modB", "entrypoint": "fnB", "tier": 0, "bus_id": "BUS_B"},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Attaching strip to Bus B routes producer output to that strip."""
        self.console.attach_to_bus("BUS_B", 1)
        self.assertIn(1, self.console.get_bus_channels("BUS_B"))

        producer_signal = {"test_data": 42, "reliability_score": 1.0}
        results = self.console.route_bus_signal("BUS_B", producer_signal)
        origin_channels = [r.get("origin_channel") for r in results]
        self.assertIn(1, origin_channels)
        self.assertIn(2, origin_channels)

    def test_absence_of_effect(self):
        """Detaching strip stops producer output reaching that strip; independent work unaffected."""
        self.console.detach_from_bus("BUS_B", 2)
        self.assertNotIn(2, self.console.get_bus_channels("BUS_B"))

        producer_signal = {"test_data": 99, "reliability_score": 1.0}
        results = self.console.route_bus_signal("BUS_B", producer_signal)
        origin_channels = [r.get("origin_channel") for r in results]
        self.assertNotIn(2, origin_channels)

        # Independent channel on Bus A remains functional
        bus_a_results = self.console.route_bus_signal("BUS_A", producer_signal)
        bus_a_channels = [r.get("origin_channel") for r in bus_a_results]
        self.assertIn(1, bus_a_channels)


class TestControl03_PreampIngressTrim(unittest.TestCase):
    """Control 3: Preamp / ingress trim (Input admission budget)."""

    def test_expected_effect(self):
        """Exceeding max_input_bytes, max_records, or max_recursion_depth raises IngressTrimExceededError."""
        trim = PreampIngressTrim(max_input_bytes=100, max_records=2, max_recursion_depth=3, trim_active=True)

        # Exceeds max_input_bytes
        large_payload = {"key": "x" * 200}
        with self.assertRaises(IngressTrimExceededError):
            trim.evaluate_payload(large_payload)

        # Exceeds max_records
        records_payload = [{"id": 1}, {"id": 2}, {"id": 3}]
        with self.assertRaises(IngressTrimExceededError):
            trim.evaluate_payload(records_payload)

        # Exceeds max_recursion_depth
        deep_payload = {"a": {"b": {"c": {"d": "too deep"}}}}
        with self.assertRaises(IngressTrimExceededError):
            trim.evaluate_payload(deep_payload)

    def test_absence_of_effect(self):
        """When trim is inactive / bypassed, valid payloads pass without truncation or knowledge amplification."""
        trim = PreampIngressTrim(trim_active=False)
        payload = {"data": "x" * 500, "deep": {"a": {"b": {"c": {"d": 1}}}}}
        receipt = trim.evaluate_payload(payload)
        self.assertTrue(receipt["admitted"])
        self.assertFalse(receipt["trim_active"])
        self.assertGreater(receipt["bytes_admitted"], 0)


class TestControl04_HPF_LPF_Scope(unittest.TestCase):
    """Control 4: HPF / LPF scope (Declared inclusion/exclusion and temporal aggregation)."""

    def setUp(self):
        self.scope = ScopeFilter(
            min_confidence=0.8,
            min_severity=0.5,
            max_depth=2,
            max_time_window=1000.0,
            filter_active=True,
        )
        self.records = [
            {"id": "valid", "confidence_score": 0.9, "severity": 0.8, "depth": 1, "timestamp": 500.0},
            {"id": "low_conf", "confidence_score": 0.4, "severity": 0.8, "depth": 1, "timestamp": 500.0},
            {"id": "low_sev", "confidence_score": 0.9, "severity": 0.2, "depth": 1, "timestamp": 500.0},
            {"id": "deep", "confidence_score": 0.9, "severity": 0.8, "depth": 5, "timestamp": 500.0},
            {"id": "late", "confidence_score": 0.9, "severity": 0.8, "depth": 1, "timestamp": 2000.0},
        ]

    def test_expected_effect(self):
        """HPF and LPF filter out records violating floors and ceilings, logging omitted_by_scope_count."""
        retained, meta = self.scope.filter_records(self.records)
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["id"], "valid")
        self.assertEqual(meta["omitted_by_scope_count"], 4)
        self.assertEqual(meta["retained_count"], 1)
        # Mandatory audit survives: omission reasons disclosed
        reasons = [o["reason"] for o in meta["omitted_records"]]
        self.assertIn("HPF_CONFIDENCE_BELOW_FLOOR", reasons)
        self.assertIn("HPF_SEVERITY_BELOW_FLOOR", reasons)
        self.assertIn("LPF_DEPTH_EXCEEDS_CEILING", reasons)
        self.assertIn("LPF_TIMESTAMP_EXCEEDS_WINDOW", reasons)

    def test_absence_of_effect(self):
        """When filter is inactive, all records survive with zero omitted_by_scope_count."""
        self.scope.filter_active = False
        retained, meta = self.scope.filter_records(self.records)
        self.assertEqual(len(retained), len(self.records))
        self.assertEqual(meta["omitted_by_scope_count"], 0)


class TestControl05_FourBandEQ(unittest.TestCase):
    """Control 5: Four-band EQ (Analysis effort / presentation allocation across declared layers)."""

    def setUp(self):
        self.records = [
            {"type": "schema", "name": "user_table", "data": "CREATE TABLE users..."},
            {"type": "function", "name": "auth_verify", "data": "def auth_verify(): pass"},
            {"type": "trace", "name": "call_stack", "data": "offset 0x7fff"},
            {"type": "token", "name": "api_secret", "data": "sk_live_1234567890"},
        ]

    def test_expected_effect(self):
        """Restricting a frequency band budget throttles items in that band while leaving others intact."""
        # Set High Frequency (HF - tokens/secrets) budget to 0 bytes
        eq = FourBandEQ(hf_budget_bytes=0, lf_budget_bytes=10000, lmf_budget_bytes=10000, hmf_budget_bytes=10000, eq_in=True)
        retained, meta = eq.allocate(self.records)

        retained_types = [r.get("type") for r in retained]
        self.assertIn("schema", retained_types)
        self.assertIn("function", retained_types)
        self.assertIn("trace", retained_types)
        self.assertNotIn("token", retained_types)

        self.assertEqual(meta["throttled_count"], 1)
        self.assertEqual(meta["throttled_records"][0]["name"], "api_secret")
        self.assertTrue(meta["throttled_records"][0]["_eq_throttled"])

    def test_absence_of_effect(self):
        """When EQ is bypassed (eq_in=False), all records pass without band curtailment."""
        eq = FourBandEQ(hf_budget_bytes=0, eq_in=False)
        retained, meta = eq.allocate(self.records)
        self.assertEqual(len(retained), 4)
        self.assertEqual(meta["throttled_count"], 0)


class TestControl06_FaderPriority(unittest.TestCase):
    """Control 6: Fader / priority (Scheduler weight or display priority under contention)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl06",
            "channel_strips": [
                {"ch": 1, "name": "LowPriority", "carrier": "modA", "entrypoint": "fnA", "tier": 0},
                {"ch": 2, "name": "HighPriority", "carrier": "modB", "entrypoint": "fnB", "tier": 0},
                {"ch": 3, "name": "MidPriority", "carrier": "modC", "entrypoint": "fnC", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Fader gain governs execution scheduling order under contention."""
        self.console.set_fader(1, -6.0)
        self.console.set_fader(2, 6.0)
        self.console.set_fader(3, 0.0)

        scheduled = self.console.schedule_execution([1, 2, 3])
        self.assertEqual(scheduled, [2, 3, 1])

    def test_absence_of_effect(self):
        """Equal fader levels preserve default order; fader never alters truth or correctness of output."""
        self.console.set_fader(1, 0.0)
        self.console.set_fader(2, 0.0)
        self.console.set_fader(3, 0.0)

        scheduled = self.console.schedule_execution([1, 2, 3])
        self.assertEqual(scheduled, [1, 2, 3])

        # Fader level attached to signal does not alter outcome
        res = self.console.stream_track(1, [{"outcome_passed": True, "value": "invariant"}])
        self.assertTrue(res[0]["outcome_passed"])
        self.assertEqual(res[0]["value"], "invariant")


class TestControl07_Mute(unittest.TestCase):
    """Control 7: Mute (Suppresses strip findings from bus projection while preserving failure evidence)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl07",
            "channel_strips": [
                {"ch": 1, "name": "Strip1", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Muting strip suppresses output from bus projection, logs 'muted': True, preserves failure evidence."""
        self.console.set_mute(1, True)
        failure_sig = {"outcome_passed": False, "reliability_score": 1.0, "error": "fatal_error"}
        out = self.console.stream_track(1, [failure_sig])

        # Bus projection suppressed
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["muted"])
        self.assertTrue(out[0]["_muted"])

        # Failure evidence preserved in channel history
        strip = self.console.channels[1]
        self.assertEqual(len(strip.failures_recorded), 1)
        self.assertEqual(strip.failures_recorded[0]["error"], "fatal_error")

    def test_absence_of_effect(self):
        """Unmuted strip streams findings directly to bus projection."""
        self.console.set_mute(1, False)
        sig = {"outcome_passed": True, "data": "live_output"}
        out = self.console.stream_track(1, [sig])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["data"], "live_output")
        self.assertNotIn("muted", out[0])


class TestControl08_Solo(unittest.TestCase):
    """Control 8: Solo (Focus selected channels without disabling mandatory Scar safety guards)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl08",
            "channel_strips": [
                {"ch": 1, "name": "SoloedChannel", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
                {"ch": 2, "name": "OtherChannel", "carrier": "mod2", "entrypoint": "fn2", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Soloing channel 1 isolates channel 1 and excludes channel 2 with safety_locked: True."""
        self.console.set_solo(1, True)
        self.console.set_solo(2, False)

        out1 = self.console.stream_track(1, [{"metric": "ch1_data"}])
        out2 = self.console.stream_track(2, [{"metric": "ch2_data"}])

        self.assertEqual(len(out1), 1)
        self.assertEqual(out1[0]["metric"], "ch1_data")
        self.assertTrue(out1[0]["safety_locked"])

        # Channel 2 is silenced by solo on channel 1
        self.assertEqual(out2, [])

    def test_absence_of_effect(self):
        """When no channels are soloed, both channels stream normally."""
        self.console.set_solo(1, False)
        self.console.set_solo(2, False)

        out1 = self.console.stream_track(1, [{"metric": "ch1"}])
        out2 = self.console.stream_track(2, [{"metric": "ch2"}])
        self.assertEqual(len(out1), 1)
        self.assertEqual(len(out2), 1)


class TestControl09_DynamicsBackpressure(unittest.TestCase):
    """Control 9: Dynamics / backpressure (Bounded queue with overflow receipts)."""

    def test_expected_effect(self):
        """Exceeding max_in_flight generates explicit overflow receipts rather than silent success."""
        compressor = VCADynamicsCompressor(max_in_flight=2, batch_size=2, dynamics_in=True)

        res1 = compressor.enqueue({"id": 1})
        res2 = compressor.enqueue({"id": 2})
        self.assertEqual(res1["status"], "QUEUED")
        self.assertEqual(res2["status"], "QUEUED")

        # 3rd record exceeds queue limit -> OVERFLOW_BACKPRESSURE receipt
        res3 = compressor.enqueue({"id": 3})
        self.assertEqual(res3["status"], "OVERFLOW_BACKPRESSURE")
        self.assertTrue(res3["dropped"])
        self.assertEqual(res3["queue_depth"], 2)
        self.assertIn("receipt_digest", res3)
        self.assertEqual(len(compressor.overflow_receipts), 1)

        # Process batch drains queue
        batch = compressor.process_batch()
        self.assertEqual(len(batch), 2)
        self.assertEqual(len(compressor.queue), 0)

    def test_absence_of_effect(self):
        """When dynamics are bypassed (dynamics_in=False), queue operates unbounded without overflow receipts."""
        compressor = VCADynamicsCompressor(max_in_flight=2, dynamics_in=False)
        for i in range(5):
            res = compressor.enqueue({"id": i})
            self.assertEqual(res["status"], "QUEUED_UNBOUNDED")
        self.assertEqual(len(compressor.queue), 5)
        self.assertEqual(len(compressor.overflow_receipts), 0)


class TestControl10_NoiseGate(unittest.TestCase):
    """Control 10: Noise gate (Filters low-confidence chatter, preserves deterministic negative findings)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl10",
            "channel_strips": [
                {"ch": 1, "name": "Strip1", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Noise gate filters low-reliability chatter but preserves deterministic negative findings."""
        self.console.set_gate(1, 0.5)

        low_reliability_chatter = {"data": "unverified_rumor", "reliability_score": 0.2, "outcome_passed": True}
        high_reliability_failure = {"data": "verified_assertion_failure", "reliability_score": 1.0, "outcome_passed": False}

        out = self.console.stream_track(1, [low_reliability_chatter, high_reliability_failure])

        # Only the high-reliability failure survives!
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["data"], "verified_assertion_failure")
        self.assertFalse(out[0]["outcome_passed"])
        self.assertEqual(out[0]["reliability_score"], 1.0)

    def test_absence_of_effect(self):
        """When noise gate threshold is 0.0, low-reliability chatter passes through unimpeded."""
        self.console.set_gate(1, 0.0)
        low_reliability_chatter = {"data": "chatter", "reliability_score": 0.1, "outcome_passed": True}
        out = self.console.stream_track(1, [low_reliability_chatter])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["data"], "chatter")


class TestControl11_PhaseComparison(unittest.TestCase):
    """Control 11: Phase comparison (Explicit typed comparison of claims and observations)."""

    def test_expected_effect(self):
        """Computes exact constructive lock vs contradiction."""
        claim_auth_true = {"authorized": True, "token": "abc"}
        claim_auth_false = {"authorized": False, "token": "abc"}

        contradiction = compare_phase(claim_auth_true, claim_auth_false)
        self.assertEqual(contradiction.status, "CONTRADICTION")
        self.assertEqual(contradiction.phase_correlation, -1.0)
        self.assertEqual(contradiction.phase_degrees, 180.0)
        self.assertIn("Key 'authorized'", contradiction.divergences[0])

        lock = compare_phase(claim_auth_true, claim_auth_true)
        self.assertEqual(lock.status, "CONSTRUCTIVE_LOCK")
        self.assertEqual(lock.phase_correlation, 1.0)
        self.assertEqual(lock.phase_degrees, 0.0)

    def test_absence_of_effect(self):
        """Disjoint contexts return INCOMPARABLE; missing facts do not become false facts."""
        claim_a = {"user_name": "alice"}
        claim_b = {"memory_offset": 0x4000}
        res = compare_phase(claim_a, claim_b)
        self.assertEqual(res.status, "INCOMPARABLE")
        self.assertEqual(res.phase_correlation, 0.0)
        self.assertEqual(res.phase_degrees, 90.0)

        empty_res = compare_phase({}, {})
        self.assertEqual(empty_res.status, "UNKNOWN")


class TestControl12_PhaseInvert(unittest.TestCase):
    """Control 12: Phase invert ∅ (Display-only view surfacing only contradictions and violations)."""

    def setUp(self):
        self.items = [
            {"id": 1, "status": "CONSTRUCTIVE_LOCK", "phase_correlation": 1.0},
            {"id": 2, "status": "CONTRADICTION", "phase_correlation": -1.0},
            {"id": 3, "status": "DIFFERENT", "phase_correlation": 0.0, "is_violation": True},
            {"id": 4, "status": "CONSTRUCTIVE_LOCK", "phase_correlation": 1.0},
        ]

    def test_expected_effect(self):
        """Phase invert inverts polarity to display only contradictions and boundary violations."""
        inverted = apply_phase_invert(self.items, phase_invert=True)
        self.assertEqual(len(inverted), 2)
        ids = [item["id"] for item in inverted]
        self.assertIn(2, ids)
        self.assertIn(3, ids)
        self.assertNotIn(1, ids)
        self.assertNotIn(4, ids)
        for item in inverted:
            self.assertTrue(item["_phase_inverted_view"])

    def test_absence_of_effect(self):
        """Without phase invert, all items are displayed; phase invert never alters underlying data."""
        normal = apply_phase_invert(self.items, phase_invert=False)
        self.assertEqual(len(normal), 4)


class TestControl13_PredicateLensSelector(unittest.TestCase):
    """Control 13: Predicate / lens selector (Restricts extraction to selected predicate families)."""

    def setUp(self):
        self.modulator = SubstrateModulator()
        self.records = [
            {"id": 1, "predicate_family": "structural_ast", "ast": "Module"},
            {"id": 2, "predicate_family": "protocol_trace", "packet": "TLS_CLIENT_HELLO"},
            {"id": 3, "predicate_family": "dynamic_call_flow", "trace": ["fnA", "fnB"]},
        ]

    def test_expected_effect(self):
        """Setting predicate lens selects only matching predicate family; relabelling static as dynamic fails."""
        self.modulator.set_predicate("structural_ast")
        filtered = self.modulator.filter_by_predicate(self.records)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], 1)

        # Prohibits relabelling static data as dynamic trace
        fraudulent_record = {"id": 4, "is_static": True, "mode": "static"}
        with self.assertRaises(PredicateTransductionError):
            self.modulator.filter_by_predicate([fraudulent_record], predicate_lens="dynamic_call_flow")

    def test_absence_of_effect(self):
        """When lens is 'all', records from all predicate families remain accessible."""
        self.modulator.set_predicate("all")
        all_records = self.modulator.filter_by_predicate(self.records)
        self.assertEqual(len(all_records), len(self.records))


class TestControl14_CompressionViscosity(unittest.TestCase):
    """Control 14: Compression / viscosity (Bounded loss-aware projection with lossless SHA-256 pointers)."""

    def setUp(self):
        self.modulator = SubstrateModulator()
        self.repeated_records = [
            {"type": "log", "name": "heartbeat", "predicate_type": "event", "status": "ok", "msg": "pulse 1"},
            {"type": "log", "name": "heartbeat", "predicate_type": "event", "status": "ok", "msg": "pulse 2"},
            {"type": "log", "name": "heartbeat", "predicate_type": "event", "status": "ok", "msg": "pulse 3"},
            {"type": "alert", "name": "oom", "predicate_type": "error", "status": "crit", "msg": "memory leak"},
        ]

    def test_expected_effect(self):
        """Compression folds repeated records into canonical summary while preserving lossless SHA-256 pointers."""
        res = self.modulator.compress_stream(self.repeated_records, viscosity_ratio=0.5)
        self.assertTrue(res["is_compressed"])
        self.assertEqual(res["total_records"], 4)
        self.assertEqual(res["emitted_records"], 2)  # 3 logs folded into 1, 1 alert
        self.assertEqual(res["folded_count"], 2)

        # Check raw evidence pointers and lossless retrieval
        folded = [r for r in res["records"] if r.get("_canonical_summary")]
        self.assertEqual(len(folded), 1)
        raw_ptr = folded[0]["raw_evidence_pointer"]
        raw_rec = self.modulator.get_raw_evidence(raw_ptr)
        self.assertIsNotNone(raw_rec)
        self.assertEqual(raw_rec["name"], "heartbeat")

    def test_absence_of_effect(self):
        """When viscosity_ratio = 1.0 (uncompressed), records pass at full fidelity without folding."""
        res = self.modulator.compress_stream(self.repeated_records, viscosity_ratio=1.0)
        self.assertFalse(res["is_compressed"])
        self.assertEqual(len(res["records"]), 4)
        self.assertEqual(res["folded_count"], 0)


class TestControl15_InsertBypass(unittest.TestCase):
    """Control 15: Insert / bypass (Runs chained pre/post transform callables, cleanly bypassed)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl15",
            "channel_strips": [
                {"ch": 1, "name": "Strip1", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """With insert_bypass=False, chained transforms execute on signal."""
        self.console.set_insert_bypass(1, False)
        self.console.add_insert_transform(1, lambda sig: {**sig, "stage_1": "applied"})
        self.console.add_insert_transform(1, lambda sig: {**sig, "stage_2": "applied"})

        res = self.console.stream_track(1, [{"raw_data": 100}])
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].get("stage_1"), "applied")
        self.assertEqual(res[0].get("stage_2"), "applied")

    def test_absence_of_effect(self):
        """With insert_bypass=True, insert transforms are skipped; mandatory safety locks remain."""
        self.console.set_insert_bypass(1, True)
        self.console.add_insert_transform(1, lambda sig: {**sig, "forbidden_mutation": True})

        res = self.console.stream_track(1, [{"raw_data": 200}])
        self.assertEqual(len(res), 1)
        self.assertNotIn("forbidden_mutation", res[0])
        self.assertTrue(res[0]["safety_locked"])  # Policy and custody cannot be bypassed


class TestControl16_MeterBridge(unittest.TestCase):
    """Control 16: Meter bridge (Observability of actual work; synthetic dB marked illustrative_only)."""

    def setUp(self):
        self.session = SSLMixingSession(patch_channels=[1], operator_intent="test_metering")

    def test_expected_effect(self):
        """Meter bridge reports measured bytes, latency, failures, and flags synthetic dB as illustrative_only."""
        payload = {"data": "test_bytes_payload", "outcome_passed": False}
        self.session.sculpt_signal(1, payload)

        bridge = self.session.read_meter_bridge()
        ch_meter = list(bridge.values())[0]

        self.assertGreater(ch_meter["measured_bytes"], 0)
        self.assertGreaterEqual(ch_meter["latency_ms"], 0.0)
        self.assertEqual(ch_meter["failures_detected"], 1)
        # Synthetic metrics marked illustrative only
        self.assertTrue(ch_meter["illustrative_only"])
        self.assertIn("dBFS", ch_meter["in_vu"])

    def test_absence_of_effect(self):
        """With zero traffic, measured meters read zero without inventing synthetic activity."""
        bridge = self.session.read_meter_bridge()
        ch_meter = list(bridge.values())[0]
        self.assertEqual(ch_meter["measured_bytes"], 0)
        self.assertEqual(ch_meter["failures_detected"], 0)
        self.assertEqual(ch_meter["contradictions_detected"], 0)


class TestControl17_AgeingPatina(unittest.TestCase):
    """Control 17: Ageing / patina (Historical reliability in SQLite; cosmetic patina strictly isolated)."""

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self.temp_db.close()
        self.engine = SSLBoardAgeingEngine(db_path=Path(self.temp_db.name))

    def tearDown(self):
        try:
            os.remove(self.temp_db.name)
        except OSError:
            pass

    def test_expected_effect(self):
        """Records empirical reliability in SQLite; cosmetic patina is strictly isolated under _cosmetic_patina."""
        self.engine.record_run(channel_number=1, success=True, latency_ms=10.0, drift_ms=0.25)
        self.engine.record_run(channel_number=1, success=False, latency_ms=15.0, drift_ms=0.5)

        stats = self.engine.get_reliability_stats(1)
        self.assertEqual(stats["total_runs"], 2)
        self.assertEqual(stats["success_runs"], 1)
        self.assertEqual(stats["failure_runs"], 1)
        self.assertEqual(stats["success_rate"], 0.5)
        self.assertEqual(stats["cumulative_drift_ms"], 0.75)

        # Apply cosmetic patina
        canonical_signal = {"raw_result": "immutable_evidence", "digest_sha256": "abc"}
        conditioned, meta = self.engine.apply_harmonic_distortion(1, canonical_signal, cosmetic_opt_in=True)

        # Canonical evidence fields are NEVER mutated
        self.assertEqual(conditioned["raw_result"], "immutable_evidence")
        self.assertEqual(conditioned["digest_sha256"], "abc")
        # Patina isolated
        self.assertTrue(conditioned["_cosmetic_patina"]["illustrative_only"])

    def test_absence_of_effect(self):
        """With cosmetic_opt_in=False, signal is returned completely untouched with no _cosmetic_patina."""
        signal = {"raw_result": "pure_signal"}
        conditioned, meta = self.engine.apply_harmonic_distortion(1, signal, cosmetic_opt_in=False)
        self.assertEqual(conditioned, signal)
        self.assertNotIn("_cosmetic_patina", conditioned)
        self.assertFalse(meta["cosmetic_opt_in"])


class TestControl18_ScarGuard(unittest.TestCase):
    """Control 18: Scar guard (Enforces ScarRegistry invariants on every strip execution)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl18",
            "channel_strips": [
                {"ch": 1, "name": "GuardedStrip", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Signal matching a known failure pattern (e.g. stale revision) triggers Scar guard adaptation."""
        violating_signal = {"expected_revision": "rev1", "action": "branch_mutation"}
        res = self.console.stream_track(1, [violating_signal])

        self.assertEqual(len(res), 1)
        self.assertTrue(res[0]["safety_locked"])
        self.assertIn("scar_adaptations", res[0])
        adaptations = [a["scar_id"] for a in res[0]["scar_adaptations"]]
        self.assertIn("SCAR-001-STALE-REVISION", adaptations)

    def test_absence_of_effect(self):
        """Benign signal passes through without triggering scar adaptations."""
        benign_signal = {"query": "clean_read_inspection"}
        res = self.console.stream_track(1, [benign_signal])
        self.assertEqual(len(res), 1)
        self.assertNotIn("scar_adaptations", res[0])
        self.assertTrue(res[0]["safety_locked"])


class TestControl19_MasterPrint(unittest.TestCase):
    """Control 19: Master print (Freezes cryptographically signed, reproducible master receipt)."""

    def setUp(self):
        self.patch = {
            "patch_id": "test_ctrl19",
            "channel_strips": [
                {"ch": 1, "name": "PrintStrip", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Freezes cryptographically signed master tape and saves master_print.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            export_file = Path(tmpdir) / "master_print.json"
            active_signals = [{"result": "verified_result", "reliability_score": 1.0}]
            thermo = [{"candidate_id": "cand_1", "peak_memory_bytes": 1024, "passed": True}]

            master = self.console.print_master(
                session_id="sess_101",
                active_signals=active_signals,
                compiled_aspects=[],
                thermodynamic_receipts=thermo,
                export_path=export_file,
            )

            self.assertEqual(master.verification_status, "VERIFIED")
            self.assertTrue(export_file.exists())
            self.assertGreater(len(master.master_sha256), 0)

            # File content matches master_sha256
            saved_data = json.loads(export_file.read_text(encoding="utf-8"))
            self.assertEqual(saved_data["master_sha256"], master.master_sha256)

            # High-reliability failures preserve confidence_score=1.0 and reliability_score=1.0 (Bug Fix)
            thermo_rec = [r for r in master.verified_evidence_records if r.get("evidence_type") == "THERMODYNAMIC_RECEIPT"][0]
            self.assertEqual(thermo_rec["confidence_score"], 1.0)
            self.assertEqual(thermo_rec["reliability_score"], 1.0)

    def test_absence_of_effect(self):
        """Cannot print VERIFIED for empty required evidence or unresolved deficits; supports truthful partial."""
        # Missing all evidence records
        empty_master = self.console.print_master(
            session_id="sess_empty",
            active_signals=[],
            compiled_aspects=[],
            thermodynamic_receipts=[],
        )
        self.assertNotEqual(empty_master.verification_status, "VERIFIED")
        self.assertEqual(empty_master.verification_status, "PARTIAL")
        self.assertIn("EMPTY_EVIDENCE_RECORDS", empty_master.required_evidence_missing)


class TestControl20_PauseResumeStop(unittest.TestCase):
    """Control 20: Pause / resume / stop (Run lifecycle integration with ProcessSupervisor)."""

    def setUp(self):
        self.supervisor = ProcessSupervisor(session_salt="test_salt_lifecycle", max_active_tokens=100)
        self.token = self.supervisor.issue_token(pid=1000, parent_pid=1, lease_duration=60.0, max_budget=300.0)
        self.patch = {
            "patch_id": "test_ctrl20",
            "channel_strips": [
                {"ch": 1, "name": "Strip1", "carrier": "mod1", "entrypoint": "fn1", "tier": 0},
                {"ch": 2, "name": "Strip2", "carrier": "mod2", "entrypoint": "fn2", "tier": 0},
            ]
        }
        self.console = ActiveConsole(self.patch)

    def test_expected_effect(self):
        """Pause checkpoints state; resume continues remaining strips; stop cancels supervisor token."""
        self.console.start_run(self.token)

        # 1. Pause
        checkpoint = self.console.pause_run(completed_strips=[1], pending_strips=[2])
        self.assertEqual(checkpoint["state"], "PAUSED")
        self.assertEqual(checkpoint["completed_strips"], [1])

        # 2. Resume (continues remaining strips only)
        pending = self.console.resume_run(checkpoint, self.supervisor, self.token)
        self.assertEqual(pending, [2])

        # 3. Stop
        stop_res = self.console.stop_run(self.supervisor, self.token)
        self.assertEqual(stop_res["status"], "STOPPED")
        self.assertTrue(self.console.is_stopped)

    def test_absence_of_effect(self):
        """Resuming with a cancelled run token fails closed (TokenCancelledError)."""
        self.console.start_run(self.token)
        checkpoint = self.console.pause_run(completed_strips=[1], pending_strips=[2])

        # Cancel the token
        self.supervisor.cancel_token(self.token.token_id)

        # Attempt to resume fails closed
        with self.assertRaises(TokenCancelledError):
            self.console.resume_run(checkpoint, self.supervisor, self.token)


if __name__ == "__main__":
    unittest.main()
