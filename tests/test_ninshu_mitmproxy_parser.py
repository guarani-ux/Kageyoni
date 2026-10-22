"""Unit & Adversarial Verification Suite for Ninshū Mitmproxy Offline Flow Decoder (CH 35).

Verifications:
1. Valid HTTP flow decoding (synthetic request and response).
2. Multiple flow streams and length-prefixed frame streams.
3. Error flow handling (e.g. connection reset, failed upstream).
4. Adversarial fuzz tests: truncated frames, depth recursion limits, corrupted string encodings.
5. Fail-closed rejection on invalid ports, status codes, and reserved MsgPack tokens.
6. Thermodynamic profiling asserting peak heap ceiling <= 64 KB.
7. Metamorphic fuzzing via AdversarialMutator.
"""
from __future__ import annotations

import io
import struct
import unittest
from typing import Any, Dict

from kageyoni.ninshu.mitmproxy_parser import (
    MitmproxyDumpParser,
    MitmproxyDumpSummary,
    MitmproxyHttpFlow,
    MsgPackDecoder,
    MsgPackSerializer,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuMitmproxyParser(unittest.TestCase):
    def setUp(self):
        # Construct synthetic HTTP Flow 1 (GET /api/v1/users)
        self.flow1_dict = {
            "id": "flow-uuid-001",
            "type": "http",
            "request": {
                "method": "GET",
                "scheme": "https",
                "host": "api.example.com",
                "port": 443,
                "path": "/api/v1/users",
                "headers": [
                    ["accept", "application/json"],
                    ["authorization", "Bearer sec-token-xyz"],
                ],
                "content": b"",
                "timestamp_start": 1600000000.0,
                "timestamp_end": 1600000000.1,
            },
            "response": {
                "status_code": 200,
                "headers": [
                    ["content-type", "application/json"],
                    ["content-length", "19"],
                ],
                "content": b'{"users":["alice"]}',
                "timestamp_start": 1600000000.1,
                "timestamp_end": 1600000000.2,
            },
            "error": None,
        }

        # Construct synthetic HTTP Flow 2 (POST /api/v1/submit with request body)
        self.flow2_dict = {
            "id": "flow-uuid-002",
            "type": "http",
            "request": {
                "method": "POST",
                "scheme": "https",
                "host": "api.example.com",
                "port": 443,
                "path": "/api/v1/submit",
                "headers": [
                    ["content-type", "application/json"],
                ],
                "content": b'{"action":"login"}',
                "timestamp_start": 1600000001.0,
                "timestamp_end": 1600000001.1,
            },
            "response": {
                "status_code": 201,
                "headers": [
                    ["content-type", "application/json"],
                ],
                "content": b'{"status":"created"}',
                "timestamp_start": 1600000001.1,
                "timestamp_end": 1600000001.2,
            },
            "error": None,
        }

        # Construct synthetic Error Flow 3 (Upstream Connection Refused)
        self.flow3_err_dict = {
            "id": "flow-uuid-003",
            "type": "http",
            "request": {
                "method": "GET",
                "scheme": "http",
                "host": "failing-backend.internal",
                "port": 8080,
                "path": "/healthz",
                "headers": [],
                "content": b"",
                "timestamp_start": 1600000002.0,
                "timestamp_end": 1600000002.1,
            },
            "response": None,
            "error": {
                "msg": "Connection refused: TCP connect failed to 10.0.0.5:8080",
                "timestamp": 1600000002.2,
            },
        }

        self.flow1_bytes = MsgPackSerializer.pack(self.flow1_dict)
        self.flow2_bytes = MsgPackSerializer.pack(self.flow2_dict)
        self.flow3_bytes = MsgPackSerializer.pack(self.flow3_err_dict)

        self.multi_flow_stream = self.flow1_bytes + self.flow2_bytes + self.flow3_bytes

    def test_valid_http_flow_decoding(self):
        """Verify extraction of request and response attributes from valid synthetic flow."""
        summary = MitmproxyDumpParser.parse_bytes(self.flow1_bytes)
        self.assertEqual(summary.flows_count, 1)
        self.assertEqual(summary.http_flows_count, 1)
        self.assertEqual(summary.error_flows_count, 0)

        flow = summary.flows[0]
        self.assertEqual(flow.flow_id, "flow-uuid-001")
        self.assertEqual(flow.method, "GET")
        self.assertEqual(flow.scheme, "https")
        self.assertEqual(flow.host, "api.example.com")
        self.assertEqual(flow.port, 443)
        self.assertEqual(flow.path, "/api/v1/users")
        self.assertEqual(flow.status_code, 200)
        self.assertEqual(flow.content_length, 19)
        self.assertEqual(flow.response_content_length, 19)
        self.assertEqual(flow.request_content_length, 0)
        self.assertIsNone(flow.error_msg)
        self.assertEqual(len(flow.request_headers), 2)
        self.assertEqual(flow.request_headers[0], ("accept", "application/json"))
        self.assertEqual(flow.request_headers[1], ("authorization", "Bearer sec-token-xyz"))
        self.assertEqual(len(flow.response_headers), 2)
        self.assertTrue(len(flow.sha256_digest) == 64)

        flow_dict = flow.to_dict()
        self.assertEqual(flow_dict["method"], "GET")
        self.assertEqual(flow_dict["status_code"], 200)

    def test_multi_flow_stream_and_error_handling(self):
        """Verify parsing multiple consecutive flows including error flows."""
        summary = MitmproxyDumpParser.parse_bytes(self.multi_flow_stream)
        self.assertEqual(summary.total_bytes, len(self.multi_flow_stream))
        self.assertEqual(summary.flows_count, 3)
        self.assertEqual(summary.http_flows_count, 3)
        self.assertEqual(summary.error_flows_count, 1)

        err_flow = summary.flows[2]
        self.assertEqual(err_flow.flow_id, "flow-uuid-003")
        self.assertEqual(err_flow.method, "GET")
        self.assertEqual(err_flow.host, "failing-backend.internal")
        self.assertEqual(err_flow.port, 8080)
        self.assertIsNone(err_flow.status_code)
        self.assertIsNotNone(err_flow.error_msg)
        self.assertIn("Connection refused", str(err_flow.error_msg))

    def test_length_prefixed_frame_decoding(self):
        """Verify parser can decode length-prefixed protocol frames."""
        prefix1 = struct.pack(">I", len(self.flow1_bytes))
        prefix2 = struct.pack(">I", len(self.flow2_bytes))
        framed_data = prefix1 + self.flow1_bytes + prefix2 + self.flow2_bytes

        summary = MitmproxyDumpParser.parse_bytes(framed_data)
        self.assertEqual(summary.flows_count, 2)
        self.assertEqual(summary.flows[0].flow_id, "flow-uuid-001")
        self.assertEqual(summary.flows[1].flow_id, "flow-uuid-002")

    def test_fail_closed_on_empty_and_corrupt_stream(self):
        """Verify fail-closed rejection on empty payloads and truncated data."""
        with self.assertRaises(ValueError):
            MitmproxyDumpParser.parse_bytes(b"")

        # Truncated flow payload
        with self.assertRaises(ValueError):
            MitmproxyDumpParser.parse_bytes(self.flow1_bytes[:15])

    def test_fail_closed_on_corrupt_port_and_status(self):
        """Verify invalid ports and status codes are rejected cleanly."""
        # Port <= 0
        bad_port_flow = dict(self.flow1_dict)
        bad_port_flow["request"] = dict(self.flow1_dict["request"])
        bad_port_flow["request"]["port"] = 0
        with self.assertRaises(ValueError):
            MitmproxyDumpParser.parse_bytes(MsgPackSerializer.pack(bad_port_flow))

        # Port > 65535
        bad_port_flow["request"]["port"] = 70000
        with self.assertRaises(ValueError):
            MitmproxyDumpParser.parse_bytes(MsgPackSerializer.pack(bad_port_flow))

        # Status code out of range
        bad_status_flow = dict(self.flow1_dict)
        bad_status_flow["response"] = dict(self.flow1_dict["response"])
        bad_status_flow["response"]["status_code"] = 999
        with self.assertRaises(ValueError):
            MitmproxyDumpParser.parse_bytes(MsgPackSerializer.pack(bad_status_flow))

    def test_depth_recursion_limit(self):
        """Verify that nested structures exceeding recursion limit raise ValueError."""
        nested: Any = "leaf"
        for _ in range(40):
            nested = [nested]
        payload = MsgPackSerializer.pack(nested)
        with self.assertRaises(ValueError):
            MsgPackDecoder.unpack(io.BytesIO(payload))

    def test_corrupted_string_encodings(self):
        """Verify corrupted UTF-8 byte sequences in strings raise ValueError."""
        # 0xA3 indicates a 3-byte string, followed by invalid UTF-8 bytes 0xFF, 0xFF, 0xFF
        bad_str_payload = b"\xa3\xff\xff\xff"
        with self.assertRaises(ValueError):
            MsgPackDecoder.unpack(io.BytesIO(bad_str_payload))

        # 0xC1 is explicitly reserved and invalid in MsgPack specification
        with self.assertRaises(ValueError):
            MsgPackDecoder.unpack(io.BytesIO(b"\xc1"))

    def test_thermodynamic_heap_ceiling(self):
        """Verify memory allocation strictly complies with <= 64 KB ceiling."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            MitmproxyDumpParser.parse_bytes,
            self.multi_flow_stream,
            candidate_id="mitmproxy_parser_ch35",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify metamorphic stability against adversarial mutations."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.flow1_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        for m in mutants:
            try:
                summary = MitmproxyDumpParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.flows_count, int)
            except ValueError:
                pass
            except Exception as err:
                self.fail(f"Unhandled crash on mutant {m.mutation_type}: {err}")


if __name__ == "__main__":
    unittest.main()
