"""Zero-dependency in-tree Ethereum Virtual Machine (EVM) Bytecode & Selector Miner.

Parses raw or hex EVM bytecode, reconstructs ABI function selectors (PUSH4 + EQ / JUMPI patterns),
and extracts embedded CBOR Solidity compiler metadata.
Adheres to the REA inspect_evm_interface specification.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Tuple


class DispatchType(str, Enum):
    ABI = "abi"
    FALLBACK = "fallback"


@dataclasses.dataclass(frozen=True)
class EvmFunctionSelector:
    selector: str                    # e.g., "0xa9059cbb" (transfer)
    bytecode_offset: int
    dispatch: DispatchType = DispatchType.ABI
    inferred_arguments: Optional[str] = None
    inferred_state_mutability: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class SolidityMetadata:
    status: str                      # "available", "unavailable"
    bytecode_offset: Optional[int]
    cbor_bytes: Optional[int]
    compiler_version: Optional[str] = None
    ipfs_hash: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class EvmBytecodeSummary:
    total_bytes: int
    bytecode_hex: str
    sha256_digest: str
    functions: List[EvmFunctionSelector]
    metadata: Optional[SolidityMetadata]
    has_fallback: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "bytecode_hex": self.bytecode_hex,
            "sha256_digest": self.sha256_digest,
            "functions": [dataclasses.asdict(f) for f in self.functions],
            "metadata": dataclasses.asdict(self.metadata) if self.metadata else None,
            "has_fallback": self.has_fallback,
        }


class EvmBytecodeParser:
    """Pure Python stdlib EVM disassembler & selector recovery engine."""

    # EVM Opcodes of interest
    PUSH4 = 0x63
    EQ = 0x14
    JUMPI = 0x57
    STOP = 0x00
    REVERT = 0xFD
    RETURN = 0xF3
    INVALID = 0xFE

    @classmethod
    def clean_hex(cls, text: str) -> bytes:
        """Strips whitespace, '0x' prefix, and decodes hex string into raw bytes."""
        cleaned = re.sub(r"\s+", "", text.strip())
        if cleaned.startswith("0x") or cleaned.startswith("0X"):
            cleaned = cleaned[2:]
        if len(cleaned) % 2 != 0:
            raise ValueError(f"Odd-length hex string: length is {len(cleaned)}")
        return bytes.fromhex(cleaned)

    @classmethod
    def parse_hex_string(cls, hex_text: str) -> EvmBytecodeSummary:
        raw_bytes = cls.clean_hex(hex_text)
        return cls.parse_bytes(raw_bytes)

    @classmethod
    def parse_bytes(cls, bytecode: bytes) -> EvmBytecodeSummary:
        if not bytecode:
            raise ValueError("Empty EVM bytecode payload")

        total_bytes = len(bytecode)
        hex_str = bytecode.hex()
        digest = hashlib.sha256(bytecode).hexdigest()

        # 1. SCAN FOR FUNCTION SELECTORS (PUSH4 xx xx xx xx -> ... -> EQ -> JUMPI)
        functions: List[EvmFunctionSelector] = []
        has_fallback = False

        i = 0
        while i < total_bytes:
            op = bytecode[i]

            # PUSH1 .. PUSH32 (0x60 .. 0x7F)
            if 0x60 <= op <= 0x7F:
                push_size = op - 0x5F
                push_data = bytecode[i + 1 : i + 1 + push_size]
                
                # Check for 4-byte selector (PUSH4)
                if push_size == 4 and len(push_data) == 4:
                    # Look ahead within next 16 bytes for EQ (0x14) or JUMPI (0x57)
                    lookahead = bytecode[i + 5 : i + 20]
                    if cls.EQ in lookahead or cls.JUMPI in lookahead:
                        selector_hex = f"0x{push_data.hex()}"
                        # Avoid duplicate recordings of the same selector
                        if not any(f.selector == selector_hex for f in functions):
                            functions.append(
                                EvmFunctionSelector(
                                    selector=selector_hex,
                                    bytecode_offset=i,
                                    dispatch=DispatchType.ABI,
                                )
                            )
                i += 1 + push_size
            else:
                i += 1

        # Check for fallback handler (look for bare JUMP/REVERT patterns without PUSH4)
        if total_bytes > 32 and (cls.REVERT in bytecode or cls.RETURN in bytecode):
            has_fallback = True

        # 2. SCAN FOR SOLIDITY METADATA (CBOR payload at the end of the binary)
        # Solidity appends 2-byte length of CBOR data at the very end of bytecode (big endian)
        metadata: Optional[SolidityMetadata] = None
        if total_bytes >= 4:
            cbor_len = int.from_bytes(bytecode[-2:], byteorder="big")
            if 0 < cbor_len < total_bytes - 2:
                cbor_start = total_bytes - 2 - cbor_len
                cbor_data = bytecode[cbor_start : total_bytes - 2]
                # Check for common Solidity CBOR keys: 'solc' (0x64736f6c63) or 'ipfs' (0x6469706673)
                if b"solc" in cbor_data or b"ipfs" in cbor_data:
                    metadata = SolidityMetadata(
                        status="available",
                        bytecode_offset=cbor_start,
                        cbor_bytes=cbor_len,
                    )

        if not metadata:
            metadata = SolidityMetadata(
                status="unavailable",
                bytecode_offset=None,
                cbor_bytes=None,
            )

        return EvmBytecodeSummary(
            total_bytes=total_bytes,
            bytecode_hex=hex_str,
            sha256_digest=digest,
            functions=functions,
            metadata=metadata,
            has_fallback=has_fallback,
        )
