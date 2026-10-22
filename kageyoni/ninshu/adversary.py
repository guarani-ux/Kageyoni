"""Ninshū Invariant Discriminator & Adversarial Scar Injector.

Connects adversarial stress testing and active failure resistance directly to the SSL 4000 Console:
1. Invariant Discriminator Engine: Executes golden test vectors and deterministically
   generates adversarial mutants (truncated bytes, boundary overflows, bit flips, malformed headers).
2. Metamorphic Discrimination Verification: Asserts positive acceptance of valid contracts
   and strict, fail-closed negative rejection of malformed payloads.
3. Zenkai Scar Binding: When a component fails to cleanly discriminate (e.g. silently accepts
   corrupted inputs, crashes unhandled, or rejects valid vectors), registers an active
   ScarImpedanceTransformer in SCAR_REGISTRY, electrically reconfiguring the SSL console.
4. SSL Console Interconnect: Bridges adversarial audit telemetry directly into ActiveConsole
   and SSLMixingSession channel strips, elevating thermal ceilings and preserving audit evidence.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from .scars import SCAR_REGISTRY, ScarImpedanceTransformer, ScarRegistry


class MutationType(str, Enum):
    """Classification of adversarial mutation strategies."""
    TRUNCATION = "TRUNCATION"
    BIT_FLIP = "BIT_FLIP"
    BOUNDARY_OVERFLOW = "BOUNDARY_OVERFLOW"
    MALFORMED_HEADER = "MALFORMED_HEADER"
    CONTROL_BYTE_INJECTION = "CONTROL_BYTE_INJECTION"


class DiscriminationDisposition(str, Enum):
    """Disposition of a single vector execution through the discriminator."""
    ACCEPTED = "ACCEPTED"
    CLEAN_REJECTION = "CLEAN_REJECTION"
    SILENT_ACCEPTANCE_FAILURE = "SILENT_ACCEPTANCE_FAILURE"
    UNHANDLED_CRASH = "UNHANDLED_CRASH"
    FALSE_NEGATIVE_FAILURE = "FALSE_NEGATIVE_FAILURE"
    ATTRIBUTE_MISMATCH = "ATTRIBUTE_MISMATCH"


@dataclasses.dataclass(frozen=True)
class GoldenVector:
    """A verified golden test vector asserting positive contract acceptance."""
    vector_id: str
    payload: bytes
    description: str
    expected_attributes: Optional[Dict[str, Any]] = None


@dataclasses.dataclass(frozen=True)
class AdversarialMutant:
    """A mutated adversarial payload asserting strict, fail-closed negative rejection."""
    mutant_id: str
    mutation_type: MutationType
    payload: bytes
    description: str
    source_vector_id: str
    expected_clean_exceptions: Tuple[type, ...] = (ValueError, TypeError)


@dataclasses.dataclass
class VectorExecutionResult:
    """Result of exercising a single golden vector or adversarial mutant."""
    vector_id: str
    is_positive: bool
    passed: bool
    disposition: DiscriminationDisposition
    payload_hex: str
    mutation_type: Optional[str] = None
    exception_class: Optional[str] = None
    exception_message: Optional[str] = None
    scar_id: Optional[str] = None
    message: str = ""
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "is_positive": self.is_positive,
            "passed": self.passed,
            "disposition": self.disposition.value,
            "payload_hex": self.payload_hex,
            "mutation_type": self.mutation_type,
            "exception_class": self.exception_class,
            "exception_message": self.exception_message,
            "scar_id": self.scar_id,
            "message": self.message,
            "details": self.details,
        }


@dataclasses.dataclass
class DiscriminationReport:
    """Complete discrimination audit report across golden vectors and adversarial mutants."""
    target_name: str
    total_vectors_tested: int
    positive_vectors_count: int
    negative_vectors_count: int
    passed_count: int
    failed_count: int
    all_passed: bool
    scars_registered: List[str]
    results: List[VectorExecutionResult]
    audit_digest: str = ""

    def __post_init__(self) -> None:
        if not self.audit_digest:
            raw = f"{self.target_name}:{self.total_vectors_tested}:{self.passed_count}:{self.failed_count}"
            self.audit_digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_name": self.target_name,
            "total_vectors_tested": self.total_vectors_tested,
            "positive_vectors_count": self.positive_vectors_count,
            "negative_vectors_count": self.negative_vectors_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "all_passed": self.all_passed,
            "scars_registered": self.scars_registered,
            "audit_digest": self.audit_digest,
            "results": [r.to_dict() for r in self.results],
        }


class AdversarialMutator:
    """Pure Python stdlib generator of deterministic adversarial mutants."""

    @classmethod
    def mutate_truncations(
        cls,
        data: bytes,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Generates truncated slices from 0 bytes up to len - 1."""
        mutants: List[AdversarialMutant] = []
        n = len(data)

        # 0 bytes (empty)
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-TRUNC-0",
                mutation_type=MutationType.TRUNCATION,
                payload=b"",
                description="Zero-length truncated empty payload",
                source_vector_id=source_id,
            )
        )

        # Key truncation boundaries: must avoid cutting exactly at full header boundary (8 bytes)
        # because an 8-byte header alone is a valid empty module.
        step_offsets: Set[int] = set()
        if n > 1:
            step_offsets.add(1)
        if n > 2:
            step_offsets.add(2)
        if n > 4:
            step_offsets.add(4)
        if n > 7:
            step_offsets.add(7)
        if n > 9:
            step_offsets.add(9)
        if n > 2 and (n // 2) != 8:
            step_offsets.add(n // 2)
        if n > 1 and (n - 1) != 8:
            step_offsets.add(n - 1)

        for off in sorted(step_offsets):
            mutants.append(
                AdversarialMutant(
                    mutant_id=f"{source_id}-TRUNC-{off}",
                    mutation_type=MutationType.TRUNCATION,
                    payload=data[:off],
                    description=f"Truncated at offset {off} of {n} bytes",
                    source_vector_id=source_id,
                )
            )

        return mutants

    @classmethod
    def mutate_bit_flips(
        cls,
        data: bytes,
        sample_limit: int = 8,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Flips deterministic bits at header and payload boundaries."""
        if not data:
            return []

        mutants: List[AdversarialMutant] = []
        target_positions = [0, 1, 2, 3] if len(data) >= 4 else list(range(len(data)))
        if len(data) > 4:
            target_positions.append(4)
        if len(data) > 7:
            target_positions.append(7)
        if len(data) > 8:
            target_positions.append(len(data) - 1)

        count = 0
        for pos in target_positions:
            for bit in (0, 7):
                if count >= sample_limit:
                    break
                flipped = bytearray(data)
                flipped[pos] ^= (1 << bit)
                mutants.append(
                    AdversarialMutant(
                        mutant_id=f"{source_id}-BITFLIP-P{pos}-B{bit}",
                        mutation_type=MutationType.BIT_FLIP,
                        payload=bytes(flipped),
                        description=f"Bit {bit} flipped at byte index {pos}",
                        source_vector_id=source_id,
                    )
                )
                count += 1
            if count >= sample_limit:
                break

        return mutants

    @classmethod
    def mutate_boundary_overflows(
        cls,
        data: bytes,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Generates boundary overflows, multi-byte LEB128 overflows, and oversized payloads."""
        mutants: List[AdversarialMutant] = []

        # 1. Trailing junk / boundary overflow
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-OVERFLOW-JUNK-1K",
                mutation_type=MutationType.BOUNDARY_OVERFLOW,
                payload=data + (b"\xff" * 1024),
                description="Oversized payload trailing with 1024 0xFF bytes",
                source_vector_id=source_id,
            )
        )

        # 2. Oversized LEB128 sequence (> 5 bytes with continuation bit set)
        leb128_overflow = b"\x80\x80\x80\x80\x80\x80\x01"
        header = data[:8] if len(data) >= 8 else data
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-OVERFLOW-LEB128-6B",
                mutation_type=MutationType.BOUNDARY_OVERFLOW,
                payload=header + b"\x01" + leb128_overflow,
                description="Malformed section with 6-byte LEB128 integer overflow",
                source_vector_id=source_id,
            )
        )

        # 3. Truncated LEB128 integer sequence (continuation bit set without terminal byte)
        leb128_truncated = b"\x80\x80\x80"
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-OVERFLOW-LEB128-TRUNC",
                mutation_type=MutationType.BOUNDARY_OVERFLOW,
                payload=header + b"\x01" + leb128_truncated,
                description="Malformed section with truncated non-terminating LEB128 integer",
                source_vector_id=source_id,
            )
        )

        # 4. Truncated section payload (declared size exceeds stream)
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-OVERFLOW-SECTION-TRUNC",
                mutation_type=MutationType.BOUNDARY_OVERFLOW,
                payload=header + b"\x01\x7f\x00",
                description="Section declaring 127 bytes size with only 1 payload byte",
                source_vector_id=source_id,
            )
        )

        return mutants

    @classmethod
    def mutate_malformed_headers(
        cls,
        data: bytes,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Generates corrupted headers, foreign signatures (ELF, PE), and invalid versions."""
        mutants: List[AdversarialMutant] = []
        body = data[8:] if len(data) >= 8 else b""

        # 1. ELF Magic
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-ELF",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"\x7fELF\x01\x00\x00\x00" + body,
                description="Foreign ELF magic header (0x7F454C46)",
                source_vector_id=source_id,
            )
        )

        # 2. PE / DOS MZ Magic
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-PE",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"MZ\x90\x00\x03\x00\x00\x00" + body,
                description="Foreign PE/DOS MZ magic header (0x4D5A)",
                source_vector_id=source_id,
            )
        )

        # 3. All Zero Magic
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-ZERO",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"\x00\x00\x00\x00\x01\x00\x00\x00" + body,
                description="Zeroed magic bytes",
                source_vector_id=source_id,
            )
        )

        # 4. All 0xFF Magic
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-0XFF",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"\xff\xff\xff\xff\x01\x00\x00\x00" + body,
                description="All 0xFF corrupted magic bytes",
                source_vector_id=source_id,
            )
        )

        # 5. Unsupported Version 0
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-VER-0",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"\x00asm\x00\x00\x00\x00" + body,
                description="Valid magic with unsupported version 0",
                source_vector_id=source_id,
            )
        )

        # 6. Unsupported Version 2
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-VER-2",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"\x00asm\x02\x00\x00\x00" + body,
                description="Valid magic with unsupported version 2",
                source_vector_id=source_id,
            )
        )

        # 7. Inverted Magic
        mutants.append(
            AdversarialMutant(
                mutant_id=f"{source_id}-HDR-INVERT",
                mutation_type=MutationType.MALFORMED_HEADER,
                payload=b"msa\x00\x01\x00\x00\x00" + body,
                description="Reversed magic bytes ('msa\\0')",
                source_vector_id=source_id,
            )
        )

        return mutants

    @classmethod
    def mutate_control_bytes(
        cls,
        data: bytes,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Injects non-printable ASCII control characters."""
        mutants: List[AdversarialMutant] = []
        if len(data) >= 8:
            corrupted = bytearray(data)
            # inject null byte and control character in middle of payload
            corrupted.insert(8, 0x00)
            corrupted.insert(9, 0x1F)
            mutants.append(
                AdversarialMutant(
                    mutant_id=f"{source_id}-CTRL-CHARS",
                    mutation_type=MutationType.CONTROL_BYTE_INJECTION,
                    payload=bytes(corrupted),
                    description="Injected ASCII control bytes (0x00, 0x1F) past header",
                    source_vector_id=source_id,
                )
            )
        return mutants

    @classmethod
    def generate_adversarial_suite(
        cls,
        data: bytes,
        source_id: str = "src"
    ) -> List[AdversarialMutant]:
        """Assembles a full deterministic suite of adversarial variations."""
        suite: List[AdversarialMutant] = []
        suite.extend(cls.mutate_truncations(data, source_id=source_id))
        suite.extend(cls.mutate_bit_flips(data, source_id=source_id))
        suite.extend(cls.mutate_boundary_overflows(data, source_id=source_id))
        suite.extend(cls.mutate_malformed_headers(data, source_id=source_id))
        suite.extend(cls.mutate_control_bytes(data, source_id=source_id))

        # Deduplicate payloads while preserving order
        seen_payloads: Set[bytes] = set()
        deduped: List[AdversarialMutant] = []
        for m in suite:
            if m.payload not in seen_payloads:
                seen_payloads.add(m.payload)
                deduped.append(m)
        return deduped


class ScarInjector:
    """Forges and registers operational impedance scars in SCAR_REGISTRY."""

    @staticmethod
    def bind_scar(
        target_name: str,
        failure_class: str,
        root_cause: str,
        learned_rule: str,
        trigger_pattern: str,
        functional_adaptation: str,
        registry: Optional[ScarRegistry] = None,
        damping_factor: float = 1.0,
        reversibility_barrier: int = 1
    ) -> ScarImpedanceTransformer:
        """
        Forges an active ScarImpedanceTransformer and registers it in SCAR_REGISTRY.
        Electrically converts the runtime failure into an internal impedance circuit.
        """
        active_registry = registry if registry is not None else SCAR_REGISTRY
        hash_seed = f"{target_name}:{failure_class}:{root_cause}"
        digest_hex = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:8].upper()
        scar_id = f"SCAR-ADV-{target_name.upper().replace(' ', '_')}-{digest_hex}"

        scar = ScarImpedanceTransformer(
            scar_id=scar_id,
            failure_class=failure_class,
            root_cause=root_cause,
            learned_rule=learned_rule,
            trigger_pattern=trigger_pattern.lower(),
            damping_factor=damping_factor,
            reversibility_barrier=reversibility_barrier,
            functional_adaptation=functional_adaptation,
        )

        active_registry.register(scar)
        return scar


class AdversarialDiscriminator:
    """The Ninshū Invariant Discriminator Engine.

    Exercises golden vectors and dynamically synthesizes adversarial variations.
    Enforces dual-ended verification:
      1. Positive Acceptance: valid golden contracts MUST execute cleanly.
      2. Negative Discrimination: adversarial mutants MUST fail-closed with clean domain errors.
    Any violation immediately binds an active Scar in SCAR_REGISTRY.
    """

    def __init__(
        self,
        target_callable: Callable[[bytes], Any],
        target_name: Optional[str] = None,
        expected_clean_exceptions: Tuple[type, ...] = (ValueError, TypeError, KeyError),
        registry: Optional[ScarRegistry] = None
    ):
        self.target_callable = target_callable
        self.target_name = target_name or getattr(target_callable, "__name__", "unknown_component")
        self.expected_clean_exceptions = expected_clean_exceptions
        self.registry = registry if registry is not None else SCAR_REGISTRY

    def discriminate(
        self,
        golden_vectors: Sequence[Union[GoldenVector, bytes, Any]],
        custom_mutants: Optional[Sequence[AdversarialMutant]] = None
    ) -> DiscriminationReport:
        """
        Runs the full metamorphic discrimination cycle across golden vectors and mutants.
        """
        results: List[VectorExecutionResult] = []
        scars_registered: List[str] = []

        # 1. Normalize and test Golden Vectors (Positive Acceptance)
        normalized_goldens: List[GoldenVector] = []
        for idx, g in enumerate(golden_vectors):
            if isinstance(g, GoldenVector):
                normalized_goldens.append(g)
            elif isinstance(g, bytes):
                normalized_goldens.append(
                    GoldenVector(
                        vector_id=f"GOLDEN-{idx:02d}",
                        payload=g,
                        description=f"Raw golden byte vector {idx}",
                    )
                )
            elif hasattr(g, "input_bytes_hex") and hasattr(g, "expect_success"):
                # Compat with planner.TestVector
                if getattr(g, "expect_success"):
                    normalized_goldens.append(
                        GoldenVector(
                            vector_id=getattr(g, "vector_id", f"GOLDEN-{idx:02d}"),
                            payload=bytes.fromhex(getattr(g, "input_bytes_hex")),
                            description=getattr(g, "description", ""),
                            expected_attributes=getattr(g, "expected_attributes", None),
                        )
                    )
            else:
                raise TypeError(f"Unsupported golden vector type: {type(g)}")

        for golden in normalized_goldens:
            res = self._execute_golden_vector(golden)
            results.append(res)
            if not res.passed and res.scar_id:
                scars_registered.append(res.scar_id)

        # 2. Synthesize Adversarial Mutants from Golden Vectors
        all_mutants: List[AdversarialMutant] = []
        for golden in normalized_goldens:
            all_mutants.extend(
                AdversarialMutator.generate_adversarial_suite(
                    golden.payload,
                    source_id=golden.vector_id
                )
            )

        if custom_mutants:
            all_mutants.extend(custom_mutants)

        # Also support negative test vectors from planner.TestVector if passed
        for idx, g in enumerate(golden_vectors):
            if hasattr(g, "input_bytes_hex") and hasattr(g, "expect_success") and not getattr(g, "expect_success"):
                all_mutants.append(
                    AdversarialMutant(
                        mutant_id=getattr(g, "vector_id", f"MUT-PLAN-{idx:02d}"),
                        mutation_type=MutationType.MALFORMED_HEADER,
                        payload=bytes.fromhex(getattr(g, "input_bytes_hex")),
                        description=getattr(g, "description", "Explicit plan negative vector"),
                        source_vector_id="PLAN",
                    )
                )

        # 3. Test Adversarial Mutants (Strict Negative Rejection)
        for mutant in all_mutants:
            res = self._execute_adversarial_mutant(mutant)
            results.append(res)
            if not res.passed and res.scar_id:
                scars_registered.append(res.scar_id)

        passed_count = sum(1 for r in results if r.passed)
        failed_count = sum(1 for r in results if not r.passed)
        pos_count = len(normalized_goldens)
        neg_count = len(all_mutants)

        return DiscriminationReport(
            target_name=self.target_name,
            total_vectors_tested=len(results),
            positive_vectors_count=pos_count,
            negative_vectors_count=neg_count,
            passed_count=passed_count,
            failed_count=failed_count,
            all_passed=(failed_count == 0),
            scars_registered=scars_registered,
            results=results,
        )

    def _execute_golden_vector(self, golden: GoldenVector) -> VectorExecutionResult:
        """Executes a positive golden vector. Must succeed cleanly."""
        payload_hex = golden.payload.hex()
        try:
            output = self.target_callable(golden.payload)
            # Check expected attributes if specified
            if golden.expected_attributes:
                for key, val in golden.expected_attributes.items():
                    actual = getattr(output, key, None)
                    if actual != val:
                        scar = ScarInjector.bind_scar(
                            target_name=self.target_name,
                            failure_class="ATTRIBUTE_MISMATCH",
                            root_cause=f"Golden vector {golden.vector_id} attr {key} mismatch: expected {val}, got {actual}",
                            learned_rule=f"Component {self.target_name} must accurately project attribute {key}",
                            trigger_pattern=f"{self.target_name}|{key}|attribute_mismatch",
                            functional_adaptation=f"Add strict attribute invariant validator for {key}",
                            registry=self.registry,
                        )
                        return VectorExecutionResult(
                            vector_id=golden.vector_id,
                            is_positive=True,
                            passed=False,
                            disposition=DiscriminationDisposition.ATTRIBUTE_MISMATCH,
                            payload_hex=payload_hex,
                            scar_id=scar.scar_id,
                            message=f"Attribute mismatch: {key} expected {val}, got {actual}",
                            details={"output": repr(output)},
                        )

            return VectorExecutionResult(
                vector_id=golden.vector_id,
                is_positive=True,
                passed=True,
                disposition=DiscriminationDisposition.ACCEPTED,
                payload_hex=payload_hex,
                message=f"Golden vector accepted successfully: {golden.description}",
            )
        except Exception as exc:
            # False Negative: Golden contract was rejected
            scar = ScarInjector.bind_scar(
                target_name=self.target_name,
                failure_class="FALSE_NEGATIVE_REJECTION",
                root_cause=f"Golden valid vector {golden.vector_id} rejected with {type(exc).__name__}: {str(exc)}",
                learned_rule=f"Component {self.target_name} must accept valid contract {golden.description}",
                trigger_pattern=f"{self.target_name}|false_negative|golden_rejection",
                functional_adaptation="Repair parser ingress to accept conformant specifications.",
                registry=self.registry,
            )
            return VectorExecutionResult(
                vector_id=golden.vector_id,
                is_positive=True,
                passed=False,
                disposition=DiscriminationDisposition.FALSE_NEGATIVE_FAILURE,
                payload_hex=payload_hex,
                exception_class=type(exc).__name__,
                exception_message=str(exc),
                scar_id=scar.scar_id,
                message=f"False negative: valid input rejected with {type(exc).__name__}: {exc}",
            )

    def _execute_adversarial_mutant(self, mutant: AdversarialMutant) -> VectorExecutionResult:
        """Executes an adversarial mutant. Must fail-closed with clean domain exception."""
        payload_hex = mutant.payload.hex()
        try:
            output = self.target_callable(mutant.payload)
            # Silent acceptance failure! Corrupted mutant was accepted as valid!
            scar = ScarInjector.bind_scar(
                target_name=self.target_name,
                failure_class="SILENT_ACCEPTANCE_OF_MALFORMED_INPUT",
                root_cause=(
                    f"Component {self.target_name} silently accepted malformed mutant "
                    f"{mutant.mutant_id} ({mutant.mutation_type.value}): {mutant.description}"
                ),
                learned_rule=f"Component {self.target_name} must reject {mutant.mutation_type.value} inputs fail-closed.",
                trigger_pattern=f"{self.target_name}|silent_acceptance|{mutant.mutation_type.value.lower()}",
                functional_adaptation="Install strict fail-closed ingress validation boundary before parsing.",
                registry=self.registry,
            )
            return VectorExecutionResult(
                vector_id=mutant.mutant_id,
                is_positive=False,
                passed=False,
                disposition=DiscriminationDisposition.SILENT_ACCEPTANCE_FAILURE,
                payload_hex=payload_hex,
                mutation_type=mutant.mutation_type.value,
                scar_id=scar.scar_id,
                message=f"Silent acceptance of malformed input: {mutant.description}",
                details={"output": repr(output)},
            )
        except self.expected_clean_exceptions as clean_exc:
            # Clean domain rejection - test passed!
            return VectorExecutionResult(
                vector_id=mutant.mutant_id,
                is_positive=False,
                passed=True,
                disposition=DiscriminationDisposition.CLEAN_REJECTION,
                payload_hex=payload_hex,
                mutation_type=mutant.mutation_type.value,
                exception_class=type(clean_exc).__name__,
                exception_message=str(clean_exc),
                message=f"Cleanly rejected with {type(clean_exc).__name__}: {clean_exc}",
            )
        except Exception as crash_exc:
            # Unhandled crash! Raised unexpected exception (e.g. IndexError, ZeroDivisionError, etc.)
            scar = ScarInjector.bind_scar(
                target_name=self.target_name,
                failure_class="UNHANDLED_CRASH",
                root_cause=(
                    f"Component {self.target_name} crashed with unhandled {type(crash_exc).__name__} "
                    f"on mutant {mutant.mutant_id}: {str(crash_exc)}"
                ),
                learned_rule=f"Component {self.target_name} must not leak unhandled exceptions across the boundary.",
                trigger_pattern=f"{self.target_name}|unhandled_crash|{type(crash_exc).__name__.lower()}",
                functional_adaptation="Wrap unsafe low-level operations in guarded try/except fail-closed boundary.",
                registry=self.registry,
            )
            return VectorExecutionResult(
                vector_id=mutant.mutant_id,
                is_positive=False,
                passed=False,
                disposition=DiscriminationDisposition.UNHANDLED_CRASH,
                payload_hex=payload_hex,
                mutation_type=mutant.mutation_type.value,
                exception_class=type(crash_exc).__name__,
                exception_message=str(crash_exc),
                scar_id=scar.scar_id,
                message=f"Unhandled crash on mutant with {type(crash_exc).__name__}: {crash_exc}",
            )


class ConsoleAdversaryBridge:
    """Interconnect bridging Adversarial Discrimination directly into the SSL 4000 Console."""

    @staticmethod
    def audit_channel(
        console: Any,
        channel_number: int,
        target_callable: Callable[[bytes], Any],
        golden_vectors: Sequence[Union[GoldenVector, bytes, Any]],
        target_name: Optional[str] = None
    ) -> DiscriminationReport:
        """
        Audits an SSL channel strip against adversarial variations:
        1. Executes metamorphic discrimination against the target callable.
        2. Streams audit telemetry records through the channel strip fader and noise gate.
        3. If any scars are forged, elevates the channel's thermal ceiling to Tier 1
           and registers the impedance circuit into the console's feedback matrix.
        """
        ch_name = target_name or (
            console.channels[channel_number].name if hasattr(console, "channels") and channel_number in console.channels else "channel"
        )
        discriminator = AdversarialDiscriminator(target_callable, target_name=ch_name)
        report = discriminator.discriminate(golden_vectors)

        # Prepare telemetry signals for the console stream
        telemetry_signals: List[Dict[str, Any]] = []
        for r in report.results:
            telemetry_signals.append({
                "vector_id": r.vector_id,
                "is_positive": r.is_positive,
                "passed": r.passed,
                "disposition": r.disposition.value,
                "confidence_score": 1.0 if r.passed else 0.0,
                "scar_id": r.scar_id,
                "mutation_type": r.mutation_type,
                "message": r.message,
                "timestamp": time.time(),
            })

        # Stream through channel strip if stream_track exists
        if hasattr(console, "stream_track"):
            console.stream_track(channel_number, telemetry_signals)

        # If any scars were forged, elevate the channel thermal ceiling
        if hasattr(console, "channels") and channel_number in console.channels:
            strip = console.channels[channel_number]
            if not report.all_passed:
                strip.thermal_ceiling = max(strip.thermal_ceiling, 1)

        return report
