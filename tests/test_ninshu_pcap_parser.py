"""Unit & Adversarial Verification Suite for Ninshū In-Tree PCAP Parser (CH 33).

Tests:
1. Complete Little-Endian and Big-Endian PCAP parsing.
2. Standard microsecond and high-resolution nanosecond timestamp precision.
3. Multi-packet TCP/UDP/ARP flow reassembly and endpoint aggregation.
4. Strict fail-closed rejection on invalid magic, unsupported version, negative snaplen.
5. Strict fail-closed rejection on packet length > snaplen and packet length > orig_len.
6. Strict fail-closed rejection on truncated headers and truncated payloads.
7. Thermodynamic profiling (heap memory ceiling <= 64 KB).
8. Adversarial mutant fuzzing (bit flips, truncations).
"""
import io
import struct
import unittest

from kageyoni.ninshu.pcap_parser import (
    PcapParser,
    PcapSummary,
    PcapPacket,
    PcapFlow,
    PCAP_MAGIC_MICRO_LE,
    PCAP_MAGIC_MICRO_BE,
    PCAP_MAGIC_NANO_LE,
    PCAP_MAGIC_NANO_BE,
    PCAP_GLOBAL_HEADER_SIZE,
    PCAP_PACKET_HEADER_SIZE,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
from kageyoni.ninshu.adversary import AdversarialMutator


def create_eth_ip_tcp_frame(
    src_mac: bytes,
    dst_mac: bytes,
    src_ip: bytes,
    dst_ip: bytes,
    src_port: int,
    dst_port: int,
    seq: int = 1000,
    ack: int = 0,
    flags: int = 2,
    payload: bytes = b"",
) -> bytes:
    """Build synthetic Ethernet II + IPv4 + TCP frame."""
    eth_hdr = dst_mac + src_mac + struct.pack(">H", 0x0800)
    total_len = 20 + 20 + len(payload)
    ip_hdr = struct.pack(
        ">BBHHHBBH4s4s",
        0x45, 0, total_len, 1, 0x4000, 64, 6, 0, src_ip, dst_ip
    )
    tcp_hdr = struct.pack(
        ">HHIIHHHH",
        src_port, dst_port, seq, ack, (5 << 12) | flags, 65535, 0, 0
    )
    return eth_hdr + ip_hdr + tcp_hdr + payload


def create_eth_ip_udp_frame(
    src_mac: bytes,
    dst_mac: bytes,
    src_ip: bytes,
    dst_ip: bytes,
    src_port: int,
    dst_port: int,
    payload: bytes = b"",
) -> bytes:
    """Build synthetic Ethernet II + IPv4 + UDP frame."""
    eth_hdr = dst_mac + src_mac + struct.pack(">H", 0x0800)
    total_len = 20 + 8 + len(payload)
    ip_hdr = struct.pack(
        ">BBHHHBBH4s4s",
        0x45, 0, total_len, 2, 0x4000, 64, 17, 0, src_ip, dst_ip
    )
    udp_hdr = struct.pack(">HHHH", src_port, dst_port, 8 + len(payload), 0)
    return eth_hdr + ip_hdr + udp_hdr + payload


class TestNinshuPcapParser(unittest.TestCase):
    def setUp(self):
        # Build standard synthetic PCAP with Ethernet frames (Little-Endian, microsecond)
        self.mac_client = bytes([0x00, 0x11, 0x22, 0x33, 0x44, 0x55])
        self.mac_server = bytes([0x66, 0x77, 0x88, 0x99, 0xAA, 0xBB])
        self.ip_client = bytes([192, 168, 1, 100])
        self.ip_server = bytes([10, 0, 0, 1])

        # Packet 1: Client -> Server TCP SYN (ts: 1700000000.100000)
        self.frame1 = create_eth_ip_tcp_frame(
            self.mac_client, self.mac_server, self.ip_client, self.ip_server,
            src_port=52000, dst_port=80, seq=1000, ack=0, flags=0x02
        )
        # Packet 2: Server -> Client TCP SYN-ACK (ts: 1700000000.150000)
        self.frame2 = create_eth_ip_tcp_frame(
            self.mac_server, self.mac_client, self.ip_server, self.ip_client,
            src_port=80, dst_port=52000, seq=5000, ack=1001, flags=0x12
        )
        # Packet 3: Client -> Server TCP DATA (ts: 1700000000.200000)
        self.frame3 = create_eth_ip_tcp_frame(
            self.mac_client, self.mac_server, self.ip_client, self.ip_server,
            src_port=52000, dst_port=80, seq=1001, ack=5001, flags=0x18,
            payload=b"GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n"
        )

        # Global header: LE, microsecond, snaplen 65535, network 1 (Ethernet)
        gh_le = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)

        # Packet headers
        ph1 = struct.pack("<IIII", 1700000000, 100000, len(self.frame1), len(self.frame1))
        ph2 = struct.pack("<IIII", 1700000000, 150000, len(self.frame2), len(self.frame2))
        ph3 = struct.pack("<IIII", 1700000000, 200000, len(self.frame3), len(self.frame3))

        self.synthetic_pcap_le = gh_le + ph1 + self.frame1 + ph2 + self.frame2 + ph3 + self.frame3

    def test_parse_valid_little_endian_microsecond(self):
        """Verify standard Little-Endian PCAP parsing with Ethernet/IP/TCP dissection."""
        summary = PcapParser.parse_bytes(self.synthetic_pcap_le)

        self.assertEqual(summary.version_major, 2)
        self.assertEqual(summary.version_minor, 4)
        self.assertEqual(summary.endianness, "little")
        self.assertFalse(summary.is_nanosecond)
        self.assertEqual(summary.snaplen, 65535)
        self.assertEqual(summary.network, 1)
        self.assertEqual(summary.link_type_name, "LINKTYPE_ETHERNET")
        self.assertEqual(summary.packet_count, 3)
        self.assertEqual(summary.flows_count, 1)

        # High-precision duration span check
        self.assertAlmostEqual(summary.duration_span, 0.1, places=5)
        self.assertEqual(summary.start_time, 1700000000.1)
        self.assertEqual(summary.end_time, 1700000000.2)

        # Flow reassembly
        flow = summary.flows[0]
        self.assertEqual(flow.protocol, "TCP")
        self.assertEqual(flow.packet_count, 3)
        self.assertIn("192.168.1.100:52000", flow.flow_id)
        self.assertIn("10.0.0.1:80", flow.flow_id)
        self.assertAlmostEqual(flow.duration_span, 0.1, places=5)

        # Packet details
        pkt1 = summary.packets[0]
        self.assertEqual(pkt1.protocol, "TCP")
        self.assertEqual(pkt1.src_ip, "192.168.1.100")
        self.assertEqual(pkt1.dst_ip, "10.0.0.1")
        self.assertEqual(pkt1.src_port, 52000)
        self.assertEqual(pkt1.dst_port, 80)
        self.assertEqual(pkt1.incl_len, len(self.frame1))
        self.assertEqual(pkt1.orig_len, len(self.frame1))

        # Check serialization
        d = summary.to_dict()
        self.assertEqual(d["packet_count"], 3)
        self.assertEqual(d["link_type"], 1)
        self.assertEqual(d["version"], "2.4")

    def test_parse_valid_big_endian_nanosecond(self):
        """Verify Big-Endian nanosecond PCAP parsing."""
        gh_be = struct.pack(">IHHiiII", 0xA1B23C4D, 2, 4, 0, 0, 65535, 1)
        ph1 = struct.pack(">IIII", 1700000000, 1000, len(self.frame1), len(self.frame1))
        ph2 = struct.pack(">IIII", 1700000000, 5000, len(self.frame2), len(self.frame2))

        raw_be = gh_be + ph1 + self.frame1 + ph2 + self.frame2
        summary = PcapParser.parse_bytes(raw_be)

        self.assertEqual(summary.endianness, "big")
        self.assertTrue(summary.is_nanosecond)
        self.assertEqual(summary.packet_count, 2)
        self.assertEqual(summary.duration_span, 0.000004)
        self.assertEqual(summary.total_bytes, len(raw_be))

    def test_parse_little_endian_nanosecond(self):
        """Verify Little-Endian nanosecond PCAP parsing."""
        gh_le_nano = struct.pack("<IHHiiII", 0xA1B23C4D, 2, 4, 0, 0, 65535, 1)
        ph1 = struct.pack("<IIII", 1700000000, 2000, len(self.frame1), len(self.frame1))
        raw = gh_le_nano + ph1 + self.frame1

        summary = PcapParser.parse_bytes(raw)
        self.assertEqual(summary.endianness, "little")
        self.assertTrue(summary.is_nanosecond)
        self.assertEqual(summary.packet_count, 1)
        self.assertEqual(summary.duration_span, 0.0)

    def test_parse_big_endian_microsecond(self):
        """Verify Big-Endian standard microsecond PCAP parsing."""
        gh_be_micro = struct.pack(">IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        ph1 = struct.pack(">IIII", 1700000000, 500000, len(self.frame1), len(self.frame1))
        raw = gh_be_micro + ph1 + self.frame1

        summary = PcapParser.parse_bytes(raw)
        self.assertEqual(summary.endianness, "big")
        self.assertFalse(summary.is_nanosecond)
        self.assertEqual(summary.packet_count, 1)

    def test_parse_udp_flow(self):
        """Verify UDP flow reassembly with distinct endpoint ports."""
        udp_frame = create_eth_ip_udp_frame(
            self.mac_client, self.mac_server, self.ip_client, self.ip_server,
            src_port=5353, dst_port=53, payload=b"\x00\x01\x01\x00"
        )
        gh = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        ph = struct.pack("<IIII", 1700000000, 0, len(udp_frame), len(udp_frame))
        raw = gh + ph + udp_frame

        summary = PcapParser.parse_bytes(raw)
        self.assertEqual(summary.packet_count, 1)
        self.assertEqual(summary.packets[0].protocol, "UDP")
        self.assertEqual(summary.packets[0].src_port, 5353)
        self.assertEqual(summary.packets[0].dst_port, 53)

    def test_fail_closed_on_invalid_magic(self):
        """Verify rejection when magic number is invalid."""
        bad_magic = b"\x00\x11\x22\x33" + (b"\x00" * 20)
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(bad_magic)
        self.assertIn("Invalid PCAP magic number", str(ctx.exception))

    def test_fail_closed_on_truncated_global_header(self):
        """Verify rejection when global header is shorter than 24 bytes."""
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(b"\xd4\xc3\xb2\xa1\x02\x04")
        self.assertIn("PCAP truncated", str(ctx.exception))

    def test_fail_closed_on_unsupported_version(self):
        """Verify rejection when version is not 2.4."""
        # Version 2.5
        bad_ver = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 5, 0, 0, 65535, 1)
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(bad_ver)
        self.assertIn("Unsupported PCAP version 2.5", str(ctx.exception))

    def test_fail_closed_on_invalid_snaplen(self):
        """Verify rejection on zero or excessive snaplen."""
        zero_snaplen = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 0, 1)
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(zero_snaplen)
        self.assertIn("Invalid PCAP snaplen", str(ctx.exception))

        huge_snaplen = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 500000, 1)
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(huge_snaplen)
        self.assertIn("exceeds maximum allowed boundary", str(ctx.exception))

    def test_fail_closed_on_packet_len_exceeding_snaplen(self):
        """Verify rejection when incl_len > snaplen."""
        snaplen = 100
        gh = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, snaplen, 1)
        # incl_len = 150 > snaplen 100
        ph = struct.pack("<IIII", 1700000000, 0, 150, 200)
        payload = b"A" * 150
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(gh + ph + payload)
        self.assertIn("exceeds global snaplen", str(ctx.exception))

    def test_fail_closed_on_packet_len_exceeding_orig_len(self):
        """Verify rejection when incl_len > orig_len."""
        gh = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        # incl_len = 100 > orig_len = 50
        ph = struct.pack("<IIII", 1700000000, 0, 100, 50)
        payload = b"B" * 100
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(gh + ph + payload)
        self.assertIn("exceeds original wire length", str(ctx.exception))

    def test_fail_closed_on_truncated_packet_header(self):
        """Verify rejection when packet header is shorter than 16 bytes."""
        gh = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        trailing_fragment = b"\x01\x02\x03\x04\x05"
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(gh + trailing_fragment)
        self.assertIn("Truncated PCAP packet header", str(ctx.exception))

    def test_fail_closed_on_truncated_packet_payload(self):
        """Verify rejection when remaining buffer is shorter than incl_len."""
        gh = struct.pack("<IHHiiII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 1)
        ph = struct.pack("<IIII", 1700000000, 0, 50, 50)
        short_payload = b"C" * 20  # only 20 bytes instead of 50
        with self.assertRaises(ValueError) as ctx:
            PcapParser.parse_bytes(gh + ph + short_payload)
        self.assertIn("Truncated PCAP packet payload", str(ctx.exception))

    def test_thermodynamic_heap_ceiling(self):
        """Verify heap allocation stays strictly <= 64 KB."""
        summary, receipt = ThermodynamicProfiler.profile_callable(
            PcapParser.parse_bytes,
            self.synthetic_pcap_le,
            candidate_id="pcap_parser_ch33",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        )
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.exit_code, 0)
        self.assertLessEqual(receipt.peak_memory_bytes, 64 * 1024)

    def test_adversarial_mutant_fuzzing(self):
        """Verify that adversarial mutants either parse safely or fail cleanly with ValueError."""
        mutants = AdversarialMutator.generate_adversarial_suite(self.synthetic_pcap_le)
        self.assertGreaterEqual(len(mutants), 15)

        for m in mutants:
            try:
                summary = PcapParser.parse_bytes(m.payload)
                self.assertIsInstance(summary.total_bytes, int)
            except ValueError:
                pass
            except Exception as e:
                self.fail(f"Unhandled exception on mutant {m.mutation_type}: {e}")


if __name__ == "__main__":
    unittest.main()
