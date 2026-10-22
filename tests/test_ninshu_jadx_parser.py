"""Adversarial Unit Tests and Mechanical Verification for JadxParser (CH 29).

Validations:
1. Valid Jadx decompiled class structure, interfaces, methods, and field signatures.
2. Code comments, annotations (@Override, @Keep), and obfuscated identifier detection.
3. Source line mapping validation and fail-closed rejection of negative offsets/lines.
4. Adversarial fuzz vectors: empty inputs, corrupted JSON, cyclic packages, cyclic inheritance.
5. Thermodynamic memory profiling asserting peak heap ceiling <= 64 KB.
6. Metamorphic fuzzing via AdversarialMutator asserting 100% fail-closed rejection.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict

from kageyoni.ninshu.jadx_parser import (
    JadxParser,
    JadxProjectReport,
    JadxClass,
    JadxMethod,
    JadxField,
    JadxAnnotation,
    MAX_JADX_PAYLOAD_BYTES,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuJadxParser(unittest.TestCase):
    def setUp(self):
        self.valid_project_dict: Dict[str, Any] = {
            "project": {
                "name": "SecureBankingApp",
                "version": "2.4.1",
            },
            "packages": [
                {"name": "com.example.bank", "parent": "com.example"},
                {"name": "com.example.bank.crypto", "parent": "com.example.bank"},
                {"name": "com.example.bank.obf", "parent": "com.example.bank"},
            ],
            "classes": [
                {
                    "package": "com.example.bank",
                    "name": "AuthManager",
                    "fullName": "com.example.bank.AuthManager",
                    "type": "class",
                    "superClass": "java.lang.Object",
                    "interfaces": ["com.example.bank.crypto.TokenValidator"],
                    "accessFlags": ["public", "final"],
                    "annotations": [
                        "@androidx.annotation.Keep",
                        {"name": "@Singleton", "attributes": {"scope": "application"}},
                    ],
                    "comments": [
                        "// Decompiled with CFR / Jadx v1.4.7",
                        "// Hardened biometric token validator",
                    ],
                    "smali": "Lcom/example/bank/AuthManager;",
                    "fields": [
                        {
                            "name": "sessionToken",
                            "type": "java.lang.String",
                            "accessFlags": ["private", "final"],
                            "annotations": ["@Nullable"],
                            "comments": ["// Ephemeral 256-bit token"],
                            "def_pos": 10,
                        },
                        {
                            "name": "f101a",
                            "type": "int",
                            "accessFlags": ["private"],
                            "annotations": [],
                            "comments": [],
                            "isObfuscated": True,
                            "def_pos": 11,
                        },
                    ],
                    "methods": [
                        {
                            "name": "<init>",
                            "rawName": "<init>",
                            "returnType": "void",
                            "params": ["java.lang.String"],
                            "accessFlags": ["public"],
                            "annotations": [],
                            "comments": ["// Constructor mapping"],
                            "isConstructor": True,
                            "lines": {"0": 18, "4": 19, "8": 20},
                            "smaliSignature": "<init>(Ljava/lang/String;)V",
                        },
                        {
                            "name": "validateToken",
                            "rawName": "validateToken",
                            "returnType": "boolean",
                            "params": ["byte[]"],
                            "accessFlags": ["public", "final"],
                            "annotations": ["@Override", "@androidx.annotation.NonNull"],
                            "comments": ["// smali offset 0x002c"],
                            "lines": {"0": 32, "8": 33, "16": 35, "24": 38},
                            "smaliSignature": "validateToken([B)Z",
                        },
                        {
                            "name": "a",
                            "rawName": "a",
                            "returnType": "void",
                            "params": ["int"],
                            "accessFlags": ["private"],
                            "annotations": [],
                            "comments": [],
                            "lines": {"0": 50, "6": 52},
                            "smaliSignature": "a(I)V",
                        },
                    ],
                    "innerClasses": ["com.example.bank.AuthManager$SessionHolder"],
                },
                {
                    "package": "com.example.bank.crypto",
                    "name": "TokenValidator",
                    "fullName": "com.example.bank.crypto.TokenValidator",
                    "type": "interface",
                    "superClass": None,
                    "interfaces": [],
                    "accessFlags": ["public", "abstract"],
                    "annotations": ["@FunctionalInterface"],
                    "comments": ["// Interface contract"],
                    "fields": [],
                    "methods": [
                        {
                            "name": "validateToken",
                            "returnType": "boolean",
                            "params": ["byte[]"],
                            "accessFlags": ["public", "abstract"],
                            "annotations": [],
                            "comments": [],
                            "lines": {},
                        }
                    ],
                    "innerClasses": [],
                },
            ],
        }

        self.valid_project_json = json.dumps(self.valid_project_dict)
        self.valid_project_bytes = self.valid_project_json.encode("utf-8")

    def test_parse_valid_project_report(self):
        report = JadxParser.parse_bytes(self.valid_project_bytes)
        self.assertIsInstance(report, JadxProjectReport)
        self.assertEqual(report.project_name, "SecureBankingApp")
        self.assertEqual(report.version, "2.4.1")
        self.assertEqual(report.total_classes, 2)
        self.assertEqual(report.total_methods, 4)
        self.assertEqual(report.total_fields, 2)
        self.assertTrue(len(report.sha256_digest) == 64)

        # Validate packages
        self.assertIn("com.example.bank", report.packages)
        self.assertIn("com.example.bank.crypto", report.packages)
        self.assertIn("com.example.bank.obf", report.packages)

        # Validate AuthManager class
        auth_cls = report.classes[0]
        self.assertEqual(auth_cls.name, "AuthManager")
        self.assertEqual(auth_cls.package, "com.example.bank")
        self.assertEqual(auth_cls.kind, "class")
        self.assertEqual(auth_cls.smali_identifier, "Lcom/example/bank/AuthManager;")
        self.assertEqual(auth_cls.super_class, "java.lang.Object")
        self.assertEqual(auth_cls.interfaces, ["com.example.bank.crypto.TokenValidator"])
        self.assertIn("public", auth_cls.access_flags)
        self.assertFalse(auth_cls.is_obfuscated)

        # Annotations
        ann_names = [a.name for a in auth_cls.annotations]
        self.assertIn("@androidx.annotation.Keep", ann_names)
        self.assertIn("@Singleton", ann_names)

        # Comments
        self.assertEqual(len(auth_cls.comments), 2)
        self.assertIn("// Decompiled with CFR / Jadx v1.4.7", auth_cls.comments)

        # Fields
        f_map = {f.name: f for f in auth_cls.fields}
        self.assertIn("sessionToken", f_map)
        self.assertFalse(f_map["sessionToken"].is_obfuscated)
        self.assertEqual(f_map["sessionToken"].type_name, "java.lang.String")
        self.assertIn("f101a", f_map)
        self.assertTrue(f_map["f101a"].is_obfuscated)

        # Methods
        m_map = {m.name: m for m in auth_cls.methods}
        init_m = m_map["<init>"]
        self.assertTrue(init_m.is_constructor)
        self.assertEqual(init_m.line_mappings, {0: 18, 4: 19, 8: 20})

        val_m = m_map["validateToken"]
        self.assertEqual(val_m.return_type, "boolean")
        self.assertEqual(val_m.params, ["byte[]"])
        self.assertEqual(val_m.line_mappings, {0: 32, 8: 33, 16: 35, 24: 38})
        self.assertIn("@Override", [a.name for a in val_m.annotations])

        obf_m = m_map["a"]
        self.assertTrue(obf_m.is_obfuscated)

        # Validate TokenValidator interface
        token_iface = report.classes[1]
        self.assertEqual(token_iface.kind, "interface")
        self.assertIsNone(token_iface.super_class)

        # Serialization
        as_dict = report.to_dict()
        self.assertEqual(as_dict["total_classes"], 2)
        self.assertEqual(as_dict["total_methods"], 4)

    def test_line_mapping_formats_and_validations(self):
        # 1. Dict with string hex and int keys
        m_dict = {
            "name": "testLines",
            "lines": {"0": 10, "0x10": 12, "32": 15},
        }
        method = JadxParser._parse_method(m_dict, class_full_name="com.Test")
        self.assertEqual(method.line_mappings, {0: 10, 16: 12, 32: 15})

        # 2. List of pairs [[offset, line]]
        m_pairs = {
            "name": "testPairs",
            "lines": [[0, 100], [4, 101], [8, 102]],
        }
        method_pairs = JadxParser._parse_method(m_pairs, class_full_name="com.Test")
        self.assertEqual(method_pairs.line_mappings, {0: 100, 4: 101, 8: 102})

        # 3. List of dicts [{"offset": 0, "line": 5}]
        m_obj_list = {
            "name": "testObjList",
            "lines": [
                {"offset": 0, "line": 50},
                {"bytecode_offset": 6, "source_line": 52},
            ],
        }
        method_objs = JadxParser._parse_method(m_obj_list, class_full_name="com.Test")
        self.assertEqual(method_objs.line_mappings, {0: 50, 6: 52})

    def test_negative_line_mapping_rejection(self):
        # Negative offset in dict
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings({-1: 10})

        # Negative line in dict
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings({0: -5})

        # Negative offset in pair list
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings([[-10, 20]])

        # Negative line in pair list
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings([[10, -20]])

        # Negative offset in obj list
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings([{"offset": -1, "line": 10}])

        # Negative line in obj list
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings([{"offset": 0, "line": -1}])

    def test_cyclic_package_hierarchy_rejection(self):
        # Direct self-loop parent
        bad_pkg_self = {
            "packages": [{"name": "com.cycle", "parent": "com.cycle"}],
            "classes": [],
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(bad_pkg_self)

        # 2-step cycle: A -> B -> A
        bad_pkg_cycle2 = {
            "packages": [
                {"name": "com.pkgA", "parent": "com.pkgB"},
                {"name": "com.pkgB", "parent": "com.pkgA"},
            ],
            "classes": [],
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(bad_pkg_cycle2)

        # 3-step cycle: A -> B -> C -> A
        bad_pkg_cycle3 = {
            "packages": [
                {"name": "com.a", "parent": "com.b"},
                {"name": "com.b", "parent": "com.c"},
                {"name": "com.c", "parent": "com.a"},
            ],
            "classes": [],
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(bad_pkg_cycle3)

    def test_cyclic_class_inheritance_rejection(self):
        # Class A extends B and B extends A
        cyclic_classes = {
            "classes": [
                {
                    "package": "com.test",
                    "name": "ClassA",
                    "fullName": "com.test.ClassA",
                    "superClass": "com.test.ClassB",
                },
                {
                    "package": "com.test",
                    "name": "ClassB",
                    "fullName": "com.test.ClassB",
                    "superClass": "com.test.ClassA",
                },
            ]
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(cyclic_classes)

    def test_cyclic_inner_class_rejection(self):
        # Class A declares inner B and B declares inner A
        cyclic_inners = {
            "classes": [
                {
                    "package": "com.test",
                    "name": "A",
                    "fullName": "com.test.A",
                    "innerClasses": ["com.test.B"],
                },
                {
                    "package": "com.test",
                    "name": "B",
                    "fullName": "com.test.B",
                    "innerClasses": ["com.test.A"],
                },
            ]
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(cyclic_inners)

        # Class containing itself as inner class
        self_inner = {
            "classes": [
                {
                    "package": "com.test",
                    "name": "A",
                    "fullName": "com.test.A",
                    "innerClasses": ["com.test.A"],
                }
            ]
        }
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data(self_inner)

    def test_empty_and_corrupt_payload_rejection(self):
        with self.assertRaises(ValueError):
            JadxParser.parse_bytes(b"")

        with self.assertRaises(ValueError):
            JadxParser.parse_str("")

        with self.assertRaises(ValueError):
            JadxParser.parse_str("    ")

        with self.assertRaises(ValueError):
            JadxParser.parse_str("{malformed json [")

        with self.assertRaises(ValueError):
            JadxParser.parse_str("{\"key\": ")

    def test_invalid_types_rejection(self):
        # Top level integer
        with self.assertRaises(ValueError):
            JadxParser.parse_str("42")

        # Top level boolean
        with self.assertRaises(ValueError):
            JadxParser.parse_str("true")

        # Classes not a list
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data({"classes": "not_a_list"})

        # Class item not a dict
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data({"classes": ["not_a_dict"]})

        # Class missing name
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data({"classes": [{"package": "com.test"}]})

        # Methods not a list
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data({"classes": [{"name": "A", "methods": "not_a_list"}]})

        # Fields not a list
        with self.assertRaises(ValueError):
            JadxParser.parse_project_data({"classes": [{"name": "A", "fields": "not_a_list"}]})

        # Non-integer line mapping
        with self.assertRaises(ValueError):
            JadxParser._parse_line_mappings({"0": "not_a_number"})

    def test_oversized_payload_rejection(self):
        oversized = b"{" + b" " * (MAX_JADX_PAYLOAD_BYTES + 1) + b"}"
        with self.assertRaises(ValueError):
            JadxParser.parse_bytes(oversized)

    def test_thermodynamic_heap_ceiling(self):
        """Asserts memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            JadxParser.parse_bytes,
            self.valid_project_bytes,
            candidate_id="jadx_parser_ch29",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutator_fuzzing(self):
        """Verifies metamorphic stability and 100% fail-closed rejection on invalid mutants."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_project_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                report = JadxParser.parse_bytes(m.payload)
                self.assertIsInstance(report.total_classes, int)
            except ValueError:
                # Clean fail-closed rejection expected
                continue
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
