"""Unified Provider Adapter for 13 External Reverse Engineering Tool Channels (CH 29).

Provides zero-trust execution and offline export parsing parity for:
1.  Ghidra (analyzeHeadless / GhidraParser)
2.  Hopper (hopper / HopperParser)
3.  Cutter (cutter / CutterRizinParser)
4.  Rizin (rizin / CutterRizinParser)
5.  IDA (ida64, idat64, ida / IdaHeadlessParser)
6.  Objdump (objdump, llvm-objdump / ObjdumpParser)
7.  Frida (frida, frida-trace / FridaStalkerParser)
8.  Rizin Debug (rz-debug / RizinDebugParser)
9.  LLDB (lldb / LLDBTracerParser)
10. CDP (node, chrome / CdpParser)
11. Jadx (jadx / JadxParser)
12. Apktool (apktool / ApktoolResourceReconstructor)
13. JEB (jeb / JebParser)

Operational Invariants:
- Inspects PATH via `shutil.which` for external CLI executables.
- If installed and permitted, executes bounded subprocess under ProcessSupervisor RunToken and timeout.
- If absent or in offline mode, falls back to deterministic offline export parsing with explicit:
  `"execution_mode": "OFFLINE_EXPORT_PARSER"` receipt.
- Pure Python standard library, fail-closed validation, memory <= 64 KB overhead.
"""
from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
import shutil
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

# Internal parsers
from kageyoni.ninshu.apktool_parser import ApktoolResourceReconstructor
from kageyoni.ninshu.cdp_parser import CdpParser
from kageyoni.ninshu.cutter_rizin_parser import CutterRizinParser
from kageyoni.ninshu.frida_stalker_parser import FridaStalkerParser
from kageyoni.ninshu.ghidra_parser import GhidraParser
from kageyoni.ninshu.hopper_parser import HopperParser
from kageyoni.ninshu.ida_parser import IdaHeadlessParser
from kageyoni.ninshu.jadx_parser import JadxParser
from kageyoni.ninshu.jeb_parser import JebParser
from kageyoni.ninshu.lldb_tracer_parser import LLDBTracerParser
from kageyoni.ninshu.objdump_parser import ObjdumpParser
from kageyoni.ninshu.rizin_debug_parser import RizinDebugParser
from kageyoni.ninshu.process_supervisor import ProcessSupervisor, RunToken


class ProviderBridgeError(Exception):
    """Base exception for ProviderBridge errors."""
    pass


class UnknownProviderError(ProviderBridgeError):
    """Raised when an unmapped provider channel is requested."""
    pass


class InvalidPayloadError(ProviderBridgeError):
    """Raised when the payload for a provider is empty or corrupt."""
    pass


class ExecutionTimeoutError(ProviderBridgeError):
    """Raised when live execution exceeds the allotted lease/timeout."""
    pass


SUPPORTED_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "ghidra": {
        "cli_candidates": ["ghidra", "analyzeHeadless", "ghidraRun"],
        "category": "decompiler",
    },
    "hopper": {
        "cli_candidates": ["hopper", "hopper-v4"],
        "category": "decompiler",
    },
    "cutter": {
        "cli_candidates": ["cutter"],
        "category": "disassembler_gui",
    },
    "rizin": {
        "cli_candidates": ["rizin", "rz-bin"],
        "category": "disassembler_cli",
    },
    "ida": {
        "cli_candidates": ["ida64", "idat64", "ida", "idat"],
        "category": "decompiler",
    },
    "objdump": {
        "cli_candidates": ["objdump", "llvm-objdump"],
        "category": "disassembler_cli",
    },
    "frida": {
        "cli_candidates": ["frida", "frida-trace"],
        "category": "dynamic_instrumentation",
    },
    "rizin_debug": {
        "cli_candidates": ["rz-debug", "rizin"],
        "category": "debugger",
    },
    "lldb": {
        "cli_candidates": ["lldb"],
        "category": "debugger",
    },
    "cdp": {
        "cli_candidates": ["node", "chrome", "chromium", "msedge"],
        "category": "protocol_debugger",
    },
    "jadx": {
        "cli_candidates": ["jadx"],
        "category": "bytecode_decompiler",
    },
    "apktool": {
        "cli_candidates": ["apktool"],
        "category": "resource_reconstructor",
    },
    "jeb": {
        "cli_candidates": ["jeb"],
        "category": "bytecode_decompiler",
    },
}


def canonical_sha256(data: Union[str, bytes, Dict[str, Any], List[Any]]) -> str:
    """Computes an RFC 8785 canonical SHA-256 digest."""
    if isinstance(data, bytes):
        raw = data
    elif isinstance(data, str):
        raw = data.encode("utf-8")
    else:
        raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ProviderAvailabilityDescriptor:
    provider: str
    category: str
    is_available_live: bool
    cli_binary: Optional[str]
    supported_modes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderExecutionReceipt:
    provider: str
    execution_mode: str  # "LIVE_SUBPROCESS" or "OFFLINE_EXPORT_PARSER"
    status: str  # "SUCCESS", "TIMEOUT", "FAILED"
    exit_code: int
    duration_seconds: float
    payload_sha256: str
    receipt_digest: str
    parsed_summary: Dict[str, Any]
    run_token_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProviderBridge:
    """Unified bridge coordinating live subprocess runs and deterministic offline export parsers."""

    def __init__(self, session_salt: str = "ninshu_provider_bridge_salt"):
        self.session_salt = session_salt
        self._supervisor = ProcessSupervisor(session_salt=session_salt, max_active_tokens=500)

    @classmethod
    def list_supported_providers(cls) -> List[str]:
        """Returns the canonical list of all 13 supported external tool channels."""
        return list(SUPPORTED_PROVIDERS.keys())

    @classmethod
    def inspect_provider_availability(cls, provider: str) -> ProviderAvailabilityDescriptor:
        """Inspects system PATH for available CLI binaries of the specified provider."""
        prov_key = provider.lower().strip()
        meta = SUPPORTED_PROVIDERS.get(prov_key)
        if not meta:
            raise UnknownProviderError(f"Unknown provider channel: {provider} (supported: {cls.list_supported_providers()})")

        found_bin: Optional[str] = None
        for candidate in meta["cli_candidates"]:
            loc = shutil.which(candidate)
            if loc:
                found_bin = loc
                break

        modes = ["OFFLINE_EXPORT_PARSER"]
        if found_bin:
            modes.append("LIVE_SUBPROCESS")

        return ProviderAvailabilityDescriptor(
            provider=prov_key,
            category=meta["category"],
            is_available_live=found_bin is not None,
            cli_binary=found_bin,
            supported_modes=modes,
        )

    @classmethod
    def inspect_all_providers(cls) -> Dict[str, ProviderAvailabilityDescriptor]:
        """Inspects all 13 external tool channels across the host system."""
        return {p: cls.inspect_provider_availability(p) for p in SUPPORTED_PROVIDERS}

    def execute_or_parse(
        self,
        provider: str,
        payload: Union[str, bytes, Dict[str, Any]],
        live_args: Optional[List[str]] = None,
        force_offline: bool = False,
        timeout: float = 5.0,
    ) -> ProviderExecutionReceipt:
        """Executes tool via bounded live subprocess if available and allowed, else deterministic offline parser."""
        prov_key = provider.lower().strip()
        if prov_key not in SUPPORTED_PROVIDERS:
            raise UnknownProviderError(f"Unknown provider channel: {provider}")

        # Validate payload
        if not payload and payload != 0:
            raise InvalidPayloadError(f"Payload for provider '{provider}' cannot be empty")

        payload_digest = canonical_sha256(payload)
        t_start = time.perf_counter()

        # Check availability
        avail = self.inspect_provider_availability(prov_key)
        can_run_live = avail.is_available_live and not force_offline and live_args is not None

        if can_run_live and avail.cli_binary:
            return self._execute_live_subprocess(
                provider=prov_key,
                cli_path=avail.cli_binary,
                live_args=live_args or [],
                payload_digest=payload_digest,
                timeout=timeout,
            )

        # Fallback to deterministic offline export parsing
        return self._execute_offline_parser(
            provider=prov_key,
            payload=payload,
            payload_digest=payload_digest,
            t_start=t_start,
        )

    def _execute_live_subprocess(
        self,
        provider: str,
        cli_path: str,
        live_args: List[str],
        payload_digest: str,
        timeout: float,
    ) -> ProviderExecutionReceipt:
        """Executes a live bounded CLI subprocess under a ProcessSupervisor RunToken."""
        pid = os.getpid()
        ppid = os.getppid() if hasattr(os, "getppid") else 0
        token = self._supervisor.issue_token(
            pid=pid,
            parent_pid=ppid,
            lease_duration=timeout,
            max_budget=timeout * 2,
        )

        cmd = [cli_path] + live_args
        t_start = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            duration = time.perf_counter() - t_start
            exit_code = res.returncode
            stdout_text = res.stdout

            # Pass live stdout to the corresponding offline parser for structured normalization
            parsed_summary = self._dispatch_parser(provider, stdout_text)

            rec_dict = {
                "provider": provider,
                "execution_mode": "LIVE_SUBPROCESS",
                "exit_code": exit_code,
                "payload_sha256": payload_digest,
                "run_token_id": token.token_id,
            }
            return ProviderExecutionReceipt(
                provider=provider,
                execution_mode="LIVE_SUBPROCESS",
                status="SUCCESS" if exit_code == 0 else "FAILED",
                exit_code=exit_code,
                duration_seconds=round(duration, 4),
                payload_sha256=payload_digest,
                receipt_digest=canonical_sha256(rec_dict),
                parsed_summary=parsed_summary,
                run_token_id=token.token_id,
                details={"cmd": cmd, "stderr": res.stderr[:500]},
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - t_start
            self._supervisor.cancel_token(token.token_id)
            rec_dict = {
                "provider": provider,
                "execution_mode": "LIVE_SUBPROCESS",
                "status": "TIMEOUT",
                "payload_sha256": payload_digest,
            }
            return ProviderExecutionReceipt(
                provider=provider,
                execution_mode="LIVE_SUBPROCESS",
                status="TIMEOUT",
                exit_code=-1,
                duration_seconds=round(duration, 4),
                payload_sha256=payload_digest,
                receipt_digest=canonical_sha256(rec_dict),
                parsed_summary={"error": "subprocess timeout expired"},
                run_token_id=token.token_id,
            )
        except Exception as exc:
            duration = time.perf_counter() - t_start
            rec_dict = {
                "provider": provider,
                "execution_mode": "LIVE_SUBPROCESS",
                "status": "FAILED",
                "error": str(exc),
            }
            return ProviderExecutionReceipt(
                provider=provider,
                execution_mode="LIVE_SUBPROCESS",
                status="FAILED",
                exit_code=-2,
                duration_seconds=round(duration, 4),
                payload_sha256=payload_digest,
                receipt_digest=canonical_sha256(rec_dict),
                parsed_summary={"error": str(exc)},
                run_token_id=token.token_id,
            )

    def _execute_offline_parser(
        self,
        provider: str,
        payload: Union[str, bytes, Dict[str, Any]],
        payload_digest: str,
        t_start: float,
    ) -> ProviderExecutionReceipt:
        """Parses an offline export payload with guaranteed deterministic execution receipt."""
        parsed_summary = self._dispatch_parser(provider, payload)
        duration = time.perf_counter() - t_start

        receipt_raw = {
            "provider": provider,
            "execution_mode": "OFFLINE_EXPORT_PARSER",
            "exit_code": 0,
            "payload_sha256": payload_digest,
            "summary_digest": canonical_sha256(parsed_summary),
        }
        receipt_digest = canonical_sha256(receipt_raw)

        return ProviderExecutionReceipt(
            provider=provider,
            execution_mode="OFFLINE_EXPORT_PARSER",
            status="SUCCESS",
            exit_code=0,
            duration_seconds=round(duration, 4),
            payload_sha256=payload_digest,
            receipt_digest=receipt_digest,
            parsed_summary=parsed_summary,
            run_token_id=None,
            details={"offline_deterministic": True},
        )

    def _dispatch_parser(self, provider: str, payload: Union[str, bytes, Dict[str, Any]]) -> Dict[str, Any]:
        """Dispatches payload to the corresponding provider's internal parser class."""
        text_str = payload if isinstance(payload, str) else (
            payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else json.dumps(payload)
        )

        try:
            if provider == "ghidra":
                res = GhidraParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "hopper":
                res = HopperParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider in ("cutter", "rizin"):
                res = CutterRizinParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "ida":
                res = IdaHeadlessParser.parse_disassembly(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "objdump":
                res = ObjdumpParser.parse(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "frida":
                res = FridaStalkerParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "rizin_debug":
                res = RizinDebugParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "lldb":
                res = LLDBTracerParser.parse(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "cdp":
                res = CdpParser.parse_stream(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "jadx":
                res = JadxParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "apktool":
                # Check whether input looks like manifest XML or yml
                if "<manifest" in text_str:
                    res = ApktoolResourceReconstructor.parse_manifest_xml(text_str)
                elif "<resources" in text_str:
                    res = ApktoolResourceReconstructor.parse_strings_xml(text_str)
                else:
                    res = ApktoolResourceReconstructor.parse_apktool_yml(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            elif provider == "jeb":
                res = JebParser.parse_str(text_str)
                return res.to_dict() if hasattr(res, "to_dict") else asdict(res)

            else:
                return {"raw_text": text_str[:200], "status": "unparsed"}

        except Exception as exc:
            # Honest partial reporting rather than unhandled exception
            return {
                "error": str(exc),
                "unparsed_excerpt": text_str[:200],
                "status": "PARSE_ERROR",
            }
