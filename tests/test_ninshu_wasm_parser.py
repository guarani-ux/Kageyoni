"""Tests for Ninshū In-Tree WASM Parser and Build Plan Compiler.

Verifies the golden test vectors specified in BuildPlanCompiler.
"""
import io
import unittest

from kageyoni.ninshu.planner import BuildPlanCompiler, ChannelReadiness
from kageyoni.ninshu.wasm_parser import WasmParser, decode_u32_leb128


class TestWasmBuildPlanAndParser(unittest.TestCase):
    def setUp(self):
        self.plan = BuildPlanCompiler.compile_wasm_parser_plan()

    def test_build_plan_invariants_and_vectors(self):
        """Verify the compiled build plan contains valid invariants, vectors, and digest."""
        self.assertEqual(self.plan.target_channel_id, 11)
        self.assertEqual(self.plan.current_readiness, ChannelReadiness.GRADE_B_NEEDS_BUILD)
        self.assertEqual(self.plan.target_readiness, ChannelReadiness.GRADE_A_LIVE_STDLIB)
        self.assertEqual(len(self.plan.invariants), 4)
        self.assertEqual(len(self.plan.test_vectors), 4)
        self.assertTrue(len(self.plan.plan_digest) == 64)

    def test_golden_vectors_execution(self):
        """Execute each test vector from the formal build plan against WasmParser."""
        for vec in self.plan.test_vectors:
            raw_bytes = bytes.fromhex(vec.input_bytes_hex)
            if vec.expect_success:
                summary = WasmParser.parse_bytes(raw_bytes)
                if vec.expected_attributes:
                    for key, expected_val in vec.expected_attributes.items():
                        actual_val = getattr(summary, key)
                        self.assertEqual(
                            actual_val,
                            expected_val,
                            f"Vector {vec.vector_id} attr {key} mismatch: {actual_val} != {expected_val}",
                        )
            else:
                with self.assertRaises(ValueError) as ctx:
                    WasmParser.parse_bytes(raw_bytes)
                if vec.expected_error_substr:
                    self.assertIn(
                        vec.expected_error_substr,
                        str(ctx.exception),
                        f"Vector {vec.vector_id} did not yield expected error substring",
                    )

    def test_leb128_multibyte_and_overflow(self):
        """Test variable length integers in LEB128."""
        # 624485 in unsigned LEB128 is 0xE5 0x8E 0x26
        stream = io.BytesIO(bytes([0xE5, 0x8E, 0x26]))
        val, bytes_read = decode_u32_leb128(stream)
        self.assertEqual(val, 624485)
        self.assertEqual(bytes_read, 3)

        # Deliberate overflow (> 5 bytes with high bit set)
        overflow_stream = io.BytesIO(bytes([0x80, 0x80, 0x80, 0x80, 0x80, 0x01]))
        with self.assertRaises(ValueError):
            decode_u32_leb128(overflow_stream)


if __name__ == "__main__":
    unittest.main()
