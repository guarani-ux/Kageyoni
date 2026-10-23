"""Ninshū "Molten Metal" Dynamic Capability Smelter and Board Reconfiguration Engine.

Enables pure-Python stdlib dynamic capability smelting:
1. Probe raw binary/JSON specimen data to detect structural grammar (magic bytes,
   fixed header fields, TLV structures, string tables, JSON schemas).
2. Cast pure-Python channel parser modules with fail-closed bounds checking and
   ThermodynamicProfiler peak heap <= 64KB, plus matching unittest suites with golden
   and adversarial vectors.
3. Quench & mount: mechanically audits synthesized modules via MechanicalAuditorGate,
   hot-mounting accepted channels into ninshu_codex.sqlite and ActiveConsole.
4. Board reconfiguration: dynamically adjusts substrate lenses, 4-band EQ layer
   splits, and insert chains on the fly.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .console import ActiveConsole, ChannelStripConfig
from .patchbay import Patchbay
from .thermodynamics import ThermodynamicProfiler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclasses.dataclass
class StructuralBlueprint:
    """Discovered structural grammar and invariants of a probed specimen."""

    specimen_format: str  # "binary_packet" | "binary_archive" | "binary_tlv" | "json_schema" | "delimited_text"
    magic_bytes: Optional[bytes] = None
    endianness: str = "<"  # "<" for little-endian, ">" for big-endian
    header_size: int = 0
    fields: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    has_tlv: bool = False
    tlv_structure: Optional[Dict[str, Any]] = None
    has_payload: bool = False
    payload_offset: int = 0
    payload_length_field: Optional[str] = None
    has_string_table: bool = False
    json_schema: Optional[Dict[str, Any]] = None
    sample_hashes: List[str] = dataclasses.field(default_factory=list)
    invariants: List[str] = dataclasses.field(default_factory=list)
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        if self.magic_bytes is not None:
            d["magic_bytes_hex"] = self.magic_bytes.hex()
            d["magic_bytes"] = repr(self.magic_bytes)
        return d


@dataclasses.dataclass
class CastArtifact:
    """Synthesized capability parser module and matching verification suite."""

    channel_number: int
    name: str
    bus: str
    blueprint: StructuralBlueprint
    impl_path: Path
    test_path: Path
    test_module: str
    impl_code: str
    test_code: str
    entrypoint: str
    sha256_digest: str


def _patchbay_execute_channel(
    self: Patchbay,
    channel_number: int,
    data: Any,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Dynamically resolves and executes a mounted channel parser."""
    ch = self.get_channel(channel_number)
    if not ch:
        raise ValueError(f"Channel {channel_number} not found in Patchbay")

    carrier_path_str = ch["carrier_path"].replace("\\", "/").strip()
    entrypoint = ch["entrypoint"]

    # Module resolution
    clean_mod_path = carrier_path_str[:-3] if carrier_path_str.endswith(".py") else carrier_path_str
    module_name = clean_mod_path.replace("/", ".")

    try:
        if module_name in sys.modules:
            mod = sys.modules[module_name]
        else:
            mod = importlib.import_module(module_name)
    except ModuleNotFoundError:
        # Load from file location directly
        file_path = REPO_ROOT / carrier_path_str
        if not file_path.exists():
            raise FileNotFoundError(f"Carrier file {file_path} not found")
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        spec.loader.exec_module(mod)

    # Entrypoint resolution
    parts = entrypoint.split(".")
    target: Any = mod
    for part in parts:
        if not hasattr(target, part):
            raise AttributeError(f"Module {module_name} has no attribute {part!r}")
        target = getattr(target, part)

    return target(data, *args, **kwargs)


# Attach execute_channel to Patchbay class if not already defined natively
if not hasattr(Patchbay, "execute_channel"):
    Patchbay.execute_channel = _patchbay_execute_channel


class MoltenSmelter:
    """
    "Molten Metal" Dynamic Capability Smelter and Board Reconfiguration Engine.
    Probes specimen invariants, synthesizes fail-closed channels, executes mechanical
    zero-trust audits, hot-mounts channels into SQLite and ActiveConsole, and reconfigures
    board parameters on the fly.
    """

    def probe_specimen(
        self,
        samples: List[Union[bytes, str, dict]],
    ) -> StructuralBlueprint:
        """
        Analyzes raw specimen data to detect structural grammar:
        magic bytes, fixed header fields, TLV structures, string tables, or JSON AST schemas.
        """
        if not samples:
            raise ValueError("No specimen samples provided to probe_specimen")

        first = samples[0]

        # Case 1: JSON / Dict specimens
        if isinstance(first, dict) or (isinstance(first, str) and first.strip().startswith(("{", "["))):
            return self._probe_json_specimens(samples)

        # Case 2: Binary specimens
        if isinstance(first, (bytes, bytearray)):
            return self._probe_binary_specimens(samples)

        # Fallback string
        if isinstance(first, str):
            return self._probe_text_specimens(samples)

        raise TypeError(f"Unsupported sample type: {type(first).__name__}")

    def _probe_binary_specimens(
        self,
        samples: List[Any],
    ) -> StructuralBlueprint:
        bytes_samples: List[bytes] = []
        sample_hashes: List[str] = []

        for s in samples:
            if not isinstance(s, (bytes, bytearray)):
                raise TypeError(f"Mixed sample types in binary probe: expected bytes, got {type(s).__name__}")
            b = bytes(s)
            bytes_samples.append(b)
            sample_hashes.append(hashlib.sha256(b).hexdigest())

        # 1. Detect magic bytes (common prefix)
        min_len = min(len(s) for s in bytes_samples)
        if min_len == 0:
            raise ValueError("Cannot probe empty binary specimen")

        prefix_len = 0
        ref = bytes_samples[0]
        for idx in range(min_len):
            b_val = ref[idx]
            if all(s[idx] == b_val for s in bytes_samples):
                prefix_len += 1
            else:
                break

        # In binary protocols, magic bytes are typically 2 to 8 bytes.
        # If single sample is provided, cap to min(prefix_len, 4).
        if len(bytes_samples) == 1:
            magic_len = min(4, min_len) if min_len >= 2 else 0
        else:
            magic_len = min(prefix_len, 8 if prefix_len >= 8 and min_len >= 16 else 4)

        magic_bytes: Optional[bytes] = ref[:magic_len] if magic_len >= 2 else None

        # 2. Endianness & Header Field Detection
        # Check standard fixed header sizes (e.g., 8, 12, 16, 20, 24 bytes)
        endianness = "<"
        header_size = 16
        fields: List[Dict[str, Any]] = []
        payload_length_field: Optional[str] = None
        has_payload = False

        # Attempt to discover if a uint16 or uint32 matches payload length across all samples
        detected_endian = None
        detected_header_size = None
        detected_len_offset = None

        candidate_header_sizes = [16, 8, 12, 20, 24]
        for cand_hdr in candidate_header_sizes:
            if min_len < cand_hdr:
                continue
            for end in ("<", ">"):
                # Try uint32 length at offset 8, 4, 12
                for offset in (8, 4, 12):
                    if offset + 4 <= cand_hdr:
                        matches = True
                        for s in bytes_samples:
                            val = struct.unpack_from(f"{end}I", s, offset)[0]
                            # Either val matches payload length or val matches total length
                            if val != (len(s) - cand_hdr) and val != len(s):
                                matches = False
                                break
                        if matches:
                            detected_endian = end
                            detected_header_size = cand_hdr
                            detected_len_offset = offset
                            break
                if detected_endian:
                    break
            if detected_endian:
                break

        if detected_endian and detected_header_size:
            endianness = detected_endian
            header_size = detected_header_size
            has_payload = any(len(s) > header_size for s in bytes_samples)

            # Build field layout
            magic_len = len(magic_bytes) if magic_bytes else 4
            fields.append({
                "name": "magic",
                "offset": 0,
                "size": magic_len,
                "type": "bytes",
                "format": f"{magic_len}s",
            })
            if detected_len_offset == 8 and header_size >= 16:
                fields.append({"name": "version", "offset": 4, "size": 2, "type": "uint16", "format": "H"})
                fields.append({"name": "packet_id", "offset": 6, "size": 2, "type": "uint16", "format": "H"})
                fields.append({"name": "payload_length", "offset": 8, "size": 4, "type": "uint32", "format": "I"})
                fields.append({"name": "sequence_id", "offset": 12, "size": 4, "type": "uint32", "format": "I"})
                payload_length_field = "payload_length"
                if header_size > 16:
                    fields.append({"name": "extra_header", "offset": 16, "size": header_size - 16, "type": "bytes", "format": f"{header_size - 16}s"})
            elif detected_len_offset == 4 and header_size >= 8:
                fields.append({"name": "payload_length", "offset": 4, "size": 4, "type": "uint32", "format": "I"})
                payload_length_field = "payload_length"
                if header_size > 8:
                    fields.append({"name": "extra_header", "offset": 8, "size": header_size - 8, "type": "bytes", "format": f"{header_size - 8}s"})
            else:
                fields.append({"name": "raw_header_data", "offset": magic_len, "size": header_size - magic_len, "type": "bytes", "format": f"{header_size - magic_len}s"})
        else:
            # Default fixed layout if no explicit length match
            magic_len = len(magic_bytes) if magic_bytes else (4 if min_len >= 4 else min_len)
            header_size = min(16, min_len)
            fields.append({"name": "magic", "offset": 0, "size": magic_len, "type": "bytes", "format": f"{magic_len}s"})
            if header_size > magic_len:
                fields.append({
                    "name": "header_data",
                    "offset": magic_len,
                    "size": header_size - magic_len,
                    "type": "bytes",
                    "format": f"{header_size - magic_len}s",
                })
            has_payload = any(len(s) > header_size for s in bytes_samples)

        # 3. Check for TLV structure in payload
        has_tlv = False
        tlv_structure = None
        if has_payload:
            tlv_valid = True
            for s in bytes_samples:
                payload = s[header_size:]
                if not payload:
                    continue
                # Try parsing repeating (tag: uint16, len: uint16, value: len bytes)
                cur = 0
                while cur < len(payload):
                    if cur + 4 > len(payload):
                        tlv_valid = False
                        break
                    _, chunk_len = struct.unpack_from(f"{endianness}HH", payload, cur)
                    cur += 4 + chunk_len
                    if cur > len(payload):
                        tlv_valid = False
                        break
                if not tlv_valid:
                    break
            if tlv_valid and any(len(s[header_size:]) >= 4 for s in bytes_samples):
                has_tlv = True
                tlv_structure = {"tag_size": 2, "length_size": 2, "endianness": endianness}

        # 4. Check for string tables
        has_string_table = False
        for s in bytes_samples:
            if b"\x00" in s[header_size:]:
                parts = [p for p in s[header_size:].split(b"\x00") if len(p) >= 3]
                if any(all(32 <= b_val <= 126 for b_val in p) for p in parts):
                    has_string_table = True
                    break

        invariants = [
            f"min_length >= {header_size}",
            f"endianness == {endianness!r}",
            "fail_closed_on_bounds_overflow",
        ]
        if magic_bytes:
            invariants.append(f"magic == {magic_bytes.hex()}")
        if payload_length_field:
            invariants.append(f"payload_length_matches_actual_bytes")
        if has_tlv:
            invariants.append("tlv_chunks_bounded_within_payload")

        return StructuralBlueprint(
            specimen_format="binary_packet" if not has_tlv else "binary_tlv",
            magic_bytes=magic_bytes,
            endianness=endianness,
            header_size=header_size,
            fields=fields,
            has_tlv=has_tlv,
            tlv_structure=tlv_structure,
            has_payload=has_payload,
            payload_offset=header_size,
            payload_length_field=payload_length_field,
            has_string_table=has_string_table,
            sample_hashes=sample_hashes,
            invariants=invariants,
            metadata={"sample_count": len(samples)},
        )

    def _probe_json_specimens(
        self,
        samples: List[Any],
    ) -> StructuralBlueprint:
        dict_samples: List[Dict[str, Any]] = []
        sample_hashes: List[str] = []

        for s in samples:
            if isinstance(s, str):
                d = json.loads(s)
            elif isinstance(s, dict):
                d = s
            else:
                raise TypeError(f"Invalid JSON specimen sample: {type(s).__name__}")
            dict_samples.append(d)
            sample_hashes.append(hashlib.sha256(json.dumps(d, sort_keys=True).encode("utf-8")).hexdigest())

        # Determine required keys vs optional keys
        all_keys = set().union(*(d.keys() for d in dict_samples))
        common_keys = set(dict_samples[0].keys())
        for d in dict_samples[1:]:
            common_keys.intersection_update(d.keys())

        schema_fields: Dict[str, Any] = {}
        for k in sorted(all_keys):
            types_seen = {type(d[k]).__name__ for d in dict_samples if k in d}
            schema_fields[k] = {
                "required": k in common_keys,
                "types": sorted(list(types_seen)),
            }

        invariants = [
            f"required_keys: {sorted(list(common_keys))}",
            "valid_json_structure",
            "fail_closed_on_missing_required_keys",
        ]

        return StructuralBlueprint(
            specimen_format="json_schema",
            json_schema=schema_fields,
            sample_hashes=sample_hashes,
            invariants=invariants,
            metadata={"sample_count": len(samples), "field_count": len(schema_fields)},
        )

    def _probe_text_specimens(
        self,
        samples: List[str],
    ) -> StructuralBlueprint:
        sample_hashes = [hashlib.sha256(s.encode("utf-8")).hexdigest() for s in samples]
        delimiters = [":", ",", "\t", "|"]
        matched_delim = None
        for delim in delimiters:
            if all(delim in s for s in samples):
                matched_delim = delim
                break

        invariants = [
            "text_record",
            f"delimiter: {matched_delim or 'line'}",
            "fail_closed_on_malformed_record",
        ]

        return StructuralBlueprint(
            specimen_format="delimited_text",
            sample_hashes=sample_hashes,
            invariants=invariants,
            metadata={"delimiter": matched_delim},
        )

    def cast_channel(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        bus: str,
    ) -> CastArtifact:
        """
        Synthesizes a new, pure-Python channel parser module (`kageyoni/ninshu/smelted_<name>.py`)
        with fail-closed bounds checking and `ThermodynamicProfiler` peak heap <= 64KB,
        PLUS a matching `unittest` suite (`tests/test_ninshu_smelted_<name>.py`) with golden
        valid vectors and adversarial mutants.
        """
        clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", name.lower().strip()).strip("_")
        cap_name = "".join(part.capitalize() for part in clean_name.split("_") if part)

        impl_filename = f"smelted_{clean_name}.py"
        test_filename = f"test_ninshu_smelted_{clean_name}.py"

        impl_path = REPO_ROOT / "kageyoni" / "ninshu" / impl_filename
        test_path = REPO_ROOT / "tests" / test_filename
        test_module = f"tests.test_ninshu_smelted_{clean_name}"
        entrypoint = f"Smelted{cap_name}Parser.parse"

        # Synthesize code based on specimen format
        if blueprint.specimen_format in ("binary_packet", "binary_tlv"):
            impl_code = self._generate_binary_parser_code(blueprint, channel_number, clean_name, cap_name)
            test_code = self._generate_binary_test_code(blueprint, channel_number, clean_name, cap_name)
        elif blueprint.specimen_format == "json_schema":
            impl_code = self._generate_json_parser_code(blueprint, channel_number, clean_name, cap_name)
            test_code = self._generate_json_test_code(blueprint, channel_number, clean_name, cap_name)
        else:
            impl_code = self._generate_generic_parser_code(blueprint, channel_number, clean_name, cap_name)
            test_code = self._generate_generic_test_code(blueprint, channel_number, clean_name, cap_name)

        # Write files to disk
        impl_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.parent.mkdir(parents=True, exist_ok=True)
        impl_path.write_text(impl_code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")

        combined_hash = hashlib.sha256((impl_code + test_code).encode("utf-8")).hexdigest()

        return CastArtifact(
            channel_number=channel_number,
            name=clean_name,
            bus=bus,
            blueprint=blueprint,
            impl_path=impl_path,
            test_path=test_path,
            test_module=test_module,
            impl_code=impl_code,
            test_code=test_code,
            entrypoint=entrypoint,
            sha256_digest=combined_hash,
        )

    def quench_and_mount(
        self,
        artifact: CastArtifact,
        patchbay: Patchbay,
        console: Optional[ActiveConsole] = None,
    ) -> Dict[str, Any]:
        """
        Runs `MechanicalAuditorGate.audit_channel()` on the synthesized files.
        If verdict is ACCEPT, hot-mounts the channel into `ninshu_codex.sqlite`
        and registers it in `ActiveConsole`.
        """
        from tools.mechanical_audit_gate import MechanicalAuditorGate

        # Relative path for audit gate
        rel_impl_file = f"kageyoni/ninshu/{artifact.impl_path.name}"
        audit_result = MechanicalAuditorGate.audit_channel(
            channel_number=artifact.channel_number,
            channel_name=artifact.name,
            impl_file=rel_impl_file,
            test_module=artifact.test_module,
        )

        if audit_result.get("verdict") != "ACCEPT":
            return {
                "verdict": "REJECT",
                "status": "REJECTED",
                "channel_number": artifact.channel_number,
                "channel_name": artifact.name,
                "reasons": audit_result.get("reasons", []),
                "anti_patterns": audit_result.get("anti_patterns_found", []),
                "mounted": False,
            }

        # 1. Hot-mount into SQLite codex
        with patchbay.conn:
            # Ensure bus exists
            patchbay.conn.execute(
                "INSERT OR IGNORE INTO busses (bus_id, name, description, channel_range) VALUES (?, ?, ?, ?)",
                (
                    artifact.bus,
                    f"Bus {artifact.bus}",
                    f"Dynamic bus for smelted {artifact.name}",
                    f"CH {artifact.channel_number}",
                ),
            )

            effects = {
                "mutatesTarget": False,
                "mutatesSession": False,
                "writesFilesystem": False,
                "launchesProcess": False,
                "accessesNetwork": False,
                "executesForeignCode": False,
                "idempotent": True,
            }
            subject_formats = ["binary", artifact.blueprint.specimen_format]

            patchbay.conn.execute(
                """
                INSERT OR REPLACE INTO channels (
                    channel_number, bus_id, name, category, description,
                    carrier_path, entrypoint, subject_formats, lens_family,
                    effects_json, reversibility_tier, epistemic_confidence,
                    coverage_status, output_mold, intent_keywords, digest_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.channel_number,
                    artifact.bus,
                    artifact.name,
                    "smelted_dynamic",
                    f"Smelted dynamic channel for {artifact.name} with fail-closed bounds checking",
                    rel_impl_file,
                    artifact.entrypoint,
                    json.dumps(subject_formats),
                    "smelted_parser",
                    json.dumps(effects),
                    0,
                    "verified",
                    "complete",
                    "Evidence",
                    f"smelted {artifact.name} {artifact.blueprint.specimen_format}",
                    artifact.sha256_digest,
                ),
            )

        # 2. Register into ActiveConsole
        manifest = patchbay.patch([artifact.channel_number], daimon_name=f"smelted_{artifact.name}")
        active_console = console or ActiveConsole(manifest)
        if artifact.channel_number not in active_console.channels:
            active_console.channels[artifact.channel_number] = ChannelStripConfig(
                channel_number=artifact.channel_number,
                name=artifact.name,
                carrier_path=rel_impl_file,
                entrypoint=artifact.entrypoint,
                thermal_ceiling=0,
                max_memory_ceiling_bytes=64 * 1024,
            )

        return {
            "verdict": "ACCEPT",
            "status": "ACCEPTED",
            "channel_number": artifact.channel_number,
            "channel_name": artifact.name,
            "bus_id": artifact.bus,
            "carrier_path": rel_impl_file,
            "entrypoint": artifact.entrypoint,
            "digest_sha256": artifact.sha256_digest,
            "audit_result": audit_result,
            "console": active_console,
            "mounted": True,
        }

    def reconfigure_channel(
        self,
        channel_number: int,
        knob_vector: Any,
        strip_config: ChannelStripConfig,
        console: Optional[ActiveConsole] = None,
        patchbay: Optional[Patchbay] = None,
    ) -> ChannelStripConfig:
        """
        Reconfigures any channel's substrate lens, 4-band EQ layer split, or insert chain on the fly.
        """
        if hasattr(knob_vector, "validate"):
            knob_vector.validate()

        substrate = getattr(knob_vector, "substrate", "stone")
        shape = getattr(knob_vector, "bandwidth_shape", "domain")
        authority = float(getattr(knob_vector, "authority_gain", 1.0))
        damping = float(getattr(knob_vector, "damping_density", 0.95))
        tier = int(getattr(knob_vector, "thermal_tier", 0))
        polarity = getattr(knob_vector, "polarity", "polyphonic")
        sidechain_from = getattr(knob_vector, "sidechain_from", None)
        deficit = getattr(knob_vector, "deficit_gain", "dry")

        # 1. Update physical settings on channel strip
        strip_config.thermal_ceiling = tier
        strip_config.fader_gain_db = round((damping - 0.5) * 12.0, 2)
        strip_config.noise_gate_threshold = 0.5 if authority >= 0.8 else 0.2

        # 2. Substrate lens configuration
        setattr(strip_config, "substrate_lens", f"substrate_lens:{substrate}")

        # 3. 4-band EQ layer split (SSL 4000 style)
        # Low (LF): Substrate ground
        # Low-Mid (LMF): Inspection/strike shape & authority
        # High-Mid (HMF): Damping density & polarity tension
        # High (HF): Thermal tier & deficit gain
        eq_split = {
            "LF": {"frequency": "60Hz", "gain_db": round(authority * 6.0, 2), "parameter": substrate},
            "LMF": {"frequency": "500Hz", "gain_db": round(damping * 6.0, 2), "shape": shape},
            "HMF": {"frequency": "2.5kHz", "gain_db": 0.0 if polarity == "polyphonic" else 3.0, "polarity": polarity},
            "HF": {"frequency": "10kHz", "gain_db": float(tier * 3.0), "deficit": deficit},
        }
        setattr(strip_config, "eq_layer_split", eq_split)

        # 4. Insert chain
        if sidechain_from:
            insert_chain = [
                {"type": "sidechain_compressor", "source": sidechain_from, "routing": "post_eq"}
            ]
        else:
            insert_chain = [
                {"type": "direct_insert", "routing": "in_line"}
            ]
        setattr(strip_config, "insert_chain", insert_chain)

        # 5. Reflect in console if provided
        if console and channel_number in console.channels:
            console.channels[channel_number] = strip_config
            console.set_fader(channel_number, strip_config.fader_gain_db)
            console.set_gate(channel_number, strip_config.noise_gate_threshold)

        # 6. Reflect in patchbay if provided
        if patchbay:
            with patchbay.conn:
                patchbay.conn.execute(
                    "UPDATE channels SET lens_family = ?, reversibility_tier = ? WHERE channel_number = ?",
                    (f"smelted_lens_{substrate}", tier, channel_number),
                )

        return strip_config

    def _generate_binary_parser_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        magic_bytes = blueprint.magic_bytes or b""
        endianness = blueprint.endianness
        header_size = blueprint.header_size

        # Build struct format and field names
        field_names = [f["name"] for f in blueprint.fields]
        fmt_parts = [endianness]
        for f in blueprint.fields:
            fmt_parts.append(f.get("format", "4s"))
        header_format = "".join(fmt_parts)

        has_tlv = blueprint.has_tlv

        code = f'''"""Smelted Channel {channel_number}: {name} Parser Module.

Synthesized dynamically by MoltenSmelter.
Pure Python stdlib with fail-closed bounds checking and ThermodynamicProfiler heap containment.
"""
from __future__ import annotations

import dataclasses
import hashlib
import struct
from typing import Any, Dict, List, Optional, Tuple

from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


@dataclasses.dataclass(frozen=True)
class Smelted{cap_name}Summary:
    channel_number: int
    specimen_format: str
    sha256_digest: str
    total_bytes: int
    header_bytes: int
    payload_bytes: bytes
    fields: Dict[str, Any]
    tlv_chunks: List[Dict[str, Any]] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {{
            "channel_number": self.channel_number,
            "specimen_format": self.specimen_format,
            "sha256_digest": self.sha256_digest,
            "total_bytes": self.total_bytes,
            "header_bytes": self.header_bytes,
            "payload_length": len(self.payload_bytes),
            "fields": dict(self.fields),
            "tlv_chunks": list(self.tlv_chunks),
        }}


class Smelted{cap_name}Parser:
    """Fail-closed binary protocol parser synthesized by MoltenSmelter."""

    MAGIC: bytes = {repr(magic_bytes)}
    HEADER_SIZE: int = {header_size}
    HEADER_FORMAT: str = {repr(header_format)}
    ENDIANNESS: str = {repr(endianness)}
    CHANNEL_NUMBER: int = {channel_number}

    @classmethod
    def parse(
        cls,
        data: bytes,
        memory_ceiling_bytes: int = 64 * 1024,
    ) -> Smelted{cap_name}Summary:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"Invalid specimen type: expected bytes or bytearray, got {{type(data).__name__}}")

        if len(data) < cls.HEADER_SIZE:
            raise ValueError(
                f"Specimen truncated: length ({{len(data)}} bytes) is smaller than header ({{cls.HEADER_SIZE}} bytes)"
            )

        if cls.MAGIC and data[: len(cls.MAGIC)] != cls.MAGIC:
            raise ValueError(
                f"Magic mismatch: expected {{cls.MAGIC!r}}, got {{data[: len(cls.MAGIC)]!r}}"
            )

        # Unpack header fields
        raw_header = data[: cls.HEADER_SIZE]
        unpacked = struct.unpack(cls.HEADER_FORMAT, raw_header)
        field_names = {repr(field_names)}
        parsed_fields = dict(zip(field_names, unpacked))

        # Payload bounds check
        payload_len = parsed_fields.get("payload_length")
        if payload_len is not None:
            expected_total = cls.HEADER_SIZE + payload_len
            if len(data) != expected_total:
                raise ValueError(
                    f"Payload size mismatch: declared payload_length={{payload_len}} "
                    f"(expected total={{expected_total}}), actual total={{len(data)}} bytes"
                )
            payload = bytes(data[cls.HEADER_SIZE : cls.HEADER_SIZE + payload_len])
        else:
            payload = bytes(data[cls.HEADER_SIZE :])

        # TLV decoding if present
        tlv_chunks: List[Dict[str, Any]] = []
        if {has_tlv}:
            cursor = 0
            while cursor < len(payload):
                if cursor + 4 > len(payload):
                    raise ValueError(f"Truncated TLV chunk header at offset {{cursor}}")
                tag, chunk_len = struct.unpack(f"{{cls.ENDIANNESS}}HH", payload[cursor : cursor + 4])
                cursor += 4
                if cursor + chunk_len > len(payload):
                    raise ValueError(
                        f"Truncated TLV value for tag {{tag}}: declared length={{chunk_len}}, remaining={{len(payload) - cursor}}"
                    )
                val = bytes(payload[cursor : cursor + chunk_len])
                cursor += chunk_len
                tlv_chunks.append({{"tag": tag, "length": chunk_len, "value_hex": val.hex()}})

        # Thermodynamic heap containment profiling
        with ThermodynamicProfiler(
            candidate_id=f"smelted_{name}_ch{{cls.CHANNEL_NUMBER}}",
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=True,
        ):
            digest = hashlib.sha256(data).hexdigest()
            return Smelted{cap_name}Summary(
                channel_number=cls.CHANNEL_NUMBER,
                specimen_format={repr(blueprint.specimen_format)},
                sha256_digest=digest,
                total_bytes=len(data),
                header_bytes=cls.HEADER_SIZE,
                payload_bytes=payload,
                fields=parsed_fields,
                tlv_chunks=tlv_chunks,
            )
'''
        return code

    def _generate_binary_test_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        has_tlv = blueprint.has_tlv
        endianness = blueprint.endianness

        code = f'''"""Adversarial and Thermodynamic Compliance Test Suite for Smelted {name} (CH {channel_number})."""
from __future__ import annotations

import struct
import unittest

from kageyoni.ninshu.smelted_{name} import Smelted{cap_name}Parser, Smelted{cap_name}Summary
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler, MemoryCeilingExceededError


class TestSmelted{cap_name}Parser(unittest.TestCase):
    """Zero-trust physical verification for smelted channel {channel_number}."""

    def _build_valid_packet(self, version: int = 1, packet_id: int = 42, payload: bytes = b"PING_PAYLOAD") -> bytes:
        fields = Smelted{cap_name}Parser.HEADER_FORMAT
        if "H" in fields and "I" in fields:
            header = struct.pack(
                fields,
                Smelted{cap_name}Parser.MAGIC,
                version,
                packet_id,
                len(payload),
                1001,
            )
        else:
            magic = Smelted{cap_name}Parser.MAGIC
            pad_len = Smelted{cap_name}Parser.HEADER_SIZE - len(magic)
            header = magic + (b"\\x00" * pad_len)
        return header + payload

    def test_golden_vector_parse(self):
        packet = self._build_valid_packet()
        summary = Smelted{cap_name}Parser.parse(packet)
        self.assertIsInstance(summary, Smelted{cap_name}Summary)
        self.assertEqual(summary.channel_number, {channel_number})
        self.assertEqual(len(summary.sha256_digest), 64)
        self.assertEqual(summary.payload_bytes, b"PING_PAYLOAD")
        d = summary.to_dict()
        self.assertEqual(d["total_bytes"], len(packet))

    def test_thermodynamic_heap_compliance(self):
        packet = self._build_valid_packet()
        with ThermodynamicProfiler(
            candidate_id="smelted_thermo_test",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        ) as profiler:
            for _ in range(5):
                Smelted{cap_name}Parser.parse(packet)
        self.assertLessEqual(profiler.peak_memory_bytes, 64 * 1024)

    def test_adversarial_corrupted_magic(self):
        if Smelted{cap_name}Parser.MAGIC:
            packet = bytearray(self._build_valid_packet())
            packet[0] ^= 0xFF
            with self.assertRaises(ValueError):
                Smelted{cap_name}Parser.parse(bytes(packet))

    def test_adversarial_truncated_header(self):
        packet = self._build_valid_packet()
        with self.assertRaises(ValueError):
            Smelted{cap_name}Parser.parse(packet[: max(0, Smelted{cap_name}Parser.HEADER_SIZE - 2)])

    def test_adversarial_truncated_payload(self):
        if {repr(blueprint.payload_length_field)} is not None:
            packet = self._build_valid_packet()
            if len(b"PING_PAYLOAD") >= 3:
                with self.assertRaises(ValueError):
                    Smelted{cap_name}Parser.parse(packet[:-3])

    def test_adversarial_trailing_garbage(self):
        if {repr(blueprint.payload_length_field)} is not None:
            packet = self._build_valid_packet() + b"GARBAGE_BYTES_AT_END"
            with self.assertRaises(ValueError):
                Smelted{cap_name}Parser.parse(packet)

    def test_adversarial_empty_specimen(self):
        with self.assertRaises(ValueError):
            Smelted{cap_name}Parser.parse(b"")

    def test_adversarial_invalid_type(self):
        with self.assertRaises(TypeError):
            Smelted{cap_name}Parser.parse("invalid_string_not_bytes")  # type: ignore
        with self.assertRaises(TypeError):
            Smelted{cap_name}Parser.parse(12345)  # type: ignore


if __name__ == "__main__":
    unittest.main()
'''
        return code

    def _generate_json_parser_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        schema = blueprint.json_schema or {}
        code = f'''"""Smelted Channel {channel_number}: {name} JSON Parser Module.

Synthesized dynamically by MoltenSmelter.
Pure Python stdlib with fail-closed schema validation and ThermodynamicProfiler heap containment.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from typing import Any, Dict, List, Optional

from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


@dataclasses.dataclass(frozen=True)
class Smelted{cap_name}Summary:
    channel_number: int
    specimen_format: str
    sha256_digest: str
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {{
            "channel_number": self.channel_number,
            "specimen_format": self.specimen_format,
            "sha256_digest": self.sha256_digest,
            "data": dict(self.data),
        }}


class Smelted{cap_name}Parser:
    """Fail-closed JSON schema parser synthesized by MoltenSmelter."""

    CHANNEL_NUMBER: int = {channel_number}
    SCHEMA_SPEC: Dict[str, Any] = {repr(schema)}

    @classmethod
    def parse(
        cls,
        data: Any,
        memory_ceiling_bytes: int = 64 * 1024,
    ) -> Smelted{cap_name}Summary:
        if isinstance(data, (bytes, bytearray)):
            try:
                parsed = json.loads(data.decode("utf-8"))
            except Exception as e:
                raise ValueError(f"Invalid JSON payload: {{e}}")
            raw_bytes = bytes(data)
        elif isinstance(data, str):
            try:
                parsed = json.loads(data)
            except Exception as e:
                raise ValueError(f"Invalid JSON payload: {{e}}")
            raw_bytes = data.encode("utf-8")
        elif isinstance(data, dict):
            parsed = data
            raw_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
        else:
            raise TypeError(f"Invalid specimen input type: {{type(data).__name__}}")

        if not isinstance(parsed, dict):
            raise ValueError(f"Top-level JSON specimen must be an object, got {{type(parsed).__name__}}")

        # Schema validation
        for field, spec in cls.SCHEMA_SPEC.items():
            if spec.get("required") and field not in parsed:
                raise ValueError(f"Missing required JSON schema field: {{field!r}}")
            if field in parsed:
                val = parsed[field]
                types_allowed = spec.get("types", [])
                if types_allowed and type(val).__name__ not in types_allowed:
                    raise TypeError(
                        f"Field {{field!r}} type mismatch: expected one of {{types_allowed}}, got {{type(val).__name__}}"
                    )

        with ThermodynamicProfiler(
            candidate_id=f"smelted_{name}_ch{{cls.CHANNEL_NUMBER}}",
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=True,
        ):
            digest = hashlib.sha256(raw_bytes).hexdigest()
            return Smelted{cap_name}Summary(
                channel_number=cls.CHANNEL_NUMBER,
                specimen_format="json_schema",
                sha256_digest=digest,
                data=parsed,
            )
'''
        return code

    def _generate_json_test_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        code = f'''"""Adversarial Test Suite for Smelted {name} JSON Schema (CH {channel_number})."""
from __future__ import annotations

import unittest
from kageyoni.ninshu.smelted_{name} import Smelted{cap_name}Parser, Smelted{cap_name}Summary
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


class TestSmelted{cap_name}Parser(unittest.TestCase):
    def test_golden_json_parse(self):
        valid = {{k: "sample" for k in Smelted{cap_name}Parser.SCHEMA_SPEC.keys()}}
        res = Smelted{cap_name}Parser.parse(valid)
        self.assertIsInstance(res, Smelted{cap_name}Summary)
        self.assertEqual(res.channel_number, {channel_number})

    def test_adversarial_malformed_json(self):
        with self.assertRaises(ValueError):
            Smelted{cap_name}Parser.parse("{{not: valid json}}")

    def test_adversarial_missing_required(self):
        req = [k for k, v in Smelted{cap_name}Parser.SCHEMA_SPEC.items() if v.get("required")]
        if req:
            with self.assertRaises(ValueError):
                Smelted{cap_name}Parser.parse({{}})

    def test_adversarial_invalid_type(self):
        with self.assertRaises(TypeError):
            Smelted{cap_name}Parser.parse(12345)


if __name__ == "__main__":
    unittest.main()
'''
        return code

    def _generate_generic_parser_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        code = f'''"""Smelted Channel {channel_number}: {name} Generic Parser Module."""
from __future__ import annotations

import dataclasses
import hashlib
from typing import Any, Dict

from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler


@dataclasses.dataclass(frozen=True)
class Smelted{cap_name}Summary:
    channel_number: int
    specimen_format: str
    sha256_digest: str
    content: str


class Smelted{cap_name}Parser:
    CHANNEL_NUMBER: int = {channel_number}

    @classmethod
    def parse(cls, data: Any, memory_ceiling_bytes: int = 64 * 1024) -> Smelted{cap_name}Summary:
        if isinstance(data, (bytes, bytearray)):
            text = data.decode("utf-8", errors="replace")
            raw_b = bytes(data)
        elif isinstance(data, str):
            text = data
            raw_b = data.encode("utf-8")
        else:
            raise TypeError(f"Unsupported generic specimen: {{type(data).__name__}}")

        if not text.strip():
            raise ValueError("Generic specimen is empty")

        with ThermodynamicProfiler(
            candidate_id=f"smelted_{name}_ch{{cls.CHANNEL_NUMBER}}",
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=True,
        ):
            digest = hashlib.sha256(raw_b).hexdigest()
            return Smelted{cap_name}Summary(
                channel_number=cls.CHANNEL_NUMBER,
                specimen_format="delimited_text",
                sha256_digest=digest,
                content=text,
            )
'''
        return code

    def _generate_generic_test_code(
        self,
        blueprint: StructuralBlueprint,
        channel_number: int,
        name: str,
        cap_name: str,
    ) -> str:
        code = f'''"""Adversarial Test Suite for Smelted {name} Generic (CH {channel_number})."""
from __future__ import annotations

import unittest
from kageyoni.ninshu.smelted_{name} import Smelted{cap_name}Parser, Smelted{cap_name}Summary


class TestSmelted{cap_name}Parser(unittest.TestCase):
    def test_golden_generic_parse(self):
        res = Smelted{cap_name}Parser.parse("VALID_ENTRY:alpha:beta")
        self.assertIsInstance(res, Smelted{cap_name}Summary)
        self.assertEqual(res.channel_number, {channel_number})

    def test_adversarial_empty(self):
        with self.assertRaises(ValueError):
            Smelted{cap_name}Parser.parse("")

    def test_adversarial_invalid_type(self):
        with self.assertRaises(TypeError):
            Smelted{cap_name}Parser.parse(12345)


if __name__ == "__main__":
    unittest.main()
'''
        return code
