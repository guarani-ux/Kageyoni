"""Unit & Adversarial Verification Suite for Ninshū LLDB Native Tracer Bridge (CH 21).

Tests:
1. Valid text dump parsing for breakpoint hits, watchpoints, signals, and backtraces.
2. Structured JSON parsing for Windows exception codes and Mach exceptions.
3. PlanComplete, Exec, and Trace stop reasons.
4. Fail-closed rejection on corrupted addresses, negative IDs, and negative frame indices.
5. Thermodynamic profiling (asserts peak heap <= 64 KB).
6. Adversarial mutant fuzzing (100% fail-closed rejection on invalid mutants).
"""
import json
import unittest

from kageyoni.ninshu.lldb_tracer_parser import (
    LLDBTracerParser,
    STOP_REASON_BREAKPOINT,
    STOP_REASON_EXCEPTION,
    STOP_REASON_EXEC,
    STOP_REASON_PLAN_COMPLETE,
    STOP_REASON_SIGNAL,
    STOP_REASON_TRACE,
    STOP_REASON_WATCHPOINT,
    decode_stop_reason,
    parse_address_token,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuLLDBTracerParser(unittest.TestCase):
    def setUp(self):
        self.sample_text_dump = (
            "* thread #1: tid = 0x1f03, name = 'main_thread', queue = 'com.apple.main-thread', "
            "stop reason = breakpoint 1.1\n"
            "  * frame #0: 0x0000000100000f50 a.out`main(argc=1, argv=0x7fff5fbff8b0) + 16 at main.c:10:5\n"
            "    frame #1: 0x00007fff8d2d55ad libsystem_c.dylib`start + 1\n"
            "thread #2: tid = 0x1f04, name = 'worker_thread', queue = 'default', "
            "stop reason = signal SIGSEGV: invalid address (fault address: 0x0)\n"
            "    frame #0: 0x00007fff91234567 libsystem_kernel.dylib`__pthread_kill + 10\n"
            "    frame #1: 0x0000000100001234 a.out`worker_func at worker.c:42\n"
        )

        self.sample_json_dict = {
            "process_id": 12345,
            "selected_thread_id": "0x1f03",
            "threads": [
                {
                    "thread_id": "0x1f03",
                    "thread_index": 1,
                    "name": "gui_thread",
                    "queue": "render",
                    "stop_reason": {
                        "reason": "eStopReasonException",
                        "description": "Exception 0xC0000005: STATUS_ACCESS_VIOLATION",
                        "exception_code": "0xC0000005",
                    },
                    "frames": [
                        {
                            "index": 0,
                            "pc": "0x7ff7a0123456",
                            "sp": "0x7ffee0001000",
                            "fp": "0x7ffee0001080",
                            "module": "ntdll.dll",
                            "symbol": "RtlDispatchException",
                            "symbol_offset": "0x20",
                            "source_file": "ntdll.c",
                            "source_line": 150,
                            "source_column": 4,
                        },
                        {
                            "index": 1,
                            "pc": "0x7ff7a0001000",
                            "module": "app.exe",
                            "symbol": "CrashHandler",
                            "source_file": "crash.cpp",
                            "source_line": 88,
                        },
                    ],
                }
            ],
        }

    def test_text_dump_parsing(self):
        """Verify parsing of standard LLDB text dump."""
        report = LLDBTracerParser.parse(self.sample_text_dump)
        self.assertEqual(len(report.threads), 2)
        self.assertEqual(report.total_frames, 4)
        self.assertEqual(report.selected_thread_id, 0x1F03)

        t1 = report.threads[0]
        self.assertEqual(t1.thread_id, 0x1F03)
        self.assertEqual(t1.thread_index, 1)
        self.assertEqual(t1.name, "main_thread")
        self.assertEqual(t1.queue, "com.apple.main-thread")
        self.assertEqual(t1.stop_reason.reason, STOP_REASON_BREAKPOINT)
        self.assertEqual(t1.stop_reason.breakpoint_id, 1)
        self.assertEqual(t1.stop_reason.extra.get("breakpoint_sub_id"), 1)
        self.assertEqual(len(t1.frames), 2)

        f0 = t1.frames[0]
        self.assertEqual(f0.index, 0)
        self.assertEqual(f0.pc, 0x0000000100000F50)
        self.assertEqual(f0.module_name, "a.out")
        self.assertIn("main", f0.symbol_name)
        self.assertEqual(f0.source_file, "main.c")
        self.assertEqual(f0.source_line, 10)
        self.assertEqual(f0.source_column, 5)
        self.assertEqual(f0.symbol_offset, 16)

        t2 = report.threads[1]
        self.assertEqual(t2.thread_id, 0x1F04)
        self.assertEqual(t2.stop_reason.reason, STOP_REASON_SIGNAL)
        self.assertEqual(t2.stop_reason.signal_name, "SIGSEGV")
        self.assertEqual(t2.stop_reason.signal_number, 11)

    def test_json_parsing_and_windows_exception(self):
        """Verify parsing of JSON telemetry with Windows STATUS_ACCESS_VIOLATION."""
        report = LLDBTracerParser.parse(self.sample_json_dict)
        self.assertEqual(report.process_id, 12345)
        self.assertEqual(len(report.threads), 1)

        t = report.threads[0]
        self.assertEqual(t.stop_reason.reason, STOP_REASON_EXCEPTION)
        self.assertEqual(t.stop_reason.exception_code, 0xC0000005)
        self.assertEqual(t.stop_reason.exception_name, "STATUS_ACCESS_VIOLATION")

        self.assertEqual(len(t.frames), 2)
        f0 = t.frames[0]
        self.assertEqual(f0.pc, 0x7FF7A0123456)
        self.assertEqual(f0.sp, 0x7FFEE0001000)
        self.assertEqual(f0.fp, 0x7FFEE0001080)
        self.assertEqual(f0.module_name, "ntdll.dll")
        self.assertEqual(f0.symbol_name, "RtlDispatchException")
        self.assertEqual(f0.symbol_offset, 0x20)

    def test_stop_reason_decoders(self):
        """Verify decoding of diverse stop reasons."""
        # Watchpoint
        wp = decode_stop_reason("eStopReasonWatchpoint", "watchpoint 2: address = 0x7fff5fbff8b0")
        self.assertEqual(wp.reason, STOP_REASON_WATCHPOINT)
        self.assertEqual(wp.watchpoint_address, 0x7FFF5FBFF8B0)

        # PlanComplete
        plan = decode_stop_reason("eStopReasonPlanComplete", "step over finished")
        self.assertEqual(plan.reason, STOP_REASON_PLAN_COMPLETE)
        self.assertTrue(plan.plan_complete)

        # Exec
        ex = decode_stop_reason("eStopReasonExec", "execve replaced image")
        self.assertEqual(ex.reason, STOP_REASON_EXEC)
        self.assertTrue(ex.exec_replaced)

        # Trace
        tr = decode_stop_reason("trace", "single step instruction")
        self.assertEqual(tr.reason, STOP_REASON_TRACE)

        # Mach exception
        mach = decode_stop_reason("eStopReasonException", "EXC_BAD_ACCESS (code=1, address=0x0)")
        self.assertEqual(mach.reason, STOP_REASON_EXCEPTION)
        self.assertEqual(mach.exception_name, "EXC_BAD_ACCESS")
        self.assertEqual(mach.exception_code, 1)

    def test_fail_closed_rejection(self):
        """Verify rejection on invalid or corrupted inputs."""
        # Negative address
        with self.assertRaises(ValueError):
            parse_address_token("-0x1000")

        # Corrupted hex address
        with self.assertRaises(ValueError):
            parse_address_token("0xGHIJK")

        # Address overflow (> 64-bit)
        with self.assertRaises(ValueError):
            parse_address_token(0x10000000000000000)

        # Unknown stop reason
        with self.assertRaises(ValueError):
            decode_stop_reason("eStopReasonCorruptedReason")

        # Empty string
        with self.assertRaises(ValueError):
            LLDBTracerParser.parse("")

        # Empty payload
        with self.assertRaises(ValueError):
            LLDBTracerParser.parse(b"")

        # Corrupted JSON
        with self.assertRaises(Exception):
            LLDBTracerParser.parse("{ invalid json }")

        # Negative thread index
        with self.assertRaises(ValueError):
            LLDBTracerParser.parse({"threads": [{"thread_id": 1, "thread_index": -5, "frames": []}]})

        # Negative frame index
        with self.assertRaises(ValueError):
            LLDBTracerParser.parse({
                "threads": [{
                    "thread_id": 1,
                    "thread_index": 0,
                    "frames": [{"index": -1, "pc": "0x1000"}]
                }]
            })

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            LLDBTracerParser.parse,
            self.sample_text_dump,
            candidate_id="lldb_tracer_parser_ch21",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify adversarial mutants either parse cleanly or fail closed safely."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.sample_text_dump.encode("utf-8"))
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                report = LLDBTracerParser.parse(m.payload)
                self.assertIsInstance(report.total_frames, int)
            except ValueError:
                # Proper fail-closed validation rejection
                pass
            except UnicodeDecodeError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
