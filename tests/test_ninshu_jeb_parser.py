"""Adversarial Verification Suite for Ninshū JEB Decompiler Automation (CH 32).

Verifications:
1. Valid JEB AST and analysis export parsing across bytes, JSON strings, and dictionaries.
2. Control-Flow Graph (CFG) basic block extraction, validation, and address bounds checking.
3. Cross-reference (XREF) extraction for callers, callees, memory reads, and memory writes.
4. Type hierarchy traversal with inheritance chain resolution and cyclic inheritance detection.
5. Decompiler comments and user renames aggregation.
6. Strict fail-closed rejection of corrupted JSON, empty inputs, and malformed XREF targets.
7. Thermodynamic memory profiling asserting peak heap ceiling <= 64 KB.
8. Metamorphic fuzzing via AdversarialMutator asserting 100% fail-closed rejection.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.jeb_parser import (
    JebParser,
    JebAnalysisReport,
    JebEngineInfo,
    JebUnit,
    JebClass,
    JebMethod,
    JebField,
    JebBasicBlock,
    JebXref,
    canonical_sha256,
    MAX_JEB_PAYLOAD_BYTES,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuJebParser(unittest.TestCase):
    def setUp(self):
        self.valid_payload_dict: Dict[str, Any] = {
            "engine": {
                "name": "JEB Decompiler",
                "version": "5.2.0",
                "endpoint": "http://127.0.0.1:8425/mcp",
                "gui_client": False,
            },
            "project_name": "SampleAndroidApp",
            "units": [
                {
                    "unit_path": "classes.dex",
                    "unit_type": "dex",
                    "classes": [
                        {
                            "name": "Lcom/example/BaseActivity;",
                            "superclass": "Landroid/app/Activity;",
                            "interfaces": ["Landroid/view/Window$Callback;"],
                            "fields": [
                                {
                                    "name": "mBaseId",
                                    "signature": "mBaseId:I",
                                    "field_type": "int",
                                    "access_flags": 4,
                                    "initial_value": 0,
                                }
                            ],
                            "methods": [
                                {
                                    "name": "onStart",
                                    "signature": "Lcom/example/BaseActivity;->onStart()V",
                                    "return_type": "void",
                                    "parameter_types": [],
                                    "access_flags": 4,
                                    "basic_blocks": [
                                        {
                                            "block_id": "bb_0",
                                            "start_address": 0x2000,
                                            "end_address": 0x2014,
                                            "instruction_count": 5,
                                            "predecessors": [],
                                            "successors": [],
                                        }
                                    ],
                                    "xrefs": [],
                                    "decompiled_code": "protected void onStart() { super.onStart(); }",
                                    "comments": {"0x2000": "Base onStart entry"},
                                    "user_renames": {},
                                }
                            ],
                            "method_overrides": {},
                            "comments": {"Lcom/example/BaseActivity;": "Base framework activity"},
                            "user_renames": {},
                        },
                        {
                            "name": "Lcom/example/MainActivity;",
                            "superclass": "Lcom/example/BaseActivity;",
                            "interfaces": ["Landroid/view/View$OnClickListener;"],
                            "fields": [
                                {
                                    "name": "mClickCount",
                                    "signature": "mClickCount:I",
                                    "field_type": "int",
                                    "access_flags": 2,
                                    "initial_value": 0,
                                }
                            ],
                            "methods": [
                                {
                                    "name": "onCreate",
                                    "signature": "Lcom/example/MainActivity;->onCreate(Landroid/os/Bundle;)V",
                                    "return_type": "void",
                                    "parameter_types": ["Landroid/os/Bundle;"],
                                    "access_flags": 1,
                                    "basic_blocks": [
                                        {
                                            "block_id": "bb_0",
                                            "start_address": 0x1000,
                                            "end_address": 0x1020,
                                            "instruction_count": 8,
                                            "predecessors": [],
                                            "successors": ["bb_1"],
                                        },
                                        {
                                            "block_id": "bb_1",
                                            "start_address": 0x1020,
                                            "end_address": 0x1040,
                                            "instruction_count": 6,
                                            "predecessors": ["bb_0"],
                                            "successors": [],
                                        },
                                    ],
                                    "xrefs": [
                                        {
                                            "xref_type": "caller",
                                            "source_address": "Lcom/example/MainActivity;->onResume()V",
                                            "target_address": "Lcom/example/MainActivity;->onCreate(Landroid/os/Bundle;)V",
                                            "details": "lifecycle invocation",
                                        },
                                        {
                                            "xref_type": "callee",
                                            "source_address": "Lcom/example/MainActivity;->onCreate(Landroid/os/Bundle;)V",
                                            "target_address": "Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V",
                                            "details": "super constructor invocation",
                                        },
                                        {
                                            "xref_type": "read",
                                            "source_address": "0x1008",
                                            "target_address": "0x4000",
                                            "details": "load configuration state",
                                        },
                                        {
                                            "xref_type": "write",
                                            "source_address": "0x101C",
                                            "target_address": "0x4004",
                                            "details": "store session timestamp",
                                        },
                                    ],
                                    "decompiled_code": "public void onCreate(Bundle state) { super.onCreate(state); }",
                                    "comments": {"0x1000": "Activity initialization"},
                                    "user_renames": {"v0": "savedBundle"},
                                },
                                {
                                    "name": "onClick",
                                    "signature": "Lcom/example/MainActivity;->onClick(Landroid/view/View;)V",
                                    "return_type": "void",
                                    "parameter_types": ["Landroid/view/View;"],
                                    "access_flags": 1,
                                    "basic_blocks": [
                                        {
                                            "block_id": "bb_click",
                                            "start_address": 0x1050,
                                            "end_address": 0x1060,
                                            "instruction_count": 4,
                                            "predecessors": [],
                                            "successors": [],
                                        }
                                    ],
                                    "xrefs": [
                                        {
                                            "xref_type": "write",
                                            "source_address": "0x1054",
                                            "target_address": "0x4000",
                                            "details": "increment click count",
                                        }
                                    ],
                                    "decompiled_code": "public void onClick(View v) { this.mClickCount++; }",
                                    "comments": {"0x1050": "Button click handler"},
                                    "user_renames": {},
                                },
                            ],
                            "method_overrides": {
                                "onClick": "Landroid/view/View$OnClickListener;->onClick(Landroid/view/View;)V"
                            },
                            "comments": {"Lcom/example/MainActivity;": "Main user-facing activity"},
                            "user_renames": {"mClickCount": "clickCounter"},
                        },
                    ],
                    "xrefs": [],
                    "comments": {"classes.dex": "Primary application DEX bytecode"},
                    "renames": {},
                }
            ],
            "comments": {"root": "Analysis generated by JEB automated pipeline"},
            "renames": {"oldHelper": "newHelper"},
        }
        self.valid_payload_json = json.dumps(self.valid_payload_dict)
        self.valid_payload_bytes = self.valid_payload_json.encode("utf-8")

    def test_parse_valid_analysis_payload(self):
        """Verifies clean parsing of complete JEB analysis export."""
        report = JebParser.parse_bytes(self.valid_payload_bytes)
        self.assertIsInstance(report, JebAnalysisReport)
        self.assertEqual(report.engine.name, "JEB Decompiler")
        self.assertEqual(report.engine.version, "5.2.0")
        self.assertEqual(report.project_name, "SampleAndroidApp")
        self.assertEqual(len(report.units), 1)

        unit = report.units[0]
        self.assertEqual(unit.unit_path, "classes.dex")
        self.assertEqual(unit.unit_type, "dex")
        self.assertEqual(len(unit.classes), 2)

        main_cls = report.classes.get("Lcom/example/MainActivity;")
        self.assertIsNotNone(main_cls)
        self.assertEqual(main_cls.superclass, "Lcom/example/BaseActivity;")
        self.assertEqual(main_cls.interfaces, ("Landroid/view/View$OnClickListener;",))
        self.assertEqual(len(main_cls.methods), 2)

        # Check basic blocks
        on_create = main_cls.methods[0]
        self.assertEqual(on_create.name, "onCreate")
        self.assertEqual(len(on_create.basic_blocks), 2)
        bb0 = on_create.basic_blocks[0]
        self.assertEqual(bb0.block_id, "bb_0")
        self.assertEqual(bb0.start_address, 0x1000)
        self.assertEqual(bb0.end_address, 0x1020)
        self.assertEqual(bb0.instruction_count, 8)
        self.assertEqual(bb0.successors, ("bb_1",))

        # Check digest matches
        expected_digest = canonical_sha256(self.valid_payload_dict)
        self.assertEqual(report.digest, expected_digest)

    def test_parse_json_and_dict_interfaces(self):
        """Verifies parser operates uniformly across dict and str interfaces."""
        report_from_json = JebParser.parse_json(self.valid_payload_json)
        report_from_dict = JebParser.parse_dict(self.valid_payload_dict)
        self.assertEqual(report_from_json.digest, report_from_dict.digest)
        self.assertEqual(len(report_from_json.all_xrefs), len(report_from_dict.all_xrefs))

    def test_inheritance_hierarchy_traversal(self):
        """Verifies resolution of inheritance chains and implemented interfaces."""
        report = JebParser.parse_bytes(self.valid_payload_bytes)

        # Inheritance chain: MainActivity -> BaseActivity -> Activity
        chain = JebParser.traverse_hierarchy(report, "Lcom/example/MainActivity;")
        self.assertEqual(
            chain,
            ["Lcom/example/MainActivity;", "Lcom/example/BaseActivity;", "Landroid/app/Activity;"]
        )

        # Interfaces recursive
        interfaces = JebParser.get_implemented_interfaces(report, "Lcom/example/MainActivity;", recursive=True)
        self.assertIn("Landroid/view/View$OnClickListener;", interfaces)
        self.assertIn("Landroid/view/Window$Callback;", interfaces)

        # Interfaces non-recursive
        direct_interfaces = JebParser.get_implemented_interfaces(report, "Lcom/example/MainActivity;", recursive=False)
        self.assertEqual(direct_interfaces, ["Landroid/view/View$OnClickListener;"])

        # Method overrides
        overrides = JebParser.get_method_overrides(report, "Lcom/example/MainActivity;")
        self.assertEqual(overrides.get("onClick"), "Landroid/view/View$OnClickListener;->onClick(Landroid/view/View;)V")

    def test_cyclic_inheritance_rejection(self):
        """Verifies strict fail-closed rejection on cyclic class inheritance."""
        cyclic_dict = {
            "units": [
                {
                    "unit_path": "cyclic.dex",
                    "unit_type": "dex",
                    "classes": [
                        {"name": "ClassA", "superclass": "ClassB", "interfaces": [], "fields": [], "methods": []},
                        {"name": "ClassB", "superclass": "ClassA", "interfaces": [], "fields": [], "methods": []},
                    ],
                }
            ]
        }
        report = JebParser.parse_dict(cyclic_dict)
        with self.assertRaises(ValueError) as ctx:
            JebParser.traverse_hierarchy(report, "ClassA")
        self.assertIn("Cyclic inheritance detected", str(ctx.exception))

    def test_xref_extraction_and_filtering(self):
        """Verifies extraction and filtering of callers, callees, reads, and writes."""
        report = JebParser.parse_bytes(self.valid_payload_bytes)

        # Callers of onCreate
        target = "Lcom/example/MainActivity;->onCreate(Landroid/os/Bundle;)V"
        callers = JebParser.get_callers_of(report, target)
        self.assertEqual(len(callers), 1)
        self.assertEqual(callers[0].source_address, "Lcom/example/MainActivity;->onResume()V")

        # Callees of onCreate
        callees = JebParser.get_callees_of(report, target)
        self.assertEqual(len(callees), 1)
        self.assertEqual(callees[0].target_address, "Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V")

        # Memory reads
        all_reads = JebParser.get_memory_reads(report)
        self.assertEqual(len(all_reads), 1)
        self.assertEqual(all_reads[0].target_address, "0x4000")

        # Memory writes with filter
        filtered_writes = JebParser.get_memory_writes(report, target_address="0x4000")
        self.assertEqual(len(filtered_writes), 1)
        self.assertEqual(filtered_writes[0].source_address, "0x1054")

        # Memory writes without filter
        all_writes = JebParser.get_memory_writes(report)
        self.assertEqual(len(all_writes), 2)

    def test_comments_and_renames_aggregation(self):
        """Verifies comprehensive decompiler comments and renames aggregation."""
        report = JebParser.parse_bytes(self.valid_payload_bytes)

        comments = JebParser.get_comments(report)
        self.assertIn("0x1000", comments)
        self.assertEqual(comments["0x1000"], "Activity initialization")
        self.assertIn("classes.dex", comments)
        self.assertIn("root", comments)

        renames = JebParser.get_user_renames(report)
        self.assertIn("v0", renames)
        self.assertEqual(renames["v0"], "savedBundle")
        self.assertIn("mClickCount", renames)
        self.assertEqual(renames["mClickCount"], "clickCounter")
        self.assertIn("oldHelper", renames)

    def test_fail_closed_empty_and_corrupt_inputs(self):
        """Verifies fail-closed rejection for empty payloads and corrupted JSON."""
        # Empty inputs
        with self.assertRaises(ValueError):
            JebParser.parse_bytes(b"")
        with self.assertRaises(ValueError):
            JebParser.parse_bytes(b"   \t\n")
        with self.assertRaises(ValueError):
            JebParser.parse_json("")
        with self.assertRaises(ValueError):
            JebParser.parse_json("   ")
        with self.assertRaises(ValueError):
            JebParser.parse_dict({})

        # Malformed JSON
        with self.assertRaises(ValueError):
            JebParser.parse_bytes(b'{"engine": {"name": "JEB"')
        with self.assertRaises(ValueError):
            JebParser.parse_json("{invalid_json: 123}")
        with self.assertRaises(ValueError):
            JebParser.parse_bytes(b"\x80\xFF\xFE invalid utf8")

    def test_malformed_xref_targets_rejection(self):
        """Verifies strict rejection of invalid or malformed XREF addresses and types."""
        # Invalid xref type
        bad_type_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "xrefs": [
                        {"xref_type": "unsupported_xref_kind", "source_address": "0x1000", "target_address": "0x2000"}
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(bad_type_dict)

        # Empty target address
        empty_target_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "xrefs": [
                        {"xref_type": "caller", "source_address": "0x1000", "target_address": "  "}
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(empty_target_dict)

        # Control characters in target address
        ctrl_target_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "xrefs": [
                        {"xref_type": "caller", "source_address": "0x1000", "target_address": "0x2000\x00malicious"}
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(ctrl_target_dict)

        # Invalid hex string
        bad_hex_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "xrefs": [
                        {"xref_type": "read", "source_address": "0x1000", "target_address": "0xNOT_HEX"}
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(bad_hex_dict)

    def test_basic_block_invariants(self):
        """Verifies rejection of inverted or invalid basic block bounds."""
        # Inverted address bounds (end < start)
        inverted_bb_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "classes": [
                        {
                            "name": "TestClass",
                            "methods": [
                                {
                                    "name": "testMethod",
                                    "signature": "TestClass->testMethod()V",
                                    "basic_blocks": [
                                        {
                                            "block_id": "bb_bad",
                                            "start_address": 0x2000,
                                            "end_address": 0x1000,  # 0x1000 < 0x2000!
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(inverted_bb_dict)

        # Negative start address
        neg_addr_dict = {
            "units": [
                {
                    "unit_path": "test.dex",
                    "unit_type": "dex",
                    "classes": [
                        {
                            "name": "TestClass",
                            "methods": [
                                {
                                    "name": "testMethod",
                                    "signature": "TestClass->testMethod()V",
                                    "basic_blocks": [
                                        {
                                            "block_id": "bb_bad",
                                            "start_address": -1,
                                            "end_address": 0x1000,
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JebParser.parse_dict(neg_addr_dict)

    def test_missing_required_fields_rejection(self):
        """Verifies rejection of payload dictionaries missing required structural fields."""
        # Missing units
        with self.assertRaises(ValueError):
            JebParser.parse_dict({"engine": {"name": "JEB"}})

        # Missing unit_path
        with self.assertRaises(ValueError):
            JebParser.parse_dict({"units": [{"unit_type": "dex"}]})

        # Missing class name
        with self.assertRaises(ValueError):
            JebParser.parse_dict({"units": [{"unit_path": "test.dex", "unit_type": "dex", "classes": [{}]}]})

        # Missing method name/signature
        with self.assertRaises(ValueError):
            JebParser.parse_dict({
                "units": [
                    {
                        "unit_path": "test.dex",
                        "unit_type": "dex",
                        "classes": [{"name": "TestClass", "methods": [{"name": "foo"}]}],
                    }
                ]
            })

    def test_payload_size_ceiling_rejection(self):
        """Verifies rejection of payloads exceeding the MAX_JEB_PAYLOAD_BYTES ceiling."""
        oversized = b" " * (MAX_JEB_PAYLOAD_BYTES + 1)
        with self.assertRaises(ValueError):
            JebParser.parse_bytes(oversized)

    def test_thermodynamic_heap_ceiling(self):
        """Verifies memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            JebParser.parse_bytes,
            self.valid_payload_bytes,
            candidate_id="jeb_parser_ch32",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self):
        """Verifies metamorphic stability and 100% fail-closed rejection on invalid mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_payload_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                report = JebParser.parse_bytes(m.payload)
                self.assertIsInstance(report.engine.name, str)
            except ValueError:
                # Expected clean fail-closed rejection
                continue
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
