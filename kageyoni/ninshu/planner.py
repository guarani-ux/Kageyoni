"""Architectural Planner & Build Plan Compiler for Ninshū Capability Estate.

Translates engineering intent, invariants, and methodological knowledge into
deterministic, executable build plans and golden vector test specifications
without LLM hallucination.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ChannelReadiness(str, Enum):
    GRADE_A_LIVE_STDLIB = "GRADE_A_LIVE_STDLIB"
    GRADE_B_NEEDS_BUILD = "GRADE_B_NEEDS_BUILD"
    GRADE_C_UNPLUGGED = "GRADE_C_UNPLUGGED"


class MethodologicalPattern(str, Enum):
    STREAMING_ZERO_COPY = "STREAMING_ZERO_COPY"
    FINITE_STATE_LEXER = "FINITE_STATE_LEXER"
    FAIL_CLOSED_VALIDATOR = "FAIL_CLOSED_VALIDATOR"
    SHADOW_EXECUTION_SANDBOX = "SHADOW_EXECUTION_SANDBOX"
    CONTENT_ADDRESSED_CACHE = "CONTENT_ADDRESSED_CACHE"
    ACTIVE_SCAR_CIRCUIT_BREAKER = "ACTIVE_SCAR_CIRCUIT_BREAKER"


@dataclasses.dataclass(frozen=True)
class InvariantRule:
    rule_id: str
    assertion: str
    failure_severity: str  # 'CIRCUIT_BREAK', 'DEGRADE_SCORE', 'REJECT_INPUT'


@dataclasses.dataclass(frozen=True)
class TestVector:
    vector_id: str
    input_bytes_hex: str
    description: str
    expect_success: bool
    expected_error_substr: Optional[str] = None
    expected_attributes: Optional[Dict[str, Any]] = None


@dataclasses.dataclass(frozen=True)
class BuildMilestone:
    sequence: int
    name: str
    deliverable: str
    verification_command: str


@dataclasses.dataclass(frozen=True)
class BuildPlan:
    plan_id: str
    target_channel_id: int
    channel_name: str
    current_readiness: ChannelReadiness
    target_readiness: ChannelReadiness
    patterns: List[MethodologicalPattern]
    invariants: List[InvariantRule]
    test_vectors: List[TestVector]
    milestones: List[BuildMilestone]
    plan_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "target_channel_id": self.target_channel_id,
            "channel_name": self.channel_name,
            "current_readiness": self.current_readiness.value,
            "target_readiness": self.target_readiness.value,
            "patterns": [p.value for p in self.patterns],
            "invariants": [dataclasses.asdict(i) for i in self.invariants],
            "test_vectors": [dataclasses.asdict(v) for v in self.test_vectors],
            "milestones": [dataclasses.asdict(m) for m in self.milestones],
            "plan_digest": self.plan_digest,
        }


class BuildPlanCompiler:
    """Compiles engineering specifications into formal, executable build plans."""

    @staticmethod
    def compile_wasm_parser_plan() -> BuildPlan:
        """Compile a formal build plan to port CH 07 (WASM Module Inspector)

        from TypeScript/wabt in rea_forge to a zero-dependency in-tree Python stdlib
        streaming parser (Grade B -> Grade A).
        """
        invariants = [
            InvariantRule(
                rule_id="WASM-INV-001",
                assertion="Magic bytes must be exact 0x00 0x61 0x73 0x6D (\\0asm) and version 0x01",
                failure_severity="CIRCUIT_BREAK",
            ),
            InvariantRule(
                rule_id="WASM-INV-002",
                assertion="Zero third-party dependencies; pure Python stdlib struct and io only",
                failure_severity="CIRCUIT_BREAK",
            ),
            InvariantRule(
                rule_id="WASM-INV-003",
                assertion="Stream parsing uses memoryview / seek without buffering arbitrary payload sizes in heap",
                failure_severity="DEGRADE_SCORE",
            ),
            InvariantRule(
                rule_id="WASM-INV-004",
                assertion="Truncated payloads or malformed LEB128 integers must fail-closed cleanly with ValueError",
                failure_severity="REJECT_INPUT",
            ),
        ]

        # Golden & Malicious Test Vectors
        test_vectors = [
            # Minimal valid WASM binary (header only: 8 bytes)
            TestVector(
                vector_id="VEC-WASM-MIN-01",
                input_bytes_hex="0061736d01000000",
                description="Minimal valid empty WASM module header",
                expect_success=True,
                expected_attributes={"version": 1, "sections_count": 0},
            ),
            # Invalid magic (e.g. standard ELF)
            TestVector(
                vector_id="VEC-WASM-ERR-MAGIC",
                input_bytes_hex="7f454c4601000000",
                description="Corrupted magic bytes (ELF signature instead of WASM)",
                expect_success=False,
                expected_error_substr="Invalid WASM magic header",
            ),
            # Truncated header (3 bytes)
            TestVector(
                vector_id="VEC-WASM-ERR-TRUNC",
                input_bytes_hex="006173",
                description="Truncated WASM header under 8 bytes",
                expect_success=False,
                expected_error_substr="Truncated WASM header",
            ),
            # Valid Type + Export section
            # 00 61 73 6d 01 00 00 00 | 01 (type section) 04 (len) 01 (1 type) 60 (func) 00 00 (0 params, 0 returns)
            TestVector(
                vector_id="VEC-WASM-SECTIONS-01",
                input_bytes_hex="0061736d01000000010401600000",
                description="Valid WASM with Type Section containing one func () -> ()",
                expect_success=True,
                expected_attributes={"version": 1, "sections_count": 1},
            ),
        ]

        milestones = [
            BuildMilestone(
                sequence=1,
                name="TDD Test Vector Suite",
                deliverable="tests/test_ninshu_wasm_parser.py",
                verification_command="pytest tests/test_ninshu_wasm_parser.py -v",
            ),
            BuildMilestone(
                sequence=2,
                name="In-Tree WASM Binary Streaming Parser",
                deliverable="kageyoni/ninshu/wasm_parser.py",
                verification_command="python -m unittest tests.test_ninshu_wasm_parser",
            ),
            BuildMilestone(
                sequence=3,
                name="Patchbay & Telemetry Integration",
                deliverable="Update seeds.py CH 07 status to LIVE_STDLIB",
                verification_command="python -m kageyoni.ninshu.cli patch --query wasm",
            ),
        ]

        raw_content = (
            "CH07_WASM_PORT_PLAN:"
            + "".join(inv.rule_id for inv in invariants)
            + "".join(v.vector_id for v in test_vectors)
        )
        plan_digest = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        return BuildPlan(
            plan_id="BP-CH11-WASM-STDLIB",
            target_channel_id=11,
            channel_name="WebAssembly (WASM) Disassembler & Module Inspector",
            current_readiness=ChannelReadiness.GRADE_B_NEEDS_BUILD,
            target_readiness=ChannelReadiness.GRADE_A_LIVE_STDLIB,
            patterns=[
                MethodologicalPattern.STREAMING_ZERO_COPY,
                MethodologicalPattern.FINITE_STATE_LEXER,
                MethodologicalPattern.FAIL_CLOSED_VALIDATOR,
            ],
            invariants=invariants,
            test_vectors=test_vectors,
            milestones=milestones,
            plan_digest=plan_digest,
        )
