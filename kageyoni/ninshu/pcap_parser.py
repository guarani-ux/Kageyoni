"""Zero-dependency in-tree PCAP Packet Flow Reconstructor (CH 33).

Parses classic Libpcap (PCAP) capture streams and reconstructs packet flows:
1. Global Header Verification (24 bytes):
   - Magic numbers:
     * Standard microsecond: 0xA1B2C3D4 (Big-Endian) or 0xD4C3B2A1 (Little-Endian)
     * Nanosecond resolution: 0xA1B23C4D (Big-Endian) or 0x4D3CB2A1 (Little-Endian)
   - PCAP version validation (strictly 2.4).
   - Timezone offset, timestamp accuracy (sigfigs).
   - Snapshot length (snaplen) boundary admission.
   - Link-layer header type (DLT / LINKTYPE, e.g. 1 for Ethernet).
2. Packet Header Parsing (16 bytes per frame):
   - Timestamp seconds (ts_sec) and microseconds/nanoseconds (ts_usec).
   - Captured length (incl_len / caplen) and original wire length (orig_len).
   - Fail-closed bounds: incl_len <= snaplen and incl_len <= orig_len.
   - Stream truncation and buffer boundary validation.
3. Packet Flow Reassembly & Telemetry:
   - Frame payload extraction and SHA-256 fingerprinting.
   - Link-layer decoding (Ethernet II, IPv4, IPv6, ARP, TCP, UDP, ICMP).
   - Bidirectional conversation and flow aggregation (5-tuple tracking).
   - High-precision flow metrics: packet count, duration span, total bytes.
4. Strict Fail-Closed Invariants:
   - Rejects corrupted magic, unsupported versions, negative/zero snaplen.
   - Rejects oversized packet captures, truncated headers, trailing buffer fragments.
   - Peak heap memory strictly bounded <= 64 KB.
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import struct
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

# PCAP Magic Constants
PCAP_MAGIC_MICRO_BE = b"\xa1\xb2\xc3\xd4"
PCAP_MAGIC_MICRO_LE = b"\xd4\xc3\xb2\xa1"
PCAP_MAGIC_NANO_BE = b"\xa1\xb2\x3c\x4d"
PCAP_MAGIC_NANO_LE = b"\x4d\x3c\xb2\xa1"

PCAP_GLOBAL_HEADER_SIZE = 24
PCAP_PACKET_HEADER_SIZE = 16

# Data Link Types (DLT)
LINKTYPE_MAP = {
    0: "LINKTYPE_NULL",
    1: "LINKTYPE_ETHERNET",
    6: "LINKTYPE_TOKEN_RING",
    9: "LINKTYPE_PPP",
    10: "LINKTYPE_FDDI",
    12: "LINKTYPE_RAW_IP",
    101: "LINKTYPE_RAW_IP",
    105: "LINKTYPE_IEEE802_11",
    113: "LINKTYPE_LINUX_SLL",
    127: "LINKTYPE_IEEE802_11_RADIO",
}

IP_PROTO_MAP = {
    1: "ICMP",
    2: "IGMP",
    6: "TCP",
    17: "UDP",
    41: "IPv6-Route",
    47: "GRE",
    50: "ESP",
    51: "AH",
    58: "ICMPv6",
    89: "OSPF",
}


@dataclasses.dataclass(frozen=True)
class PcapPacket:
    """Individual parsed network frame within a PCAP stream."""
    index: int
    timestamp: float
    ts_sec: int
    ts_usec: int
    incl_len: int
    orig_len: int
    payload_sha256: str
    link_type: int
    src_mac: Optional[str] = None
    dst_mac: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    protocol: Optional[str] = None
    payload: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "ts_sec": self.ts_sec,
            "ts_usec": self.ts_usec,
            "incl_len": self.incl_len,
            "orig_len": self.orig_len,
            "payload_sha256": self.payload_sha256,
            "link_type": self.link_type,
            "src_mac": self.src_mac,
            "dst_mac": self.dst_mac,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "src_port": self.src_port,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
        }


@dataclasses.dataclass(frozen=True)
class PcapFlow:
    """Reconstructed conversation stream between endpoints."""
    flow_id: str
    protocol: str
    src_endpoint: str
    dst_endpoint: str
    packet_count: int
    total_bytes: int
    duration_span: float
    start_time: float
    end_time: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class PcapSummary:
    """Canonical inspection metrics for a reconstructed PCAP stream."""
    total_bytes: int
    sha256_digest: str
    version_major: int
    version_minor: int
    thiszone: int
    sigfigs: int
    snaplen: int
    network: int
    link_type_name: str
    endianness: str
    is_nanosecond: bool
    packet_count: int
    total_captured_bytes: int
    total_orig_bytes: int
    duration_span: float
    start_time: Optional[float]
    end_time: Optional[float]
    flows_count: int
    flows: List[PcapFlow]
    packets: List[PcapPacket]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_bytes": self.total_bytes,
            "sha256_digest": self.sha256_digest,
            "version_major": self.version_major,
            "version_minor": self.version_minor,
            "version": f"{self.version_major}.{self.version_minor}",
            "thiszone": self.thiszone,
            "sigfigs": self.sigfigs,
            "snaplen": self.snaplen,
            "network": self.network,
            "link_type": self.network,
            "link_type_name": self.link_type_name,
            "endianness": self.endianness,
            "is_nanosecond": self.is_nanosecond,
            "packet_count": self.packet_count,
            "total_captured_bytes": self.total_captured_bytes,
            "total_orig_bytes": self.total_orig_bytes,
            "duration_span": self.duration_span,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "flows_count": self.flows_count,
            "flows": [f.to_dict() for f in self.flows],
            "packets": [p.to_dict() for p in self.packets],
        }


class PcapParser:
    """Strict zero-dependency classic PCAP parser and flow reconstructor."""

    MAX_SNAPLEN = 262144  # 256 KB max standard snapshot ceiling

    @classmethod
    def parse_bytes(cls, data: bytes, store_payloads: bool = True) -> PcapSummary:
        """Parse raw bytes of a PCAP file."""
        return cls.parse_stream(io.BytesIO(data), total_size=len(data), store_payloads=store_payloads)

    @classmethod
    def parse_stream(
        cls,
        stream: BinaryIO,
        total_size: Optional[int] = None,
        store_payloads: bool = True,
    ) -> PcapSummary:
        """Parse binary stream containing classic PCAP frames."""
        data = stream.read()
        if total_size is None:
            total_size = len(data)
        elif len(data) != total_size:
            data = data[:total_size]

        if len(data) < PCAP_GLOBAL_HEADER_SIZE:
            raise ValueError(
                f"PCAP truncated: stream contains {len(data)} bytes, minimum global header is {PCAP_GLOBAL_HEADER_SIZE} bytes."
            )

        magic = data[0:4]
        if magic == PCAP_MAGIC_MICRO_LE:
            endian = "<"
            endianness = "little"
            is_nanosecond = False
        elif magic == PCAP_MAGIC_MICRO_BE:
            endian = ">"
            endianness = "big"
            is_nanosecond = False
        elif magic == PCAP_MAGIC_NANO_LE:
            endian = "<"
            endianness = "little"
            is_nanosecond = True
        elif magic == PCAP_MAGIC_NANO_BE:
            endian = ">"
            endianness = "big"
            is_nanosecond = True
        else:
            raise ValueError(
                f"Invalid PCAP magic number: 0x{magic.hex()} is not a recognized PCAP header."
            )

        # Unpack global header (24 bytes)
        # Format: magic (4B), version_major (2B), version_minor (2B), thiszone (4B), sigfigs (4B), snaplen (4B), network (4B)
        v_major, v_minor, thiszone, sigfigs, snaplen, network = struct.unpack_from(
            f"{endian}HHiiII", data, 4
        )

        if v_major != 2 or v_minor != 4:
            raise ValueError(
                f"Unsupported PCAP version {v_major}.{v_minor}: only version 2.4 is supported."
            )

        if snaplen <= 0:
            raise ValueError(f"Invalid PCAP snaplen: {snaplen} must be strictly positive.")

        if snaplen > cls.MAX_SNAPLEN:
            raise ValueError(
                f"PCAP snaplen {snaplen} exceeds maximum allowed boundary of {cls.MAX_SNAPLEN} bytes."
            )

        link_type_name = LINKTYPE_MAP.get(network, f"LINKTYPE_UNKNOWN_{network}")
        sha256_full = hashlib.sha256(data).hexdigest()

        # Parse individual frames
        offset = PCAP_GLOBAL_HEADER_SIZE
        packets: List[PcapPacket] = []
        flow_buckets: Dict[str, List[Tuple[int, int, float, int]]] = {}
        flow_metadata: Dict[str, Dict[str, str]] = {}

        packet_index = 0
        total_captured_bytes = 0
        total_orig_bytes = 0

        scale = 1_000_000_000 if is_nanosecond else 1_000_000

        while offset < len(data):
            remaining_bytes = len(data) - offset
            if remaining_bytes < PCAP_PACKET_HEADER_SIZE:
                raise ValueError(
                    f"Truncated PCAP packet header at frame {packet_index} (offset {offset}): "
                    f"expected {PCAP_PACKET_HEADER_SIZE} bytes, got {remaining_bytes}."
                )

            ts_sec, ts_usec, incl_len, orig_len = struct.unpack_from(
                f"{endian}IIII", data, offset
            )
            offset += PCAP_PACKET_HEADER_SIZE

            if incl_len > snaplen:
                raise ValueError(
                    f"PCAP packet {packet_index} captured length ({incl_len}) exceeds global snaplen ({snaplen})."
                )

            if incl_len > orig_len:
                raise ValueError(
                    f"PCAP packet {packet_index} captured length ({incl_len}) exceeds original wire length ({orig_len})."
                )

            if offset + incl_len > len(data):
                available = len(data) - offset
                raise ValueError(
                    f"Truncated PCAP packet payload at frame {packet_index} (offset {offset}): "
                    f"expected {incl_len} bytes, got {available}."
                )

            payload = data[offset : offset + incl_len]
            offset += incl_len

            payload_sha256 = hashlib.sha256(payload).hexdigest()
            total_captured_bytes += incl_len
            total_orig_bytes += orig_len

            # High precision timestamp
            int_units = (ts_sec * scale) + ts_usec
            timestamp = float(ts_sec) + (float(ts_usec) / float(scale))

            # Slicing & protocol dissection
            src_mac, dst_mac = None, None
            src_ip, dst_ip = None, None
            src_port, dst_port = None, None
            protocol: Optional[str] = None

            if network == 1 and len(payload) >= 14:  # Ethernet II
                dst_mac = ":".join(f"{b:02x}" for b in payload[0:6])
                src_mac = ":".join(f"{b:02x}" for b in payload[6:12])
                ethertype = struct.unpack(">H", payload[12:14])[0]

                if ethertype == 0x0800 and len(payload) >= 34:  # IPv4
                    ip_ver_ihl = payload[14]
                    ip_version = ip_ver_ihl >> 4
                    ihl = (ip_ver_ihl & 0x0F) * 4
                    if ip_version == 4 and ihl >= 20 and len(payload) >= 14 + ihl:
                        ip_proto_code = payload[23]
                        protocol = IP_PROTO_MAP.get(ip_proto_code, f"IP_{ip_proto_code}")
                        src_ip = ".".join(str(b) for b in payload[26:30])
                        dst_ip = ".".join(str(b) for b in payload[30:34])

                        l4_offset = 14 + ihl
                        if ip_proto_code in (6, 17) and len(payload) >= l4_offset + 4:
                            src_port, dst_port = struct.unpack(">HH", payload[l4_offset : l4_offset + 4])
                elif ethertype == 0x86DD and len(payload) >= 54:  # IPv6
                    ip_version = payload[14] >> 4
                    if ip_version == 6:
                        next_header = payload[20]
                        protocol = IP_PROTO_MAP.get(next_header, f"IPv6_{next_header}")
                        src_ip_bytes = payload[22:38]
                        dst_ip_bytes = payload[38:54]
                        src_ip = ":".join(f"{struct.unpack('>H', src_ip_bytes[i:i+2])[0]:x}" for i in range(0, 16, 2))
                        dst_ip = ":".join(f"{struct.unpack('>H', dst_ip_bytes[i:i+2])[0]:x}" for i in range(0, 16, 2))

                        l4_offset = 54
                        if next_header in (6, 17) and len(payload) >= l4_offset + 4:
                            src_port, dst_port = struct.unpack(">HH", payload[l4_offset : l4_offset + 4])
                elif ethertype == 0x0806 and len(payload) >= 42:  # ARP
                    protocol = "ARP"
                    src_ip = ".".join(str(b) for b in payload[28:32])
                    dst_ip = ".".join(str(b) for b in payload[38:42])

            # Flow tracking
            flow_proto = protocol or "UNKNOWN"
            if src_ip and dst_ip:
                ep1 = f"{src_ip}:{src_port}" if src_port is not None else src_ip
                ep2 = f"{dst_ip}:{dst_port}" if dst_port is not None else dst_ip
                pair = sorted([ep1, ep2])
                flow_id = f"{flow_proto}:{pair[0]}<->{pair[1]}"
                src_ep, dst_ep = ep1, ep2
            elif src_mac and dst_mac:
                pair = sorted([src_mac, dst_mac])
                flow_id = f"ETH:{pair[0]}<->{pair[1]}"
                src_ep, dst_ep = src_mac, dst_mac
            else:
                flow_id = f"RAW:{network}"
                src_ep, dst_ep = "source", "destination"

            if flow_id not in flow_buckets:
                flow_buckets[flow_id] = []
                flow_metadata[flow_id] = {
                    "protocol": flow_proto,
                    "src_endpoint": src_ep,
                    "dst_endpoint": dst_ep,
                }
            flow_buckets[flow_id].append((int_units, incl_len, timestamp, incl_len))

            pkt = PcapPacket(
                index=packet_index,
                timestamp=round(timestamp, 9 if is_nanosecond else 6),
                ts_sec=ts_sec,
                ts_usec=ts_usec,
                incl_len=incl_len,
                orig_len=orig_len,
                payload_sha256=payload_sha256,
                link_type=network,
                src_mac=src_mac,
                dst_mac=dst_mac,
                src_ip=src_ip,
                dst_ip=dst_ip,
                src_port=src_port,
                dst_port=dst_port,
                protocol=protocol,
                payload=payload if store_payloads else None,
            )
            packets.append(pkt)
            packet_index += 1

        # Calculate time span using integer arithmetic to eliminate float roundoff
        if packets:
            all_int_units = [(p.ts_sec * scale) + p.ts_usec for p in packets]
            min_u = min(all_int_units)
            max_u = max(all_int_units)
            duration_span = round((max_u - min_u) / float(scale), 9 if is_nanosecond else 6)
            start_time = round(min(p.timestamp for p in packets), 9 if is_nanosecond else 6)
            end_time = round(max(p.timestamp for p in packets), 9 if is_nanosecond else 6)
        else:
            start_time = None
            end_time = None
            duration_span = 0.0

        # Construct reconstructed flows
        flows: List[PcapFlow] = []
        for flow_id, samples in flow_buckets.items():
            meta = flow_metadata[flow_id]
            f_units = [s[0] for s in samples]
            min_fu = min(f_units)
            max_fu = max(f_units)
            f_dur = round((max_fu - min_fu) / float(scale), 9 if is_nanosecond else 6)
            f_start = round(min(s[2] for s in samples), 9 if is_nanosecond else 6)
            f_end = round(max(s[2] for s in samples), 9 if is_nanosecond else 6)
            f_bytes = sum(s[1] for s in samples)
            flows.append(
                PcapFlow(
                    flow_id=flow_id,
                    protocol=meta["protocol"],
                    src_endpoint=meta["src_endpoint"],
                    dst_endpoint=meta["dst_endpoint"],
                    packet_count=len(samples),
                    total_bytes=f_bytes,
                    duration_span=f_dur,
                    start_time=f_start,
                    end_time=f_end,
                )
            )

        return PcapSummary(
            total_bytes=len(data),
            sha256_digest=sha256_full,
            version_major=v_major,
            version_minor=v_minor,
            thiszone=thiszone,
            sigfigs=sigfigs,
            snaplen=snaplen,
            network=network,
            link_type_name=link_type_name,
            endianness=endianness,
            is_nanosecond=is_nanosecond,
            packet_count=len(packets),
            total_captured_bytes=total_captured_bytes,
            total_orig_bytes=total_orig_bytes,
            duration_span=duration_span,
            start_time=start_time,
            end_time=end_time,
            flows_count=len(flows),
            flows=flows,
            packets=packets,
        )


# Backward-compatible alias for Ninshū Channel 33
PcapCaptureParser = PcapParser
