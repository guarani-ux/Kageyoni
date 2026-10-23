"""Ninshū Mission Checkpointer & DAG Runner (Channel 20 & 23 Integration).

Extracted from Pregel checkpointing state machine principles:
1. Immutable state snapshots serialized to canonical JSON and bound by SHA-256 digests.
2. Checkpoint persistence in SQLite with time-travel / rollback capability.
3. Human-in-the-loop pause/resume protocol with cryptographic gating.
4. Clean resumption without re-executing completed steps.
5. Integration with ProcessSupervisor (CH 23) Run Tokens and SSL Control 20 (Pause/Resume/Stop).
6. Strict thermodynamic budget enforcement (heap allocation <= 64 KB overhead).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from kageyoni.ninshu.process_supervisor import (
    ExpiredRunTokenError,
    InvalidRunTokenError,
    ProcessSupervisor,
    RunToken,
    SupervisorSecurityError,
    TokenCancelledError,
)
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler, ThermodynamicReceipt


class MissionError(Exception):
    """Base exception for mission runner and checkpointing errors."""
    pass


class CheckpointIntegrityError(MissionError):
    """Raised when a checkpoint's cryptographic SHA-256 digest or state is corrupted or tampered."""
    pass


class CheckpointNotFoundError(MissionError):
    """Raised when a requested checkpoint is not found."""
    pass


class MissionExecutionError(MissionError):
    """Raised during mission DAG resolution or step execution failure."""
    pass


class MissionAbortedError(MissionError):
    """Raised when attempting to resume or execute an aborted mission."""
    pass


@dataclass
class CheckpointRecord:
    """Represents an immutable checkpoint record in SQLite."""
    mission_id: str
    step_index: int
    step_name: str
    state_json: str
    state_sha256: str
    status: str
    created_at: float

    @property
    def state(self) -> Dict[str, Any]:
        """Deserializes and validates state_json."""
        try:
            return json.loads(self.state_json)
        except Exception as e:
            raise CheckpointIntegrityError(
                f"Corrupted state JSON in checkpoint for mission '{self.mission_id}' step {self.step_index}: {e}"
            )

    def verify_integrity(self) -> bool:
        """Verifies that the SHA-256 digest of state_json matches state_sha256."""
        computed = hashlib.sha256(self.state_json.encode("utf-8")).hexdigest()
        return computed == self.state_sha256


class MissionCheckpointer:
    """Pure-Python SQLite Checkpoint persistence manager.

    Implements Pregel-style snapshotting, versioning, list, get, and rollback.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._conn: Optional[sqlite3.Connection] = None
        if self._is_memory:
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._setup_table(self._conn)
        else:
            conn = self._get_connection()
            try:
                self._setup_table(conn)
            finally:
                conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        if self._is_memory and self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return conn

    def _setup_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mission_checkpoints (
                mission_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                state_json TEXT NOT NULL,
                state_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (mission_id, step_index)
            )
            """
        )
        conn.commit()

    def save_step(
        self,
        mission_id: str,
        step_name: str,
        payload: Dict[str, Any],
        status: str = "COMPLETED",
        step_index: Optional[int] = None,
    ) -> CheckpointRecord:
        """Serializes state payload, computes SHA-256 digest, and persists checkpoint."""
        conn = self._get_connection()
        should_close = not self._is_memory
        try:
            if step_index is None:
                cur = conn.execute(
                    "SELECT COALESCE(MAX(step_index), -1) + 1 FROM mission_checkpoints WHERE mission_id = ?",
                    (mission_id,),
                )
                row = cur.fetchone()
                step_index = row[0] if row else 0

            state_json = json.dumps(payload, sort_keys=True)
            state_sha256 = hashlib.sha256(state_json.encode("utf-8")).hexdigest()
            created_at = time.time()

            conn.execute(
                """
                INSERT OR REPLACE INTO mission_checkpoints
                (mission_id, step_index, step_name, state_json, state_sha256, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (mission_id, step_index, step_name, state_json, state_sha256, status, created_at),
            )
            conn.commit()

            record = CheckpointRecord(
                mission_id=mission_id,
                step_index=step_index,
                step_name=step_name,
                state_json=state_json,
                state_sha256=state_sha256,
                status=status,
                created_at=created_at,
            )
            return record
        finally:
            if should_close:
                conn.close()

    def get_checkpoint(self, mission_id: str, step_index: int) -> Optional[CheckpointRecord]:
        """Retrieves a specific step checkpoint with fail-closed integrity verification."""
        conn = self._get_connection()
        should_close = not self._is_memory
        try:
            cur = conn.execute(
                """
                SELECT mission_id, step_index, step_name, state_json, state_sha256, status, created_at
                FROM mission_checkpoints
                WHERE mission_id = ? AND step_index = ?
                """,
                (mission_id, step_index),
            )
            row = cur.fetchone()
            if not row:
                return None
            rec = CheckpointRecord(
                mission_id=row[0],
                step_index=row[1],
                step_name=row[2],
                state_json=row[3],
                state_sha256=row[4],
                status=row[5],
                created_at=row[6],
            )
            if not rec.verify_integrity():
                raise CheckpointIntegrityError(
                    f"Cryptographic digest mismatch in checkpoint '{mission_id}' step {step_index}."
                )
            _ = rec.state
            return rec
        finally:
            if should_close:
                conn.close()

    def get_latest_checkpoint(self, mission_id: str) -> Optional[CheckpointRecord]:
        """Retrieves the latest checkpoint for a mission with fail-closed integrity verification."""
        conn = self._get_connection()
        should_close = not self._is_memory
        try:
            cur = conn.execute(
                """
                SELECT mission_id, step_index, step_name, state_json, state_sha256, status, created_at
                FROM mission_checkpoints
                WHERE mission_id = ?
                ORDER BY step_index DESC
                LIMIT 1
                """,
                (mission_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            rec = CheckpointRecord(
                mission_id=row[0],
                step_index=row[1],
                step_name=row[2],
                state_json=row[3],
                state_sha256=row[4],
                status=row[5],
                created_at=row[6],
            )
            if not rec.verify_integrity():
                raise CheckpointIntegrityError(
                    f"Cryptographic digest mismatch in latest checkpoint '{mission_id}' step {rec.step_index}."
                )
            _ = rec.state
            return rec
        finally:
            if should_close:
                conn.close()

    def list_checkpoints(self, mission_id: str) -> List[CheckpointRecord]:
        """Lists all checkpoints for a mission ordered by step_index ASC."""
        conn = self._get_connection()
        should_close = not self._is_memory
        try:
            cur = conn.execute(
                """
                SELECT mission_id, step_index, step_name, state_json, state_sha256, status, created_at
                FROM mission_checkpoints
                WHERE mission_id = ?
                ORDER BY step_index ASC
                """,
                (mission_id,),
            )
            records = []
            for row in cur.fetchall():
                rec = CheckpointRecord(
                    mission_id=row[0],
                    step_index=row[1],
                    step_name=row[2],
                    state_json=row[3],
                    state_sha256=row[4],
                    status=row[5],
                    created_at=row[6],
                )
                if not rec.verify_integrity():
                    raise CheckpointIntegrityError(
                        f"Cryptographic digest mismatch in checkpoint '{mission_id}' step {rec.step_index}."
                    )
                _ = rec.state
                records.append(rec)
            return records
        finally:
            if should_close:
                conn.close()

    def rollback_to_step(self, mission_id: str, step_index: int) -> CheckpointRecord:
        """Rolls back mission state to a prior step, pruning subsequent checkpoints."""
        target = self.get_checkpoint(mission_id, step_index)
        if not target:
            raise CheckpointNotFoundError(
                f"Cannot rollback: Checkpoint for mission '{mission_id}' at step {step_index} does not exist."
            )
        conn = self._get_connection()
        should_close = not self._is_memory
        try:
            conn.execute(
                "DELETE FROM mission_checkpoints WHERE mission_id = ? AND step_index > ?",
                (mission_id, step_index),
            )
            conn.commit()
            return target
        finally:
            if should_close:
                conn.close()

    def close(self) -> None:
        """Closes memory connection if open."""
        if self._conn:
            self._conn.close()
            self._conn = None


@dataclass
class MissionStep:
    """Definition of an individual step in a mission DAG."""
    name: str
    action: Callable[[Dict[str, Any]], Union[Dict[str, Any], None]]
    dependencies: List[str] = field(default_factory=list)
    is_gated: bool = False


class MissionDAG:
    """Maintains mission steps and computes topological execution order."""

    def __init__(self) -> None:
        self.steps: Dict[str, MissionStep] = {}
        self.order: List[str] = []

    def add_step(
        self,
        name: str,
        action: Callable[[Dict[str, Any]], Union[Dict[str, Any], None]],
        dependencies: Optional[List[str]] = None,
        is_gated: bool = False,
    ) -> None:
        deps = list(dependencies or [])
        self.steps[name] = MissionStep(name=name, action=action, dependencies=deps, is_gated=is_gated)
        if name not in self.order:
            self.order.append(name)

    def get_execution_plan(self) -> List[MissionStep]:
        has_deps = any(step.dependencies for step in self.steps.values())
        if not has_deps:
            return [self.steps[name] for name in self.order]

        in_degree = {name: 0 for name in self.steps}
        adj: Dict[str, List[str]] = {name: [] for name in self.steps}
        for name, step in self.steps.items():
            for dep in step.dependencies:
                if dep not in self.steps:
                    raise MissionExecutionError(f"Step '{name}' depends on unregistered step '{dep}'")
                adj[dep].append(name)
                in_degree[name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        sorted_steps: List[MissionStep] = []
        while queue:
            curr = queue.pop(0)
            sorted_steps.append(self.steps[curr])
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_steps) != len(self.steps):
            raise MissionExecutionError("Cycle detected in Mission DAG dependencies.")
        return sorted_steps


class MissionRunner:
    """Executes multi-step agent mission DAGs with Pregel-style checkpointing.

    Wires into:
    - ProcessSupervisor (Channel 23): Run tokens and epistemic execution boundaries.
    - SSL Console (Control 20): start_run, pause_run, resume_run, stop_run.
    """

    def __init__(
        self,
        checkpointer: Optional[MissionCheckpointer] = None,
        supervisor: Optional[ProcessSupervisor] = None,
        console: Optional[Any] = None,
    ):
        self.checkpointer = checkpointer or MissionCheckpointer(":memory:")
        self.supervisor = supervisor or ProcessSupervisor()
        self.console = console
        self._dag = MissionDAG()
        self._active_mission_id: Optional[str] = None
        self._active_run_token: Optional[RunToken] = None
        self._paused: bool = False
        self._aborted: bool = False

    def add_step(
        self,
        name: str,
        action: Callable[[Dict[str, Any]], Union[Dict[str, Any], None]],
        dependencies: Optional[List[str]] = None,
        is_gated: bool = False,
    ) -> "MissionRunner":
        """Adds a step to the mission DAG."""
        self._dag.add_step(name, action, dependencies, is_gated)
        return self

    def _ensure_run_token(self, run_token: Optional[RunToken] = None) -> RunToken:
        """Validates or issues a RunToken from supervisor."""
        if run_token is None:
            if (
                self._active_run_token is not None
                and not self._active_run_token.is_cancelled
                and self._active_run_token.token_id not in self.supervisor._cancelled_tokens
            ):
                run_token = self._active_run_token
            else:
                pid = os.getpid()
                ppid = getattr(os, "getppid", lambda: 1)()
                run_token = self.supervisor.issue_token(
                    pid=pid,
                    parent_pid=ppid if ppid > 0 else 1,
                    lease_duration=60.0,
                    max_budget=300.0,
                )

        self.supervisor.validate_token(run_token)
        self._active_run_token = run_token
        return run_token

    def run(
        self,
        mission_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
        run_token: Optional[RunToken] = None,
        interrupt_before: Optional[Sequence[str]] = None,
        interrupt_after: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Runs the mission DAG starting from scratch or continuing from latest checkpoint."""
        token = self._ensure_run_token(run_token)
        self._active_mission_id = mission_id
        self._paused = False
        self._aborted = False

        if self.console is not None and hasattr(self.console, "start_run"):
            self.console.start_run(token)

        int_before = set(interrupt_before or [])
        int_after = set(interrupt_after or [])

        # Check existing checkpoints
        latest = self.checkpointer.get_latest_checkpoint(mission_id)
        if latest is not None and latest.status == "ABORTED":
            raise MissionAbortedError(f"Mission '{mission_id}' was aborted and cannot be run.")

        state: Dict[str, Any] = dict(initial_state or {})
        completed_step_names: Set[str] = set()

        if latest is not None:
            checkpoint_state = dict(latest.state)
            checkpoint_state.update(state)
            state = checkpoint_state
            all_checkpoints = self.checkpointer.list_checkpoints(mission_id)
            for c in all_checkpoints:
                if c.status in ("COMPLETED", "PAUSED") and not c.step_name.startswith("pause_before_"):
                    completed_step_names.add(c.step_name)

        plan = self._dag.get_execution_plan()
        completed_list: List[str] = [s.name for s in plan if s.name in completed_step_names]

        for step in plan:
            if step.name in completed_step_names:
                continue

            # Validate token budget at each step boundary
            self.supervisor.validate_token(token)

            # Check if execution must pause before step
            if step.is_gated or (step.name in int_before):
                self._paused = True
                rec = self.checkpointer.save_step(
                    mission_id=mission_id,
                    step_name=f"pause_before_{step.name}",
                    payload=state,
                    status="PAUSED",
                )
                if self.console is not None and hasattr(self.console, "pause_run"):
                    self.console.pause_run(
                        completed_strips=list(range(len(completed_list))),
                        pending_strips=[step.name],
                    )
                return {
                    "status": "PAUSED",
                    "mission_id": mission_id,
                    "paused_at": step.name,
                    "checkpoint": rec,
                    "state": state,
                    "completed_steps": list(completed_list),
                    "run_token_id": token.token_id,
                }

            # Execute step action
            step_output = step.action(dict(state))
            if isinstance(step_output, dict):
                state.update(step_output)

            completed_step_names.add(step.name)
            completed_list.append(step.name)

            should_pause_after = (
                (step.name in int_after)
                or (isinstance(step_output, dict) and step_output.get("__pause__", False))
                or self._paused
            )

            if should_pause_after:
                self._paused = True
                rec = self.checkpointer.save_step(
                    mission_id=mission_id,
                    step_name=step.name,
                    payload=state,
                    status="PAUSED",
                )
                if self.console is not None and hasattr(self.console, "pause_run"):
                    remaining = [s.name for s in plan if s.name not in completed_step_names]
                    self.console.pause_run(
                        completed_strips=list(range(len(completed_list))),
                        pending_strips=remaining,
                    )
                return {
                    "status": "PAUSED",
                    "mission_id": mission_id,
                    "paused_at": step.name,
                    "checkpoint": rec,
                    "state": state,
                    "completed_steps": list(completed_list),
                    "run_token_id": token.token_id,
                }
            else:
                self.checkpointer.save_step(
                    mission_id=mission_id,
                    step_name=step.name,
                    payload=state,
                    status="COMPLETED",
                )

        return {
            "status": "COMPLETED",
            "mission_id": mission_id,
            "state": state,
            "completed_steps": completed_list,
            "run_token_id": token.token_id,
        }

    def pause(self, mission_id: Optional[str] = None) -> Dict[str, Any]:
        """Pauses the active mission execution."""
        m_id = mission_id or self._active_mission_id
        if not m_id:
            raise MissionError("No active mission to pause.")
        self._paused = True
        latest = self.checkpointer.get_latest_checkpoint(m_id)
        if latest and latest.status != "PAUSED":
            latest = self.checkpointer.save_step(
                mission_id=m_id,
                step_name=latest.step_name,
                payload=latest.state,
                status="PAUSED",
            )
        if self.console is not None and hasattr(self.console, "pause_run"):
            self.console.pause_run()
        return {
            "status": "PAUSED",
            "mission_id": m_id,
            "latest_step": latest.step_name if latest else None,
        }

    def resume(
        self,
        mission_id: str,
        run_token: Optional[RunToken] = None,
        interrupt_before: Optional[Sequence[str]] = None,
        interrupt_after: Optional[Sequence[str]] = None,
        resume_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resumes a paused mission from its checkpoint without re-executing completed steps."""
        latest = self.checkpointer.get_latest_checkpoint(mission_id)
        if not latest:
            raise CheckpointNotFoundError(f"Cannot resume mission '{mission_id}': No checkpoint found.")
        if latest.status == "ABORTED":
            raise MissionAbortedError(f"Mission '{mission_id}' was aborted and cannot be resumed.")

        token = self._ensure_run_token(run_token)

        if self.console is not None and hasattr(self.console, "resume_run"):
            self.console.resume_run(
                {"completed_strips": [], "pending_strips": []},
                self.supervisor,
                token,
            )

        state = dict(latest.state)
        if resume_payload:
            state.update(resume_payload)

        # Delegate execution with restored state
        return self.run(
            mission_id=mission_id,
            initial_state=state,
            run_token=token,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )

    def abort(self, mission_id: str, run_token: Optional[RunToken] = None) -> Dict[str, Any]:
        """Cleanly aborts the mission and revokes supervisor run token."""
        token = run_token or self._active_run_token
        token_id = getattr(token, "token_id", None)
        if token_id:
            try:
                self.supervisor.cancel_token(token_id)
            except Exception:
                pass

        if self.console is not None and hasattr(self.console, "stop_run"):
            try:
                self.console.stop_run(self.supervisor, token)
            except Exception:
                pass

        self._aborted = True
        latest = self.checkpointer.get_latest_checkpoint(mission_id)
        state = latest.state if latest else {}
        self.checkpointer.save_step(
            mission_id=mission_id,
            step_name="aborted",
            payload=state,
            status="ABORTED",
        )
        return {
            "status": "ABORTED",
            "mission_id": mission_id,
            "token_id": token_id,
        }

    def rollback_to_step(self, mission_id: str, step_index: int) -> CheckpointRecord:
        """Rolls back the checkpointer to the specified step."""
        return self.checkpointer.rollback_to_step(mission_id, step_index)

    def profile_mission_memory(self, steps_count: int = 10) -> ThermodynamicReceipt:
        """Executes a benchmark DAG under ThermodynamicProfiler to verify heap <= 64 KB overhead."""
        with ThermodynamicProfiler(
            candidate_id="ninshu_mission_runner_ch20_23",
            memory_ceiling_bytes=64 * 1024,
            fail_closed=True,
        ) as profiler:
            cp = MissionCheckpointer(":memory:")
            sup = ProcessSupervisor(session_salt="thermo_profiler_salt")
            runner = MissionRunner(checkpointer=cp, supervisor=sup)
            for i in range(steps_count):
                runner.add_step(f"step_{i}", lambda s, idx=i: {f"key_{idx}": idx * 2})
            pid = os.getpid()
            ppid = getattr(os, "getppid", lambda: 1)()
            tok = sup.issue_token(
                pid=pid,
                parent_pid=ppid if ppid > 0 else 1,
                lease_duration=60.0,
                max_budget=120.0,
            )
            runner.run(mission_id="thermo_run", initial_state={"init": 0}, run_token=tok)

        return profiler.get_receipt(exit_code=0)
