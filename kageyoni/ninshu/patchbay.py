"""Ninshū Patchbay & Query Engine.

Provides instant FTS5 / multi-axis routing over the 48-channel desk.
Used by situated Daimons to retrieve exact channel strips on-demand
without loading the whole estate into LLM context.
Also provides live callable resolution, execution, and patch composition
under strict thermodynamic budgets (heap <= 64KB).
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import inspect
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .schema import init_db
from .seeds import BUSSES, CHANNELS, digest_record
from .thermodynamics import ThermodynamicProfiler, canonical_digest

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "ninshu_codex.sqlite"


class ExecutionResult(dict):
    """Result of a channel strip execution, supporting both dict indexing and attribute access."""

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        res = self.get("result")
        if res is not None and hasattr(res, name):
            return getattr(res, name)
        raise AttributeError(f"'ExecutionResult' object has no attribute {name!r}")

    def __getitem__(self, key: Any) -> Any:
        if key in self:
            return super().__getitem__(key)
        res = self.get("result")
        if res is not None and isinstance(res, dict) and key in res:
            return res[key]
        return super().__getitem__(key)


def compute_seeds_digest() -> str:
    """Computes deterministic canonical SHA-256 hash of all seed busses and channels."""
    blob = json.dumps(
        {"busses": BUSSES, "channels": CHANNELS},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Patchbay:
    """The SSL 4000 Patchbay for Kageyōni and REA."""

    def __init__(self, db_path: Optional[str | Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        is_new = not self.db_path.exists()
        self.conn = init_db(self.db_path)
        
        # Ensure schema_meta table exists for tracking seed hash
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        
        current_seeds_hash = compute_seeds_digest()
        stored_seeds_hash = self._get_meta("seeds_digest")

        if is_new or stored_seeds_hash != current_seeds_hash or self._channel_count() == 0:
            self.seed()
            self._set_meta("seeds_digest", current_seeds_hash)

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

    def __enter__(self) -> "Patchbay":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def _get_meta(self, key: str) -> Optional[str]:
        cur = self.conn.execute("SELECT value FROM schema_meta WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def _channel_count(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM channels")
        return cur.fetchone()[0]

    def seed(self) -> None:
        """Seeds the database with the 6 Busses and 48 Channels."""
        with self.conn:
            # Seed Busses
            for b in BUSSES:
                self.conn.execute(
                    "INSERT OR REPLACE INTO busses (bus_id, name, description, channel_range) VALUES (?, ?, ?, ?)",
                    (b["bus_id"], b["name"], b["description"], b["channel_range"]),
                )

            # Seed Channels
            for c in CHANNELS:
                digest = digest_record(c)
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO channels (
                        channel_number, bus_id, name, category, description,
                        carrier_path, entrypoint, subject_formats, lens_family,
                        effects_json, reversibility_tier, epistemic_confidence,
                        coverage_status, output_mold, intent_keywords, digest_sha256
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["channel_number"],
                        c["bus_id"],
                        c["name"],
                        c["category"],
                        c["description"],
                        c["carrier_path"],
                        c["entrypoint"],
                        json.dumps(c["subject_formats"]),
                        c["lens_family"],
                        json.dumps(c["effects"]),
                        c["reversibility_tier"],
                        c["epistemic_confidence"],
                        c["coverage_status"],
                        c["output_mold"],
                        c["intent_keywords"],
                        digest,
                    ),
                )

    def get_busses(self) -> List[Dict[str, Any]]:
        """Returns all 6 Master Busses."""
        rows = self.conn.execute("SELECT * FROM busses ORDER BY bus_id").fetchall()
        return [dict(r) for r in rows]

    def get_channel(self, channel_number: int) -> Optional[Dict[str, Any]]:
        """Returns a single channel strip by channel number."""
        row = self.conn.execute(
            "SELECT * FROM channels WHERE channel_number = ?", (channel_number,)
        ).fetchone()
        if not row:
            return None
        res = dict(row)
        res["subject_formats"] = json.loads(res["subject_formats"])
        res["effects"] = json.loads(res["effects_json"])
        return res

    def list_channels(self, bus_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all channels, optionally filtered by bus."""
        query = "SELECT * FROM channels"
        params: list[Any] = []
        if bus_id:
            query += " WHERE bus_id = ?"
            params.append(bus_id)
        query += " ORDER BY channel_number"
        rows = self.conn.execute(query, params).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["subject_formats"] = json.loads(d["subject_formats"])
            d["effects"] = json.loads(d["effects_json"])
            res.append(d)
        return res

    def route(
        self,
        intent: str,
        subject: Optional[str] = None,
        max_tier: int = 2,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Routes a natural language intent or technical keyword to the optimal channel strips.

        Filters by subject format compatibility and reversibility tier.
        """
        # Clean intent tokens for FTS5
        clean_tokens = [
            w for w in intent.lower().replace(":", " ").replace("-", " ").split() if len(w) >= 2
        ]
        if not clean_tokens:
            return []

        fts_query = " OR ".join(f'"{t}"' for t in clean_tokens)

        sql = """
        SELECT c.*, rank
        FROM channels c
        JOIN channels_fts fts ON c.channel_number = fts.rowid
        WHERE channels_fts MATCH ?
          AND c.reversibility_tier <= ?
        ORDER BY rank
        LIMIT ?
        """
        rows = self.conn.execute(sql, (fts_query, max_tier, limit * 2)).fetchall()

        matched: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["subject_formats"] = json.loads(d["subject_formats"])
            d["effects"] = json.loads(d["effects_json"])

            # Filter by subject if specified
            if (
                subject
                and subject.lower() not in [s.lower() for s in d["subject_formats"]]
                and "file" not in d["subject_formats"]
            ):
                continue

            matched.append(d)
            if len(matched) >= limit:
                break

        return matched

    def patch(
        self, channel_numbers: List[int], daimon_name: str = "ad_hoc_submix"
    ) -> Dict[str, Any]:
        """Builds a multi-track Ninshū Sub-Mix Patch from a list of channel numbers.

        Returns the runnable wiring manifest without code duplication.
        """
        strips = []
        for ch in channel_numbers:
            strip = self.get_channel(ch)
            if strip:
                strips.append(strip)

        max_tier = max((s["reversibility_tier"] for s in strips), default=0)

        return {
            "patch_id": f"patch:{daimon_name}",
            "channel_count": len(strips),
            "reversibility_tier": max_tier,
            "requires_human_gate": max_tier > 0,
            "channel_strips": [
                {
                    "ch": s["channel_number"],
                    "name": s["name"],
                    "bus": s["bus_id"],
                    "carrier": s["carrier_path"],
                    "entrypoint": s["entrypoint"],
                    "authority": s["epistemic_confidence"],
                    "tier": s["reversibility_tier"],
                }
                for s in strips
            ],
        }

    def resolve_callable(self, channel_number: int) -> Callable:
        """Dynamically loads and returns the real callable entrypoint for a channel.

        If the target entrypoint is an instance method, instantiates the class
        with default arguments and returns the bound method.
        """
        strip = self.get_channel(channel_number)
        if not strip:
            raise ValueError(f"Channel {channel_number} not found in Patchbay")

        carrier_path = strip["carrier_path"]
        entrypoint = strip["entrypoint"]

        # Ensure workspace root is in sys.path
        workspace_root = str(Path(__file__).resolve().parents[2])
        if workspace_root not in sys.path:
            sys.path.insert(0, workspace_root)

        # Derive module name
        if carrier_path.endswith(".py"):
            mod_name = carrier_path[:-3].replace("/", ".").replace("\\", ".")
        else:
            mod_name = carrier_path.replace("/", ".").replace("\\", ".")

        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            # Fallback to direct spec loading from disk
            carrier_file = Path(carrier_path)
            if not carrier_file.is_absolute():
                candidate = Path(workspace_root) / carrier_file
                if candidate.exists():
                    carrier_file = candidate
            if not carrier_file.exists():
                raise FileNotFoundError(f"Carrier file not found: {carrier_path}")

            spec = importlib.util.spec_from_file_location(mod_name, str(carrier_file))
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load module spec for {carrier_file}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)

        parts = entrypoint.split(".")
        if len(parts) == 1:
            fn_name = parts[0]
            if not hasattr(mod, fn_name):
                raise AttributeError(f"Module '{mod_name}' has no attribute '{fn_name}'")
            return getattr(mod, fn_name)
        elif len(parts) == 2:
            cls_name, meth_name = parts[0], parts[1]
            if not hasattr(mod, cls_name):
                raise AttributeError(f"Module '{mod_name}' has no class '{cls_name}'")
            cls_obj = getattr(mod, cls_name)
            if not hasattr(cls_obj, meth_name):
                raise AttributeError(f"Class '{cls_name}' has no method '{meth_name}'")

            raw_attr = cls_obj.__dict__.get(meth_name)
            if isinstance(raw_attr, (classmethod, staticmethod)):
                return getattr(cls_obj, meth_name)

            attr = getattr(cls_obj, meth_name)
            if inspect.isfunction(attr):
                params = list(inspect.signature(attr).parameters.values())
                if params and params[0].name == "self":
                    # Instance method: instantiate class with default arguments
                    instance = cls_obj()
                    return getattr(instance, meth_name)
            return attr
        else:
            raise ValueError(f"Unsupported entrypoint format: {entrypoint}")

    def _compute_payload_digest(self, payload: Any) -> str:
        """Computes deterministic canonical SHA-256 digest of arbitrary payload."""
        if isinstance(payload, (bytes, bytearray)):
            return hashlib.sha256(payload).hexdigest()
        if isinstance(payload, str):
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()
        try:
            if hasattr(payload, "digest") and callable(payload.digest):
                d = payload.digest()
                if isinstance(d, str) and len(d) == 64:
                    return d
            if hasattr(payload, "to_dict") and callable(payload.to_dict):
                payload = payload.to_dict()
            canonical = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
            )
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        except Exception:
            return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()

    def execute_channel(
        self,
        channel_number: int,
        payload: Any,
        *,
        console: Optional[Any] = None,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        """Runs the callable under ThermodynamicProfiler.

        Enforces peak heap <= 64KB, computes input/output SHA-256 hashes,
        latency, and returns structured result.
        """
        strip = self.get_channel(channel_number)
        if not strip:
            raise ValueError(f"Channel {channel_number} not found in Patchbay")

        input_sha256 = self._compute_payload_digest(payload)
        target_fn = self.resolve_callable(channel_number)

        max_memory = 64 * 1024
        if console and hasattr(console, "channels") and channel_number in console.channels:
            cfg = console.channels[channel_number]
            if hasattr(cfg, "max_memory_ceiling_bytes") and cfg.max_memory_ceiling_bytes:
                max_memory = cfg.max_memory_ceiling_bytes
            if getattr(cfg, "mute", False):
                return {
                    "channel_number": channel_number,
                    "channel_name": strip["name"],
                    "status": "muted",
                    "input_sha256": input_sha256,
                    "output_sha256": hashlib.sha256(b"").hexdigest(),
                    "result": None,
                    "latency_seconds": 0.0,
                    "cpu_time_seconds": 0.0,
                    "peak_memory_bytes": 0,
                    "thermodynamic_passed": True,
                    "thermodynamic_receipt": None,
                }

        profiler = ThermodynamicProfiler(
            candidate_id=f"channel_{channel_number:02d}",
            memory_ceiling_bytes=max_memory,
            fail_closed=fail_closed,
        )

        try:
            with profiler:
                result = target_fn(payload)
        except Exception as exc:
            output_sha256 = hashlib.sha256(b"").hexdigest()
            receipt = profiler.get_receipt(
                artifact_sha256=output_sha256,
                exit_code=1,
                passed=False,
                details={"error": str(exc)},
            )
            if fail_closed:
                raise
            return ExecutionResult({
                "channel_number": channel_number,
                "channel_name": strip["name"],
                "status": "error",
                "error": str(exc),
                "input_sha256": input_sha256,
                "output_sha256": output_sha256,
                "result": None,
                "latency_seconds": receipt.wall_time_seconds,
                "cpu_time_seconds": receipt.cpu_time_seconds,
                "peak_memory_bytes": receipt.peak_memory_bytes,
                "thermodynamic_passed": False,
                "thermodynamic_receipt": receipt.to_dict(),
            })

        output_sha256 = self._compute_payload_digest(result)
        receipt = profiler.get_receipt(
            artifact_sha256=output_sha256,
            exit_code=0,
            passed=True,
        )

        if console and hasattr(console, "channels") and channel_number in console.channels:
            console.channels[channel_number].thermodynamic_receipt = receipt.to_dict()

        return ExecutionResult({
            "channel_number": channel_number,
            "channel_name": strip["name"],
            "status": "success",
            "input_sha256": input_sha256,
            "output_sha256": output_sha256,
            "result": result,
            "latency_seconds": receipt.wall_time_seconds,
            "cpu_time_seconds": receipt.cpu_time_seconds,
            "peak_memory_bytes": receipt.peak_memory_bytes,
            "thermodynamic_passed": receipt.passed,
            "thermodynamic_receipt": receipt.to_dict(),
        })

    def execute_patch(
        self,
        channel_numbers: List[int],
        initial_payload: Any,
        *,
        mode: str = "parallel",
        console: Optional[Any] = None,
        fail_closed: bool = True,
    ) -> Dict[str, Any]:
        """Executes a multi-channel patch across selected channel strips.

        Modes:
        - 'parallel': Broadcasts initial_payload to all channels simultaneously.
        - 'serial': Cascades execution where output of channel N feeds into channel N+1.
        """
        if mode not in ("parallel", "serial"):
            raise ValueError(
                f"Unsupported patch execution mode: {mode}. Must be 'parallel' or 'serial'."
            )
        if not channel_numbers:
            raise ValueError("channel_numbers list cannot be empty")

        results: List[Dict[str, Any]] = []

        if mode == "serial":
            current_input = initial_payload
            for ch in channel_numbers:
                res = self.execute_channel(
                    ch, current_input, console=console, fail_closed=fail_closed
                )
                results.append(res)
                current_input = res["result"]
            final_output = current_input
        else:  # parallel
            for ch in channel_numbers:
                res = self.execute_channel(
                    ch, initial_payload, console=console, fail_closed=fail_closed
                )
                results.append(res)
            final_output = {r["channel_number"]: r["result"] for r in results}

        all_passed = all(r.get("thermodynamic_passed", False) for r in results)
        total_latency = sum(r.get("latency_seconds", 0.0) for r in results)

        return {
            "patch_id": f"patch:{mode}:{'_'.join(str(c) for c in channel_numbers)}",
            "mode": mode,
            "channel_count": len(results),
            "channels_executed": channel_numbers,
            "all_thermodynamic_passed": all_passed,
            "total_latency_seconds": total_latency,
            "final_output": final_output,
            "step_results": results,
        }
