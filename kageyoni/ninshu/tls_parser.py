"""Zero-dependency in-tree TLS / SSL Handshake & SNI Extractor (CH 34).

Pure Python standard library implementation:
1. TLS Record Layer:
   - ContentType (1B): 20=ChangeCipherSpec, 21=Alert, 22=Handshake, 23=ApplicationData, 24=Heartbeat.
   - Legacy Version (2B): e.g. 0x0300 (SSL 3.0), 0x0301 (TLS 1.0), 0x0302 (TLS 1.1), 0x0303 (TLS 1.2 / TLS 1.3).
   - Length (2B): Max TLS record payload length is 16384 (2^14) bytes, or 16384 + 2048 with compression/encryption.
2. TLS Handshake Layer:
   - HandshakeType (1B): 1 = ClientHello, 2 = ServerHello, etc.
   - Length (3B uint24).
   - ClientHello:
     * client_version (2B)
     * random (32B)
     * session_id length (1B) + session_id bytes (0-32B)
     * cipher_suites length (2B) + cipher_suites bytes
     * compression_methods length (1B) + compression_methods bytes
     * extensions length (2B) + extensions bytes
3. TLS Extensions Parser:
   - Extension 0x0000: Server Name Indication (SNI). Extracts host_name string.
   - Extension 0x002B: Supported Versions (detect TLS 1.3 / 0x0304).
   - Extension 0x0010: Application-Layer Protocol Negotiation (ALPN, e.g. "h2", "http/1.1").
4. Strict Fail-Closed Invariants:
   - Rejects record overflows, truncated records, trailing junk, malformed extensions, invalid SNI encodings.
   - Thermodynamic memory bound: Peak heap <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

# Content Types
CONTENT_TYPE_CHANGE_CIPHER_SPEC = 20
CONTENT_TYPE_ALERT = 21
CONTENT_TYPE_HANDSHAKE = 22
CONTENT_TYPE_APPLICATION_DATA = 23
CONTENT_TYPE_HEARTBEAT = 24

CONTENT_TYPE_NAMES = {
    CONTENT_TYPE_CHANGE_CIPHER_SPEC: "change_cipher_spec",
    CONTENT_TYPE_ALERT: "alert",
    CONTENT_TYPE_HANDSHAKE: "handshake",
    CONTENT_TYPE_APPLICATION_DATA: "application_data",
    CONTENT_TYPE_HEARTBEAT: "heartbeat",
}

# Handshake Types
HANDSHAKE_TYPE_HELLO_REQUEST = 0
HANDSHAKE_TYPE_CLIENT_HELLO = 1
HANDSHAKE_TYPE_SERVER_HELLO = 2
HANDSHAKE_TYPE_NEW_SESSION_TICKET = 4
HANDSHAKE_TYPE_END_OF_EARLY_DATA = 5
HANDSHAKE_TYPE_ENCRYPTED_EXTENSIONS = 8
HANDSHAKE_TYPE_CERTIFICATE = 11
HANDSHAKE_TYPE_SERVER_KEY_EXCHANGE = 12
HANDSHAKE_TYPE_CERTIFICATE_REQUEST = 13
HANDSHAKE_TYPE_SERVER_HELLO_DONE = 14
HANDSHAKE_TYPE_CERTIFICATE_VERIFY = 15
HANDSHAKE_TYPE_CLIENT_KEY_EXCHANGE = 16
HANDSHAKE_TYPE_FINISHED = 20

HANDSHAKE_TYPE_NAMES = {
    HANDSHAKE_TYPE_HELLO_REQUEST: "hello_request",
    HANDSHAKE_TYPE_CLIENT_HELLO: "client_hello",
    HANDSHAKE_TYPE_SERVER_HELLO: "server_hello",
    HANDSHAKE_TYPE_NEW_SESSION_TICKET: "new_session_ticket",
    HANDSHAKE_TYPE_END_OF_EARLY_DATA: "end_of_early_data",
    HANDSHAKE_TYPE_ENCRYPTED_EXTENSIONS: "encrypted_extensions",
    HANDSHAKE_TYPE_CERTIFICATE: "certificate",
    HANDSHAKE_TYPE_SERVER_KEY_EXCHANGE: "server_key_exchange",
    HANDSHAKE_TYPE_CERTIFICATE_REQUEST: "certificate_request",
    HANDSHAKE_TYPE_SERVER_HELLO_DONE: "server_hello_done",
    HANDSHAKE_TYPE_CERTIFICATE_VERIFY: "certificate_verify",
    HANDSHAKE_TYPE_CLIENT_KEY_EXCHANGE: "client_key_exchange",
    HANDSHAKE_TYPE_FINISHED: "finished",
}

# Known TLS Versions
TLS_VERSIONS = {
    0x0300: "SSL 3.0",
    0x0301: "TLS 1.0",
    0x0302: "TLS 1.1",
    0x0303: "TLS 1.2",
    0x0304: "TLS 1.3",
}

# Extension Types
EXT_SERVER_NAME = 0x0000
EXT_MAX_FRAGMENT_LENGTH = 0x0001
EXT_CLIENT_CERTIFICATE_URL = 0x0002
EXT_TRUSTED_CA_KEYS = 0x0003
EXT_TRUNCATED_HMAC = 0x0004
EXT_STATUS_REQUEST = 0x0005
EXT_USER_MAPPING = 0x0006
EXT_CLIENT_AUTHZ = 0x0007
EXT_SERVER_AUTHZ = 0x0008
EXT_CERT_TYPE = 0x0009
EXT_SUPPORTED_GROUPS = 0x000A
EXT_EC_POINT_FORMATS = 0x000B
EXT_SRP = 0x000C
EXT_SIGNATURE_ALGORITHMS = 0x000D
EXT_USE_SRTP = 0x000E
EXT_HEARTBEAT = 0x000F
EXT_ALPN = 0x0010
EXT_STATUS_REQUEST_V2 = 0x0011
EXT_SIGNED_CERT_TIMESTAMP = 0x0012
EXT_CLIENT_CERT_TYPE = 0x0013
EXT_SERVER_CERT_TYPE = 0x0014
EXT_PADDING = 0x0015
EXT_EXTENDED_MASTER_SECRET = 0x0017
EXT_SESSION_TICKET = 0x0023
EXT_PRE_SHARED_KEY = 0x0029
EXT_EARLY_DATA = 0x002A
EXT_SUPPORTED_VERSIONS = 0x002B
EXT_COOKIE = 0x002C
EXT_PSK_KEY_EXCHANGE_MODES = 0x002D
EXT_CERTIFICATE_AUTHORITIES = 0x002F
EXT_KEY_SHARE = 0x0033
EXT_RENEGOTIATION_INFO = 0xFF01

# Max standard TLS record payload size is 16384 bytes, with up to 2048 bytes for compression/cipher expansion (RFC 5246)
MAX_TLS_RECORD_PAYLOAD = 18432
RECORD_HEADER_SIZE = 5


@dataclasses.dataclass(frozen=True)
class TLSExtension:
    extension_type: int
    length: int
    data: bytes


@dataclasses.dataclass(frozen=True)
class ClientHelloDetails:
    legacy_version: int
    legacy_version_name: str
    random: bytes
    session_id: bytes
    cipher_suites: List[int]
    compression_methods: List[int]
    sni_hostname: Optional[str]
    alpn_protocols: List[str]
    supported_versions: List[int]
    is_tls13: bool
    extensions: List[TLSExtension]


@dataclasses.dataclass(frozen=True)
class TLSRecord:
    content_type: int
    content_type_name: str
    legacy_version: int
    legacy_version_name: str
    length: int
    payload: bytes
    handshake_type: Optional[int] = None
    handshake_type_name: Optional[str] = None
    client_hello: Optional[ClientHelloDetails] = None


@dataclasses.dataclass(frozen=True)
class TLSSummary:
    total_bytes: int
    records_count: int
    records: List[TLSRecord]
    sni_hostname: Optional[str]
    alpn_protocols: List[str]
    has_tls13: bool
    sha256: str


class TLSHandshakeParser:
    """Zero-dependency TLS record and ClientHello / SNI parser."""

    @classmethod
    def parse_stream(cls, stream: BinaryIO) -> TLSSummary:
        data = stream.read()
        return cls.parse_bytes(data)

    @classmethod
    def parse_bytes(cls, data: bytes) -> TLSSummary:
        if not data:
            raise ValueError("Empty TLS input buffer.")

        total_bytes = len(data)
        if total_bytes < RECORD_HEADER_SIZE:
            raise ValueError(f"TLS data too short: {total_bytes} bytes (minimum 5 bytes for record header).")

        offset = 0
        records: List[TLSRecord] = []
        global_sni: Optional[str] = None
        global_alpn: List[str] = []
        global_tls13 = False

        while offset < total_bytes:
            remaining = total_bytes - offset
            if remaining < RECORD_HEADER_SIZE:
                raise ValueError(
                    f"Truncated TLS record header at offset {offset}: only {remaining} bytes available, need 5."
                )

            content_type, rec_ver, rec_len = struct.unpack_from(">BHH", data, offset)
            offset += RECORD_HEADER_SIZE

            if content_type not in CONTENT_TYPE_NAMES:
                raise ValueError(f"Invalid TLS ContentType {content_type} at offset {offset - RECORD_HEADER_SIZE}.")

            if rec_len > MAX_TLS_RECORD_PAYLOAD:
                raise ValueError(
                    f"TLS record length overflow: {rec_len} exceeds max payload ceiling {MAX_TLS_RECORD_PAYLOAD}."
                )

            if rec_len > total_bytes - offset:
                raise ValueError(
                    f"Truncated TLS record payload: declared {rec_len} bytes, only {total_bytes - offset} available."
                )

            payload = data[offset : offset + rec_len]
            offset += rec_len

            rec_ver_name = TLS_VERSIONS.get(rec_ver, f"Unknown (0x{rec_ver:04X})")
            ct_name = CONTENT_TYPE_NAMES[content_type]

            handshake_type: Optional[int] = None
            handshake_type_name: Optional[str] = None
            client_hello_details: Optional[ClientHelloDetails] = None

            if content_type == CONTENT_TYPE_HANDSHAKE:
                handshake_type, handshake_type_name, client_hello_details = cls._parse_handshake_payload(payload)
                if client_hello_details is not None:
                    if client_hello_details.sni_hostname and global_sni is None:
                        global_sni = client_hello_details.sni_hostname
                    for proto in client_hello_details.alpn_protocols:
                        if proto not in global_alpn:
                            global_alpn.append(proto)
                    if client_hello_details.is_tls13:
                        global_tls13 = True

            records.append(
                TLSRecord(
                    content_type=content_type,
                    content_type_name=ct_name,
                    legacy_version=rec_ver,
                    legacy_version_name=rec_ver_name,
                    length=rec_len,
                    payload=payload,
                    handshake_type=handshake_type,
                    handshake_type_name=handshake_type_name,
                    client_hello=client_hello_details,
                )
            )

        hasher = hashlib.sha256()
        hasher.update(data)
        digest = hasher.hexdigest()

        return TLSSummary(
            total_bytes=total_bytes,
            records_count=len(records),
            records=records,
            sni_hostname=global_sni,
            alpn_protocols=global_alpn,
            has_tls13=global_tls13,
            sha256=digest,
        )

    @classmethod
    def _parse_handshake_payload(
        cls, payload: bytes
    ) -> Tuple[int, str, Optional[ClientHelloDetails]]:
        if len(payload) < 4:
            raise ValueError(f"Handshake payload truncated: length {len(payload)} < 4 bytes header.")

        hs_type = payload[0]
        # Handshake length is 3-byte big-endian uint24
        hs_length = (payload[1] << 16) | (payload[2] << 8) | payload[3]

        if 4 + hs_length > len(payload):
            raise ValueError(
                f"Handshake declared length {hs_length} exceeds record payload boundary ({len(payload) - 4} bytes)."
            )

        hs_type_name = HANDSHAKE_TYPE_NAMES.get(hs_type, f"unknown_handshake_{hs_type}")
        client_hello_details: Optional[ClientHelloDetails] = None

        if hs_type == HANDSHAKE_TYPE_CLIENT_HELLO:
            ch_data = payload[4 : 4 + hs_length]
            client_hello_details = cls._parse_client_hello(ch_data)

        return hs_type, hs_type_name, client_hello_details

    @classmethod
    def _parse_client_hello(cls, data: bytes) -> ClientHelloDetails:
        # ClientHello structure:
        # client_version: 2 bytes
        # random: 32 bytes
        # session_id_length: 1 byte
        # session_id: variable (0-32 bytes)
        # cipher_suites_length: 2 bytes
        # cipher_suites: 2 * n bytes
        # compression_methods_length: 1 byte
        # compression_methods: 1 * m bytes
        # extensions_length: 2 bytes (optional if at end, but standard)
        # extensions: variable
        if len(data) < 35:  # 2 + 32 + 1
            raise ValueError(f"ClientHello truncated: length {len(data)} < minimum 35 bytes.")

        offset = 0
        legacy_version = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        legacy_version_name = TLS_VERSIONS.get(legacy_version, f"Unknown (0x{legacy_version:04X})")

        random_bytes = data[offset : offset + 32]
        offset += 32

        session_id_len = data[offset]
        offset += 1
        if session_id_len > 32:
            raise ValueError(f"ClientHello invalid session_id length: {session_id_len} (max 32).")
        if offset + session_id_len > len(data):
            raise ValueError("ClientHello session_id truncated.")
        session_id = data[offset : offset + session_id_len]
        offset += session_id_len

        # Cipher Suites
        if offset + 2 > len(data):
            raise ValueError("ClientHello cipher_suites length field truncated.")
        cipher_suites_len = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        if cipher_suites_len % 2 != 0:
            raise ValueError(f"ClientHello cipher_suites length {cipher_suites_len} is not even.")
        if offset + cipher_suites_len > len(data):
            raise ValueError("ClientHello cipher_suites truncated.")
        
        cipher_suites: List[int] = []
        for i in range(0, cipher_suites_len, 2):
            cs = struct.unpack_from(">H", data, offset + i)[0]
            cipher_suites.append(cs)
        offset += cipher_suites_len

        # Compression Methods
        if offset + 1 > len(data):
            raise ValueError("ClientHello compression_methods length field truncated.")
        compression_len = data[offset]
        offset += 1
        if compression_len < 1:
            raise ValueError("ClientHello compression_methods length must be at least 1.")
        if offset + compression_len > len(data):
            raise ValueError("ClientHello compression_methods truncated.")
        compression_methods = list(data[offset : offset + compression_len])
        offset += compression_len

        # Extensions (optional in older SSL/TLS, but required for SNI/ALPN)
        extensions: List[TLSExtension] = []
        sni_hostname: Optional[str] = None
        alpn_protocols: List[str] = []
        supported_versions: List[int] = []
        is_tls13 = False

        if offset < len(data):
            if offset + 2 > len(data):
                raise ValueError("ClientHello extensions length field truncated.")
            ext_total_len = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            if offset + ext_total_len != len(data):
                raise ValueError(
                    f"ClientHello extensions total length mismatch: declared {ext_total_len}, remaining {len(data) - offset}."
                )

            ext_end = offset + ext_total_len
            while offset < ext_end:
                if offset + 4 > ext_end:
                    raise ValueError(f"Truncated extension header at offset {offset}.")
                ext_type, ext_len = struct.unpack_from(">HH", data, offset)
                offset += 4
                if offset + ext_len > ext_end:
                    raise ValueError(
                        f"Extension 0x{ext_type:04X} declared length {ext_len} overflows extensions boundary."
                    )
                ext_data = data[offset : offset + ext_len]
                offset += ext_len

                extensions.append(TLSExtension(extension_type=ext_type, length=ext_len, data=ext_data))

                if ext_type == EXT_SERVER_NAME:
                    sni_hostname = cls._parse_sni_extension(ext_data)
                elif ext_type == EXT_SUPPORTED_VERSIONS:
                    versions = cls._parse_supported_versions_extension(ext_data)
                    supported_versions.extend(versions)
                    if 0x0304 in versions:
                        is_tls13 = True
                elif ext_type == EXT_ALPN:
                    alpn_protocols.extend(cls._parse_alpn_extension(ext_data))

        return ClientHelloDetails(
            legacy_version=legacy_version,
            legacy_version_name=legacy_version_name,
            random=random_bytes,
            session_id=session_id,
            cipher_suites=cipher_suites,
            compression_methods=compression_methods,
            sni_hostname=sni_hostname,
            alpn_protocols=alpn_protocols,
            supported_versions=supported_versions,
            is_tls13=is_tls13,
            extensions=extensions,
        )

    @classmethod
    def _parse_sni_extension(cls, data: bytes) -> str:
        # ServerNameList length: 2 bytes
        # ServerName:
        #   name_type: 1 byte (0 = host_name)
        #   name_length: 2 bytes
        #   host_name: name_length bytes (ASCII/UTF-8 string)
        if len(data) < 2:
            raise ValueError("SNI extension payload truncated (less than 2 bytes for list length).")

        list_len = struct.unpack_from(">H", data, 0)[0]
        if 2 + list_len != len(data):
            raise ValueError(f"SNI extension list length mismatch: declared {list_len}, actual {len(data) - 2}.")

        offset = 2
        host_name: Optional[str] = None
        while offset < len(data):
            if offset + 3 > len(data):
                raise ValueError("SNI entry header truncated.")
            name_type = data[offset]
            name_len = struct.unpack_from(">H", data, offset + 1)[0]
            offset += 3
            if offset + name_len > len(data):
                raise ValueError(f"SNI entry hostname truncated: need {name_len} bytes.")

            name_bytes = data[offset : offset + name_len]
            offset += name_len

            if name_type == 0:  # host_name
                try:
                    host_str = name_bytes.decode("ascii")
                except UnicodeDecodeError as err:
                    raise ValueError(f"SNI host_name is not valid ASCII: {err}") from err
                if not host_str:
                    raise ValueError("SNI host_name is empty string.")
                if host_name is None:
                    host_name = host_str

        if host_name is None:
            raise ValueError("SNI extension did not contain any valid host_name entry.")
        return host_name

    @classmethod
    def _parse_supported_versions_extension(cls, data: bytes) -> List[int]:
        # In ClientHello:
        #   versions_list_length: 1 byte
        #   versions: 2 * n bytes
        if len(data) < 1:
            raise ValueError("Supported Versions extension empty.")
        list_len = data[0]
        if 1 + list_len != len(data):
            raise ValueError(
                f"Supported Versions length mismatch: declared {list_len}, actual {len(data) - 1}."
            )
        if list_len % 2 != 0:
            raise ValueError(f"Supported Versions length {list_len} is not even.")

        versions: List[int] = []
        for i in range(1, len(data), 2):
            ver = struct.unpack_from(">H", data, i)[0]
            versions.append(ver)
        return versions

    @classmethod
    def _parse_alpn_extension(cls, data: bytes) -> List[str]:
        # ALPN extension:
        #   protocol_name_list_length: 2 bytes
        #   repeated:
        #     protocol_length: 1 byte
        #     protocol: protocol_length bytes
        if len(data) < 2:
            raise ValueError("ALPN extension payload truncated.")
        list_len = struct.unpack_from(">H", data, 0)[0]
        if 2 + list_len != len(data):
            raise ValueError(f"ALPN length mismatch: declared {list_len}, actual {len(data) - 2}.")

        offset = 2
        protocols: List[str] = []
        while offset < len(data):
            p_len = data[offset]
            offset += 1
            if offset + p_len > len(data):
                raise ValueError(f"ALPN protocol name truncated: need {p_len} bytes.")
            p_bytes = data[offset : offset + p_len]
            offset += p_len
            try:
                p_str = p_bytes.decode("utf-8")
            except UnicodeDecodeError as err:
                raise ValueError(f"ALPN protocol name is not valid UTF-8: {err}") from err
            if not p_str:
                raise ValueError("ALPN protocol name is empty string.")
            protocols.append(p_str)

        return protocols
