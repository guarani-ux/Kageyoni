"""Unit & Adversarial Verification Suite for Ninshū Protobuf Parser (CH 36).

Verifies:
1. Valid Protobuf message decoding across all supported wire types:
   - Wire type 0 (VARINT): int32, int64, sint32, sint64, bool
   - Wire type 1 (I64): fixed64, sfixed64, double
   - Wire type 2 (LEN): string, bytes, packed repeated fields
   - Wire type 5 (I32): fixed32, sfixed32, float
2. Recursive nested Protobuf message inspection and contract schema reconstruction.
3. Strict fail-closed parsing against adversarial attacks:
   - Truncated varints, varints exceeding 10 bytes, 64-bit varint overflows.
   - Deprecated wire types (3, 4) and unknown wire types (6, 7).
   - Field number 0 rejection.
   - Truncated fixed-length fields (fixed32, fixed64).
   - Length overflows and payload truncations.
   - Trailing unparsed garbage bytes.
4. Thermodynamic profiling: Peak heap allocation <= 64 KB.
5. Mutation suite fuzzing with zero unhandled exceptions.
"""
from __future__ import annotations

import io
import struct
import unittest

from kageyoni.ninshu.protobuf_parser import (
    ProtobufParser,
    ProtobufMessage,
    ProtobufField,
    WIRE_TYPE_VARINT,
    WIRE_TYPE_I64,
    WIRE_TYPE_LEN,
    WIRE_TYPE_I32,
    decode_varint,
    encode_varint,
    encode_tag,
    zigzag_encode,
    zigzag_decode,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


def build_complex_test_message() -> bytes:
    """Builds a rich Protobuf binary payload exercising all wire types and nesting."""
    buf = bytearray()

    # Field 1: Varint (int64) = 150
    buf.extend(encode_tag(1, WIRE_TYPE_VARINT))
    buf.extend(encode_varint(150))

    # Field 2: Varint (bool) = True (1)
    buf.extend(encode_tag(2, WIRE_TYPE_VARINT))
    buf.extend(encode_varint(1))

    # Field 3: Varint (sint32) = -42 (ZigZag encoded: 83)
    buf.extend(encode_tag(3, WIRE_TYPE_VARINT))
    buf.extend(encode_varint(zigzag_encode(-42, bits=32)))

    # Field 4: I32 (fixed32) = 0x12345678
    buf.extend(encode_tag(4, WIRE_TYPE_I32))
    buf.extend(struct.pack("<I", 0x12345678))

    # Field 5: I32 (float) = 3.1415927
    buf.extend(encode_tag(5, WIRE_TYPE_I32))
    buf.extend(struct.pack("<f", 3.1415927))

    # Field 6: I64 (fixed64) = 0x0102030405060708
    buf.extend(encode_tag(6, WIRE_TYPE_I64))
    buf.extend(struct.pack("<Q", 0x0102030405060708))

    # Field 7: I64 (double) = 2.718281828459045
    buf.extend(encode_tag(7, WIRE_TYPE_I64))
    buf.extend(struct.pack("<d", 2.718281828459045))

    # Field 8: LEN (UTF-8 string) = "Kageyoni Ninshu Sniffer"
    str_bytes = "Kageyoni Ninshu Sniffer".encode("utf-8")
    buf.extend(encode_tag(8, WIRE_TYPE_LEN))
    buf.extend(encode_varint(len(str_bytes)))
    buf.extend(str_bytes)

    # Field 9: LEN (Nested Message)
    nested_buf = bytearray()
    nested_buf.extend(encode_tag(1, WIRE_TYPE_VARINT))
    nested_buf.extend(encode_varint(999))
    nested_str = "SubContract".encode("utf-8")
    nested_buf.extend(encode_tag(2, WIRE_TYPE_LEN))
    nested_buf.extend(encode_varint(len(nested_str)))
    nested_buf.extend(nested_str)

    buf.extend(encode_tag(9, WIRE_TYPE_LEN))
    buf.extend(encode_varint(len(nested_buf)))
    buf.extend(nested_buf)

    # Field 10: LEN (Packed Varints) = [10, 20, 30, 40]
    packed_buf = bytearray()
    for v in [10, 20, 30, 40]:
        packed_buf.extend(encode_varint(v))
    buf.extend(encode_tag(10, WIRE_TYPE_LEN))
    buf.extend(encode_varint(len(packed_buf)))
    buf.extend(packed_buf)

    # Field 11: LEN (Binary Blob) = raw non-UTF-8 bytes
    blob = b"\x80\xff\xfe\x00\x01\x02"
    buf.extend(encode_tag(11, WIRE_TYPE_LEN))
    buf.extend(encode_varint(len(blob)))
    buf.extend(blob)

    return bytes(buf)


class TestNinshuProtobufParser(unittest.TestCase):
    def setUp(self):
        self.complex_payload = build_complex_test_message()

    def test_varint_and_zigzag_helpers(self):
        """Verify varint and zigzag encoding/decoding parity."""
        # Test positive integers
        for val in [0, 1, 127, 128, 300, 16384, 2147483647, 0x7FFFFFFFFFFFFFFF]:
            enc = encode_varint(val)
            dec = decode_varint(io.BytesIO(enc))
            self.assertEqual(val, dec)

        # Test ZigZag
        for n in [0, -1, 1, -2, 2, -100, 100, -2147483648, 2147483647]:
            zz = zigzag_encode(n, bits=32)
            orig = zigzag_decode(zz)
            self.assertEqual(n, orig)

    def test_valid_message_decoding(self):
        """Verify decoding of all primitive fields and types."""
        msg = ProtobufParser.parse_bytes(self.complex_payload)
        self.assertIsInstance(msg, ProtobufMessage)
        self.assertEqual(msg.total_bytes, len(self.complex_payload))
        self.assertEqual(len(msg.sha256), 64)

        # Field 1: varint = 150
        f1 = msg.get(1)
        self.assertIsNotNone(f1)
        self.assertEqual(f1.wire_type, WIRE_TYPE_VARINT)
        self.assertEqual(f1.value, 150)

        # Field 2: bool = 1
        f2 = msg.get(2)
        self.assertIsNotNone(f2)
        self.assertEqual(f2.value, 1)

        # Field 3: sint32 = -42
        f3 = msg.get(3)
        self.assertIsNotNone(f3)
        self.assertEqual(f3.sint_value, -42)

        # Field 4: fixed32
        f4 = msg.get(4)
        self.assertIsNotNone(f4)
        self.assertEqual(f4.wire_type, WIRE_TYPE_I32)
        self.assertEqual(f4.value, 0x12345678)

        # Field 5: float
        f5 = msg.get(5)
        self.assertIsNotNone(f5)
        self.assertAlmostEqual(f5.float_value, 3.1415927, places=5)

        # Field 6: fixed64
        f6 = msg.get(6)
        self.assertIsNotNone(f6)
        self.assertEqual(f6.wire_type, WIRE_TYPE_I64)
        self.assertEqual(f6.value, 0x0102030405060708)

        # Field 7: double
        f7 = msg.get(7)
        self.assertIsNotNone(f7)
        self.assertAlmostEqual(f7.float_value, 2.718281828459045, places=8)

        # Field 8: string
        f8 = msg.get(8)
        self.assertIsNotNone(f8)
        self.assertEqual(f8.inferred_type, "string")
        self.assertEqual(f8.string_value, "Kageyoni Ninshu Sniffer")

        # Field 10: packed varints
        f10 = msg.get(10)
        self.assertIsNotNone(f10)
        self.assertEqual(f10.inferred_type, "packed_varints")
        self.assertEqual(f10.packed_varints, [10, 20, 30, 40])

        # Field 11: binary blob
        f11 = msg.get(11)
        self.assertIsNotNone(f11)
        self.assertEqual(f11.inferred_type, "bytes")
        self.assertEqual(f11.value, b"\x80\xff\xfe\x00\x01\x02")

    def test_nested_message_parsing_and_contract_schema(self):
        """Verify recursive nested message inspection and proto3 schema generation."""
        msg = ProtobufParser.parse_bytes(self.complex_payload)
        f9 = msg.get(9)
        self.assertIsNotNone(f9)
        self.assertEqual(f9.inferred_type, "message")
        self.assertIsNotNone(f9.sub_message)

        sub = f9.sub_message
        self.assertEqual(sub.get_value(1), 999)
        self.assertEqual(sub.get_value(2), "SubContract")

        # Verify contract schema reconstruction
        schema = msg.to_proto_schema("TelemetryPacket")
        self.assertIn("message TelemetryPacket {", schema)
        self.assertIn("message SubMessage_9 {", schema)
        self.assertIn("int64 field_1 = 1;", schema)
        self.assertIn("string field_8 = 8;", schema)
        self.assertIn("SubMessage_9 field_9 = 9;", schema)

        # Verify dictionary serialization
        msg_dict = msg.to_dict()
        self.assertEqual(msg_dict["field_count"], 11)
        self.assertIn("sha256", msg_dict)

    def test_stream_interface(self):
        """Verify stream interface parity with bytes interface."""
        stream = io.BytesIO(self.complex_payload)
        msg = ProtobufParser.parse_stream(stream)
        self.assertEqual(msg.total_bytes, len(self.complex_payload))
        self.assertEqual(msg.get_value(1), 150)

    def test_fail_closed_empty_buffer(self):
        """Verify that empty buffer without allow_empty raises ValueError."""
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(b"")

        empty_allowed = ProtobufParser.parse_bytes(b"", allow_empty=True)
        self.assertEqual(empty_allowed.total_bytes, 0)
        self.assertEqual(len(empty_allowed.fields), 0)

    def test_fail_closed_truncated_varint(self):
        """Verify rejection of truncated varints with continuation bit set."""
        # Field 1 tag (0x08), followed by byte 0x80 (continuation bit set) and EOF
        truncated = b"\x08\x80"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(truncated)

    def test_fail_closed_varint_overflow(self):
        """Verify rejection of varints exceeding 10 bytes."""
        # 11 bytes of 0x80
        overflow_varint = b"\x08" + (b"\x80" * 10) + b"\x01"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(overflow_varint)

        # 10th byte with bits > bit 0 set (overflowing 64 bits)
        ten_byte_overflow = b"\x08" + (b"\x80" * 9) + b"\x02"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(ten_byte_overflow)

    def test_fail_closed_invalid_field_number(self):
        """Verify rejection of field number 0."""
        # Tag with field_number = 0, wire_type = 0 -> 0x00
        invalid_tag = b"\x00\x01"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(invalid_tag)

    def test_fail_closed_deprecated_and_unknown_wire_types(self):
        """Verify rejection of deprecated wire types (3, 4) and invalid types (6, 7)."""
        # Wire type 3 (SGROUP): tag = (1 << 3) | 3 = 0x0B
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(b"\x0b")

        # Wire type 4 (EGROUP): tag = (1 << 3) | 4 = 0x0C
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(b"\x0c")

        # Wire type 6: tag = (1 << 3) | 6 = 0x0E
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(b"\x0e")

        # Wire type 7: tag = (1 << 3) | 7 = 0x0F
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(b"\x0f")

    def test_fail_closed_truncated_fixed_fields(self):
        """Verify rejection of truncated fixed32 and fixed64 fields."""
        # Fixed32 tag (0x0D = field 1, wire 5) with only 2 bytes instead of 4
        truncated_i32 = b"\x0d\x01\x02"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(truncated_i32)

        # Fixed64 tag (0x09 = field 1, wire 1) with only 4 bytes instead of 8
        truncated_i64 = b"\x09\x01\x02\x03\x04"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(truncated_i64)

    def test_fail_closed_length_delimited_overflow(self):
        """Verify rejection when declared length exceeds buffer boundaries."""
        # Field 1 LEN (0x0A), declared length 50, but only 5 bytes provided
        overflow_len = b"\x0a\x32\x01\x02\x03\x04\x05"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(overflow_len)

    def test_fail_closed_trailing_garbage(self):
        """Verify rejection when valid message has trailing unparsed bytes."""
        valid = encode_tag(1, WIRE_TYPE_VARINT) + encode_varint(42)
        corrupted = valid + b"\x99\x88\x77"
        with self.assertRaises(ValueError):
            ProtobufParser.parse_bytes(corrupted)

    def test_thermodynamic_heap_ceiling(self):
        """Verify peak heap allocation stays strictly <= 64 KB."""
        msg, receipt = ThermodynamicProfiler.profile_callable(
            ProtobufParser.parse_bytes,
            self.complex_payload,
            candidate_id="protobuf_parser_ch36",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse cleanly or raise ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.complex_payload)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                msg = ProtobufParser.parse_bytes(m.payload)
                self.assertIsInstance(msg.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
