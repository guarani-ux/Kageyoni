"""Adversarial unit tests and heap compliance checks for NapiBridgeParser (CH 24)."""
from __future__ import annotations

import struct
import tracemalloc
import unittest

from kageyoni.ninshu.napi_bridge_parser import (
    IMAGE_FILE_MACHINE_AMD64,
    IMAGE_FILE_MACHINE_I386,
    NAPI_ATTR_CONFIGURABLE,
    NAPI_ATTR_DEFAULT,
    NAPI_ATTR_ENUMERABLE,
    NAPI_ATTR_STATIC,
    NAPI_ATTR_WRITABLE,
    NODE_API_ENTRYPOINTS,
    MsvcDemangledSymbol,
    MsvcDemangler,
    NapiBridgeBuilder,
    NapiBridgeParser,
    NapiBridgeSummary,
    NapiExportedFunction,
    NapiPropertyDescriptor,
)


class TestNapiBridgeParser(unittest.TestCase):
    """Rigorous verification suite for Node-API Windows C++ DLL inspector and demangler."""

    def test_msvc_demangle_free_functions(self):
        """Tests demangling of C++ free functions across calling conventions."""
        cases = [
            (
                "?Init@@YAXPEAUenv__@@PEAUvalue__@@@Z",
                "Init",
                (),
                False,
                False,
                "__cdecl",
                "void",
                ("struct env__ *", "struct value__ *"),
                "void __cdecl Init(struct env__ *, struct value__ *)",
            ),
            (
                "?CalculateSum@@YAHHH@Z",
                "CalculateSum",
                (),
                False,
                False,
                "__cdecl",
                "int",
                ("int", "int"),
                "int __cdecl CalculateSum(int, int)",
            ),
            (
                "?StdCallWorker@@YGXXZ",
                "StdCallWorker",
                (),
                False,
                False,
                "__stdcall",
                "void",
                ("void",),
                "void __stdcall StdCallWorker(void)",
            ),
            (
                "?FastProcessor@@YI_NH@Z",
                "FastProcessor",
                (),
                False,
                False,
                "__fastcall",
                "bool",
                ("int",),
                "bool __fastcall FastProcessor(int)",
            ),
            (
                "?VectorMath@@YKNN@Z",
                "VectorMath",
                (),
                False,
                False,
                "__vectorcall",
                "double",
                ("double",),
                "double __vectorcall VectorMath(double)",
            ),
        ]

        for raw, unqual, scope, is_member, is_static, conv, ret, params, expected_demangled in cases:
            res = MsvcDemangler.demangle(raw)
            self.assertEqual(res.unqualified_name, unqual)
            self.assertEqual(res.scope, scope)
            self.assertEqual(res.is_member_method, is_member)
            self.assertEqual(res.is_static, is_static)
            self.assertEqual(res.calling_convention, conv)
            self.assertEqual(res.return_type, ret)
            self.assertEqual(res.parameter_types, params)
            self.assertEqual(res.demangled, expected_demangled)
            d = res.to_dict()
            self.assertEqual(d["unqualified_name"], unqual)
            self.assertEqual(d["calling_convention"], conv)

    def test_msvc_demangle_member_methods(self):
        """Tests demangling of class member methods, scopes, access modifiers, and static/const."""
        cases = [
            (
                "?Method@MyClass@@QAEXXZ",
                "Method",
                ("MyClass",),
                "MyClass::Method",
                True,
                False,
                False,
                False,
                "public",
                "__thiscall",
                "void",
                ("void",),
                "public: void __thiscall MyClass::Method(void)",
            ),
            (
                "?GetCounter@BridgeClass@@QBEHXZ",
                "GetCounter",
                ("BridgeClass",),
                "BridgeClass::GetCounter",
                True,
                False,
                False,
                True,
                "public",
                "__thiscall",
                "int",
                ("void",),
                "public: int __thiscall BridgeClass::GetCounter(void) const",
            ),
            (
                "?CreateInstance@Factory@@SAHXZ",
                "CreateInstance",
                ("Factory",),
                "Factory::CreateInstance",
                True,
                True,
                False,
                False,
                "public",
                "__cdecl",
                "int",
                ("void",),
                "public: static int __cdecl Factory::CreateInstance(void)",
            ),
            (
                "?VirtualDraw@Renderer@@UAEXXZ",
                "VirtualDraw",
                ("Renderer",),
                "Renderer::VirtualDraw",
                True,
                False,
                True,
                False,
                "public",
                "__thiscall",
                "void",
                ("void",),
                "public: virtual void __thiscall Renderer::VirtualDraw(void)",
            ),
            (
                "?InternalHook@Engine@Core@@IAEXXZ",
                "InternalHook",
                ("Core", "Engine"),
                "Core::Engine::InternalHook",
                True,
                False,
                False,
                False,
                "protected",
                "__thiscall",
                "void",
                ("void",),
                "protected: void __thiscall Core::Engine::InternalHook(void)",
            ),
            (
                "?SecretKey@Vault@@AAEXXZ",
                "SecretKey",
                ("Vault",),
                "Vault::SecretKey",
                True,
                False,
                False,
                False,
                "private",
                "__thiscall",
                "void",
                ("void",),
                "private: void __thiscall Vault::SecretKey(void)",
            ),
            (
                "?ExplicitCdecl@Bridge@@QAAXXZ",
                "ExplicitCdecl",
                ("Bridge",),
                "Bridge::ExplicitCdecl",
                True,
                False,
                False,
                False,
                "public",
                "__cdecl",
                "void",
                ("void",),
                "public: void __cdecl Bridge::ExplicitCdecl(void)",
            ),
        ]

        for raw, unqual, scope, qual, is_member, is_static, is_virtual, is_const, access, conv, ret, params, expected_demangled in cases:
            res = MsvcDemangler.demangle(raw)
            self.assertEqual(res.unqualified_name, unqual)
            self.assertEqual(res.scope, scope)
            self.assertEqual(res.qualified_name, qual)
            self.assertEqual(res.is_member_method, is_member)
            self.assertEqual(res.is_static, is_static)
            self.assertEqual(res.is_virtual, is_virtual)
            self.assertEqual(res.is_const, is_const)
            self.assertEqual(res.access, access)
            self.assertEqual(res.calling_convention, conv)
            self.assertEqual(res.return_type, ret)
            self.assertEqual(res.parameter_types, params)
            self.assertEqual(res.demangled, expected_demangled)

    def test_napi_entrypoints_discovery(self):
        """Verifies entrypoint discovery for standard N-API, Node, and NAN export hooks."""
        symbols = [
            "napi_register_module_v1",
            "some_internal_fn",
            "node_register_module_v1",
            "_register_node_addon",
            "another_fn",
        ]
        found = NapiBridgeParser.discover_entrypoints(symbols)
        self.assertEqual(len(found), 3)
        self.assertIn("napi_register_module_v1", found)
        self.assertIn("node_register_module_v1", found)
        self.assertIn("_register_node_addon", found)

    def test_pe64_full_module_inspection(self):
        """Verifies full parsing of a 64-bit Windows PE .node addon with exports and properties."""
        descriptors = [
            {
                "name": "reaProbeOne",
                "method_rva": 0x1010,
                "attributes": NAPI_ATTR_WRITABLE | NAPI_ATTR_CONFIGURABLE,
            },
            {
                "name": "volumeLevel",
                "getter_rva": 0x1020,
                "setter_rva": 0x1030,
                "attributes": NAPI_ATTR_ENUMERABLE | NAPI_ATTR_CONFIGURABLE,
            },
            {
                "name": "STATIC_VERSION",
                "value_rva": 0x1040,
                "attributes": NAPI_ATTR_STATIC | NAPI_ATTR_ENUMERABLE,
            },
        ]

        pe_bytes = NapiBridgeBuilder.build_pe_dll(
            module_name="voice_engine.node",
            exported_names=[
                "napi_register_module_v1",
                "?CalculateGain@@YAHHH@Z",
                "?RenderFrame@DspProcessor@@QAEXXZ",
            ],
            is_64_bit=True,
            descriptors=descriptors,
        )

        summary = NapiBridgeParser.parse_pe(pe_bytes)
        self.assertTrue(summary.is_64_bit)
        self.assertTrue(summary.is_dll)
        self.assertEqual(summary.machine, "x64")
        self.assertEqual(summary.export_module_name, "voice_engine.node")
        self.assertTrue(summary.has_napi_entrypoint)
        self.assertEqual(summary.discovered_entrypoints, ["napi_register_module_v1"])

        # Exported functions check
        self.assertEqual(len(summary.exported_functions), 3)
        f0 = summary.exported_functions[0]
        self.assertEqual(f0.name, "napi_register_module_v1")
        self.assertTrue(f0.is_napi_entrypoint)
        self.assertFalse(f0.is_mangled_msvc)

        f1 = summary.exported_functions[1]
        self.assertEqual(f1.name, "?CalculateGain@@YAHHH@Z")
        self.assertFalse(f1.is_napi_entrypoint)
        self.assertTrue(f1.is_mangled_msvc)
        self.assertIsNotNone(f1.demangled)
        self.assertFalse(f1.demangled.is_member_method)
        self.assertEqual(f1.demangled.calling_convention, "__cdecl")

        f2 = summary.exported_functions[2]
        self.assertEqual(f2.name, "?RenderFrame@DspProcessor@@QAEXXZ")
        self.assertTrue(f2.is_mangled_msvc)
        self.assertIsNotNone(f2.demangled)
        self.assertTrue(f2.demangled.is_member_method)
        self.assertEqual(f2.demangled.calling_convention, "__thiscall")

        # Demangled symbols list
        self.assertEqual(len(summary.demangled_symbols), 2)

        # Property descriptors check
        self.assertEqual(len(summary.property_descriptors), 3)
        p0 = summary.property_descriptors[0]
        self.assertEqual(p0.name, "reaProbeOne")
        self.assertTrue(p0.is_method)
        self.assertFalse(p0.is_accessor)
        self.assertTrue(p0.is_writable)
        self.assertFalse(p0.is_enumerable)
        self.assertTrue(p0.is_configurable)

        p1 = summary.property_descriptors[1]
        self.assertEqual(p1.name, "volumeLevel")
        self.assertFalse(p1.is_method)
        self.assertTrue(p1.is_accessor)
        self.assertTrue(p1.has_getter)
        self.assertTrue(p1.has_setter)
        self.assertTrue(p1.is_enumerable)

        p2 = summary.property_descriptors[2]
        self.assertEqual(p2.name, "STATIC_VERSION")
        self.assertFalse(p2.is_method)
        self.assertFalse(p2.is_accessor)
        self.assertTrue(p2.is_static)
        self.assertTrue(p2.is_enumerable)

        d = summary.to_dict()
        self.assertEqual(d["machine"], "x64")
        self.assertEqual(d["has_napi_entrypoint"], True)
        self.assertEqual(len(d["property_descriptors"]), 3)

    def test_pe32_module_inspection(self):
        """Verifies full parsing of a 32-bit (x86) Windows PE .node addon."""
        descriptors = [
            {
                "name": "legacyMethod",
                "method_rva": 0x1010,
                "attributes": NAPI_ATTR_DEFAULT,
            }
        ]

        pe32_bytes = NapiBridgeBuilder.build_pe_dll(
            module_name="addon32.node",
            exported_names=["node_register_module_v1", "_register_node_addon"],
            is_64_bit=False,
            descriptors=descriptors,
        )

        summary = NapiBridgeParser.parse_pe(pe32_bytes)
        self.assertFalse(summary.is_64_bit)
        self.assertEqual(summary.machine, "x86")
        self.assertTrue(summary.has_napi_entrypoint)
        self.assertIn("node_register_module_v1", summary.discovered_entrypoints)
        self.assertIn("_register_node_addon", summary.discovered_entrypoints)
        self.assertEqual(len(summary.property_descriptors), 1)
        self.assertEqual(summary.property_descriptors[0].name, "legacyMethod")

    def test_standalone_property_descriptor_parsing(self):
        """Verifies standalone parsing of 64-bit and 32-bit property descriptor structures."""
        # 64-bit descriptor: utf8name_rva=0, name_rva=0, method_rva=0x2000, getter=0, setter=0, val=0, attr=2, ctx=0
        blob64 = struct.pack("<QQQQQQIIQ", 0, 0, 0x2000, 0, 0, 0, NAPI_ATTR_ENUMERABLE, 0, 0)
        desc64 = NapiBridgeParser.parse_property_descriptor(blob64, offset=0, is_64_bit=True)
        self.assertTrue(desc64.is_method)
        self.assertTrue(desc64.is_enumerable)
        self.assertFalse(desc64.is_writable)

        # 32-bit descriptor:
        blob32 = struct.pack("<IIIIIIII", 0, 0, 0, 0x1000, 0x1004, 0, NAPI_ATTR_WRITABLE, 0)
        desc32 = NapiBridgeParser.parse_property_descriptor(blob32, offset=0, is_64_bit=False)
        self.assertFalse(desc32.is_method)
        self.assertTrue(desc32.is_accessor)
        self.assertTrue(desc32.has_getter)
        self.assertTrue(desc32.has_setter)
        self.assertTrue(desc32.is_writable)

    def test_demangler_adversarial_rejections(self):
        """Verifies fail-closed rejection on invalid or corrupted mangled symbols."""
        invalid_symbols = [
            "",                                # Empty
            "not_a_mangled_symbol",            # Missing leading '?'
            "?TruncatedName",                  # Missing '@@'
            "?Func@@",                         # Truncated after '@@'
            "?Func@@Y",                        # Truncated after 'Y'
            "?Func@@Y9XXZ",                    # Invalid calling convention '9'
            "?Func@@Y?XXZ",                    # Invalid calling convention '?'
            "?Func@@9AEXXZ",                   # Invalid modifier '9'
            "?Func@Cls@@Q9EXXZ",               # Invalid this modifier '9'
            "?Func@Cls@@QA9XXZ",               # Invalid member calling convention '9'
            "?Func@@YA@@",                     # Corrupted type descriptor
            "?Func@@YAXPEAU@@",                # Truncated struct name in pointer
        ]

        for inv in invalid_symbols:
            with self.assertRaises(ValueError, msg=f"Expected ValueError for {inv}"):
                MsvcDemangler.demangle(inv)

    def test_pe_header_truncation_rejections(self):
        """Verifies fail-closed rejection on truncated or corrupted PE binary headers."""
        # Empty payload
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(b"")

        # DOS header < 64 bytes
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(b"MZ" + (b"\x00" * 30))

        # Invalid DOS magic
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(b"XX" + (b"\x00" * 62))

        # Corrupted e_lfanew pointing out of bounds
        bad_lfanew = bytearray(64)
        bad_lfanew[0:2] = b"MZ"
        struct.pack_into("<I", bad_lfanew, 0x3C, 0x100000)
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(bytes(bad_lfanew))

        # Valid DOS header but missing PE signature
        bad_pe_sig = bytearray(128)
        bad_pe_sig[0:2] = b"MZ"
        struct.pack_into("<I", bad_pe_sig, 0x3C, 64)
        bad_pe_sig[64:68] = b"NE\x00\x00"  # Invalid signature
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(bytes(bad_pe_sig))

        # Truncated COFF File header
        trunc_coff = bytearray(72)
        trunc_coff[0:2] = b"MZ"
        struct.pack_into("<I", trunc_coff, 0x3C, 64)
        trunc_coff[64:68] = b"PE\x00\x00"
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_pe(bytes(trunc_coff))

    def test_property_descriptor_truncation_rejections(self):
        """Verifies fail-closed rejection on truncated descriptor buffers."""
        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_property_descriptor(b"\x00" * 30, is_64_bit=True)

        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_property_descriptor(b"\x00" * 20, is_64_bit=False)

        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_property_descriptor_table(b"\x00" * 100, count=5, is_64_bit=True)

        with self.assertRaises(ValueError):
            NapiBridgeParser.parse_property_descriptor_table(b"\x00" * 100, count=-1)

    def test_adversarial_bitflip_fuzzing(self):
        """Verifies parser robustness against byte mutations across the entire header region."""
        valid_pe = NapiBridgeBuilder.build_pe_dll(
            module_name="fuzz_target.node",
            exported_names=["napi_register_module_v1", "?Func@@YAHH@Z"],
        )

        # Mutate critical byte offsets in headers
        test_offsets = [0, 1, 0x3C, 0x80, 0x81, 0x84, 0x86, 0x98, 0x100, 0x200]
        for off in test_offsets:
            if off < len(valid_pe):
                mutated = bytearray(valid_pe)
                mutated[off] ^= 0xFF
                try:
                    NapiBridgeParser.parse_pe(bytes(mutated))
                except ValueError:
                    # Clean fail-closed rejection is expected
                    pass

    def test_thermodynamic_memory_allocation_ceiling(self):
        """Ensures NapiBridgeParser operates strictly within 64 KB peak heap memory."""
        # Synthesize a realistic payload with multiple exports and descriptors
        descriptors = [
            {"name": f"probe_{i}", "method_rva": 0x1000 + (i * 16), "attributes": 5}
            for i in range(12)
        ]
        exports = [
            "napi_register_module_v1",
            "node_register_module_v1",
            "_register_node_addon",
            "?InitEngine@@YAXPEAUenv__@@@Z",
            "?ProcessFrame@Processor@@QAEXXZ",
            "?GetSampleRate@Audio@@QBEHXZ",
        ]
        large_pe = NapiBridgeBuilder.build_pe_dll(
            module_name="large_addon.node",
            exported_names=exports,
            is_64_bit=True,
            descriptors=descriptors,
        )

        tracemalloc.start()
        try:
            summary = NapiBridgeParser.inspect(large_pe)
            current, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        self.assertTrue(summary.has_napi_entrypoint)
        self.assertEqual(len(summary.exported_functions), 6)
        self.assertEqual(len(summary.property_descriptors), 12)
        self.assertLessEqual(
            peak, 64 * 1024, f"Peak memory {peak} bytes exceeded 64 KB ceiling"
        )


if __name__ == "__main__":
    unittest.main()
