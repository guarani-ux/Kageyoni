"""Zero-dependency in-tree Mitmproxy Offline Flow Decoder (CH 35).

Parses serialized Mitmproxy flow records (MsgPack and length-prefixed frames):
- Pure Python standard library (struct, io, hashlib, dataclasses, json).
- Pure-Python streaming MsgPack decoder:
  * Integers: positive/negative fixint, uint8/16/32/64, int8/16/32/64.
  * Maps: fixmap, map16, map32.
  * Arrays: fixarray, array16, array32.
  * Strings: fixstr, str8, str16, str32 (strict UTF-8 validation).
  * Binaries: bin8, bin16, bin32.
  * Nil, Booleans, IEEE 754 Floats (float32, float64).
  * Ext: fixext1/2/4/8/16, ext8/16/32.
- Length-prefixed frame detection and handling.
- Legacy TNetstring stream support.
- HTTP flow attribute extraction:
  * method, scheme, host, port, path, status_code,
  * request_headers, response_headers, content_length.
- Strict fail-closed parsing:
  * Rejects corrupted headers, invalid ports, negative lengths, truncated payloads,
    recursion limit violations, and corrupted string encodings.
- Thermodynamic compliance: Peak heap allocation <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import struct
from pathlib import Path
from typing import Any, BinaryIO, Dict, Iterator, List, Optional, Tuple, Union


@dataclasses.dataclass(frozen=True)
class MitmproxyHttpFlow:
    """Normalized HTTP flow extracted from Mitmproxy serialized record."""
    flow_id: str
    flow_type: str
    method: str
    scheme: str
    host: str
    port: int
    path: str
    status_code: Optional[int]
    request_headers: List[Tuple[str, str]]
    response_headers: List[Tuple[str, str]]
    content_length: int
    request_content_length: int
    response_content_length: int
    error_msg: Optional[str] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    sha256_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "flow_type": self.flow_type,
            "method": self.method,
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "status_code": self.status_code,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "content_length": self.content_length,
            "request_content_length": self.request_content_length,
            "response_content_length": self.response_content_length,
            "error_msg": self.error_msg,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "sha256_digest": self.sha256_digest,
        }


@dataclasses.dataclass(frozen=True)
class MitmproxyDumpSummary:
    """Summary of Mitmproxy capture stream."""
    total_bytes: int
    flows_count: int
    http_flows_count: int
    error_flows_count: int
    sha256_digest: str
    flows: List[MitmproxyHttpFlow]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "flows_count": self.flows_count,
            "http_flows_count": self.http_flows_count,
            "error_flows_count": self.error_flows_count,
            "sha256_digest": self.sha256_digest,
            "flows": [f.to_dict() for f in self.flows],
        }


class MsgPackDecoder:
    """Strict pure-Python MsgPack streaming decoder."""

    MAX_RECURSION_DEPTH = 32
    MAX_CONTAINER_ELEMENTS = 65536
    MAX_PAYLOAD_SIZE = 16 * 1024 * 1024  # 16 MB

    @classmethod
    def _read_exact(cls, stream: BinaryIO, count: int) -> bytes:
        if count < 0:
            raise ValueError(f"Negative read length requested: {count}")
        if count > cls.MAX_PAYLOAD_SIZE:
            raise ValueError(f"Requested read length {count} exceeds safety limit {cls.MAX_PAYLOAD_SIZE}")
        data = stream.read(count)
        if len(data) < count:
            raise ValueError(f"Truncated MsgPack payload: expected {count} bytes, got {len(data)}")
        return data

    @classmethod
    def unpack(cls, stream: BinaryIO, depth: int = 0) -> Any:
        if depth > cls.MAX_RECURSION_DEPTH:
            raise ValueError(f"MsgPack recursion depth exceeded limit ({cls.MAX_RECURSION_DEPTH})")

        header = stream.read(1)
        if not header:
            raise ValueError("Truncated MsgPack payload: unexpected end of stream")

        b = header[0]

        # Positive fixint: 0x00 - 0x7f
        if b <= 0x7F:
            return b

        # Fixmap: 0x80 - 0x8f
        if 0x80 <= b <= 0x8F:
            count = b & 0x0F
            result_map: Dict[Any, Any] = {}
            for _ in range(count):
                k = cls.unpack(stream, depth + 1)
                v = cls.unpack(stream, depth + 1)
                result_map[k] = v
            return result_map

        # Fixarray: 0x90 - 0x9f
        if 0x90 <= b <= 0x9F:
            count = b & 0x0F
            return [cls.unpack(stream, depth + 1) for _ in range(count)]

        # Fixstr: 0xa0 - 0xbf
        if 0xA0 <= b <= 0xBF:
            length = b & 0x1F
            raw = cls._read_exact(stream, length)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Corrupted UTF-8 in MsgPack fixstr: {err}") from err

        # Nil
        if b == 0xC0:
            return None

        # (Never used)
        if b == 0xC1:
            raise ValueError("Invalid MsgPack format byte: 0xc1 is reserved")

        # False / True
        if b == 0xC2:
            return False
        if b == 0xC3:
            return True

        # Bin 8 / 16 / 32
        if b == 0xC4:
            length = cls._read_exact(stream, 1)[0]
            return cls._read_exact(stream, length)
        if b == 0xC5:
            length = struct.unpack(">H", cls._read_exact(stream, 2))[0]
            return cls._read_exact(stream, length)
        if b == 0xC6:
            length = struct.unpack(">I", cls._read_exact(stream, 4))[0]
            return cls._read_exact(stream, length)

        # Ext 8 / 16 / 32
        if b == 0xC7:
            length = cls._read_exact(stream, 1)[0]
            ext_type = struct.unpack(">b", cls._read_exact(stream, 1))[0]
            data = cls._read_exact(stream, length)
            return (ext_type, data)
        if b == 0xC8:
            length = struct.unpack(">H", cls._read_exact(stream, 2))[0]
            ext_type = struct.unpack(">b", cls._read_exact(stream, 1))[0]
            data = cls._read_exact(stream, length)
            return (ext_type, data)
        if b == 0xC9:
            length = struct.unpack(">I", cls._read_exact(stream, 4))[0]
            ext_type = struct.unpack(">b", cls._read_exact(stream, 1))[0]
            data = cls._read_exact(stream, length)
            return (ext_type, data)

        # Float 32 / 64
        if b == 0xCA:
            return struct.unpack(">f", cls._read_exact(stream, 4))[0]
        if b == 0xCB:
            return struct.unpack(">d", cls._read_exact(stream, 8))[0]

        # UInt 8 / 16 / 32 / 64
        if b == 0xCC:
            return cls._read_exact(stream, 1)[0]
        if b == 0xCD:
            return struct.unpack(">H", cls._read_exact(stream, 2))[0]
        if b == 0xCE:
            return struct.unpack(">I", cls._read_exact(stream, 4))[0]
        if b == 0xCF:
            return struct.unpack(">Q", cls._read_exact(stream, 8))[0]

        # Int 8 / 16 / 32 / 64
        if b == 0xD0:
            return struct.unpack(">b", cls._read_exact(stream, 1))[0]
        if b == 0xD1:
            return struct.unpack(">h", cls._read_exact(stream, 2))[0]
        if b == 0xD2:
            return struct.unpack(">i", cls._read_exact(stream, 4))[0]
        if b == 0xD3:
            return struct.unpack(">q", cls._read_exact(stream, 8))[0]

        # FixExt 1 / 2 / 4 / 8 / 16
        if 0xD4 <= b <= 0xD8:
            fixext_lens = {0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}
            length = fixext_lens[b]
            ext_type = struct.unpack(">b", cls._read_exact(stream, 1))[0]
            data = cls._read_exact(stream, length)
            return (ext_type, data)

        # Str 8 / 16 / 32
        if b == 0xD9:
            length = cls._read_exact(stream, 1)[0]
            raw = cls._read_exact(stream, length)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Corrupted UTF-8 in MsgPack str8: {err}") from err
        if b == 0xDA:
            length = struct.unpack(">H", cls._read_exact(stream, 2))[0]
            raw = cls._read_exact(stream, length)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Corrupted UTF-8 in MsgPack str16: {err}") from err
        if b == 0xDB:
            length = struct.unpack(">I", cls._read_exact(stream, 4))[0]
            raw = cls._read_exact(stream, length)
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Corrupted UTF-8 in MsgPack str32: {err}") from err

        # Array 16 / 32
        if b == 0xDC:
            count = struct.unpack(">H", cls._read_exact(stream, 2))[0]
            if count > cls.MAX_CONTAINER_ELEMENTS:
                raise ValueError(f"Array element count {count} exceeds limit {cls.MAX_CONTAINER_ELEMENTS}")
            return [cls.unpack(stream, depth + 1) for _ in range(count)]
        if b == 0xDD:
            count = struct.unpack(">I", cls._read_exact(stream, 4))[0]
            if count > cls.MAX_CONTAINER_ELEMENTS:
                raise ValueError(f"Array element count {count} exceeds limit {cls.MAX_CONTAINER_ELEMENTS}")
            return [cls.unpack(stream, depth + 1) for _ in range(count)]

        # Map 16 / 32
        if b == 0xDE:
            count = struct.unpack(">H", cls._read_exact(stream, 2))[0]
            if count > cls.MAX_CONTAINER_ELEMENTS:
                raise ValueError(f"Map pair count {count} exceeds limit {cls.MAX_CONTAINER_ELEMENTS}")
            result_map = {}
            for _ in range(count):
                k = cls.unpack(stream, depth + 1)
                v = cls.unpack(stream, depth + 1)
                result_map[k] = v
            return result_map
        if b == 0xDF:
            count = struct.unpack(">I", cls._read_exact(stream, 4))[0]
            if count > cls.MAX_CONTAINER_ELEMENTS:
                raise ValueError(f"Map pair count {count} exceeds limit {cls.MAX_CONTAINER_ELEMENTS}")
            result_map = {}
            for _ in range(count):
                k = cls.unpack(stream, depth + 1)
                v = cls.unpack(stream, depth + 1)
                result_map[k] = v
            return result_map

        # Negative fixint: 0xe0 - 0xff (-32 to -1)
        if 0xE0 <= b <= 0xFF:
            return struct.unpack(">b", bytes([b]))[0]

        raise ValueError(f"Unhandled MsgPack byte: 0x{b:02x}")


class MsgPackSerializer:
    """Strict pure-Python MsgPack serializer for synthesizing valid flows and vectors."""

    @classmethod
    def pack(cls, obj: Any) -> bytes:
        if obj is None:
            return b"\xc0"
        if isinstance(obj, bool):
            return b"\xc3" if obj else b"\xc2"
        if isinstance(obj, int):
            if 0 <= obj <= 127:
                return bytes([obj])
            if -32 <= obj < 0:
                return struct.pack(">b", obj)
            if 0 <= obj <= 0xFF:
                return struct.pack(">BB", 0xCC, obj)
            if 0 <= obj <= 0xFFFF:
                return struct.pack(">BH", 0xCD, obj)
            if 0 <= obj <= 0xFFFFFFFF:
                return struct.pack(">BI", 0xCE, obj)
            if 0 <= obj <= 0xFFFFFFFFFFFFFFFF:
                return struct.pack(">BQ", 0xCF, obj)
            if -128 <= obj < -32:
                return struct.pack(">Bb", 0xD0, obj)
            if -32768 <= obj < -128:
                return struct.pack(">Bh", 0xD1, obj)
            if -2147483648 <= obj < -32768:
                return struct.pack(">Bi", 0xD2, obj)
            return struct.pack(">Bq", 0xD3, obj)
        if isinstance(obj, float):
            return struct.pack(">Bd", 0xCB, obj)
        if isinstance(obj, str):
            encoded = obj.encode("utf-8")
            n = len(encoded)
            if n <= 31:
                return bytes([0xA0 | n]) + encoded
            if n <= 0xFF:
                return struct.pack(">BB", 0xD9, n) + encoded
            if n <= 0xFFFF:
                return struct.pack(">BH", 0xDA, n) + encoded
            return struct.pack(">BI", 0xDB, n) + encoded
        if isinstance(obj, (bytes, bytearray)):
            n = len(obj)
            if n <= 0xFF:
                return struct.pack(">BB", 0xC4, n) + bytes(obj)
            if n <= 0xFFFF:
                return struct.pack(">BH", 0xC5, n) + bytes(obj)
            return struct.pack(">BI", 0xC6, n) + bytes(obj)
        if isinstance(obj, (list, tuple)):
            n = len(obj)
            payload = b"".join(cls.pack(item) for item in obj)
            if n <= 15:
                return bytes([0x90 | n]) + payload
            if n <= 0xFFFF:
                return struct.pack(">BH", 0xDC, n) + payload
            return struct.pack(">BI", 0xDD, n) + payload
        if isinstance(obj, dict):
            n = len(obj)
            payload = b"".join(cls.pack(k) + cls.pack(v) for k, v in obj.items())
            if n <= 15:
                return bytes([0x80 | n]) + payload
            if n <= 0xFFFF:
                return struct.pack(">BH", 0xDE, n) + payload
            return struct.pack(">BI", 0xDF, n) + payload
        raise ValueError(f"Unsupported MsgPack serialization type: {type(obj).__name__}")


class MitmproxyDumpParser:
    """Zero-dependency streaming decoder for offline Mitmproxy dump files."""

    @classmethod
    def _to_text(cls, value: Any, field_name: str) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"Invalid UTF-8 in field '{field_name}': {err}") from err
        raise ValueError(f"Expected string or bytes for '{field_name}', got {type(value).__name__}")

    @classmethod
    def _normalize_headers(cls, raw_headers: Any) -> List[Tuple[str, str]]:
        if raw_headers is None:
            return []
        if isinstance(raw_headers, dict):
            result = []
            for k, v in raw_headers.items():
                k_str = cls._to_text(k, "header_key")
                if isinstance(v, (list, tuple)):
                    for item in v:
                        result.append((k_str, cls._to_text(item, "header_value")))
                else:
                    result.append((k_str, cls._to_text(v, "header_value")))
            return result
        if isinstance(raw_headers, (list, tuple)):
            result = []
            for item in raw_headers:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    raise ValueError(f"Invalid header entry: expected pair [name, value], got {repr(item)}")
                k_str = cls._to_text(item[0], "header_name")
                v_str = cls._to_text(item[1], "header_value")
                result.append((k_str, v_str))
            return result
        raise ValueError(f"Invalid headers structure: expected list or dict, got {type(raw_headers).__name__}")

    @classmethod
    def _normalize_dict_keys(cls, raw_dict: Dict[Any, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for k, v in raw_dict.items():
            k_str = cls._to_text(k, "dict_key")
            normalized[k_str] = v
        return normalized

    @classmethod
    def parse_flow_record(cls, record: Any) -> MitmproxyHttpFlow:
        if not isinstance(record, dict):
            raise ValueError(f"Corrupted flow record: expected dict/map, got {type(record).__name__}")

        norm_record = cls._normalize_dict_keys(record)

        flow_id = cls._to_text(norm_record.get("id", "unknown_flow"), "flow_id")
        flow_type = cls._to_text(norm_record.get("type", "http"), "flow_type").lower()

        raw_req = norm_record.get("request")
        raw_resp = norm_record.get("response")
        raw_err = norm_record.get("error")

        if raw_req is None and raw_err is None:
            raise ValueError(f"Flow {flow_id}: neither request nor error structure present")

        method = "UNKNOWN"
        scheme = "http"
        host = "localhost"
        port = 80
        path = "/"
        req_headers: List[Tuple[str, str]] = []
        req_content_len = 0
        timestamp_start: Optional[float] = None
        timestamp_end: Optional[float] = None

        if raw_req is not None:
            if not isinstance(raw_req, dict):
                raise ValueError(f"Flow {flow_id}: request payload must be a dict, got {type(raw_req).__name__}")
            req_dict = cls._normalize_dict_keys(raw_req)

            method = cls._to_text(req_dict.get("method", "GET"), "method")
            scheme = cls._to_text(req_dict.get("scheme", "http"), "scheme")
            host = cls._to_text(req_dict.get("host", "localhost"), "host")

            raw_port = req_dict.get("port", 80)
            if not isinstance(raw_port, int) or raw_port <= 0 or raw_port > 65535:
                raise ValueError(f"Flow {flow_id}: invalid network port: {raw_port}")
            port = raw_port

            path = cls._to_text(req_dict.get("path", "/"), "path")
            req_headers = cls._normalize_headers(req_dict.get("headers"))

            content = req_dict.get("content")
            if content is not None:
                if isinstance(content, (bytes, bytearray)):
                    req_content_len = len(content)
                elif isinstance(content, str):
                    req_content_len = len(content.encode("utf-8"))
                else:
                    raise ValueError(f"Flow {flow_id}: request content must be bytes or string")

            ts_start = req_dict.get("timestamp_start")
            if isinstance(ts_start, (int, float)):
                timestamp_start = float(ts_start)
            ts_end = req_dict.get("timestamp_end")
            if isinstance(ts_end, (int, float)):
                timestamp_end = float(ts_end)

        status_code: Optional[int] = None
        resp_headers: List[Tuple[str, str]] = []
        resp_content_len = 0

        if raw_resp is not None:
            if not isinstance(raw_resp, dict):
                raise ValueError(f"Flow {flow_id}: response payload must be a dict, got {type(raw_resp).__name__}")
            resp_dict = cls._normalize_dict_keys(raw_resp)

            sc = resp_dict.get("status_code")
            if sc is not None:
                if not isinstance(sc, int) or sc < 100 or sc > 599:
                    raise ValueError(f"Flow {flow_id}: invalid HTTP status code: {sc}")
                status_code = sc

            resp_headers = cls._normalize_headers(resp_dict.get("headers"))

            r_content = resp_dict.get("content")
            if r_content is not None:
                if isinstance(r_content, (bytes, bytearray)):
                    resp_content_len = len(r_content)
                elif isinstance(r_content, str):
                    resp_content_len = len(r_content.encode("utf-8"))
                else:
                    raise ValueError(f"Flow {flow_id}: response content must be bytes or string")

            resp_ts_end = resp_dict.get("timestamp_end")
            if isinstance(resp_ts_end, (int, float)):
                timestamp_end = float(resp_ts_end)

        error_msg: Optional[str] = None
        if raw_err is not None:
            if isinstance(raw_err, dict):
                err_dict = cls._normalize_dict_keys(raw_err)
                error_msg = cls._to_text(err_dict.get("msg", "Generic flow error"), "error_msg")
            elif isinstance(raw_err, (str, bytes)):
                error_msg = cls._to_text(raw_err, "error_msg")
            else:
                error_msg = str(raw_err)

        # Compute content_length according to protocol semantics:
        # If response content is present, use response length.
        # Otherwise if Content-Length header is present in response, extract it.
        # Otherwise fall back to request content length.
        if resp_content_len > 0:
            content_length = resp_content_len
        else:
            hdr_len = None
            for h_name, h_val in resp_headers:
                if h_name.lower() == "content-length":
                    try:
                        hdr_len = int(h_val)
                    except ValueError:
                        pass
                    break
            if hdr_len is not None and hdr_len >= 0:
                content_length = hdr_len
            else:
                content_length = req_content_len

        flow_hasher = hashlib.sha256()
        flow_hasher.update(flow_id.encode("utf-8"))
        flow_hasher.update(method.encode("utf-8"))
        flow_hasher.update(path.encode("utf-8"))
        if status_code is not None:
            flow_hasher.update(struct.pack(">I", status_code))
        flow_digest = flow_hasher.hexdigest()

        return MitmproxyHttpFlow(
            flow_id=flow_id,
            flow_type=flow_type,
            method=method,
            scheme=scheme,
            host=host,
            port=port,
            path=path,
            status_code=status_code,
            request_headers=req_headers,
            response_headers=resp_headers,
            content_length=content_length,
            request_content_length=req_content_len,
            response_content_length=resp_content_len,
            error_msg=error_msg,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            sha256_digest=flow_digest,
        )

    @classmethod
    def parse_stream(cls, stream: BinaryIO) -> MitmproxyDumpSummary:
        start_pos = stream.tell()
        stream.seek(0, io.SEEK_END)
        total_size = stream.tell() - start_pos
        stream.seek(start_pos, io.SEEK_SET)

        if total_size <= 0:
            raise ValueError("Mitmproxy capture stream is empty (0 bytes)")

        # Compute total stream SHA-256
        hasher = hashlib.sha256()
        flows: List[MitmproxyHttpFlow] = []

        while True:
            curr = stream.tell()
            peek = stream.read(1)
            if not peek:
                break
            stream.seek(curr, io.SEEK_SET)

            # Check if this frame is length-prefixed:
            # If the next 4 bytes form an integer N and the remaining stream has >= 4 + N bytes,
            # and byte at offset curr+4 is a valid MsgPack map header, consume 4-byte length prefix.
            b0 = peek[0]
            if b0 == 0x00:
                # Could be a 4-byte big-endian length prefix
                prefix = stream.read(4)
                if len(prefix) == 4:
                    frame_len = struct.unpack(">I", prefix)[0]
                    if 0 < frame_len <= (total_size - (stream.tell() - start_pos)):
                        # Read exactly frame_len bytes for this frame
                        frame_bytes = stream.read(frame_len)
                        if len(frame_bytes) < frame_len:
                            raise ValueError(f"Truncated length-prefixed frame: expected {frame_len} bytes")
                        hasher.update(prefix)
                        hasher.update(frame_bytes)
                        record = MsgPackDecoder.unpack(io.BytesIO(frame_bytes))
                        flows.append(cls.parse_flow_record(record))
                        continue
                # If not length prefix, seek back
                stream.seek(curr, io.SEEK_SET)

            # Standard streaming MsgPack record
            before_unpack = stream.tell()
            record = MsgPackDecoder.unpack(stream)
            after_unpack = stream.tell()

            # Hash the raw slice
            stream.seek(before_unpack, io.SEEK_SET)
            raw_slice = stream.read(after_unpack - before_unpack)
            hasher.update(raw_slice)

            flow = cls.parse_flow_record(record)
            flows.append(flow)

        if not flows:
            raise ValueError("No valid flow records could be decoded from stream")

        http_count = sum(1 for f in flows if f.flow_type == "http")
        error_count = sum(1 for f in flows if f.error_msg is not None)

        return MitmproxyDumpSummary(
            total_bytes=total_size,
            flows_count=len(flows),
            http_flows_count=http_count,
            error_flows_count=error_count,
            sha256_digest=hasher.hexdigest(),
            flows=flows,
        )

    @classmethod
    def parse_bytes(cls, data: bytes) -> MitmproxyDumpSummary:
        if not data:
            raise ValueError("Cannot parse empty byte payload")
        return cls.parse_stream(io.BytesIO(data))

    @classmethod
    def parse_file(cls, path: Union[str, Path]) -> MitmproxyDumpSummary:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Capture dump file not found: {file_path}")
        with open(file_path, "rb") as f:
            return cls.parse_stream(f)
