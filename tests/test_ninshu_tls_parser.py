"""Unit & Adversarial Verification Suite for Ninshū In-Tree TLS / SSL Parser (CH 34).

Tests:
1. Valid ClientHello record containing SNI, Supported Versions (TLS 1.3), and ALPN.
2. Non-handshake records (Alert, Application Data).
3. Adversarial fuzz vectors: truncated records, length overflows, corrupted SNI names, malformed extensions.
4. Thermodynamic profiling (heap ceiling <= 64 KB).
5. Comprehensive mutant fuzzing via AdversarialMutator.
"""
import io
import struct
import unittest

from kageyoni.ninshu.tls_parser import (
    TLSHandshakeParser,
    CONTENT_TYPE_ALERT,
    CONTENT_TYPE_APPLICATION_DATA,
    CONTENT_TYPE_HANDSHAKE,
    HANDSHAKE_TYPE_CLIENT_HELLO,
    EXT_SERVER_NAME,
    EXT_SUPPORTED_VERSIONS,
    EXT_ALPN,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


def build_client_hello_record(
    sni: str = "example.com",
    alpns: list = None,
    include_tls13: bool = True,
    legacy_version: int = 0x0303,
) -> bytes:
    if alpns is None:
        alpns = ["h2", "http/1.1"]

    # 1. SNI Extension (0x0000)
    sni_bytes = sni.encode("ascii")
    # server_name entry: type(1B=0), length(2B), hostname
    sni_entry = struct.pack(">BH", 0, len(sni_bytes)) + sni_bytes
    # server_name_list: length(2B) + entries
    sni_ext_data = struct.pack(">H", len(sni_entry)) + sni_entry
    sni_ext = struct.pack(">HH", EXT_SERVER_NAME, len(sni_ext_data)) + sni_ext_data

    # 2. Supported Versions Extension (0x002B)
    sup_versions = [0x0304, 0x0303] if include_tls13 else [0x0303]
    sup_ver_bytes = bytearray([len(sup_versions) * 2])
    for v in sup_versions:
        sup_ver_bytes.extend(struct.pack(">H", v))
    sup_ver_ext = struct.pack(">HH", EXT_SUPPORTED_VERSIONS, len(sup_ver_bytes)) + bytes(sup_ver_bytes)

    # 3. ALPN Extension (0x0010)
    alpn_entries = bytearray()
    for proto in alpns:
        p_bytes = proto.encode("utf-8")
        alpn_entries.append(len(p_bytes))
        alpn_entries.extend(p_bytes)
    alpn_ext_data = struct.pack(">H", len(alpn_entries)) + bytes(alpn_entries)
    alpn_ext = struct.pack(">HH", EXT_ALPN, len(alpn_ext_data)) + alpn_ext_data

    extensions_payload = sni_ext + sup_ver_ext + alpn_ext
    extensions_header = struct.pack(">H", len(extensions_payload))

    # ClientHello body
    client_version = legacy_version
    random_bytes = b"\xaa" * 32
    session_id = b"\x01\x02\x03\x04"
    session_id_field = bytes([len(session_id)]) + session_id
    cipher_suites = [0x1301, 0x1302, 0xC02F, 0xC030]  # TLS_AES_128_GCM_SHA256, etc.
    cipher_suites_bytes = bytearray()
    for cs in cipher_suites:
        cipher_suites_bytes.extend(struct.pack(">H", cs))
    cipher_suites_field = struct.pack(">H", len(cipher_suites_bytes)) + bytes(cipher_suites_bytes)
    compression_methods_field = bytes([1, 0])  # length 1, null compression

    client_hello_body = (
        struct.pack(">H", client_version)
        + random_bytes
        + session_id_field
        + cipher_suites_field
        + compression_methods_field
        + extensions_header
        + extensions_payload
    )

    # Handshake header: type (1B = 1), length (3B)
    hs_len = len(client_hello_body)
    hs_header = bytes([HANDSHAKE_TYPE_CLIENT_HELLO, (hs_len >> 16) & 0xFF, (hs_len >> 8) & 0xFF, hs_len & 0xFF])
    handshake_payload = hs_header + client_hello_body

    # TLS Record header: content_type (1B = 22), legacy_ver (2B = 0x0301 or 0x0303), length (2B)
    rec_header = struct.pack(">BHH", CONTENT_TYPE_HANDSHAKE, 0x0301, len(handshake_payload))
    return rec_header + handshake_payload


class TestNinshuTLSParser(unittest.TestCase):
    def setUp(self):
        self.valid_client_hello = build_client_hello_record(
            sni="test.kageyoni.org",
            alpns=["h2", "http/1.1"],
            include_tls13=True,
        )

    def test_valid_client_hello_parsing(self):
        """Verify normal ClientHello parsing with SNI, ALPN, and TLS 1.3 detection."""
        summary = TLSHandshakeParser.parse_bytes(self.valid_client_hello)
        self.assertEqual(summary.records_count, 1)
        self.assertEqual(summary.total_bytes, len(self.valid_client_hello))
        self.assertEqual(summary.sni_hostname, "test.kageyoni.org")
        self.assertEqual(summary.alpn_protocols, ["h2", "http/1.1"])
        self.assertTrue(summary.has_tls13)
        self.assertTrue(len(summary.sha256) == 64)

        rec = summary.records[0]
        self.assertEqual(rec.content_type, CONTENT_TYPE_HANDSHAKE)
        self.assertEqual(rec.content_type_name, "handshake")
        self.assertIsNotNone(rec.client_hello)
        self.assertEqual(rec.client_hello.sni_hostname, "test.kageyoni.org")
        self.assertIn(0x0304, rec.client_hello.supported_versions)
        self.assertIn(0x1301, rec.client_hello.cipher_suites)

    def test_stream_interface(self):
        """Verify stream parsing parity with bytes parsing."""
        stream = io.BytesIO(self.valid_client_hello)
        summary = TLSHandshakeParser.parse_stream(stream)
        self.assertEqual(summary.sni_hostname, "test.kageyoni.org")
        self.assertTrue(summary.has_tls13)

    def test_non_handshake_records(self):
        """Verify parsing of Alert and Application Data TLS records."""
        # Alert record: close_notify (21, 0x0303, len=2, payload = [1, 0])
        alert_rec = struct.pack(">BHHBB", CONTENT_TYPE_ALERT, 0x0303, 2, 1, 0)
        # Application Data record (23, 0x0303, len=10, encrypted payload)
        app_data = b"ENCRYPTED!"
        app_rec = struct.pack(">BHH", CONTENT_TYPE_APPLICATION_DATA, 0x0303, len(app_data)) + app_data

        multi_record = alert_rec + app_rec
        summary = TLSHandshakeParser.parse_bytes(multi_record)
        self.assertEqual(summary.records_count, 2)
        self.assertEqual(summary.records[0].content_type_name, "alert")
        self.assertEqual(summary.records[0].payload, b"\x01\x00")
        self.assertEqual(summary.records[1].content_type_name, "application_data")
        self.assertEqual(summary.records[1].payload, app_data)
        self.assertIsNone(summary.sni_hostname)
        self.assertFalse(summary.has_tls13)

    def test_fail_closed_empty_or_truncated(self):
        """Verify fail-closed rejection on empty or truncated headers."""
        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(b"")

        # Less than 5 bytes record header
        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(b"\x16\x03\x01\x00")

        # Invalid ContentType (e.g. 99)
        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(b"\x63\x03\x01\x00\x05hello")

        # Declared length exceeds payload
        truncated_record = struct.pack(">BHH", CONTENT_TYPE_HANDSHAKE, 0x0301, 100) + b"\x01\x00\x00\x0512345"
        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(truncated_record)

    def test_fail_closed_length_overflow(self):
        """Verify rejection when record length exceeds max TLS ceiling."""
        oversized = struct.pack(">BHH", CONTENT_TYPE_HANDSHAKE, 0x0301, 65000) + (b"\x00" * 65000)
        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(oversized)

    def test_fail_closed_corrupted_sni(self):
        """Verify rejection on corrupted SNI encodings and length mismatches."""
        # Corrupt SNI hostname to non-ASCII bytes
        corrupt = bytearray(self.valid_client_hello)
        # Find "test.kageyoni.org" in corrupt
        target = b"test.kageyoni.org"
        idx = corrupt.find(target)
        self.assertNotEqual(idx, -1)
        corrupt[idx : idx + 4] = b"\xff\xfe\xfd\xfc"

        with self.assertRaises(ValueError):
            TLSHandshakeParser.parse_bytes(bytes(corrupt))

    def test_fail_closed_extension_overflow(self):
        """Verify rejection if extension length exceeds extensions container."""
        # Find extension length in ClientHello and inflate it
        corrupt = bytearray(self.valid_client_hello)
        # Find SNI extension type (0x0000)
        idx = corrupt.find(b"\x00\x00\x00")
        if idx != -1:
            # Overwrite extension length to 0xFFFF
            corrupt[idx + 2 : idx + 4] = b"\xff\xff"
            with self.assertRaises(ValueError):
                TLSHandshakeParser.parse_bytes(bytes(corrupt))

    def test_thermodynamic_heap_ceiling(self):
        """Verify peak heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            TLSHandshakeParser.parse_bytes,
            self.valid_client_hello,
            candidate_id="tls_parser_ch34",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse cleanly or raise ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.valid_client_hello)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = TLSHandshakeParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
