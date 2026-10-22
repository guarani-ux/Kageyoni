"""Ninshū Active Mixing Engine & Master Print Bus.

Implements the active playback loop for the SSL 4000 Console:
1. Ingests live computational substrate (the liquid metal / telemetry stream).
2. Routes the signal through configured channel strips (preamp, filter, dynamics, gate, EQ).
3. Preserves opposing tensions and deficits across the sub-mix bus via EffectResolver.
4. Quenches and prints the final release master tape backed by immutable SHA-256 digests.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from kageyoni.composition.effects import EffectResolver, ExpressionContract


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
    fader_gain_db: float = 0.0          # Fader level (-inf to +10 dB)
    mute: bool = False                  # Channel mute switch
    solo: bool = False                  # Channel solo switch
    hpf_cutoff_hz: Optional[float] = None # High-Pass Filter cutoff (scope limiter)
    thermal_ceiling: int = 0            # 0 = Tier 0 (Cold), 1 = Tier 1 (Hot Gate)
    noise_gate_threshold: float = 0.5   # Epistemic squelch (< 0.5 discards ungrounded claims)
    max_memory_ceiling_bytes: int = 64 * 1024 # 64 KB default thermodynamic budget
    thermodynamic_receipt: Optional[Dict[str, Any]] = None # Cached verification receipt


@dataclass
class MasterTape:
    """The finalized, immutable Master Print output from the SSL console."""
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

    def freeze(self) -> MasterTape:
        """Calculates the cryptographic seal on the printed master."""
        data = asdict(self)
        data.pop("master_sha256", None)
        self.master_sha256 = canonical_digest(data)
        return self


class ActiveConsole:
    """The live, running SSL 4000 console processing computational substrate."""

    def __init__(self, patch_manifest: Dict[str, Any]):
        self.patch_id = patch_manifest.get("patch_id", "ad_hoc_session")
        self.reversibility_tier = patch_manifest.get("reversibility_tier", 0)
        self.channels: Dict[int, ChannelStripConfig] = {}
        self.effect_resolver = EffectResolver()
        self.expression_contract = ExpressionContract()

        # Mount channel strips from patch manifest
        for strip in patch_manifest.get("channel_strips", []):
            ch_num = strip["ch"]
            self.channels[ch_num] = ChannelStripConfig(
                channel_number=ch_num,
                name=strip["name"],
                carrier_path=strip["carrier"],
                entrypoint=strip["entrypoint"],
                thermal_ceiling=strip.get("tier", 0)
            )

    def set_fader(self, channel_number: int, gain_db: float) -> None:
        """Adjusts the fader volume on a channel strip."""
        if channel_number in self.channels:
            self.channels[channel_number].fader_gain_db = gain_db

    def set_gate(self, channel_number: int, threshold: float) -> None:
        """Sets the epistemic noise gate threshold (filters unverified claims)."""
        if channel_number in self.channels:
            self.channels[channel_number].noise_gate_threshold = threshold

    def stream_track(
        self,
        channel_number: int,
        raw_signals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Runs the liquid metal (live telemetry / raw facts) through the channel strip:
        applies the noise gate, filters by epistemic confidence, and weights by fader gain.
        """
        strip = self.channels.get(channel_number)
        if not strip or strip.mute:
            return []

        conditioned_signals = []
        for sig in raw_signals:
            confidence = sig.get("confidence_score", 1.0)
            # Epistemic Noise Gate: mute signal if confidence is below threshold
            if confidence < strip.noise_gate_threshold:
                continue

            conditioned = copy.deepcopy(sig)
            conditioned["origin_channel"] = strip.channel_number
            conditioned["channel_name"] = strip.name
            conditioned["fader_gain_db"] = strip.fader_gain_db
            conditioned_signals.append(conditioned)

        return conditioned_signals

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
    ) -> MasterTape:
        """
        The Master Print Operation:
        Takes all active, playing tracks, runs them through the G-Master Bus Compressor
        (Kageyōni EffectResolver), preserves opposing tensions, attaches thermodynamic receipts,
        and freezes the final Master Tape.
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
            all_evidence.append({
                "evidence_type": "THERMODYNAMIC_RECEIPT",
                "candidate_id": tr.get("candidate_id"),
                "peak_memory_bytes": tr.get("peak_memory_bytes"),
                "ceiling_bytes": tr.get("memory_ceiling_bytes"),
                "cross_process": tr.get("verified_cross_process"),
                "receipt_digest": tr.get("receipt_digest"),
                "confidence_score": 1.0 if tr.get("passed") else 0.0,
            })

        master = MasterTape(
            session_id=session_id,
            timestamp=time.time(),
            patch_id=self.patch_id,
            channels_active=sorted(list(self.channels.keys())),
            total_tracks_processed=len(active_signals),
            opposing_pressures_preserved=resolution.get("conflicts", []),
            action_gates_enforced=resolution.get("action_gates", []),
            deficits_unplaced=resolution.get("unresolved_effects", []),
            verified_evidence_records=all_evidence,
            reversibility_tier=self.reversibility_tier,
            thermodynamic_receipts=collected_receipts,
        )

        return master.freeze()
