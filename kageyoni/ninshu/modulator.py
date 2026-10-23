"""The Substrate Modulator Engine (Reverse-Engineered from REA Domain Projections).

Reverse-Engineered Primitives:
1. Projection Filter: Bounded Cartesian candidate projection with JSON byte quotas.
2. Predicate Transducer: Shifts predicate_type across observation domains (Control 13).
3. Carrier Attenuator: Modulates between static representation, in-memory execution, and transport.
4. Epistemic Phase Modulator: Adjusts confidence between observed, derived, and inferred.
5. Viscosity Compressor: Bounded loss-aware projection folding repeated records with SHA-256 evidence pointers (Control 14).
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class PredicateTransductionError(ValueError):
    """Raised when an invalid predicate transformation or static-as-dynamic relabelling is attempted."""
    pass


@dataclass
class ModulatorDialSetting:
    """The real-time modulation state governing streaming liquid metal."""
    bandwidth_quota_bytes: int = 1048576       # Default 1MB per projection window
    predicate_lens: str = "structural_ast"     # "structural_ast", "dynamic_call_flow", "protocol_trace"
    viscosity_attenuation: float = 1.0         # 1.0 = raw stream, 0.1 = high-density condensed summary
    epistemic_grade: str = "derived"           # "observed", "derived", "inferred"
    phase_shift_deg: float = 0.0               # Phase angle adjustment (-180 to +180)


def validate_predicate_observation(record: Dict[str, Any], requested_lens: str) -> Tuple[bool, str]:
    """Validates whether a record satisfies the observation contract for the requested lens (Control 13).

    Crucial invariant: Relabelling static data as dynamic execution without runtime proof fails.
    """
    if requested_lens == "dynamic_call_flow":
        # Static claims without dynamic runtime proof cannot be relabelled as dynamic
        is_static = record.get("is_static", False) or record.get("mode") == "static"
        has_runtime_trace = bool(
            record.get("trace") or record.get("runtime_events") or
            record.get("call_stack") or record.get("pid")
        )
        if is_static and not has_runtime_trace:
            return False, "RELABELLING_STATIC_AS_DYNAMIC_PROHIBITED"

    # Verify lens family compatibility if specified in record
    rec_lens = record.get("predicate_family", record.get("lens_family"))
    if rec_lens and requested_lens != "all" and rec_lens != requested_lens:
        return False, f"PREDICATE_FAMILY_MISMATCH: record is '{rec_lens}', requested '{requested_lens}'"

    return True, "VALID"


class SubstrateModulator:
    """The active modulator governing the shape, velocity, and density of liquid metal."""

    def __init__(self, initial_dials: Optional[ModulatorDialSetting] = None):
        self.dials = initial_dials or ModulatorDialSetting()
        self.total_bytes_transduced = 0
        self.modulation_cycles = 0
        # Lossless raw evidence registry keyed by SHA-256 digest
        self.raw_evidence_store: Dict[str, Dict[str, Any]] = {}

    def set_predicate(self, predicate_lens: str) -> str:
        """Transmutes the perceptual lens through which the substrate is viewed (Control 13)."""
        self.dials.predicate_lens = predicate_lens
        return self.dials.predicate_lens

    def set_viscosity(self, attenuation: float) -> float:
        """Modulates the viscosity (density) of the liquid metal (Control 14)."""
        self.dials.viscosity_attenuation = max(0.01, min(1.0, float(attenuation)))
        return self.dials.viscosity_attenuation

    def filter_by_predicate(
        self,
        records: List[Dict[str, Any]],
        predicate_lens: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Restricts extraction/stream to selected predicate families (Control 13).

        Fails closed if static data is fraudulently relabelled as dynamic.
        """
        lens = predicate_lens or self.dials.predicate_lens
        if lens == "all" or not lens:
            return list(records)

        filtered = []
        for r in records:
            valid, reason = validate_predicate_observation(r, lens)
            if not valid:
                if reason == "RELABELLING_STATIC_AS_DYNAMIC_PROHIBITED":
                    raise PredicateTransductionError(
                        f"Cannot observe static candidate under '{lens}': relabelling static as dynamic prohibited."
                    )
                continue
            item = copy.deepcopy(r)
            item["predicate_lens"] = lens
            filtered.append(item)

        return filtered

    def compress_stream(
        self,
        records: List[Dict[str, Any]],
        viscosity_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """Bounded loss-aware projection (Control 14).

        When viscosity < 1.0: Folds repeated records into canonical summaries
        while preserving lossless SHA-256 raw evidence pointers.
        When viscosity == 1.0: Passes records at full fidelity without folding.
        """
        ratio = self.dials.viscosity_attenuation if viscosity_ratio is None else max(0.01, min(1.0, float(viscosity_ratio)))

        # Register raw records in lossless storage
        raw_digests = []
        for r in records:
            raw_bytes = json.dumps(r, sort_keys=True, ensure_ascii=False).encode("utf-8")
            digest = hashlib.sha256(raw_bytes).hexdigest()
            self.raw_evidence_store[digest] = copy.deepcopy(r)
            raw_digests.append(digest)

        if ratio >= 1.0:
            return {
                "records": list(records),
                "is_compressed": False,
                "viscosity_ratio": 1.0,
                "total_records": len(records),
                "folded_count": 0,
                "raw_evidence_pointers": raw_digests,
            }

        # Loss-aware folding for repeated or redundant records
        groups: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
        for r, dig in zip(records, raw_digests):
            # Grouping key by structural fingerprint
            key = f"{r.get('type')}:{r.get('name')}:{r.get('predicate_type')}:{r.get('status')}"
            groups.setdefault(key, []).append((r, dig))

        folded_records: List[Dict[str, Any]] = []
        folded_count = 0

        for key, items in groups.items():
            if len(items) > 1:
                rep_record, first_dig = items[0]
                summary_record = copy.deepcopy(rep_record)
                item_digests = [d for _, d in items]
                summary_record["_canonical_summary"] = f"Folded {len(items)} occurrences of [{key}]"
                summary_record["_occurrence_count"] = len(items)
                summary_record["raw_evidence_pointer"] = first_dig
                summary_record["all_evidence_pointers"] = item_digests
                summary_record["lossless_pointer_retained"] = True
                summary_record["truncation_map"] = {
                    "original_count": len(items),
                    "folded_into": 1,
                    "representative_key": key,
                }
                folded_records.append(summary_record)
                folded_count += len(items) - 1
            else:
                rep_record, dig = items[0]
                rec_copy = copy.deepcopy(rep_record)
                rec_copy["raw_evidence_pointer"] = dig
                rec_copy["lossless_pointer_retained"] = True
                folded_records.append(rec_copy)

        return {
            "records": folded_records,
            "is_compressed": True,
            "viscosity_ratio": ratio,
            "total_records": len(records),
            "emitted_records": len(folded_records),
            "folded_count": folded_count,
            "raw_evidence_pointers": raw_digests,
            "coverage_status": "complete" if folded_count == 0 else "partial",
        }

    def get_raw_evidence(self, pointer: str) -> Optional[Dict[str, Any]]:
        """Retrieves raw evidence record by its lossless SHA-256 pointer."""
        return self.raw_evidence_store.get(pointer)

    def modulate_stream(
        self,
        raw_stream: List[Dict[str, Any]],
        predicate_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Passes incoming substrate through projection algorithm, enforcing byte budget and predicate transduction."""
        lens = predicate_type or self.dials.predicate_lens
        budget = self.dials.bandwidth_quota_bytes
        attenuation = self.dials.viscosity_attenuation

        emitted: List[Dict[str, Any]] = []
        accumulated_bytes = 2 # JSON array overhead
        omitted_count = 0

        for item in raw_stream:
            # Apply predicate lens
            projected = copy.deepcopy(item)
            projected["predicate_type"] = f"rea.projection.{lens}"
            projected["_epistemic_grade"] = self.dials.epistemic_grade
            projected["_phase_deg"] = self.dials.phase_shift_deg

            # Apply viscosity condensation if required
            if attenuation < 1.0:
                for k, v in list(projected.items()):
                    if isinstance(v, str) and len(v) > int(200 * attenuation):
                        limit = max(20, int(len(v) * attenuation))
                        projected[k] = v[:limit] + "...[CONDENSED]"

            item_bytes = len(json.dumps(projected, ensure_ascii=False).encode("utf-8"))
            if accumulated_bytes + item_bytes > budget:
                omitted_count += 1
                continue

            emitted.append(projected)
            accumulated_bytes += item_bytes + 1

        self.total_bytes_transduced += accumulated_bytes
        self.modulation_cycles += 1

        return {
            "projection_metadata": {
                "predicate_lens": lens,
                "coverage_status": "complete" if omitted_count == 0 else "partial",
                "total_candidates": len(raw_stream),
                "emitted_candidates": len(emitted),
                "omitted_candidates": omitted_count,
                "retained_bytes": accumulated_bytes,
                "viscosity_ratio": attenuation,
            },
            "payload": emitted,
            "digest_sha256": hashlib.sha256(json.dumps(emitted, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        }
