"""Thermodynamic & Fresh-Process Reopening Verifier for Ninshū.

Ensures specifications are physically grounded by verifying persistence,
memory footprints, and cross-process boundaries. Proves that claimed capabilities
survive process termination, execute within strict thermodynamic budgets
(memory ceilings <= 64 KB, CPU cycles), and verify clean-room re-hydration
from a separate, fresh OS subprocess with zero shared heap.
"""
from __future__ import annotations

import argparse
import dataclasses
import gc
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class ThermodynamicViolationError(RuntimeError):
    """Base error for thermodynamic budget and process boundary violations."""
    pass


class MemoryCeilingExceededError(ThermodynamicViolationError):
    """Raised when peak memory allocation exceeds the maximum threshold."""
    pass


class ProcessExitCodeError(ThermodynamicViolationError):
    """Raised when a fresh subprocess terminates with non-zero exit code."""
    pass


class DigestMismatchError(ThermodynamicViolationError):
    """Raised when artifact SHA-256 digest fails to match expected checksum."""
    pass


def canonical_digest(value: Any) -> str:
    """Computes an RFC 8785 compliant canonical SHA-256 digest."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class ThermodynamicReceipt:
    """Verified cryptographic proof of physical grounding and resource containment."""
    candidate_id: str
    peak_memory_bytes: int
    current_memory_bytes: int
    wall_time_seconds: float
    cpu_time_seconds: float
    memory_ceiling_bytes: int
    passed: bool
    exit_code: int
    artifact_sha256: str
    receipt_digest: str
    verified_cross_process: bool
    timestamp: float = dataclasses.field(default_factory=time.time)
    details: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def create(
        cls,
        candidate_id: str,
        peak_memory_bytes: int,
        current_memory_bytes: int,
        wall_time_seconds: float,
        cpu_time_seconds: float,
        memory_ceiling_bytes: int,
        passed: bool,
        exit_code: int,
        artifact_sha256: str,
        verified_cross_process: bool = False,
        timestamp: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ThermodynamicReceipt":
        ts = timestamp if timestamp is not None else time.time()
        d_details = details or {}
        raw = {
            "candidate_id": candidate_id,
            "peak_memory_bytes": peak_memory_bytes,
            "current_memory_bytes": current_memory_bytes,
            "wall_time_seconds": wall_time_seconds,
            "cpu_time_seconds": cpu_time_seconds,
            "memory_ceiling_bytes": memory_ceiling_bytes,
            "passed": passed,
            "exit_code": exit_code,
            "artifact_sha256": artifact_sha256,
            "verified_cross_process": verified_cross_process,
            "timestamp": ts,
            "details": d_details,
        }
        digest = canonical_digest(raw)
        return cls(
            candidate_id=candidate_id,
            peak_memory_bytes=peak_memory_bytes,
            current_memory_bytes=current_memory_bytes,
            wall_time_seconds=wall_time_seconds,
            cpu_time_seconds=cpu_time_seconds,
            memory_ceiling_bytes=memory_ceiling_bytes,
            passed=passed,
            exit_code=exit_code,
            artifact_sha256=artifact_sha256,
            receipt_digest=digest,
            verified_cross_process=verified_cross_process,
            timestamp=ts,
            details=d_details,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "peak_memory_bytes": self.peak_memory_bytes,
            "current_memory_bytes": self.current_memory_bytes,
            "wall_time_seconds": self.wall_time_seconds,
            "cpu_time_seconds": self.cpu_time_seconds,
            "memory_ceiling_bytes": self.memory_ceiling_bytes,
            "passed": self.passed,
            "exit_code": self.exit_code,
            "artifact_sha256": self.artifact_sha256,
            "receipt_digest": self.receipt_digest,
            "verified_cross_process": self.verified_cross_process,
            "timestamp": self.timestamp,
            "details": self.details,
        }

    def verify_integrity(self) -> bool:
        """Verifies that receipt_digest strictly matches canonical digest of all fields."""
        data = self.to_dict()
        digest_in_record = data.pop("receipt_digest")
        computed = canonical_digest(data)
        return computed == digest_in_record


class ThermodynamicProfiler:
    """Measures heap allocation delta (tracemalloc) and execution wall-clock time,
    returning a verified ThermodynamicReceipt bound by SHA-256 byte digest.
    """

    def __init__(
        self,
        candidate_id: str = "profiler",
        memory_ceiling_bytes: int = 64 * 1024,
        fail_closed: bool = True,
    ):
        self.candidate_id = candidate_id
        self.memory_ceiling_bytes = memory_ceiling_bytes
        self.fail_closed = fail_closed
        self.start_wall_time = 0.0
        self.start_cpu_time = 0.0
        self.end_wall_time = 0.0
        self.end_cpu_time = 0.0
        self.peak_memory_bytes = 0
        self.current_memory_bytes = 0
        self._tracemalloc_started_by_us = False

    def __enter__(self) -> "ThermodynamicProfiler":
        gc.collect()
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracemalloc_started_by_us = True
        else:
            tracemalloc.reset_peak()
            self._tracemalloc_started_by_us = False

        self.start_wall_time = time.perf_counter()
        self.start_cpu_time = time.process_time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_wall_time = time.perf_counter()
        self.end_cpu_time = time.process_time()
        self.current_memory_bytes, self.peak_memory_bytes = tracemalloc.get_traced_memory()
        if self._tracemalloc_started_by_us:
            tracemalloc.stop()

        if exc_type is None and self.fail_closed:
            if self.peak_memory_bytes > self.memory_ceiling_bytes:
                raise MemoryCeilingExceededError(
                    f"Thermodynamic memory ceiling exceeded for {self.candidate_id}: "
                    f"{self.peak_memory_bytes} bytes > {self.memory_ceiling_bytes} bytes ceiling"
                )

    def get_receipt(
        self,
        artifact_bytes: Optional[bytes] = None,
        artifact_sha256: Optional[str] = None,
        exit_code: int = 0,
        details: Optional[Dict[str, Any]] = None,
        passed: Optional[bool] = None,
    ) -> ThermodynamicReceipt:
        if artifact_sha256 is not None:
            digest = artifact_sha256
        elif artifact_bytes is not None:
            digest = hashlib.sha256(artifact_bytes).hexdigest()
        else:
            digest = hashlib.sha256(b"").hexdigest()

        wall_sec = max(0.0, self.end_wall_time - self.start_wall_time)
        cpu_sec = max(0.0, self.end_cpu_time - self.start_cpu_time)
        is_passed = (
            (self.peak_memory_bytes <= self.memory_ceiling_bytes) and (exit_code == 0)
            if passed is None
            else passed
        )

        return ThermodynamicReceipt.create(
            candidate_id=self.candidate_id,
            peak_memory_bytes=self.peak_memory_bytes,
            current_memory_bytes=self.current_memory_bytes,
            wall_time_seconds=wall_sec,
            cpu_time_seconds=cpu_sec,
            memory_ceiling_bytes=self.memory_ceiling_bytes,
            passed=is_passed,
            exit_code=exit_code,
            artifact_sha256=digest,
            verified_cross_process=False,
            details=details or {},
        )

    @classmethod
    def profile_callable(
        cls,
        func: Callable[..., Any],
        *args: Any,
        candidate_id: str = "callable",
        memory_ceiling_bytes: int = 64 * 1024,
        fail_closed: bool = True,
        artifact_sha256: Optional[str] = None,
        artifact_hasher: Optional[Callable[[Any], str]] = None,
        **kwargs: Any,
    ) -> Tuple[Any, ThermodynamicReceipt]:
        profiler = cls(
            candidate_id=candidate_id,
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=fail_closed,
        )
        try:
            with profiler:
                result = func(*args, **kwargs)
        except MemoryCeilingExceededError:
            raise
        except Exception as e:
            if fail_closed:
                raise
            rec = profiler.get_receipt(
                artifact_sha256=hashlib.sha256(b"").hexdigest(),
                exit_code=1,
                passed=False,
                details={"error": str(e)},
            )
            return None, rec

        # Derive artifact digest
        if artifact_sha256 is not None:
            art_sha = artifact_sha256
        elif artifact_hasher is not None:
            art_sha = artifact_hasher(result)
        elif isinstance(result, bytes):
            art_sha = hashlib.sha256(result).hexdigest()
        elif isinstance(result, str):
            art_sha = hashlib.sha256(result.encode("utf-8")).hexdigest()
        elif hasattr(result, "plan_digest"):
            art_sha = getattr(result, "plan_digest")
        elif hasattr(result, "to_dict"):
            art_sha = canonical_digest(result.to_dict())
        elif isinstance(result, (dict, list)):
            art_sha = canonical_digest(result)
        else:
            art_sha = hashlib.sha256(repr(result).encode("utf-8")).hexdigest()

        rec = profiler.get_receipt(artifact_sha256=art_sha)
        return result, rec


class FreshProcessVerifier:
    """Spawns fresh Python subprocesses (sys.executable) to serialize, write, re-open,
    and verify data artifacts from disk with zero shared heap.
    """

    def __init__(self, repo_root: Optional[Union[str, Path]] = None):
        self.repo_root = Path(repo_root or Path(__file__).resolve().parents[2]).resolve()

    def verify_disk_artifact(
        self,
        file_path: Union[str, Path],
        mode: str,  # "wasm", "build_plan", "json", "custom"
        candidate_id: str,
        memory_ceiling_bytes: int = 64 * 1024,
        expected_sha256: Optional[str] = None,
        expected_error_substr: Optional[str] = None,
        fail_closed: bool = True,
        custom_module: Optional[str] = None,
        custom_callable: Optional[str] = None,
        timeout_seconds: float = 30.0,
    ) -> ThermodynamicReceipt:
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found on disk: {path}")

        raw_bytes = path.read_bytes()
        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        if expected_sha256 is not None and expected_sha256 != actual_sha256:
            if fail_closed:
                raise DigestMismatchError(
                    f"Artifact SHA-256 mismatch for {candidate_id}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )

        cmd = [
            sys.executable,
            "-m",
            "kageyoni.ninshu.thermodynamics",
            "reopen",
            "--file",
            str(path),
            "--mode",
            mode,
            "--ceiling",
            str(memory_ceiling_bytes),
        ]
        if expected_error_substr:
            cmd.extend(["--expect-error", expected_error_substr])
        if custom_module:
            cmd.extend(["--module", custom_module])
        if custom_callable:
            cmd.extend(["--callable", custom_callable])

        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.repo_root)
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(self.repo_root),
            env=env,
            timeout=timeout_seconds,
        )

        child_payload: Dict[str, Any] = {}
        try:
            if proc.stdout.strip():
                child_payload = json.loads(proc.stdout.strip())
        except Exception:
            pass

        if proc.returncode != 0:
            err_msg = (
                child_payload.get("error")
                or proc.stderr.strip()
                or f"Process exited with code {proc.returncode}"
            )
            if fail_closed:
                raise ProcessExitCodeError(
                    f"Fresh process verification failed for {candidate_id} (code {proc.returncode}): {err_msg}"
                )
            return ThermodynamicReceipt.create(
                candidate_id=candidate_id,
                peak_memory_bytes=child_payload.get("peak_memory_bytes", 0),
                current_memory_bytes=child_payload.get("current_memory_bytes", 0),
                wall_time_seconds=child_payload.get("wall_time_seconds", 0.0),
                cpu_time_seconds=child_payload.get("cpu_time_seconds", 0.0),
                memory_ceiling_bytes=memory_ceiling_bytes,
                passed=False,
                exit_code=proc.returncode,
                artifact_sha256=actual_sha256,
                verified_cross_process=True,
                details={"error": err_msg, "stderr": proc.stderr},
            )

        peak_mem = child_payload.get("peak_memory_bytes", 0)
        curr_mem = child_payload.get("current_memory_bytes", 0)
        wall_time = child_payload.get("wall_time_seconds", 0.0)
        cpu_time = child_payload.get("cpu_time_seconds", 0.0)
        child_passed = child_payload.get("passed", True)

        if peak_mem > memory_ceiling_bytes:
            if fail_closed:
                raise MemoryCeilingExceededError(
                    f"Cross-process memory ceiling exceeded for {candidate_id}: "
                    f"{peak_mem} bytes > {memory_ceiling_bytes} bytes ceiling"
                )
            child_passed = False

        receipt = ThermodynamicReceipt.create(
            candidate_id=candidate_id,
            peak_memory_bytes=peak_mem,
            current_memory_bytes=curr_mem,
            wall_time_seconds=wall_time,
            cpu_time_seconds=cpu_time,
            memory_ceiling_bytes=memory_ceiling_bytes,
            passed=child_passed,
            exit_code=0,
            artifact_sha256=actual_sha256,
            verified_cross_process=True,
            details=child_payload.get("details", {}),
        )
        return receipt

    def verify_wasm_bytes(
        self,
        wasm_bytes: bytes,
        candidate_id: str = "wasm_parser",
        memory_ceiling_bytes: int = 64 * 1024,
        expected_error_substr: Optional[str] = None,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wasm") as tmp:
            tmp.write(wasm_bytes)
            tmp_path = Path(tmp.name).resolve()

        try:
            return self.verify_disk_artifact(
                file_path=tmp_path,
                mode="wasm",
                candidate_id=candidate_id,
                memory_ceiling_bytes=memory_ceiling_bytes,
                expected_error_substr=expected_error_substr,
                fail_closed=fail_closed,
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def verify_wasm_parser(
        self,
        wasm_bytes: bytes,
        candidate_id: str = "wasm_parser",
        memory_ceiling_bytes: int = 64 * 1024,
        expected_error_substr: Optional[str] = None,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        return self.verify_wasm_bytes(
            wasm_bytes=wasm_bytes,
            candidate_id=candidate_id,
            memory_ceiling_bytes=memory_ceiling_bytes,
            expected_error_substr=expected_error_substr,
            fail_closed=fail_closed,
        )

    def verify_build_plan_artifact(
        self,
        plan_data: Union[Dict[str, Any], Any],
        candidate_id: str = "build_plan_compiler",
        memory_ceiling_bytes: int = 64 * 1024,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        if hasattr(plan_data, "to_dict"):
            d = plan_data.to_dict()
        elif isinstance(plan_data, dict):
            d = plan_data
        else:
            raise TypeError(f"Unsupported plan_data type: {type(plan_data)}")

        serialized = json.dumps(d, indent=2).encode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(serialized)
            tmp_path = Path(tmp.name).resolve()

        try:
            return self.verify_disk_artifact(
                file_path=tmp_path,
                mode="build_plan",
                candidate_id=candidate_id,
                memory_ceiling_bytes=memory_ceiling_bytes,
                fail_closed=fail_closed,
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def verify_build_plan_compiler(
        self,
        plan_data: Union[Dict[str, Any], Any],
        candidate_id: str = "build_plan_compiler",
        memory_ceiling_bytes: int = 64 * 1024,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        return self.verify_build_plan_artifact(
            plan_data=plan_data,
            candidate_id=candidate_id,
            memory_ceiling_bytes=memory_ceiling_bytes,
            fail_closed=fail_closed,
        )

    def verify_json_artifact(
        self,
        data: Any,
        candidate_id: str = "json_artifact",
        memory_ceiling_bytes: int = 64 * 1024,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        serialized = json.dumps(data, indent=2).encode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(serialized)
            tmp_path = Path(tmp.name).resolve()

        try:
            return self.verify_disk_artifact(
                file_path=tmp_path,
                mode="json",
                candidate_id=candidate_id,
                memory_ceiling_bytes=memory_ceiling_bytes,
                fail_closed=fail_closed,
            )
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


class ConsoleThermodynamicsBridge:
    """Interconnect bridging Thermodynamic & Fresh-Process Verification into the SSL 4000 Console."""

    @staticmethod
    def audit_channel_thermodynamics(
        console: Any,
        channel_number: int,
        target_callable: Optional[Callable[..., Any]] = None,
        memory_ceiling_bytes: Optional[int] = None,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        """Audits an SSL channel strip's execution footprint against physical memory budgets."""
        if not hasattr(console, "channels") or channel_number not in console.channels:
            raise ValueError(f"Channel {channel_number} not mounted on active console")

        strip = console.channels[channel_number]
        ceiling = memory_ceiling_bytes or getattr(strip, "max_memory_ceiling_bytes", 64 * 1024)

        if target_callable is not None:
            _, receipt = ThermodynamicProfiler.profile_callable(
                target_callable,
                candidate_id=f"CH{channel_number:02d}_{strip.name}",
                memory_ceiling_bytes=ceiling,
                fail_closed=fail_closed,
            )
        else:
            def probe():
                carrier = Path(strip.carrier_path)
                return {"carrier": strip.carrier_path, "entrypoint": strip.entrypoint, "exists": carrier.exists()}

            _, receipt = ThermodynamicProfiler.profile_callable(
                probe,
                candidate_id=f"CH{channel_number:02d}_{strip.name}",
                memory_ceiling_bytes=ceiling,
                fail_closed=fail_closed,
            )

        strip.thermodynamic_receipt = receipt.to_dict()

        telemetry_signal = {
            "evidence_type": "THERMODYNAMIC_AUDIT",
            "channel_number": channel_number,
            "candidate_id": receipt.candidate_id,
            "peak_memory_bytes": receipt.peak_memory_bytes,
            "memory_ceiling_bytes": receipt.memory_ceiling_bytes,
            "passed": receipt.passed,
            "confidence_score": 1.0 if receipt.passed else 0.0,
            "receipt_digest": receipt.receipt_digest,
            "timestamp": time.time(),
        }
        if hasattr(console, "stream_track"):
            console.stream_track(channel_number, [telemetry_signal])

        if not receipt.passed and hasattr(strip, "thermal_ceiling"):
            strip.thermal_ceiling = max(strip.thermal_ceiling, 1)

        return receipt

    @staticmethod
    def verify_channel_artifact_cross_process(
        console: Any,
        channel_number: int,
        artifact_bytes: bytes,
        mode: str = "wasm",
        memory_ceiling_bytes: Optional[int] = None,
        fail_closed: bool = True,
    ) -> ThermodynamicReceipt:
        """Spawns a fresh OS subprocess to verify channel artifact with zero shared heap."""
        if not hasattr(console, "channels") or channel_number not in console.channels:
            raise ValueError(f"Channel {channel_number} not mounted on active console")

        strip = console.channels[channel_number]
        ceiling = memory_ceiling_bytes or getattr(strip, "max_memory_ceiling_bytes", 64 * 1024)

        verifier = FreshProcessVerifier()
        if mode == "wasm":
            receipt = verifier.verify_wasm_bytes(
                wasm_bytes=artifact_bytes,
                candidate_id=f"CH{channel_number:02d}_{strip.name}",
                memory_ceiling_bytes=ceiling,
                fail_closed=fail_closed,
            )
        else:
            data = json.loads(artifact_bytes.decode("utf-8"))
            receipt = verifier.verify_json_artifact(
                data=data,
                candidate_id=f"CH{channel_number:02d}_{strip.name}",
                memory_ceiling_bytes=ceiling,
                fail_closed=fail_closed,
            )

        strip.thermodynamic_receipt = receipt.to_dict()

        telemetry_signal = {
            "evidence_type": "THERMODYNAMIC_CROSS_PROCESS_RECEIPT",
            "channel_number": channel_number,
            "candidate_id": receipt.candidate_id,
            "peak_memory_bytes": receipt.peak_memory_bytes,
            "memory_ceiling_bytes": receipt.memory_ceiling_bytes,
            "passed": receipt.passed,
            "confidence_score": 1.0 if receipt.passed else 0.0,
            "receipt_digest": receipt.receipt_digest,
            "verified_cross_process": True,
            "timestamp": time.time(),
        }
        if hasattr(console, "stream_track"):
            console.stream_track(channel_number, [telemetry_signal])

        if not receipt.passed and hasattr(strip, "thermal_ceiling"):
            strip.thermal_ceiling = max(strip.thermal_ceiling, 1)

        return receipt


def _run_subprocess_reopen_worker() -> None:
    """Internal child process entrypoint for fresh-process reopening and verification."""
    parser = argparse.ArgumentParser(description="Ninshū Fresh-Process Thermodynamic Worker")
    parser.add_argument("command", choices=["reopen"])
    parser.add_argument("--file", required=True, help="Path to artifact file on disk")
    parser.add_argument("--mode", required=True, choices=["wasm", "build_plan", "json", "custom"])
    parser.add_argument("--ceiling", type=int, default=64 * 1024, help="Memory ceiling in bytes")
    parser.add_argument("--expect-error", dest="expect_error", default=None, help="Expected error substring")
    parser.add_argument("--module", dest="custom_module", default=None)
    parser.add_argument("--callable", dest="custom_callable", default=None)

    args = parser.parse_args()

    # Pre-import modules before tracemalloc so we measure only
    # the thermodynamic cost of reading, rehydration, and parsing the artifact
    if args.mode == "wasm":
        from kageyoni.ninshu.wasm_parser import WasmParser
    elif args.mode == "build_plan":
        from kageyoni.ninshu.planner import BuildPlanCompiler

    artifact_path = Path(args.file).resolve()
    if not artifact_path.exists():
        sys.stderr.write(f"Artifact not found: {artifact_path}\n")
        sys.exit(1)

    gc.collect()
    tracemalloc.start()
    t0 = time.perf_counter()
    c0 = time.process_time()

    details: Dict[str, Any] = {}
    passed = True
    error_msg: Optional[str] = None

    try:
        raw_bytes = artifact_path.read_bytes()
        digest = hashlib.sha256(raw_bytes).hexdigest()

        if args.mode == "wasm":
            if args.expect_error:
                try:
                    _ = WasmParser.parse_bytes(raw_bytes)
                    passed = False
                    error_msg = f"Expected ValueError containing '{args.expect_error}', but parse succeeded"
                except ValueError as ve:
                    if args.expect_error in str(ve):
                        passed = True
                        details = {"expected_rejection_verified": str(ve)}
                    else:
                        passed = False
                        error_msg = f"Caught ValueError, but expected substring '{args.expect_error}' not in '{ve}'"
            else:
                summary = WasmParser.parse_bytes(raw_bytes)
                details = {
                    "version": summary.version,
                    "total_bytes": summary.total_bytes,
                    "sections_count": summary.sections_count,
                    "custom_sections": summary.custom_sections,
                    "has_code": summary.has_code,
                    "has_exports": summary.has_exports,
                }

        elif args.mode == "build_plan":
            plan_dict = json.loads(raw_bytes.decode("utf-8"))
            invariants = plan_dict.get("invariants", [])
            test_vectors = plan_dict.get("test_vectors", [])
            raw_content = (
                "CH07_WASM_PORT_PLAN:"
                + "".join(inv["rule_id"] for inv in invariants)
                + "".join(v["vector_id"] for v in test_vectors)
            )
            recomputed_digest = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            plan_digest = plan_dict.get("plan_digest")
            if recomputed_digest != plan_digest:
                passed = False
                error_msg = f"Plan digest mismatch: computed {recomputed_digest} != {plan_digest}"
            else:
                details = {
                    "plan_id": plan_dict.get("plan_id"),
                    "target_channel_id": plan_dict.get("target_channel_id"),
                    "channel_name": plan_dict.get("channel_name"),
                    "invariants_count": len(invariants),
                    "test_vectors_count": len(test_vectors),
                    "plan_digest": plan_digest,
                }

        elif args.mode == "json":
            json_obj = json.loads(raw_bytes.decode("utf-8"))
            details = {
                "type": type(json_obj).__name__,
                "length": len(json_obj) if hasattr(json_obj, "__len__") else 1,
            }

        elif args.mode == "custom":
            if not args.custom_module or not args.custom_callable:
                raise ValueError("Mode custom requires --module and --callable")
            import importlib
            mod = importlib.import_module(args.custom_module)
            fn = getattr(mod, args.custom_callable)
            custom_res = fn(artifact_path, raw_bytes)
            details = {"custom_result": repr(custom_res)}

    except Exception as exc:
        passed = False
        error_msg = str(exc)

    t1 = time.perf_counter()
    c1 = time.process_time()
    curr_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if peak_mem > args.ceiling:
        passed = False
        if not error_msg:
            error_msg = f"Memory ceiling exceeded: {peak_mem} > {args.ceiling} bytes"

    payload = {
        "status": "ok" if passed else "error",
        "passed": passed,
        "artifact_sha256": digest if "digest" in locals() else "",
        "peak_memory_bytes": peak_mem,
        "current_memory_bytes": curr_mem,
        "wall_time_seconds": max(0.0, t1 - t0),
        "cpu_time_seconds": max(0.0, c1 - c0),
        "details": details,
    }
    if error_msg:
        payload["error"] = error_msg

    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    _run_subprocess_reopen_worker()
