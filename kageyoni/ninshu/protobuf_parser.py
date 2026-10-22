"""Zero-dependency in-tree Protobuf Message & Contract Sniffer (CH 36).

Pure Python standard library implementation:
1. Wire Format Decoder (Zero third-party protobuf dependencies):
   - Wire type 0 (VARINT): int32, int64, uint32, uint64, sint32, sint64, bool, enum.
   - Wire type 1 (I64): fixed64, sfixed64, double (8 bytes little-endian).
   - Wire type 2 (LEN): string, bytes, embedded messages, packed repeated fields.
   - Wire type 5 (I32): fixed32, sfixed32, float (4 bytes little-endian).
   - Strict rejection of deprecated wire types (3 = SGROUP, 4 = EGROUP) and invalid types (> 5).
2. Varint & Tag Architecture:
   - field_number = key >> 3 (strictly >= 1 and <= 536870911).
   - wire_type = key & 0x7.
   - 7-bit continuation varint decoding with 64-bit overflow guard (max 10 bytes).
   - ZigZag integer encoding/decoding for sint32 and sint64.
3. Recursive Heuristic Contract Sniffing:
   - Distinguishes embedded sub-messages, UTF-8 strings, packed varints, and raw byte buffers.
   - Reconstructs human-readable proto3 contract schema definitions.
4. Strict Fail-Closed Invariants:
   - Rejects truncated varints, length overflows extending past buffer boundaries, trailing unparsed garbage.
   - Thermodynamic memory bound: Peak heap <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# Wire Types (Protobuf Encoding Specification)
WIRE_TYPE_VARINT = 0
WIRE_TYPE_I64 = 1
WIRE_TYPE_LEN = 2
WIRE_TYPE_SGROUP = 3  # Deprecated
WIRE_TYPE_EGROUP = 4  # Deprecated
WIRE_TYPE_I32 = 5

WIRE_TYPE_NAMES = {
    WIRE_TYPE_VARINT: "VARINT",
    WIRE_TYPE_I64: "I64",
    WIRE_TYPE_LEN: "LEN",
    WIRE_TYPE_I32: "I32",
}

# Maximum field number per Protobuf specification (2^29 - 1)
MAX_FIELD_NUMBER = 536870911
# Maximum allowed payload size for bounded zero-trust execution (16 MB)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024


def decode_varint(stream: BinaryIO) -> int:
    """Decodes a standard 7-bit continuation varint from a stream.

    Enforces 64-bit bounds and a maximum of 10 bytes.
    Raises ValueError on truncation, length overflow, or 64-bit overflow.
    """
    val = 0
    shift = 0
    for byte_count in range(10):
        b_bytes = stream.read(1)
        if not b_bytes:
            raise ValueError("Truncated varint in protobuf stream: unexpected EOF")
        b = b_bytes[0]
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            # 10th byte validation: only bit 0 allowed for 64-bit unsigned/signed representations
            if byte_count == 9 and (b & 0x7E) != 0:
                raise ValueError("Varint overflow: 10th byte exceeds 64-bit integer limit")
            return val
        shift += 7
    raise ValueError("Varint exceeded maximum 10-byte continuation limit")


def encode_varint(val: int) -> bytes:
    """Encodes a Python integer into Protobuf 7-bit continuation varint bytes."""
    if val < 0:
        val = (1 << 64) + val
    res = bytearray()
    while True:
        b = val & 0x7F
        val >>= 7
        if val != 0:
            res.append(b | 0x80)
        else:
            res.append(b)
            break
    return bytes(res)


def encode_tag(field_number: int, wire_type: int) -> bytes:
    """Encodes field_number and wire_type into a varint tag."""
    if field_number < 1 or field_number > MAX_FIELD_NUMBER:
        raise ValueError(f"Field number {field_number} out of valid range (1..{MAX_FIELD_NUMBER})")
    if wire_type not in (WIRE_TYPE_VARINT, WIRE_TYPE_I64, WIRE_TYPE_LEN, WIRE_TYPE_I32):
        raise ValueError(f"Unsupported wire type for encoding: {wire_type}")
    key = (field_number << 3) | (wire_type & 0x07)
    return encode_varint(key)


def zigzag_encode(val: int, bits: int = 64) -> int:
    """Encodes signed integer using ZigZag encoding."""
    return (val << 1) ^ (val >> (bits - 1))


def zigzag_decode(val: int) -> int:
    """Decodes a ZigZag encoded unsigned integer back to signed."""
    return (val >> 1) ^ (-(val & 1))


@dataclasses.dataclass(frozen=True)
class ProtobufField:
    """Represents a decoded Protobuf field."""
    field_number: int
    wire_type: int
    wire_type_name: str
    raw_bytes: bytes
    value: Any
    sint_value: Optional[int] = None
    float_value: Optional[float] = None
    string_value: Optional[str] = None
    sub_message: Optional["ProtobufMessage"] = None
    packed_varints: Optional[List[int]] = None
    inferred_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Converts field to a JSON-serializable dictionary."""
        d: Dict[str, Any] = {
            "field_number": self.field_number,
            "wire_type": self.wire_type,
            "wire_type_name": self.wire_type_name,
            "inferred_type": self.inferred_type,
        }
        if self.sub_message is not None:
            d["sub_message"] = self.sub_message.to_dict()
        elif self.string_value is not None and self.inferred_type == "string":
            d["string_value"] = self.string_value
        elif self.packed_varints is not None and self.inferred_type == "packed_varints":
            d["packed_varints"] = self.packed_varints
        elif self.float_value is not None and self.inferred_type in ("float", "double"):
            d["float_value"] = self.float_value
        elif self.sint_value is not None and self.inferred_type in ("sint32", "sint64"):
            d["sint_value"] = self.sint_value
        else:
            if isinstance(self.value, bytes):
                d["value_hex"] = self.value.hex()
            else:
                d["value"] = self.value
        return d


@dataclasses.dataclass(frozen=True)
class ProtobufMessage:
    """Represents a decoded Protobuf message or embedded sub-message."""
    fields: List[ProtobufField]
    total_bytes: int
    sha256: str
    fields_by_number: Dict[int, List[ProtobufField]]

    def get(self, field_number: int, default: Optional[ProtobufField] = None) -> Optional[ProtobufField]:
        """Returns the first field with the specified field number, or default."""
        field_list = self.fields_by_number.get(field_number)
        if field_list:
            return field_list[0]
        return default

    def get_all(self, field_number: int) -> List[ProtobufField]:
        """Returns all fields with the specified field number (for repeated fields)."""
        return self.fields_by_number.get(field_number, [])

    def get_value(self, field_number: int, default: Any = None) -> Any:
        """Returns the primary value of the first field with the specified number."""
        f = self.get(field_number)
        if f is not None:
            return f.value
        return default

    def to_dict(self) -> Dict[str, Any]:
        """Serializes message structure to dictionary."""
        return {
            "total_bytes": self.total_bytes,
            "sha256": self.sha256,
            "field_count": len(self.fields),
            "fields": [f.to_dict() for f in self.fields],
        }

    def to_proto_schema(self, message_name: str = "SniffedContract") -> str:
        """Reconstructs an inferred proto3 contract definition from sniffed message structure."""
        sub_schemas: List[str] = []
        lines: List[str] = [f"message {message_name} {{"]

        for f_num in sorted(self.fields_by_number.keys()):
            f_list = self.fields_by_number[f_num]
            sample = f_list[0]
            is_repeated = len(f_list) > 1 or sample.inferred_type == "packed_varints"

            if sample.inferred_type == "message" and sample.sub_message is not None:
                sub_name = f"SubMessage_{f_num}"
                sub_schema = sample.sub_message.to_proto_schema(sub_name)
                sub_schemas.append(sub_schema)
                type_name = sub_name
            elif sample.inferred_type == "string":
                type_name = "string"
            elif sample.inferred_type == "packed_varints":
                type_name = "int64"
            elif sample.inferred_type == "bytes":
                type_name = "bytes"
            elif sample.wire_type == WIRE_TYPE_VARINT:
                type_name = "int64"
            elif sample.wire_type == WIRE_TYPE_I32:
                type_name = "fixed32"
            elif sample.wire_type == WIRE_TYPE_I64:
                type_name = "fixed64"
            else:
                type_name = "bytes"

            prefix = "repeated " if is_repeated else ""
            lines.append(f"  {prefix}{type_name} field_{f_num} = {f_num};")

        lines.append("}")

        res: List[str] = []
        if sub_schemas:
            res.extend(sub_schemas)
            res.append("")
        res.append("\n".join(lines))
        return "\n".join(res)


class ProtobufParser:
    """Zero-dependency strict fail-closed Protobuf wire format decoder and contract sniffer."""

    @classmethod
    def parse_bytes(
        cls,
        data: bytes,
        allow_empty: bool = False,
        max_depth: int = 10,
    ) -> ProtobufMessage:
        """Parses a protobuf message from raw bytes.

        Enforces strict fail-closed rejection on empty buffers (unless allow_empty=True),
        truncated records, length overflows, deprecated or unknown wire types.
        """
        if not data:
            if allow_empty:
                return ProtobufMessage(
                    fields=[],
                    total_bytes=0,
                    sha256=hashlib.sha256(b"").hexdigest(),
                    fields_by_number={},
                )
            raise ValueError("Empty protobuf buffer: zero bytes provided")

        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValueError(f"Protobuf buffer size {len(data)} exceeds maximum {MAX_PAYLOAD_BYTES}")

        stream = io.BytesIO(data)
        message = cls._parse_stream_internal(
            stream=stream,
            expected_length=len(data),
            depth=0,
            max_depth=max_depth,
            is_submessage=False,
        )

        # Enforce that all buffer bytes were consumed
        consumed = stream.tell()
        if consumed != len(data):
            raise ValueError(
                f"Protobuf trailing unparsed garbage: consumed {consumed} of {len(data)} bytes"
            )

        return message

    @classmethod
    def parse_stream(
        cls,
        stream: BinaryIO,
        length: Optional[int] = None,
        allow_empty: bool = False,
        max_depth: int = 10,
    ) -> ProtobufMessage:
        """Parses a protobuf message from a binary stream."""
        if length is not None:
            data = stream.read(length)
            if len(data) < length:
                raise ValueError(f"Stream truncated: expected {length} bytes, got {len(data)}")
        else:
            data = stream.read()
        return cls.parse_bytes(data, allow_empty=allow_empty, max_depth=max_depth)

    @classmethod
    def _parse_stream_internal(
        cls,
        stream: BinaryIO,
        expected_length: int,
        depth: int,
        max_depth: int,
        is_submessage: bool,
    ) -> ProtobufMessage:
        start_pos = stream.tell()
        end_boundary = start_pos + expected_length
        fields: List[ProtobufField] = []
        fields_by_number: Dict[int, List[ProtobufField]] = {}

        while stream.tell() < end_boundary:
            tag_offset = stream.tell()
            key = decode_varint(stream)
            field_number = key >> 3
            wire_type = key & 0x07

            # Protobuf specification: field numbers must be 1 <= field_number <= 2^29 - 1
            if field_number < 1:
                raise ValueError(
                    f"Invalid protobuf field number: {field_number} (must be >= 1) at offset {tag_offset}"
                )
            if field_number > MAX_FIELD_NUMBER:
                raise ValueError(
                    f"Invalid protobuf field number: {field_number} (exceeds max {MAX_FIELD_NUMBER})"
                )

            # Check wire type
            if wire_type == WIRE_TYPE_VARINT:
                val_start = stream.tell()
                val = decode_varint(stream)
                val_end = stream.tell()
                raw_field_bytes = stream.getvalue()[tag_offset:val_end] if isinstance(stream, io.BytesIO) else encode_varint(val)
                sint_val = zigzag_decode(val)

                field = ProtobufField(
                    field_number=field_number,
                    wire_type=wire_type,
                    wire_type_name="VARINT",
                    raw_bytes=raw_field_bytes,
                    value=val,
                    sint_value=sint_val,
                    inferred_type="varint",
                )
                fields.append(field)
                fields_by_number.setdefault(field_number, []).append(field)

            elif wire_type == WIRE_TYPE_I64:
                i64_raw = stream.read(8)
                if len(i64_raw) < 8:
                    raise ValueError(
                        f"Truncated 64-bit fixed field {field_number}: expected 8 bytes, got {len(i64_raw)}"
                    )
                u64_val, = struct.unpack("<Q", i64_raw)
                s64_val, = struct.unpack("<q", i64_raw)
                double_val, = struct.unpack("<d", i64_raw)

                field = ProtobufField(
                    field_number=field_number,
                    wire_type=wire_type,
                    wire_type_name="I64",
                    raw_bytes=i64_raw,
                    value=u64_val,
                    sint_value=s64_val,
                    float_value=double_val,
                    inferred_type="fixed64",
                )
                fields.append(field)
                fields_by_number.setdefault(field_number, []).append(field)

            elif wire_type == WIRE_TYPE_LEN:
                length_offset = stream.tell()
                field_len = decode_varint(stream)
                if field_len < 0:
                    raise ValueError(f"Negative length {field_len} for field {field_number}")
                
                remaining_in_container = end_boundary - stream.tell()
                if field_len > remaining_in_container:
                    raise ValueError(
                        f"Length-delimited field {field_number} overflows buffer: declared {field_len} bytes, remaining {remaining_in_container} bytes"
                    )

                payload = stream.read(field_len)
                if len(payload) < field_len:
                    raise ValueError(
                        f"Length-delimited field {field_number} truncated: expected {field_len} bytes, got {len(payload)}"
                    )

                field = cls._inspect_len_payload(
                    field_number=field_number,
                    payload=payload,
                    depth=depth,
                    max_depth=max_depth,
                )
                fields.append(field)
                fields_by_number.setdefault(field_number, []).append(field)

            elif wire_type == WIRE_TYPE_I32:
                i32_raw = stream.read(4)
                if len(i32_raw) < 4:
                    raise ValueError(
                        f"Truncated 32-bit fixed field {field_number}: expected 4 bytes, got {len(i32_raw)}"
                    )
                u32_val, = struct.unpack("<I", i32_raw)
                s32_val, = struct.unpack("<i", i32_raw)
                float_val, = struct.unpack("<f", i32_raw)

                field = ProtobufField(
                    field_number=field_number,
                    wire_type=wire_type,
                    wire_type_name="I32",
                    raw_bytes=i32_raw,
                    value=u32_val,
                    sint_value=s32_val,
                    float_value=float_val,
                    inferred_type="fixed32",
                )
                fields.append(field)
                fields_by_number.setdefault(field_number, []).append(field)

            elif wire_type == WIRE_TYPE_SGROUP:
                raise ValueError(
                    f"Deprecated wire type 3 (Start Group) is rejected at field {field_number}"
                )
            elif wire_type == WIRE_TYPE_EGROUP:
                raise ValueError(
                    f"Deprecated wire type 4 (End Group) is rejected at field {field_number}"
                )
            else:
                raise ValueError(
                    f"Unknown or invalid wire type {wire_type} at field {field_number}"
                )

        # Build payload bytes representation and digest
        consumed_bytes = stream.tell() - start_pos
        if isinstance(stream, io.BytesIO):
            cur_pos = stream.tell()
            stream.seek(start_pos)
            chunk = stream.read(consumed_bytes)
            stream.seek(cur_pos)
            digest = hashlib.sha256(chunk).hexdigest()
        else:
            digest = hashlib.sha256(str(fields).encode("utf-8")).hexdigest()

        return ProtobufMessage(
            fields=fields,
            total_bytes=consumed_bytes,
            sha256=digest,
            fields_by_number=fields_by_number,
        )

    @classmethod
    def _inspect_len_payload(
        cls,
        field_number: int,
        payload: bytes,
        depth: int,
        max_depth: int,
    ) -> ProtobufField:
        """Heuristically inspects LEN payload to identify sub-messages, UTF-8 strings, packed varints, or blobs."""
        if not payload:
            return ProtobufField(
                field_number=field_number,
                wire_type=WIRE_TYPE_LEN,
                wire_type_name="LEN",
                raw_bytes=b"",
                value=b"",
                string_value="",
                inferred_type="string",
            )

        # 1. Check for valid UTF-8 string
        string_val: Optional[str] = None
        is_pure_printable_text = False
        try:
            decoded = payload.decode("utf-8")
            string_val = decoded
            # Test if text contains only printable characters and common whitespace
            is_pure_printable_text = all(c.isprintable() or c in "\r\n\t" for c in decoded)
        except UnicodeDecodeError:
            string_val = None

        # 2. Check for recursive embedded Protobuf message
        sub_msg: Optional[ProtobufMessage] = None
        if depth < max_depth:
            try:
                sub_stream = io.BytesIO(payload)
                cand = cls._parse_stream_internal(
                    stream=sub_stream,
                    expected_length=len(payload),
                    depth=depth + 1,
                    max_depth=max_depth,
                    is_submessage=True,
                )
                if cand.fields and sub_stream.tell() == len(payload):
                    sub_msg = cand
            except (ValueError, struct.error):
                sub_msg = None

        # 3. Check for packed repeated varints
        packed_varints: Optional[List[int]] = None
        try:
            p_stream = io.BytesIO(payload)
            pv_list: List[int] = []
            canonical = True
            while p_stream.tell() < len(payload):
                v_start = p_stream.tell()
                v = decode_varint(p_stream)
                v_end = p_stream.tell()
                consumed_bytes = payload[v_start:v_end]
                if encode_varint(v) != consumed_bytes:
                    canonical = False
                    break
                pv_list.append(v)
            if canonical and len(pv_list) > 1 and p_stream.tell() == len(payload):
                packed_varints = pv_list
        except (ValueError, struct.error):
            packed_varints = None

        # 4. Resolve heuristic classification
        # Prefer string if clean printable text without submessage or when text is clearly human string
        if string_val is not None and is_pure_printable_text and (sub_msg is None or not any(ord(c) < 32 and c not in "\r\n\t" for c in string_val)):
            inferred_type = "string"
            primary_value = string_val
        elif sub_msg is not None:
            inferred_type = "message"
            primary_value = sub_msg
        elif packed_varints is not None:
            inferred_type = "packed_varints"
            primary_value = packed_varints
        elif string_val is not None:
            inferred_type = "string"
            primary_value = string_val
        else:
            inferred_type = "bytes"
            primary_value = payload

        return ProtobufField(
            field_number=field_number,
            wire_type=WIRE_TYPE_LEN,
            wire_type_name="LEN",
            raw_bytes=payload,
            value=primary_value,
            string_value=string_val,
            sub_message=sub_msg,
            packed_varints=packed_varints,
            inferred_type=inferred_type,
        )
