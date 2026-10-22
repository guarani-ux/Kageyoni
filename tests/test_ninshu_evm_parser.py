"""Unit and Adversarial Verification Suite for Ninshū In-Tree EVM Parser (CH 12).

Tests:
1. Standard ERC-20 transfer(address,uint256) dispatcher selector (0xa9059cbb).
2. ERC-20 balanceOf(address) selector (0x70a08231).
3. Hex decoding with 0x prefix, whitespace, and case variance.
4. Fail-closed rejection on odd-length or empty hex bytecode.
5. Thermodynamic profiling (heap ceiling <= 64 KB).
6. Adversarial mutant fuzzing.
"""
import unittest
from kageyoni.ninshu.evm_parser import EvmBytecodeParser, DispatchType
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuEvmParser(unittest.TestCase):
    # Minimal synthetic EVM dispatcher with ERC-20 transfer (0xa9059cbb) and balanceOf (0x70a08231)
    # PUSH4 a9059cbb -> DUP1 -> PUSH1 0x14 (EQ) -> PUSH1 0x20 -> JUMPI
    # PUSH4 70a08231 -> DUP1 -> PUSH1 0x14 (EQ) -> PUSH1 0x40 -> JUMPI -> STOP
    SYNTHETIC_ERC20_HEX = (
        "6080604052348015600f57600080fd5b50"
        "63a9059cbb8114602057"
        "6370a082318114604057"
        "00"
    )

    def test_evm_selector_extraction(self):
        """Verify extraction of known ERC-20 selectors from bytecode."""
        summary = EvmBytecodeParser.parse_hex_string(self.SYNTHETIC_ERC20_HEX)
        self.assertEqual(summary.total_bytes, len(bytes.fromhex(self.SYNTHETIC_ERC20_HEX)))
        self.assertEqual(len(summary.functions), 2)
        selectors = [f.selector for f in summary.functions]
        self.assertIn("0xa9059cbb", selectors)
        self.assertIn("0x70a08231", selectors)

    def test_hex_formatting_tolerance(self):
        """Verify parsing handles 0x prefix, leading/trailing whitespace, and mixed case."""
        formatted_hex = f"  0X{self.SYNTHETIC_ERC20_HEX.upper()}  \n"
        summary = EvmBytecodeParser.parse_hex_string(formatted_hex)
        self.assertEqual(len(summary.functions), 2)

    def test_fail_closed_on_corrupt_hex(self):
        """Verify fail-closed rejection on invalid hex or empty input."""
        with self.assertRaises(ValueError):
            EvmBytecodeParser.parse_hex_string("")

        with self.assertRaises(ValueError):
            # Odd length hex (missing last nibble)
            EvmBytecodeParser.parse_hex_string("608060405")

        with self.assertRaises(ValueError):
            # Invalid hex character 'Z'
            EvmBytecodeParser.parse_hex_string("608060405Z")

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation during EVM parsing stays strictly <= 64 KB."""
        raw_bytes = bytes.fromhex(self.SYNTHETIC_ERC20_HEX)
        summary, receipt = ThermodynamicProfiler.profile_callable(
            EvmBytecodeParser.parse_bytes,
            raw_bytes,
            candidate_id="evm_parser_ch12",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that all generated adversarial mutants either parse safely or fail cleanly with ValueError."""
        raw_bytes = bytes.fromhex(self.SYNTHETIC_ERC20_HEX)
        mutants = AdversarialMutator.generate_adversarial_suite(raw_bytes)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = EvmBytecodeParser.parse_bytes(m.payload)
                # If it succeeds, it must produce valid structure
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                # Clean, expected domain rejection
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
