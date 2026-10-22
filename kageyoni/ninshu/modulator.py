"""The Substrate Modulator Engine (Reverse-Engineered from REA Domain Projections).

Reverse-Engineered Primitives:
1. Projection Filter: Bounded Cartesian candidate projection with JSON byte quotas.
2. Predicate Transducer: Shifts predicate_type across observation domains.
3. Carrier Attenuator: Modulates between static representation, in-memory execution, and transport.
4. Epistemic Phase Modulator: Adjusts confidence between observed, derived, and inferred.
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


@dataclass
class ModulatorDialSetting:
    """The real-time modulation state governing streaming liquid metal."""
    bandwidth_quota_bytes: int = 1048576       # Default 1MB per projection window
    predicate_lens: str = "structural_ast"     # "structural_ast", "dynamic_call_flow", "protocol_trace"
    viscosity_attenuation: float = 1.0         # 1.0 = raw stream, 0.1 = high-density condensed summary
    epistemic_grade: str = "derived"           # "observed", "derived", "inferred"
    phase_shift_deg: float = 0.0               # Phase angle adjustment (-180 to +180)


class SubstrateModulator:
    """The active modulator governing the shape, velocity, and density of liquid metal."""

    def __init__(self, initial_dials: Optional[ModulatorDialSetting] = None):
        self.dials = initial_dials or ModulatorDialSetting()
        self.total_bytes_transduced = 0
        self.modulation_cycles = 0

    def set_predicate(self, predicate_lens: str) -> str:
        """Transmutes the perceptual lens through which the substrate is viewed."""
        self.dials.predicate_lens = predicate_lens
        return self.dials.predicate_lens

    def set_viscosity(self, attenuation: float) -> float:
        """
        Modulates the viscosity (density) of the liquid metal:
        - 1.0: Full raw byte and symbol streaming.
        - 0.5: Removes formatting overhead and structural whitespace.
        - 0.1: Highly condensed state representations (essential for large LLM contexts).
        """
        self.dials.viscosity_attenuation = max(0.01, min(1.0, float(attenuation)))
        return self.dials.viscosity_attenuation

    def modulate_stream(
        self,
        raw_stream: List[Dict[str, Any]],
        predicate_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Passes incoming substrate through the REA-derived projection algorithm:
        Enforces byte budget, applies predicate transduction, and condenses payload.
        """
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

            item_bytes = len(json.dumps(projected).encode("utf-8"))
            if accumulated_bytes + item_bytes > budget:
                omitted_count += 1
                continue

            emitted.append(projected)
            accumulated_bytes += item_bytes + 1

        self.total_bytes_transduced += accumulated_bytes
        self.modulation_cycles += 1

        # Emit the modulated projection bundle (Reverse-Engineered from bridgeCandidateProjection.ts)
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
            "digest_sha256": hashlib.sha256(json.dumps(emitted, sort_keys=True).encode("utf-8")).hexdigest()
        }
