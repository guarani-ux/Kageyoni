"""Unit & Adversarial Verification Suite for Ninshū CDP Parser (CH 27).

Verifications:
1. Valid command and response parsing and ID matching.
2. Network event flow reconstruction (requestWillBeSent, responseReceived, loadingFailed).
3. Page navigation and lifecycle events (frameNavigated, loadEventFired, domContentEventFired).
4. Console API and runtime exception tracking.
5. DOM mutation events (documentUpdated, setChildNodes).
6. Fail-closed rejection:
   - Non-integer / boolean / negative IDs
   - Missing method / result / error fields
   - Corrupted JSON / empty payload
   - Memory ceiling violation (> 64 KB)
7. Thermodynamic profiling asserting peak heap ceiling <= 64 KB.
8. Adversarial fuzzing via AdversarialMutator.
"""
from __future__ import annotations

import json
import unittest
from typing import Any, Dict, List

from kageyoni.ninshu.cdp_parser import (
    CdpCommand,
    CdpDomainError,
    CdpEvent,
    CdpInvalidJsonError,
    CdpParseError,
    CdpParser,
    CdpPayloadExceededError,
    CdpResponse,
    CdpSchemaViolationError,
    CdpSessionSummary,
    DomDocumentUpdated,
    DomSetChildNodes,
    NetworkFlow,
    NetworkLoadingFailed,
    NetworkRequestWillBeSent,
    NetworkResponseReceived,
    PageDomContentEventFired,
    PageFrameNavigated,
    PageLoadEventFired,
    RuntimeConsoleApiCalled,
    RuntimeExceptionThrown,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


class TestNinshuCdpParser(unittest.TestCase):
    def setUp(self) -> None:
        # Golden command
        self.cmd_dict = {
            "id": 101,
            "method": "Page.navigate",
            "params": {"url": "https://example.internal/login"},
        }

        # Golden response
        self.resp_dict = {
            "id": 101,
            "result": {"frameId": "F001", "loaderId": "L001"},
        }

        # Golden error response
        self.err_resp_dict = {
            "id": 102,
            "error": {"code": -32601, "message": "Method not found"},
        }

        # Golden Network events
        self.net_req_event = {
            "method": "Network.requestWillBeSent",
            "params": {
                "requestId": "req-999",
                "loaderId": "L001",
                "documentURL": "https://example.internal/login",
                "request": {
                    "url": "https://example.internal/api/auth",
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                        "User-Agent": "Kageyoni-Agent",
                    },
                },
                "timestamp": 1000.12,
                "initiator": {"type": "script"},
            },
        }

        self.net_resp_event = {
            "method": "Network.responseReceived",
            "params": {
                "requestId": "req-999",
                "loaderId": "L001",
                "timestamp": 1000.25,
                "response": {
                    "url": "https://example.internal/api/auth",
                    "status": 200,
                    "mimeType": "application/json",
                    "headers": {
                        "Content-Type": "application/json",
                        "Content-Length": "42",
                    },
                },
            },
        }

        self.net_fail_event = {
            "method": "Network.loadingFailed",
            "params": {
                "requestId": "req-888",
                "timestamp": 1000.30,
                "errorText": "net::ERR_CONNECTION_REFUSED",
                "canceled": False,
                "blockedReason": "inspector",
            },
        }

        # Golden Page events
        self.page_nav_event = {
            "method": "Page.frameNavigated",
            "params": {
                "frame": {
                    "id": "F001",
                    "loaderId": "L001",
                    "url": "https://example.internal/login",
                    "securityOrigin": "https://example.internal",
                    "mimeType": "text/html",
                }
            },
        }

        self.page_load_event = {
            "method": "Page.loadEventFired",
            "params": {"timestamp": 1000.40},
        }

        self.page_dom_event = {
            "method": "Page.domContentEventFired",
            "params": {"timestamp": 1000.35},
        }

        # Golden Runtime events
        self.console_event = {
            "method": "Runtime.consoleAPICalled",
            "params": {
                "type": "info",
                "args": [
                    {"type": "string", "value": "User session initialized"},
                    {"type": "number", "value": 42},
                ],
                "timestamp": 1000.50,
                "executionContextId": 1,
            },
        }

        self.exception_event = {
            "method": "Runtime.exceptionThrown",
            "params": {
                "timestamp": 1000.60,
                "exceptionDetails": {
                    "text": "Uncaught TypeError: Cannot read properties of undefined",
                    "lineNumber": 45,
                    "columnNumber": 12,
                    "scriptId": "s-100",
                    "url": "https://example.internal/main.js",
                    "stackTrace": {
                        "callFrames": [
                            {
                                "functionName": "bootstrap",
                                "scriptId": "s-100",
                                "url": "https://example.internal/main.js",
                                "lineNumber": 45,
                                "columnNumber": 12,
                            }
                        ]
                    },
                },
            },
        }

        # Golden DOM events
        self.dom_updated_event = {
            "method": "DOM.documentUpdated",
            "params": {},
        }

        self.dom_set_nodes_event = {
            "method": "DOM.setChildNodes",
            "params": {
                "parentId": 1,
                "nodes": [
                    {"nodeId": 2, "nodeType": 1, "nodeName": "BODY"},
                    {"nodeId": 3, "nodeType": 1, "nodeName": "DIV"},
                ],
            },
        }

        # Multi-message session stream (NDJSON)
        stream_messages = [
            self.cmd_dict,
            self.resp_dict,
            self.net_req_event,
            self.net_resp_event,
            self.page_nav_event,
            self.page_dom_event,
            self.page_load_event,
            self.console_event,
            self.exception_event,
            self.dom_updated_event,
            self.dom_set_nodes_event,
            self.net_fail_event,
        ]
        self.ndjson_stream = "\n".join(json.dumps(m) for m in stream_messages)
        self.json_array_stream = json.dumps(stream_messages)

    def test_command_and_response_parsing(self) -> None:
        """Verify command and response parsing with strict types and correlation."""
        cmd = CdpParser.parse_message(json.dumps(self.cmd_dict))
        self.assertIsInstance(cmd, CdpCommand)
        self.assertEqual(cmd.id, 101)
        self.assertEqual(cmd.method, "Page.navigate")
        self.assertEqual(cmd.params["url"], "https://example.internal/login")

        resp = CdpParser.parse_message(json.dumps(self.resp_dict))
        self.assertIsInstance(resp, CdpResponse)
        self.assertEqual(resp.id, 101)
        self.assertTrue(resp.is_success)
        self.assertEqual(resp.result["frameId"], "F001")

        err_resp = CdpParser.parse_message(json.dumps(self.err_resp_dict))
        self.assertIsInstance(err_resp, CdpResponse)
        self.assertFalse(err_resp.is_success)
        self.assertEqual(err_resp.error["code"], -32601)

    def test_domain_event_decoding(self) -> None:
        """Verify all core domain event telemetry decoders."""
        # Network request
        ev_req = CdpParser.parse_message(self.net_req_event)
        self.assertIsInstance(ev_req, CdpEvent)
        decoded_req = CdpParser.decode_event(ev_req)
        self.assertIsInstance(decoded_req, NetworkRequestWillBeSent)
        self.assertEqual(decoded_req.request_id, "req-999")
        self.assertEqual(decoded_req.method, "POST")
        self.assertEqual(decoded_req.headers["Content-Type"], "application/json")

        # Network response
        ev_resp = CdpParser.parse_message(self.net_resp_event)
        decoded_resp = CdpParser.decode_event(ev_resp)
        self.assertIsInstance(decoded_resp, NetworkResponseReceived)
        self.assertEqual(decoded_resp.status, 200)
        self.assertEqual(decoded_resp.mime_type, "application/json")

        # Network failure
        ev_fail = CdpParser.parse_message(self.net_fail_event)
        decoded_fail = CdpParser.decode_event(ev_fail)
        self.assertIsInstance(decoded_fail, NetworkLoadingFailed)
        self.assertEqual(decoded_fail.error_text, "net::ERR_CONNECTION_REFUSED")
        self.assertEqual(decoded_fail.blocked_reason, "inspector")

        # Page navigation
        ev_nav = CdpParser.parse_message(self.page_nav_event)
        decoded_nav = CdpParser.decode_event(ev_nav)
        self.assertIsInstance(decoded_nav, PageFrameNavigated)
        self.assertEqual(decoded_nav.frame_id, "F001")
        self.assertEqual(decoded_nav.url, "https://example.internal/login")

        # Page lifecycle
        ev_load = CdpParser.parse_message(self.page_load_event)
        decoded_load = CdpParser.decode_event(ev_load)
        self.assertIsInstance(decoded_load, PageLoadEventFired)

        ev_dom_content = CdpParser.parse_message(self.page_dom_event)
        decoded_dom_content = CdpParser.decode_event(ev_dom_content)
        self.assertIsInstance(decoded_dom_content, PageDomContentEventFired)

        # Runtime console
        ev_console = CdpParser.parse_message(self.console_event)
        decoded_console = CdpParser.decode_event(ev_console)
        self.assertIsInstance(decoded_console, RuntimeConsoleApiCalled)
        self.assertEqual(decoded_console.type, "info")
        self.assertIn("User session initialized 42", decoded_console.text)

        # Runtime exception
        ev_exc = CdpParser.parse_message(self.exception_event)
        decoded_exc = CdpParser.decode_event(ev_exc)
        self.assertIsInstance(decoded_exc, RuntimeExceptionThrown)
        self.assertEqual(decoded_exc.line_number, 45)
        self.assertIn("Cannot read properties", decoded_exc.text)

        # DOM updates
        ev_dom_up = CdpParser.parse_message(self.dom_updated_event)
        decoded_dom_up = CdpParser.decode_event(ev_dom_up)
        self.assertIsInstance(decoded_dom_up, DomDocumentUpdated)

        ev_dom_nodes = CdpParser.parse_message(self.dom_set_nodes_event)
        decoded_dom_nodes = CdpParser.decode_event(ev_dom_nodes)
        self.assertIsInstance(decoded_dom_nodes, DomSetChildNodes)
        self.assertEqual(decoded_dom_nodes.nodes_count, 2)

    def test_session_stream_correlation_and_network_flow(self) -> None:
        """Verify full stream decoding, command-response matching, and network flow reconstruction."""
        summary = CdpParser.parse_stream(self.ndjson_stream)
        self.assertIsInstance(summary, CdpSessionSummary)
        self.assertEqual(summary.total_messages, 12)
        self.assertEqual(summary.commands_count, 1)
        self.assertEqual(summary.responses_count, 1)
        self.assertEqual(summary.events_count, 10)

        # Correlation check
        self.assertEqual(len(summary.correlated_exchanges), 1)
        exchange = summary.correlated_exchanges[0]
        self.assertEqual(exchange.command_id, 101)
        self.assertEqual(exchange.command_method, "Page.navigate")
        self.assertTrue(exchange.is_success)
        self.assertEqual(exchange.response_result["frameId"], "F001")

        # Network flow reconstruction check
        flows = summary.network_flows
        self.assertIn("req-999", flows)
        req999 = flows["req-999"]
        self.assertEqual(req999["method"], "POST")
        self.assertEqual(req999["status"], 200)
        self.assertEqual(req999["mime_type"], "application/json")
        self.assertFalse(req999["failed"])

        self.assertIn("req-888", flows)
        req888 = flows["req-888"]
        self.assertTrue(req888["failed"])
        self.assertEqual(req888["error_text"], "net::ERR_CONNECTION_REFUSED")

        # Telemetry aggregations
        self.assertEqual(len(summary.console_events), 1)
        self.assertEqual(len(summary.exceptions), 1)
        self.assertEqual(len(summary.page_navigations), 1)
        self.assertEqual(summary.dom_updates_count, 2)

        # JSON array input format test
        summary_arr = CdpParser.parse_stream(self.json_array_stream)
        self.assertEqual(summary_arr.total_messages, 12)
        self.assertEqual(len(summary_arr.correlated_exchanges), 1)

    def test_fail_closed_on_invalid_numeric_ids(self) -> None:
        """Verify fail-closed rejection on invalid, boolean, or corrupted IDs."""
        # Boolean ID
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": True, "method": "Page.reload"})

        # Negative ID
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": -5, "method": "Page.reload"})

        # Zero ID
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 0, "method": "Page.reload"})

        # Float ID
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 1.5, "method": "Page.reload"})

        # String non-integer ID
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": "cmd-1", "method": "Page.reload"})

    def test_fail_closed_on_missing_and_corrupt_fields(self) -> None:
        """Verify schema rejection when required protocol fields are missing or corrupted."""
        # Empty message object
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({})

        # Response missing both result and error
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 10})

        # Response having both result and error
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 10, "result": {}, "error": {}})

        # Ambiguous message with method and result
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 10, "method": "DOM.enable", "result": {}})

        # Corrupted method name without domain
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message({"id": 10, "method": "enable"})

        # Non-dict root
        with self.assertRaises(CdpSchemaViolationError):
            CdpParser.parse_message('"Just a string"')

        # Empty payload
        with self.assertRaises(CdpInvalidJsonError):
            CdpParser.parse_message("")

        with self.assertRaises(CdpInvalidJsonError):
            CdpParser.parse_message("   ")

        # Invalid JSON syntax
        with self.assertRaises(CdpInvalidJsonError):
            CdpParser.parse_message("{id: 101, method: ")

    def test_fail_closed_on_corrupt_domain_payloads(self) -> None:
        """Verify domain parser rejects missing or corrupted domain event fields."""
        # Network request missing request object
        bad_net = CdpEvent(method="Network.requestWillBeSent", domain="Network", event_name="requestWillBeSent", params={"requestId": "r1"})
        with self.assertRaises(CdpDomainError):
            CdpParser.decode_event(bad_net)

        # Network response with non-integer status
        bad_status = CdpEvent(
            method="Network.responseReceived",
            domain="Network",
            event_name="responseReceived",
            params={"requestId": "r1", "response": {"status": "200OK"}},
        )
        with self.assertRaises(CdpDomainError):
            CdpParser.decode_event(bad_status)

        # Page frame navigated missing frame object
        bad_page = CdpEvent(method="Page.frameNavigated", domain="Page", event_name="frameNavigated", params={})
        with self.assertRaises(CdpDomainError):
            CdpParser.decode_event(bad_page)

    def test_payload_memory_ceiling_exceeded(self) -> None:
        """Verify rejection when payload exceeds 64 KB memory limit."""
        massive_payload = json.dumps({"id": 1, "method": "Page.navigate", "params": {"data": "X" * 70000}})
        with self.assertRaises(CdpPayloadExceededError):
            CdpParser.parse_message(massive_payload)

        with self.assertRaises(CdpPayloadExceededError):
            CdpParser.parse_stream(massive_payload)

    def test_thermodynamic_heap_ceiling(self) -> None:
        """Verify memory allocation strictly complies with <= 64 KB ceiling under ThermodynamicProfiler."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            CdpParser.parse_stream,
            self.ndjson_stream,
            candidate_id="cdp_parser_ch27",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)
        self.assertEqual(summary.total_messages, 12)

    def test_adversarial_mutant_fuzzing(self) -> None:
        """Verify fail-closed resilience against deterministic adversarial mutations."""
        golden_bytes = self.ndjson_stream.encode("utf-8")
        mutants = AdversarialMutator.generate_adversarial_suite(golden_bytes)
        self.assertGreaterEqual(len(mutants), 10)

        unhandled_errors: List[str] = []
        for m in mutants:
            try:
                CdpParser.parse_stream(m.payload)
            except (CdpParseError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
                pass
            except Exception as err:
                unhandled_errors.append(f"{m.mutation_type}: {err}")

        self.assertEqual(
            len(unhandled_errors),
            0,
            f"Adversarial mutations caused unhandled crashes: {unhandled_errors}",
        )


if __name__ == "__main__":
    unittest.main()
