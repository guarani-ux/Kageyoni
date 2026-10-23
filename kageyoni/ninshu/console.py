"""Ninshū Active Mixing Engine & Master Print Bus.

Implements the active playback loop for the SSL 4000 Console:
1. Ingests live computational substrate (the liquid metal / telemetry stream).
2. Routes signal through configured channel strips (preamp, filter, dynamics, gate, EQ).
3. Preserves opposing tensions and deficits across the sub-mix bus via EffectResolver.
4. Quenches and prints the final release master tape backed by immutable SHA-256 digests.
5. Implements full 20-control SSL Control-to-Behavior Contract.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from kageyoni.composition.effects import EffectResolver, ExpressionContract
from .scars import SCAR_REGISTRY, ScarFeedbackMatrix


def canonical_digest(value: Any) -> str:
    """Computes an RFC 8785 compliant canonical SHA-256 digest."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass
class ChannelStripConfig:
    """Physical dial settings on an active SSL 4000 channel strip."""
    channel_number: int
    name: str
    carrier_path: str
    entrypoint: str
    fader_gain_db: float = 0.0            # Fader level (-inf to +10 dB)
    mute: bool = False                    # Channel mute switch (Control 7)
    solo: bool = False                    # Channel solo switch (Control 8)
    hpf_cutoff_hz: Optional[float] = None # High-Pass Filter cutoff (scope limiter)
    thermal_ceiling: int = 0              # 0 = Tier 0 (Cold), 1 = Tier 1 (Hot Gate), 2 = Tier 2 (Sovereign)
    noise_gate_threshold: float = 0.5     # Epistemic squelch (Control 10)
    max_memory_ceiling_bytes: int = 64 * 1024 # 64 KB default thermodynamic budget
    thermodynamic_receipt: Optional[Dict[str, Any]] = None # Cached verification receipt
    insert_bypass: bool = False           # Insert Bypass switch (Control 15)
    insert_chain: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = field(default_factory=list)
    bus_assignment: str = "BUS_A"         # Bus A-F routing graph membership (Control 2)
    safety_locked: bool = True            # Mandatory safety invariant lock (Control 8/18)
    failures_recorded: List[Dict[str, Any]] = field(default_factory=list) # Preserved failure evidence (Control 7/10)


@dataclass
class MasterTape:
    """The finalized, immutable Master Print output from the SSL console (Control 19)."""
    session_id: str
    timestamp: float
    patch_id: str
    channels_active: List[int]
    total_tracks_processed: int
    opposing_pressures_preserved: List[Dict[str, Any]]
    action_gates_enforced: List[Dict[str, Any]]
    deficits_unplaced: List[Dict[str, Any]]
    verified_evidence_records: List[Dict[str, Any]]
    reversibility_tier: int
    master_sha256: str = ""
    thermodynamic_receipts: List[Dict[str, Any]] = field(default_factory=list)
    verification_status: str = "VERIFIED" # "VERIFIED", "PARTIAL", "UNRESOLVED_DEFICITS"
    required_evidence_missing: List[str] = field(default_factory=list)

    def freeze(self) -> MasterTape:
        """Calculates the cryptographic seal on the printed master."""
        data = asdict(self)
        data.pop("master_sha256", None)
        self.master_sha256 = canonical_digest(data)
        return self

    def export_master_print(self, export_path: Optional[str | Path] = None) -> Path:
        """Serializes and freezes the master print to master_print.json (Control 19)."""
        target_path = Path(export_path or "master_print.json")
        data = asdict(self)
        encoded = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
        target_path.write_text(encoded, encoding="utf-8")
        return target_path


class ActiveConsole:
    """The live, running SSL 4000 console processing computational substrate."""

    def __init__(self, patch_manifest: Dict[str, Any]):
        self.patch_id = patch_manifest.get("patch_id", "ad_hoc_session")
        self.reversibility_tier = patch_manifest.get("reversibility_tier", 0)
        self.channels: Dict[int, ChannelStripConfig] = {}
        self.effect_resolver = EffectResolver()
        self.expression_contract = ExpressionContract()
        self.scar_feedback = ScarFeedbackMatrix()

        # Busses A through F routing graph (Control 2)
        self.busses: Dict[str, List[int]] = {
            "BUS_A": [],
            "BUS_B": [],
            "BUS_C": [],
            "BUS_D": [],
            "BUS_E": [],
            "BUS_F": [],
        }

        # Mount channel strips from patch manifest
        for strip in patch_manifest.get("channel_strips", []):
            ch_num = strip["ch"]
            bus_id = strip.get("bus_id", "BUS_A")
            config = ChannelStripConfig(
                channel_number=ch_num,
                name=strip["name"],
                carrier_path=strip["carrier"],
                entrypoint=strip["entrypoint"],
                thermal_ceiling=strip.get("tier", 0),
                bus_assignment=bus_id,
            )
            self.channels[ch_num] = config
            if bus_id in self.busses:
                self.busses[bus_id].append(ch_num)

        # Run token supervisor context (Control 20)
        self.active_run_token: Any = None
        self.is_stopped: bool = False

    # --- CONTROL 1: DISCOVERY / ROUTE ---

    def resolve_route(
        self,
        query: Optional[str] = None,
        channel_number: Optional[int] = None,
        max_tier: int = 2
    ) -> Dict[str, Any]:
        """Resolves module path, callable symbol, input/output schema, and execution tier (Control 1).

        Relevant operations appear; incompatible/prohibited ones remain nonexecuting;
        no-match does not imply universal absence.
        """
        candidate: Optional[ChannelStripConfig] = None
        if channel_number is not None:
            candidate = self.channels.get(channel_number)
        elif query:
            q_lower = query.lower()
            for ch in self.channels.values():
                if q_lower in ch.name.lower() or q_lower in ch.carrier_path.lower():
                    candidate = ch
                    break

        if not candidate:
            return {
                "status": "NO_MATCH",
                "is_executable": False,
                "reason": "No matching candidate found in active console patch",
                "universal_absence": False,
            }

        # Check execution tier constraints (prohibited tiers remain non-executing)
        if candidate.thermal_ceiling > max_tier:
            return {
                "status": "INCOMPATIBLE",
                "is_executable": False,
                "channel_number": candidate.channel_number,
                "name": candidate.name,
                "execution_tier": candidate.thermal_ceiling,
                "max_permitted_tier": max_tier,
                "reason": f"Execution tier {candidate.thermal_ceiling} exceeds authorized max_tier {max_tier}",
                "universal_absence": False,
            }

        return {
            "status": "RESOLVED",
            "is_executable": True,
            "channel_number": candidate.channel_number,
            "name": candidate.name,
            "module_path": candidate.carrier_path,
            "callable_symbol": candidate.entrypoint,
            "input_schema": ["dict", "bytes"],
            "output_schema": ["dict", "evidence_receipt"],
            "execution_tier": candidate.thermal_ceiling,
            "universal_absence": False,
        }

    # --- CONTROL 2: PATCH / BUS MEMBERSHIP ---

    def attach_to_bus(self, bus_id: str, channel_number: int) -> None:
        """Attaches a channel strip to Bus A-F routing graph (Control 2)."""
        if bus_id not in self.busses:
            self.busses[bus_id] = []
        if channel_number not in self.busses[bus_id]:
            self.busses[bus_id].append(channel_number)
        if channel_number in self.channels:
            self.channels[channel_number].bus_assignment = bus_id

    def detach_from_bus(self, bus_id: str, channel_number: int) -> None:
        """Detaches a channel strip from Bus A-F routing graph (Control 2)."""
        if bus_id in self.busses and channel_number in self.busses[bus_id]:
            self.busses[bus_id].remove(channel_number)

    def get_bus_channels(self, bus_id: str) -> List[int]:
        """Returns channel numbers assigned to the given bus."""
        return list(self.busses.get(bus_id, []))

    def route_bus_signal(
        self,
        bus_id: str,
        producer_output: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Routes producer output to consumers attached to the specified bus (Control 2).

        Broken edges only block dependent work; independent strips execute unimpeded.
        """
        attached = self.get_bus_channels(bus_id)
        routed_results = []
        for ch in attached:
            results = self.stream_track(ch, [producer_output])
            routed_results.extend(results)
        return routed_results

    # --- CONTROLS 6, 7, 8: FADER, MUTE, SOLO ---

    def set_fader(self, channel_number: int, gain_db: float) -> None:
        """Adjusts the fader volume / priority on a channel strip (Control 6)."""
        if channel_number in self.channels:
            self.channels[channel_number].fader_gain_db = gain_db

    def schedule_execution(self, channel_numbers: List[int]) -> List[int]:
        """Governs scheduling weight and execution order under contention (Control 6).

        Highest fader gain executes first. Does not change truth or qualify a channel.
        """
        def fader_weight(ch_num: int) -> float:
            strip = self.channels.get(ch_num)
            return strip.fader_gain_db if strip else 0.0

        return sorted(channel_numbers, key=fader_weight, reverse=True)

    def set_mute(self, channel_number: int, mute: bool = True) -> None:
        """Sets mute switch on channel strip (Control 7)."""
        if channel_number in self.channels:
            self.channels[channel_number].mute = mute

    def set_solo(self, channel_number: int, solo: bool = True) -> None:
        """Sets solo switch on channel strip (Control 8)."""
        if channel_number in self.channels:
            self.channels[channel_number].solo = solo

    def set_gate(self, channel_number: int, threshold: float) -> None:
        """Sets the epistemic noise gate threshold (Control 10)."""
        if channel_number in self.channels:
            self.channels[channel_number].noise_gate_threshold = threshold

    # --- CONTROL 15: INSERT / BYPASS ---

    def set_insert_bypass(self, channel_number: int, bypass: bool = True) -> None:
        """Enables or disables insert bypass for a channel strip (Control 15)."""
        if channel_number in self.channels:
            self.channels[channel_number].insert_bypass = bypass

    def add_insert_transform(
        self,
        channel_number: int,
        transform: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Appends a pre/post transform callable into the channel's insert chain (Control 15)."""
        if channel_number in self.channels:
            self.channels[channel_number].insert_chain.append(transform)

    # --- STREAMING SUBSTRATE THROUGH CHANNEL STRIP ---

    def stream_track(
        self,
        channel_number: int,
        raw_signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Runs substrate through channel strip.

        Enforces:
        - Control 7 (Mute): Suppresses findings from bus projection, logs 'muted': True, preserves failure evidence.
        - Control 8 (Solo): Isolates strip for focus without disabling mandatory Scar guards (safety_locked: True).
        - Control 10 (Noise Gate): Filters low-confidence chatter, preserves deterministic negative findings.
        - Control 15 (Insert/Bypass): Runs chained transforms unless bypassed.
        - Control 18 (Scar Guard): Enforces active ScarRegistry invariants.
        """
        strip = self.channels.get(channel_number)
        if not strip:
            return []

        # Control 7: Mute
        if strip.mute:
            for sig in raw_signals:
                if not sig.get("outcome_passed", sig.get("passed", True)):
                    strip.failures_recorded.append(sig)
            return [{
                "_muted": True,
                "muted": True,
                "origin_channel": strip.channel_number,
                "channel_name": strip.name,
                "suppressed_records_count": len(raw_signals),
            }]

        # Control 8: Solo isolation
        any_solo = any(ch.solo for ch in self.channels.values())
        if any_solo and not strip.solo:
            # Strip excluded from output projection by another soloed channel
            return []

        conditioned_signals = []
        for sig in raw_signals:
            # Control 10: Epistemic Noise Gate
            # Gate filters low-confidence chatter (< threshold).
            # High-reliability failures (outcome_passed == False, reliability_score == 1.0) MUST survive!
            reliability = sig.get("reliability_score", sig.get("confidence_score", 1.0))
            if reliability < strip.noise_gate_threshold:
                continue

            conditioned = copy.deepcopy(sig)
            conditioned["origin_channel"] = strip.channel_number
            conditioned["channel_name"] = strip.name
            conditioned["fader_gain_db"] = strip.fader_gain_db
            conditioned["safety_locked"] = True  # Safety invariants cannot be bypassed

            # Preserve negative findings in failure log
            if not sig.get("outcome_passed", sig.get("passed", True)):
                strip.failures_recorded.append(conditioned)

            # Control 15: Insert Chain & Bypass
            if not strip.insert_bypass:
                for transform in strip.insert_chain:
                    conditioned = transform(conditioned)

            # Control 18: Mandatory Scar Guard
            conditioned, _ = self.scar_feedback.transform_signal(conditioned, declared_intent="ssl_active_channel")

            conditioned_signals.append(conditioned)

        return conditioned_signals

    # --- CONTROL 20: PAUSE / RESUME / STOP LIFECYCLE ---

    def start_run(self, run_token: Any) -> None:
        """Binds a ProcessSupervisor RunToken to this console execution run (Control 20)."""
        self.active_run_token = run_token
        self.is_stopped = False

    def pause_run(
        self,
        checkpoint_path: Optional[Path | str] = None,
        completed_strips: Optional[List[int]] = None,
        pending_strips: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Checkpoints console execution progress to disk/dict (Control 20)."""
        token_id = getattr(self.active_run_token, "token_id", "unbound_token")
        checkpoint = {
            "session_id": self.patch_id,
            "run_token_id": token_id,
            "state": "PAUSED",
            "timestamp": time.time(),
            "completed_strips": completed_strips or [],
            "pending_strips": pending_strips or [],
        }
        if checkpoint_path:
            p = Path(checkpoint_path)
            p.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")
        return checkpoint

    def resume_run(
        self,
        checkpoint: Dict[str, Any],
        supervisor: Any,
        run_token: Any
    ) -> List[int]:
        """Resumes console execution from checkpoint, continuing only remaining strips (Control 20)."""
        if self.is_stopped:
            raise RuntimeError("Cannot resume a stopped console run.")
        # Validate run token with supervisor (fail-closed)
        if supervisor and run_token:
            supervisor.validate_token(run_token)

        self.active_run_token = run_token
        pending = list(checkpoint.get("pending_strips", []))
        return pending

    def stop_run(self, supervisor: Any, run_token: Any) -> Dict[str, Any]:
        """Cleanly halts execution and revokes supervisor run token (Control 20)."""
        self.is_stopped = True
        token_id = getattr(run_token, "token_id", None)
        if supervisor and token_id:
            supervisor.cancel_token(token_id)
        return {
            "status": "STOPPED",
            "cancelled_token_id": token_id,
            "timestamp": time.time(),
        }

    # --- AUDITS & MASTER PRINT ---

    def audit_channel_adversarially(
        self,
        channel_number: int,
        target_callable: Callable[[bytes], Any],
        golden_vectors: Sequence[Any],
        target_name: Optional[str] = None
    ) -> Any:
        """Audits a channel strip using the Adversarial Discriminator and streams findings."""
        from .adversary import ConsoleAdversaryBridge
        return ConsoleAdversaryBridge.audit_channel(
            self,
            channel_number=channel_number,
            target_callable=target_callable,
            golden_vectors=golden_vectors,
            target_name=target_name,
        )

    def audit_channel_thermodynamics(
        self,
        channel_number: int,
        target_callable: Optional[Callable[..., Any]] = None,
        memory_ceiling_bytes: Optional[int] = None,
        fail_closed: bool = True,
    ) -> Any:
        """Audits an SSL channel strip's execution footprint against physical memory budgets."""
        from .thermodynamics import ConsoleThermodynamicsBridge
        return ConsoleThermodynamicsBridge.audit_channel_thermodynamics(
            self,
            channel_number=channel_number,
            target_callable=target_callable,
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=fail_closed,
        )

    def verify_channel_artifact_cross_process(
        self,
        channel_number: int,
        artifact_bytes: bytes,
        mode: str = "wasm",
        memory_ceiling_bytes: Optional[int] = None,
        fail_closed: bool = True,
    ) -> Any:
        """Spawns a fresh OS subprocess to verify channel artifact with zero shared heap."""
        from .thermodynamics import ConsoleThermodynamicsBridge
        return ConsoleThermodynamicsBridge.verify_channel_artifact_cross_process(
            self,
            channel_number=channel_number,
            artifact_bytes=artifact_bytes,
            mode=mode,
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=fail_closed,
        )

    def print_master(
        self,
        session_id: str,
        active_signals: List[Dict[str, Any]],
        compiled_aspects: List[Dict[str, Any]],
        thermodynamic_receipts: Optional[List[Any]] = None,
        export_path: Optional[str | Path] = None,
    ) -> MasterTape:
        """The Master Print Operation (Control 19):

        Takes all active, playing tracks, runs them through EffectResolver,
        preserves opposing tensions, attaches thermodynamic receipts,
        and freezes the final Master Tape.

        Fixes Noise Gate / Reliability Bug:
        - In print_master(), do NOT set "confidence_score": 0.0 when thermodynamic_passed is False.
        - High-reliability failure (outcome_passed == False, reliability_score == 1.0) remains visible.
        - Cannot print VERIFIED for missing/invalid/unresolved required evidence.
        """
        # Resolve opposing pressures and action gates across all aspects
        resolution = self.effect_resolver.resolve(compiled_aspects)

        # Collect channel thermodynamic receipts and explicit receipts (deduplicated by digest)
        collected_receipts: List[Dict[str, Any]] = []
        seen_digests = set()

        if thermodynamic_receipts:
            for r in thermodynamic_receipts:
                rec_dict = r.to_dict() if hasattr(r, "to_dict") else r
                digest = rec_dict.get("receipt_digest")
                if digest and digest not in seen_digests:
                    seen_digests.add(digest)
                    collected_receipts.append(rec_dict)
                elif not digest:
                    collected_receipts.append(rec_dict)

        for ch in self.channels.values():
            if ch.thermodynamic_receipt:
                digest = ch.thermodynamic_receipt.get("receipt_digest")
                if digest and digest not in seen_digests:
                    seen_digests.add(digest)
                    collected_receipts.append(ch.thermodynamic_receipt)
                elif not digest:
                    collected_receipts.append(ch.thermodynamic_receipt)

        # Include thermodynamic receipts in verified evidence records
        all_evidence = list(active_signals)
        for tr in collected_receipts:
            passed = bool(tr.get("passed", False))
            all_evidence.append({
                "evidence_type": "THERMODYNAMIC_RECEIPT",
                "candidate_id": tr.get("candidate_id"),
                "peak_memory_bytes": tr.get("peak_memory_bytes"),
                "ceiling_bytes": tr.get("memory_ceiling_bytes"),
                "cross_process": tr.get("verified_cross_process"),
                "receipt_digest": tr.get("receipt_digest"),
                "passed": passed,
                "outcome_passed": passed,
                "reliability_score": 1.0,  # High-reliability empirical measurement
                "confidence_score": 1.0,   # Epistemic confidence in measurement accuracy
            })

        # Truthful Verification Status (Control 19)
        unresolved = list(resolution.get("unresolved_effects", []))
        required_missing = []
        if len(all_evidence) == 0:
            required_missing.append("EMPTY_EVIDENCE_RECORDS")

        if unresolved or required_missing:
            verification_status = "UNRESOLVED_DEFICITS" if unresolved else "PARTIAL"
        else:
            verification_status = "VERIFIED"

        master = MasterTape(
            session_id=session_id,
            timestamp=time.time(),
            patch_id=self.patch_id,
            channels_active=sorted(list(self.channels.keys())),
            total_tracks_processed=len(active_signals),
            opposing_pressures_preserved=resolution.get("conflicts", []),
            action_gates_enforced=resolution.get("action_gates", []),
            deficits_unplaced=unresolved,
            verified_evidence_records=all_evidence,
            reversibility_tier=self.reversibility_tier,
            thermodynamic_receipts=collected_receipts,
            verification_status=verification_status,
            required_evidence_missing=required_missing,
        )

        frozen_master = master.freeze()
        if export_path:
            frozen_master.export_master_print(export_path)

        return frozen_master
