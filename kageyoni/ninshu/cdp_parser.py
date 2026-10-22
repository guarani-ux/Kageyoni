"""Zero-dependency Chrome DevTools Protocol (CDP) Browser Automator & Telemetry Decoder (CH 27).

Parses CDP WebSocket messages, event streams, command/response flows, and domain telemetry:
- Pure Python standard library (json, dataclasses, hashlib, re, typing).
- CDP Message Types:
  * Commands: id (positive int), method (Domain.method), params (dict).
  * Responses: id (matching command), result (dict) or error (dict).
  * Events: method (Domain.event), params (dict).
- Core Domains:
  * Network:
    - requestWillBeSent (url, method, headers, requestId, timestamp)
    - responseReceived (status, mimeType, headers, requestId, timestamp)
    - loadingFailed (requestId, timestamp, errorText, canceled, blockedReason)
  * Page:
    - frameNavigated (frame details, url, loaderId)
    - loadEventFired (timestamp)
    - domContentEventFired (timestamp)
  * Runtime:
    - consoleAPICalled (type, args, timestamp, executionContextId)
    - exceptionThrown (text, lineNumber, columnNumber, scriptId, url, stackTrace)
  * DOM:
    - documentUpdated
    - setChildNodes (parentId, nodes)
- Request-Response Correlation:
  * Correlates response IDs to issued command methods and parameters.
  * Tracks network request-response lifecycles and error states.
- Strict Fail-Closed Verification:
  * Enforces memory ceiling <= 64 KB (65536 bytes) per message/stream buffer.
  * Rejects corrupted numeric IDs (e.g. booleans, floats, negative values, non-numeric strings).
  * Rejects missing method/result fields, ambiguous structures, and malformed JSON.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

# Maximum memory buffer size: 64 KB
MAX_PAYLOAD_SIZE: int = 64 * 1024

# Method naming format: Domain.methodName
METHOD_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*$")


class CdpParseError(ValueError):
    """Base exception for CDP parsing and validation failures."""
    pass


class CdpPayloadExceededError(CdpParseError):
    """Raised when payload size exceeds the 64 KB memory limit."""
    pass


class CdpInvalidJsonError(CdpParseError):
    """Raised when input contains invalid JSON or unsupported payload format."""
    pass


class CdpSchemaViolationError(CdpParseError):
    """Raised when CDP message structure violates required protocol schema."""
    pass


class CdpDomainError(CdpParseError):
    """Raised when domain-specific telemetry event parameters are invalid or corrupted."""
    pass


class CdpMessageType(Enum):
    """CDP message classifications."""
    COMMAND = "command"
    RESPONSE = "response"
    EVENT = "event"


# ---------------------------------------------------------------------------
# Core CDP Protocol Primitives
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class CdpCommand:
    """Outgoing command message sent to browser/target."""
    id: int
    method: str
    params: Dict[str, Any] = dataclasses.field(default_factory=dict)
    session_id: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id <= 0:
            raise CdpSchemaViolationError(f"Command ID must be a strictly positive integer, got: {self.id!r}")
        if not isinstance(self.method, str) or not METHOD_PATTERN.match(self.method):
            raise CdpSchemaViolationError(f"Invalid command method name format: {self.method!r}")
        if not isinstance(self.params, dict):
            raise CdpSchemaViolationError(f"Command params must be a dictionary, got: {type(self.params).__name__}")


@dataclasses.dataclass(frozen=True)
class CdpResponse:
    """Incoming response message confirming command execution."""
    id: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id <= 0:
            raise CdpSchemaViolationError(f"Response ID must be a strictly positive integer, got: {self.id!r}")
        if self.result is None and self.error is None:
            raise CdpSchemaViolationError("Response must contain either 'result' or 'error' field")
        if self.result is not None and self.error is not None:
            raise CdpSchemaViolationError("Response cannot contain both 'result' and 'error'")
        if self.result is not None and not isinstance(self.result, dict):
            raise CdpSchemaViolationError(f"'result' field must be a dictionary, got: {type(self.result).__name__}")
        if self.error is not None and not isinstance(self.error, dict):
            raise CdpSchemaViolationError(f"'error' field must be a dictionary, got: {type(self.error).__name__}")

    @property
    def is_success(self) -> bool:
        return self.error is None


@dataclasses.dataclass(frozen=True)
class CdpEvent:
    """Asynchronous notification event emitted by browser/target."""
    method: str
    domain: str
    event_name: str
    params: Dict[str, Any] = dataclasses.field(default_factory=dict)
    session_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.method, str) or not METHOD_PATTERN.match(self.method):
            raise CdpSchemaViolationError(f"Invalid event method name format: {self.method!r}")
        if not isinstance(self.params, dict):
            raise CdpSchemaViolationError(f"Event params must be a dictionary, got: {type(self.params).__name__}")


# ---------------------------------------------------------------------------
# Domain-Specific Telemetry Dataclasses
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class NetworkRequestWillBeSent:
    """Network.requestWillBeSent telemetry event."""
    request_id: str
    url: str
    method: str
    headers: Dict[str, str]
    timestamp: float
    loader_id: Optional[str] = None
    document_url: Optional[str] = None
    initiator_type: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class NetworkResponseReceived:
    """Network.responseReceived telemetry event."""
    request_id: str
    url: str
    status: int
    mime_type: str
    headers: Dict[str, str]
    timestamp: float
    loader_id: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class NetworkLoadingFailed:
    """Network.loadingFailed telemetry event."""
    request_id: str
    timestamp: float
    error_text: str
    canceled: bool = False
    blocked_reason: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class PageFrameNavigated:
    """Page.frameNavigated telemetry event."""
    frame_id: str
    url: str
    loader_id: Optional[str] = None
    name: Optional[str] = None
    security_origin: Optional[str] = None
    mime_type: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class PageLoadEventFired:
    """Page.loadEventFired telemetry event."""
    timestamp: float


@dataclasses.dataclass(frozen=True)
class PageDomContentEventFired:
    """Page.domContentEventFired telemetry event."""
    timestamp: float


@dataclasses.dataclass(frozen=True)
class RuntimeConsoleApiCalled:
    """Runtime.consoleAPICalled telemetry event."""
    type: str
    args: List[Any]
    text: str
    timestamp: float
    execution_context_id: Optional[int] = None
    stack_trace: Optional[Dict[str, Any]] = None


@dataclasses.dataclass(frozen=True)
class RuntimeExceptionThrown:
    """Runtime.exceptionThrown telemetry event."""
    text: str
    timestamp: float
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    script_id: Optional[str] = None
    url: Optional[str] = None
    stack_trace: Optional[Dict[str, Any]] = None


@dataclasses.dataclass(frozen=True)
class DomDocumentUpdated:
    """DOM.documentUpdated telemetry event."""
    pass


@dataclasses.dataclass(frozen=True)
class DomSetChildNodes:
    """DOM.setChildNodes telemetry event."""
    parent_id: int
    nodes_count: int
    nodes: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Correlation & Session Aggregation
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class CorrelatedExchange:
    """Command-response matched pair."""
    command_id: int
    command_method: str
    command_params: Dict[str, Any]
    response_result: Optional[Dict[str, Any]]
    response_error: Optional[Dict[str, Any]]
    is_success: bool
    session_id: Optional[str] = None


@dataclasses.dataclass
class NetworkFlow:
    """Reconstructed HTTP/Network request lifecycle."""
    request_id: str
    url: str
    method: str
    request_headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    status: Optional[int] = None
    mime_type: Optional[str] = None
    response_headers: Dict[str, str] = dataclasses.field(default_factory=dict)
    failed: bool = False
    error_text: Optional[str] = None
    canceled: bool = False
    request_timestamp: Optional[float] = None
    response_timestamp: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "url": self.url,
            "method": self.method,
            "request_headers": self.request_headers,
            "status": self.status,
            "mime_type": self.mime_type,
            "response_headers": self.response_headers,
            "failed": self.failed,
            "error_text": self.error_text,
            "canceled": self.canceled,
            "request_timestamp": self.request_timestamp,
            "response_timestamp": self.response_timestamp,
        }


@dataclasses.dataclass(frozen=True)
class CdpSessionSummary:
    """Summary of complete decoded CDP session with correlated telemetry."""
    total_messages: int
    commands_count: int
    responses_count: int
    events_count: int
    correlated_exchanges: List[CorrelatedExchange]
    unmatched_responses_count: int
    network_flows: Dict[str, Dict[str, Any]]
    console_events: List[Dict[str, Any]]
    exceptions: List[Dict[str, Any]]
    page_navigations: List[Dict[str, Any]]
    dom_updates_count: int
    sha256_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_messages": self.total_messages,
            "commands_count": self.commands_count,
            "responses_count": self.responses_count,
            "events_count": self.events_count,
            "correlated_exchanges": [dataclasses.asdict(e) for e in self.correlated_exchanges],
            "unmatched_responses_count": self.unmatched_responses_count,
            "network_flows": self.network_flows,
            "console_events": self.console_events,
            "exceptions": self.exceptions,
            "page_navigations": self.page_navigations,
            "dom_updates_count": self.dom_updates_count,
            "sha256_digest": self.sha256_digest,
        }


# ---------------------------------------------------------------------------
# CDP Parser Implementation
# ---------------------------------------------------------------------------

class CdpParser:
    """Zero-dependency Chrome DevTools Protocol parser and telemetry decoder."""

    @classmethod
    def _validate_raw_payload(cls, raw: Union[str, bytes]) -> str:
        """Validates payload size <= 64 KB and decodes to text strictly."""
        if isinstance(raw, bytes):
            if len(raw) > MAX_PAYLOAD_SIZE:
                raise CdpPayloadExceededError(
                    f"Payload size {len(raw)} bytes exceeds 64 KB limit ({MAX_PAYLOAD_SIZE} bytes)"
                )
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as err:
                raise CdpInvalidJsonError(f"Corrupted UTF-8 payload: {err}") from err
        elif isinstance(raw, str):
            encoded_len = len(raw.encode("utf-8"))
            if encoded_len > MAX_PAYLOAD_SIZE:
                raise CdpPayloadExceededError(
                    f"Payload size {encoded_len} bytes exceeds 64 KB limit ({MAX_PAYLOAD_SIZE} bytes)"
                )
            text = raw
        else:
            raise CdpInvalidJsonError(f"Expected str or bytes payload, got: {type(raw).__name__}")

        if not text.strip():
            raise CdpInvalidJsonError("CDP payload is empty or whitespace only")

        return text

    @classmethod
    def parse_message(
        cls, message: Union[str, bytes, Dict[str, Any]]
    ) -> Union[CdpCommand, CdpResponse, CdpEvent]:
        """Parses a single CDP message into CdpCommand, CdpResponse, or CdpEvent.

        Strict fail-closed schema checks:
        - Must be a JSON object (dict).
        - Commands have integer 'id' and 'method'.
        - Responses have integer 'id' and either 'result' or 'error' (no 'method').
        - Events have 'method' and no 'id'.
        """
        if isinstance(message, dict):
            data = message
        else:
            text = cls._validate_raw_payload(message)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as err:
                raise CdpInvalidJsonError(f"JSON decode failure: {err}") from err

        if not isinstance(data, dict):
            raise CdpSchemaViolationError(f"Root CDP message must be a JSON object, got: {type(data).__name__}")

        session_id = data.get("sessionId")
        if session_id is not None and not isinstance(session_id, str):
            raise CdpSchemaViolationError(f"sessionId must be a string if provided, got: {type(session_id).__name__}")

        has_id = "id" in data
        has_method = "method" in data
        has_result = "result" in data
        has_error = "error" in data

        if not has_id and not has_method:
            raise CdpSchemaViolationError("CDP message missing both 'id' and 'method' fields")

        # Command: has 'id' and 'method'
        if has_id and has_method:
            if has_result or has_error:
                raise CdpSchemaViolationError("Ambiguous CDP message containing both 'method' and 'result'/'error'")
            msg_id = data["id"]
            method = data["method"]
            params = data.get("params", {})
            return CdpCommand(id=msg_id, method=method, params=params, session_id=session_id)

        # Response: has 'id' but no 'method'
        if has_id and not has_method:
            msg_id = data["id"]
            result = data.get("result")
            error = data.get("error")
            return CdpResponse(id=msg_id, result=result, error=error, session_id=session_id)

        # Event: has 'method' but no 'id'
        method = data["method"]
        if not isinstance(method, str) or "." not in method:
            raise CdpSchemaViolationError(f"Event method must be a string containing 'Domain.event', got: {method!r}")
        domain, event_name = method.split(".", 1)
        params = data.get("params", {})
        return CdpEvent(method=method, domain=domain, event_name=event_name, params=params, session_id=session_id)

    @classmethod
    def decode_event(cls, event: CdpEvent) -> Any:
        """Decodes a CdpEvent into a typed domain event if recognized, else returns event as-is."""
        if not isinstance(event, CdpEvent):
            raise CdpDomainError(f"Expected CdpEvent instance, got: {type(event).__name__}")

        params = event.params
        method = event.method

        if method == "Network.requestWillBeSent":
            return cls._decode_network_request_will_be_sent(params)
        elif method == "Network.responseReceived":
            return cls._decode_network_response_received(params)
        elif method == "Network.loadingFailed":
            return cls._decode_network_loading_failed(params)
        elif method == "Page.frameNavigated":
            return cls._decode_page_frame_navigated(params)
        elif method == "Page.loadEventFired":
            return cls._decode_page_load_event(params)
        elif method == "Page.domContentEventFired":
            return cls._decode_page_dom_content_event(params)
        elif method == "Runtime.consoleAPICalled":
            return cls._decode_runtime_console_api(params)
        elif method == "Runtime.exceptionThrown":
            return cls._decode_runtime_exception(params)
        elif method == "DOM.documentUpdated":
            return DomDocumentUpdated()
        elif method == "DOM.setChildNodes":
            return cls._decode_dom_set_child_nodes(params)

        return event

    # --- Domain decoders ---

    @staticmethod
    def _decode_network_request_will_be_sent(params: Dict[str, Any]) -> NetworkRequestWillBeSent:
        request_id = params.get("requestId")
        if not request_id or not isinstance(request_id, str):
            raise CdpDomainError("Network.requestWillBeSent missing valid 'requestId'")

        req = params.get("request")
        if not isinstance(req, dict):
            raise CdpDomainError("Network.requestWillBeSent missing 'request' object")

        url = req.get("url")
        if not isinstance(url, str):
            raise CdpDomainError("Network request object missing valid 'url'")

        method = req.get("method")
        if not isinstance(method, str):
            raise CdpDomainError("Network request object missing valid 'method'")

        headers = req.get("headers", {})
        if not isinstance(headers, dict):
            raise CdpDomainError("Network request headers must be a dictionary")

        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError(f"Network request timestamp must be numeric, got: {type(raw_ts).__name__}")

        initiator = params.get("initiator", {})
        initiator_type = initiator.get("type") if isinstance(initiator, dict) else None

        return NetworkRequestWillBeSent(
            request_id=request_id,
            url=url,
            method=method,
            headers={str(k): str(v) for k, v in headers.items()},
            timestamp=float(raw_ts),
            loader_id=params.get("loaderId"),
            document_url=params.get("documentURL"),
            initiator_type=initiator_type,
        )

    @staticmethod
    def _decode_network_response_received(params: Dict[str, Any]) -> NetworkResponseReceived:
        request_id = params.get("requestId")
        if not request_id or not isinstance(request_id, str):
            raise CdpDomainError("Network.responseReceived missing valid 'requestId'")

        res = params.get("response")
        if not isinstance(res, dict):
            raise CdpDomainError("Network.responseReceived missing 'response' object")

        url = res.get("url", "")
        if not isinstance(url, str):
            raise CdpDomainError("Network response object missing valid 'url'")

        status = res.get("status")
        if isinstance(status, bool) or not isinstance(status, int):
            raise CdpDomainError(f"Network response status must be integer, got: {status!r}")

        mime_type = res.get("mimeType", "")
        if not isinstance(mime_type, str):
            raise CdpDomainError("Network response mimeType must be a string")

        headers = res.get("headers", {})
        if not isinstance(headers, dict):
            raise CdpDomainError("Network response headers must be a dictionary")

        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Network response timestamp must be numeric")

        return NetworkResponseReceived(
            request_id=request_id,
            url=url,
            status=status,
            mime_type=mime_type,
            headers={str(k): str(v) for k, v in headers.items()},
            timestamp=float(raw_ts),
            loader_id=params.get("loaderId"),
        )

    @staticmethod
    def _decode_network_loading_failed(params: Dict[str, Any]) -> NetworkLoadingFailed:
        request_id = params.get("requestId")
        if not request_id or not isinstance(request_id, str):
            raise CdpDomainError("Network.loadingFailed missing valid 'requestId'")

        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Network.loadingFailed timestamp must be numeric")

        error_text = params.get("errorText", "")
        if not isinstance(error_text, str):
            raise CdpDomainError("Network.loadingFailed errorText must be a string")

        canceled = bool(params.get("canceled", False))
        blocked_reason = params.get("blockedReason")

        return NetworkLoadingFailed(
            request_id=request_id,
            timestamp=float(raw_ts),
            error_text=error_text,
            canceled=canceled,
            blocked_reason=blocked_reason if isinstance(blocked_reason, str) else None,
        )

    @staticmethod
    def _decode_page_frame_navigated(params: Dict[str, Any]) -> PageFrameNavigated:
        frame = params.get("frame")
        if not isinstance(frame, dict):
            raise CdpDomainError("Page.frameNavigated missing 'frame' object")

        frame_id = frame.get("id")
        if not frame_id or not isinstance(frame_id, str):
            raise CdpDomainError("Page frame missing valid 'id'")

        url = frame.get("url")
        if not isinstance(url, str):
            raise CdpDomainError("Page frame missing valid 'url'")

        return PageFrameNavigated(
            frame_id=frame_id,
            url=url,
            loader_id=frame.get("loaderId"),
            name=frame.get("name"),
            security_origin=frame.get("securityOrigin"),
            mime_type=frame.get("mimeType"),
        )

    @staticmethod
    def _decode_page_load_event(params: Dict[str, Any]) -> PageLoadEventFired:
        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Page.loadEventFired timestamp must be numeric")
        return PageLoadEventFired(timestamp=float(raw_ts))

    @staticmethod
    def _decode_page_dom_content_event(params: Dict[str, Any]) -> PageDomContentEventFired:
        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Page.domContentEventFired timestamp must be numeric")
        return PageDomContentEventFired(timestamp=float(raw_ts))

    @staticmethod
    def _decode_runtime_console_api(params: Dict[str, Any]) -> RuntimeConsoleApiCalled:
        log_type = params.get("type")
        if not log_type or not isinstance(log_type, str):
            raise CdpDomainError("Runtime.consoleAPICalled missing valid 'type'")

        raw_args = params.get("args", [])
        if not isinstance(raw_args, list):
            raise CdpDomainError("Runtime.consoleAPICalled args must be a list")

        # Format values from RemoteObjects
        formatted_parts: List[str] = []
        for a in raw_args:
            if isinstance(a, dict):
                if "value" in a:
                    formatted_parts.append(str(a["value"]))
                elif "description" in a:
                    formatted_parts.append(str(a["description"]))
                else:
                    formatted_parts.append(json.dumps(a))
            else:
                formatted_parts.append(str(a))

        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Runtime.consoleAPICalled timestamp must be numeric")

        ctx_id = params.get("executionContextId")
        if ctx_id is not None and (isinstance(ctx_id, bool) or not isinstance(ctx_id, int)):
            raise CdpDomainError("executionContextId must be an integer")

        stack = params.get("stackTrace")
        return RuntimeConsoleApiCalled(
            type=log_type,
            args=raw_args,
            text=" ".join(formatted_parts),
            timestamp=float(raw_ts),
            execution_context_id=ctx_id,
            stack_trace=stack if isinstance(stack, dict) else None,
        )

    @staticmethod
    def _decode_runtime_exception(params: Dict[str, Any]) -> RuntimeExceptionThrown:
        raw_ts = params.get("timestamp", 0.0)
        if not isinstance(raw_ts, (int, float)):
            raise CdpDomainError("Runtime.exceptionThrown timestamp must be numeric")

        details = params.get("exceptionDetails")
        if not isinstance(details, dict):
            raise CdpDomainError("Runtime.exceptionThrown missing 'exceptionDetails' object")

        text = details.get("text")
        if not text or not isinstance(text, str):
            raise CdpDomainError("exceptionDetails missing valid 'text'")

        line_num = details.get("lineNumber")
        if line_num is not None and (isinstance(line_num, bool) or not isinstance(line_num, int)):
            raise CdpDomainError("lineNumber must be integer")

        col_num = details.get("columnNumber")
        if col_num is not None and (isinstance(col_num, bool) or not isinstance(col_num, int)):
            raise CdpDomainError("columnNumber must be integer")

        return RuntimeExceptionThrown(
            text=text,
            timestamp=float(raw_ts),
            line_number=line_num,
            column_number=col_num,
            script_id=details.get("scriptId"),
            url=details.get("url"),
            stack_trace=details.get("stackTrace") if isinstance(details.get("stackTrace"), dict) else None,
        )

    @staticmethod
    def _decode_dom_set_child_nodes(params: Dict[str, Any]) -> DomSetChildNodes:
        parent_id = params.get("parentId")
        if isinstance(parent_id, bool) or not isinstance(parent_id, int):
            raise CdpDomainError("DOM.setChildNodes parentId must be an integer")

        nodes = params.get("nodes")
        if not isinstance(nodes, list):
            raise CdpDomainError("DOM.setChildNodes nodes must be a list")

        return DomSetChildNodes(
            parent_id=parent_id,
            nodes_count=len(nodes),
            nodes=nodes,
        )

    @classmethod
    def parse_stream(
        cls, stream_data: Union[str, bytes, List[Union[str, bytes, Dict[str, Any]]]]
    ) -> CdpSessionSummary:
        """Parses a complete stream of CDP messages, correlating commands, responses, and events."""
        if isinstance(stream_data, (str, bytes)):
            text = cls._validate_raw_payload(stream_data)
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

            stripped = text.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    items = json.loads(stripped)
                    if not isinstance(items, list):
                        raise CdpInvalidJsonError("Expected JSON array of messages")
                except json.JSONDecodeError as err:
                    raise CdpInvalidJsonError(f"JSON array decode failure: {err}") from err
            else:
                # Line-delimited JSON (NDJSON)
                lines = [line.strip() for line in stripped.splitlines() if line.strip()]
                if not lines:
                    raise CdpInvalidJsonError("Stream contains no valid message lines")
                items = lines
        elif isinstance(stream_data, list):
            if not stream_data:
                raise CdpInvalidJsonError("Empty message list provided")
            items = stream_data
            serialized = json.dumps(
                [i if isinstance(i, dict) else str(i) for i in items], sort_keys=True
            ).encode("utf-8")
            if len(serialized) > MAX_PAYLOAD_SIZE:
                raise CdpPayloadExceededError(f"List payload exceeds {MAX_PAYLOAD_SIZE} bytes")
            digest = hashlib.sha256(serialized).hexdigest()
        else:
            raise CdpInvalidJsonError(f"Unsupported stream_data type: {type(stream_data).__name__}")

        total_messages = 0
        commands_count = 0
        responses_count = 0
        events_count = 0

        # Command tracking for correlation: id -> CdpCommand
        pending_commands: Dict[int, CdpCommand] = {}
        correlated_exchanges: List[CorrelatedExchange] = []
        unmatched_responses_count = 0

        # Domain trackers
        network_flows: Dict[str, NetworkFlow] = {}
        console_events: List[Dict[str, Any]] = []
        exceptions: List[Dict[str, Any]] = []
        page_navigations: List[Dict[str, Any]] = []
        dom_updates_count = 0

        for item in items:
            total_messages += 1
            msg = cls.parse_message(item)

            if isinstance(msg, CdpCommand):
                commands_count += 1
                pending_commands[msg.id] = msg

            elif isinstance(msg, CdpResponse):
                responses_count += 1
                if msg.id in pending_commands:
                    cmd = pending_commands.pop(msg.id)
                    correlated_exchanges.append(
                        CorrelatedExchange(
                            command_id=msg.id,
                            command_method=cmd.method,
                            command_params=cmd.params,
                            response_result=msg.result,
                            response_error=msg.error,
                            is_success=msg.is_success,
                            session_id=msg.session_id,
                        )
                    )
                else:
                    unmatched_responses_count += 1

            elif isinstance(msg, CdpEvent):
                events_count += 1
                decoded = cls.decode_event(msg)

                if isinstance(decoded, NetworkRequestWillBeSent):
                    network_flows[decoded.request_id] = NetworkFlow(
                        request_id=decoded.request_id,
                        url=decoded.url,
                        method=decoded.method,
                        request_headers=decoded.headers,
                        request_timestamp=decoded.timestamp,
                    )
                elif isinstance(decoded, NetworkResponseReceived):
                    flow = network_flows.get(decoded.request_id)
                    if flow is None:
                        flow = NetworkFlow(
                            request_id=decoded.request_id,
                            url=decoded.url,
                            method="UNKNOWN",
                        )
                        network_flows[decoded.request_id] = flow
                    flow.status = decoded.status
                    flow.mime_type = decoded.mime_type
                    flow.response_headers = decoded.headers
                    flow.response_timestamp = decoded.timestamp
                    if decoded.url and not flow.url:
                        flow.url = decoded.url

                elif isinstance(decoded, NetworkLoadingFailed):
                    flow = network_flows.get(decoded.request_id)
                    if flow is None:
                        flow = NetworkFlow(
                            request_id=decoded.request_id,
                            url="",
                            method="UNKNOWN",
                        )
                        network_flows[decoded.request_id] = flow
                    flow.failed = True
                    flow.error_text = decoded.error_text
                    flow.canceled = decoded.canceled

                elif isinstance(decoded, PageFrameNavigated):
                    page_navigations.append(dataclasses.asdict(decoded))

                elif isinstance(decoded, RuntimeConsoleApiCalled):
                    console_events.append(dataclasses.asdict(decoded))

                elif isinstance(decoded, RuntimeExceptionThrown):
                    exceptions.append(dataclasses.asdict(decoded))

                elif isinstance(decoded, (DomDocumentUpdated, DomSetChildNodes)):
                    dom_updates_count += 1

        return CdpSessionSummary(
            total_messages=total_messages,
            commands_count=commands_count,
            responses_count=responses_count,
            events_count=events_count,
            correlated_exchanges=correlated_exchanges,
            unmatched_responses_count=unmatched_responses_count,
            network_flows={k: v.to_dict() for k, v in network_flows.items()},
            console_events=console_events,
            exceptions=exceptions,
            page_navigations=page_navigations,
            dom_updates_count=dom_updates_count,
            sha256_digest=digest,
        )
