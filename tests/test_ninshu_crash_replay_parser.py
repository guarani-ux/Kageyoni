"""Adversarial unit tests and heap compliance checks for CrashReplayParser (CH 22)."""
import os
import struct
import tracemalloc
import unittest

from kageyoni.ninshu.crash_replay_parser import (
    CLASS_CONTROL_FLOW_HIJACK,
    CLASS_DIVIDE_BY_ZERO,
    CLASS_HEAP_CORRUPTION,
    CLASS_ILLEGAL_INSTRUCTION,
    CLASS_NULL_POINTER_DEREFERENCE,
    CLASS_STACK_BUFFER_OVERFLOW,
    CLASS_UNKNOWN,
    DEFAULT_ALPHABET,
    MAX_CYCLIC_LENGTH,
    SUPPORTED_SIGNALS,
    CrashAnalysis,
    CrashReplayEngine,
    CrashSignal,
    CrashTrace,
    CrashTraceParser,
    MitigationDetector,
    RegisterState,
    SecurityMitigations,
    cyclic,
    cyclic_find,
    de_bruijn_sequence,
)


class TestCrashReplayParser(unittest.TestCase):
    """Rigorous verification suite for Pwntools Exploit & Crash Replay Engine."""

    # ---------------------------------------------------------------------
    # 1. Cyclic Pattern Generation & Offset Finding
    # ---------------------------------------------------------------------

    def test_cyclic_generation_length(self):
        """Validates pattern generation lengths and determinism."""
        self.assertEqual(cyclic(0), b"")
        self.assertEqual(cyclic(4), b"aaaa")
        self.assertEqual(cyclic(8), b"aaaabaaa")
        self.assertEqual(cyclic(16), b"aaaabaaacaaadaaa")
        self.assertEqual(len(cyclic(1024)), 1024)

    def test_cyclic_find_offsets(self):
        """Validates exact offset resolution across types (int, bytes, str)."""
        # Exact match at offset 0
        self.assertEqual(cyclic_find("aaaa"), 0)
        self.assertEqual(cyclic_find(b"aaaa"), 0)
        self.assertEqual(cyclic_find(0x61616161), 0)

        # Exact match at offset 4
        self.assertEqual(cyclic_find("baaa"), 4)
        self.assertEqual(cyclic_find(b"baaa"), 4)
        self.assertEqual(cyclic_find(0x61616162), 4)

        # Exact match at offset 8
        self.assertEqual(cyclic_find("caaa"), 8)
        self.assertEqual(cyclic_find(0x61616163), 8)

        # Exact match at offset 12 (0x61616164 in little-endian is b'daaa')
        self.assertEqual(cyclic_find("daaa"), 12)
        self.assertEqual(cyclic_find(b"daaa"), 12)
        self.assertEqual(cyclic_find(0x61616164), 12)

    def test_cyclic_custom_alphabet_and_stride(self):
        """Tests custom alphabet and stride."""
        custom_alpha = "0123456789"
        pat = cyclic(20, n=2, alphabet=custom_alpha)
        self.assertEqual(len(pat), 20)
        # Find offset in numeric pattern
        sub = pat[6:8]
        self.assertEqual(cyclic_find(sub, n=2, alphabet=custom_alpha), 6)

    # ---------------------------------------------------------------------
    # 2. Crash Classification: Control Flow Hijacking
    # ---------------------------------------------------------------------

    def test_sigsegv_control_flow_hijack_x86(self):
        """Verifies x86 EIP overwrite identification at offset 12."""
        crash_dict = {
            "signal": "SIGSEGV",
            "signum": 11,
            "fault_address": 0x61616164,
            "registers": {
                "eip": 0x61616164,
                "esp": 0xFFFFD000,
                "ebp": 0x61616163,
            },
        }
        analysis = CrashReplayEngine.analyze(crash_dict)
        self.assertEqual(analysis.classification, CLASS_CONTROL_FLOW_HIJACK)
        self.assertTrue(analysis.control_flow_hijacked)
        self.assertEqual(analysis.cyclic_offset, 12)
        self.assertEqual(analysis.cyclic_register, "eip")
        self.assertEqual(analysis.signal.signum, 11)

    def test_sigsegv_control_flow_hijack_x86_64(self):
        """Verifies x86-64 RIP overwrite detection."""
        crash_dict = {
            "signal": "SIGSEGV",
            "signum": 11,
            "fault_address": 0x61616164,
            "registers": {
                "rip": 0x61616164,
                "rsp": 0x7FFFFFFFE020,
                "rbp": 0x61616163,
            },
        }
        analysis = CrashReplayEngine.analyze(crash_dict)
        self.assertEqual(analysis.classification, CLASS_CONTROL_FLOW_HIJACK)
        self.assertTrue(analysis.control_flow_hijacked)
        self.assertEqual(analysis.cyclic_offset, 12)
        self.assertEqual(analysis.cyclic_register, "rip")

    def test_text_trace_parsing_gdb_dump(self):
        """Tests parsing a standard GDB text crash dump."""
        gdb_text = """
Program received signal SIGSEGV, Segmentation fault.
0x0000000061616164 in ?? ()
rax: 0x0000000000000000
rbx: 0x0000000000000000
rcx: 0x00007fffffffe000
rdx: 0x0000000000000001
rsi: 0x00007fffffffe100
rdi: 0x0000000000000002
rbp: 0x61616163
rsp: 0x00007fffffffe020
rip: 0x0000000061616164
Fault address: 0x61616164
"""
        analysis = CrashReplayEngine.analyze(gdb_text)
        self.assertEqual(analysis.classification, CLASS_CONTROL_FLOW_HIJACK)
        self.assertTrue(analysis.control_flow_hijacked)
        self.assertEqual(analysis.cyclic_offset, 12)
        self.assertEqual(analysis.cyclic_register, "rip")

    def test_linux_dmesg_segfault_parsing(self):
        """Tests parsing Linux kernel dmesg segfault line."""
        dmesg_line = "a.out[4201]: segfault at 61616164 ip 0000000061616164 sp 00007fffffffe020 error 4 in a.out"
        analysis = CrashReplayEngine.analyze(dmesg_line)
        self.assertEqual(analysis.classification, CLASS_CONTROL_FLOW_HIJACK)
        self.assertEqual(analysis.cyclic_offset, 12)

    # ---------------------------------------------------------------------
    # 3. Crash Classification: Other Vulnerabilities
    # ---------------------------------------------------------------------

    def test_null_pointer_dereference(self):
        """Tests Null Pointer Dereference detection (first page memory fault)."""
        crash_dict = {
            "signal": "SIGSEGV",
            "fault_address": 0x0,
            "registers": {
                "eip": 0x08048450,
                "esp": 0xFFFFD000,
            },
        }
        analysis = CrashReplayEngine.analyze(crash_dict)
        self.assertEqual(analysis.classification, CLASS_NULL_POINTER_DEREFERENCE)
        self.assertFalse(analysis.control_flow_hijacked)
        self.assertEqual(analysis.signal.fault_address, 0x0)

        # Near-null pointer (offset within struct, e.g. 0x28)
        crash_dict_offset = {
            "signal": "SIGSEGV",
            "fault_address": 0x28,
            "registers": {"eip": 0x08048450, "esp": 0xFFFFD000},
        }
        analysis_offset = CrashReplayEngine.analyze(crash_dict_offset)
        self.assertEqual(analysis_offset.classification, CLASS_NULL_POINTER_DEREFERENCE)

    def test_heap_corruption(self):
        """Tests Heap Corruption / Double-free detection."""
        crash_text = """
*** Error in `./vuln`: double free or corruption (out): 0x0804b008 ***
Program received signal SIGABRT, Aborted.
Fault address: 0x0804b008
eip: 0xb7e23160
"""
        analysis = CrashReplayEngine.analyze(crash_text)
        self.assertEqual(analysis.classification, CLASS_HEAP_CORRUPTION)
        self.assertIn("heap_corruption_detected", analysis.details)

    def test_stack_buffer_overflow_via_canary(self):
        """Tests Stack Buffer Overflow detection via stack canary check failure."""
        crash_text = """
*** stack smashing detected ***: terminated
Program received signal SIGABRT, Aborted.
eip: 0xb7e23160
"""
        analysis = CrashReplayEngine.analyze(crash_text)
        self.assertEqual(analysis.classification, CLASS_STACK_BUFFER_OVERFLOW)
        self.assertTrue(analysis.details.get("canary_destruction_detected"))

    def test_stack_buffer_overflow_via_frame_pointer(self):
        """Tests Stack Buffer Overflow detection via EBP overwrite when EIP is intact."""
        crash_dict = {
            "signal": "SIGSEGV",
            "fault_address": 0xDEADBEEF,
            "registers": {
                "eip": 0x08048500,  # Valid code address
                "ebp": 0x61616163,  # Cyclic pattern 'caaa'
                "esp": 0xFFFFD000,
            },
        }
        analysis = CrashReplayEngine.analyze(crash_dict)
        self.assertEqual(analysis.classification, CLASS_STACK_BUFFER_OVERFLOW)
        self.assertTrue(analysis.details.get("stack_frame_corrupted"))
        self.assertEqual(analysis.details.get("bp_overwrite_offset"), 8)

    def test_divide_by_zero_and_illegal_instruction(self):
        """Tests SIGFPE and SIGILL signals."""
        fpe_trace = {"signal": "SIGFPE", "registers": {"eip": 0x08048400, "esp": 0xFFFFD000}}
        analysis_fpe = CrashReplayEngine.analyze(fpe_trace)
        self.assertEqual(analysis_fpe.classification, CLASS_DIVIDE_BY_ZERO)

        ill_trace = {"signal": "SIGILL", "registers": {"eip": 0x08048400, "esp": 0xFFFFD000}}
        analysis_ill = CrashReplayEngine.analyze(ill_trace)
        self.assertEqual(analysis_ill.classification, CLASS_ILLEGAL_INSTRUCTION)

    # ---------------------------------------------------------------------
    # 4. Security Mitigation Detection
    # ---------------------------------------------------------------------

    def test_mitigation_detection_dict(self):
        """Tests mitigation extraction from dictionary."""
        mit = MitigationDetector.detect({"nx": True, "pie": False, "canary": True, "relro": "Full"})
        self.assertTrue(mit.nx)
        self.assertFalse(mit.pie)
        self.assertTrue(mit.canary)
        self.assertEqual(mit.relro, "Full")

    def test_mitigation_detection_synthetic_elf(self):
        """Tests mitigation detection from synthetic ELF binary header."""
        # 64-bit ELF header with ET_DYN (PIE = True)
        # e_ident: 16 bytes
        e_ident = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 8
        # e_type = 3 (ET_DYN), e_machine = 0x3E (x86-64), e_version = 1, e_entry = 0, e_phoff = 64
        # e_shoff = 0, e_flags = 0, e_ehsize = 64, e_phentsize = 56, e_phnum = 2, e_shentsize = 64, e_shnum = 0, e_shstrndx = 0
        elf_hdr = struct.pack("<16sHHIQQQIHHHHHH", e_ident, 3, 0x3E, 1, 0x1000, 64, 0, 0, 64, 56, 2, 64, 0, 0)

        # Program header 1: PT_GNU_STACK (0x6474e551), flags = 6 (RW, non-executable -> NX enabled)
        ph1 = struct.pack("<IIQQQQQQ", 0x6474E551, 6, 0, 0, 0, 0, 0, 8)
        # Program header 2: PT_GNU_RELRO (0x6474e552), flags = 4 (R)
        ph2 = struct.pack("<IIQQQQQQ", 0x6474E552, 4, 0, 0, 0, 0, 0, 8)

        # String pool containing stack canary symbol and bind_now marker
        sym_data = b"__stack_chk_fail\x00BIND_NOW\x00"

        elf_blob = elf_hdr + ph1 + ph2 + sym_data
        mit = MitigationDetector.detect_from_elf(elf_blob)

        self.assertTrue(mit.nx)
        self.assertTrue(mit.pie)
        self.assertTrue(mit.canary)
        self.assertEqual(mit.relro, "Full")

    # ---------------------------------------------------------------------
    # 5. Fail-Closed Invariants & Adversarial Fuzzing
    # ---------------------------------------------------------------------

    def test_fail_closed_negative_cyclic_requests(self):
        """Ensures negative cyclic generation and search values are strictly rejected."""
        with self.assertRaises(ValueError):
            cyclic(-1)

        with self.assertRaises(ValueError):
            cyclic(-100)

        with self.assertRaises(ValueError):
            cyclic_find(-1)

        with self.assertRaises(ValueError):
            cyclic_find(-42)

    def test_fail_closed_out_of_bounds_length(self):
        """Ensures cyclic requests exceeding 64 KB memory ceiling raise ValueError."""
        with self.assertRaises(ValueError):
            cyclic(MAX_CYCLIC_LENGTH + 1)

    def test_fail_closed_invalid_sub_patterns(self):
        """Ensures invalid sub-patterns (out of alphabet or empty) are rejected or return -1."""
        with self.assertRaises(ValueError):
            cyclic_find("")

        with self.assertRaises(ValueError):
            cyclic_find(b"")

        # Characters not in alphabet 'a-z'
        self.assertEqual(cyclic_find("1234"), -1)
        self.assertEqual(cyclic_find(b"\xff\xff\xff\xff"), -1)
        self.assertEqual(cyclic_find("ABCD"), -1)

    def test_fail_closed_corrupted_crash_traces(self):
        """Ensures corrupted, empty, or negative crash trace inputs fail-closed."""
        with self.assertRaises(ValueError):
            CrashTraceParser.parse("")

        with self.assertRaises(ValueError):
            CrashTraceParser.parse({})

        # Negative register value in dict
        with self.assertRaises(ValueError):
            CrashTraceParser.parse({"signal": "SIGSEGV", "registers": {"eip": -5}})

        # Unsupported signal
        with self.assertRaises(ValueError):
            CrashTraceParser.parse({"signal": "SIGKILL"})

    def test_adversarial_register_fuzzing(self):
        """Fuzzes corrupted register values to ensure fail-closed execution."""
        fuzz_values = [0x0, 0x1, 0x7FFFFFFF, 0xFFFFFFFF, 0x61616164]
        for val in fuzz_values:
            crash = {
                "signal": "SIGSEGV",
                "fault_address": val,
                "registers": {"eip": val, "esp": 0xFFFFD000},
            }
            analysis = CrashReplayEngine.analyze(crash)
            self.assertIsInstance(analysis, CrashAnalysis)
            self.assertIn(analysis.classification, [
                CLASS_CONTROL_FLOW_HIJACK,
                CLASS_NULL_POINTER_DEREFERENCE,
                CLASS_UNKNOWN,
            ])

    # ---------------------------------------------------------------------
    # 6. Thermodynamic Memory Ceiling (<= 64 KB)
    # ---------------------------------------------------------------------

    def test_memory_allocation_ceiling(self):
        """Guarantees generator and analyzer operate strictly within <= 64 KB heap allocation."""
        tracemalloc.start()
        try:
            # 1. Generate pattern of 4096 bytes
            pat = cyclic(4096)
            # 2. Find offset of 0x61616164
            off = cyclic_find(0x61616164)
            # 3. Analyze crash trace
            trace = {
                "signal": "SIGSEGV",
                "fault_address": 0x61616164,
                "registers": {
                    "eip": 0x61616164,
                    "esp": 0xFFFFD000,
                    "ebp": 0x61616163,
                },
            }
            analysis = CrashReplayEngine.analyze(trace)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertEqual(off, 12)
        self.assertEqual(analysis.classification, CLASS_CONTROL_FLOW_HIJACK)
        self.assertLessEqual(
            peak,
            64 * 1024,
            f"Peak memory allocation {peak} bytes exceeded 64 KB ceiling",
        )


if __name__ == "__main__":
    unittest.main()
