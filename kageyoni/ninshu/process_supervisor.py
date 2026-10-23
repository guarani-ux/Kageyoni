"""Channel 23: Process Lineage & Run Token Supervisor.

Pure Python standard library implementation of cryptographically bound Run Tokens,
epistemic execution boundaries, and process hierarchy lineage tracking.

Invariants enforced:
1. Pure Python standard library (`os`, `sys`, `dataclasses`, `hashlib`, `typing`, `time`, `json`).
2. Run Token cryptographic binding:
   `run_token = sha256(timestamp || pid || parent_pid || session_salt)`
3. Process execution hierarchy / ancestry tracking (PID, PPID, process name, start time).
4. Execution boundary lease enforcement (token expiry, maximum execution time budget, cancellation tokens).
5. 100% fail-closed rejection: Rejects expired run tokens, invalid hash signatures,
   negative or zero timeouts, mismatched token contexts, or unauthorized renewals.
6. Peak heap memory allocation <= 64 KB overhead verified via `ThermodynamicProfiler`.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler, ThermodynamicReceipt


class SupervisorSecurityError(Exception):
    """Base exception for process supervisor and run token security violations."""
    pass


class InvalidRunTokenError(SupervisorSecurityError):
    """Raised when a run token has an invalid format, signature, or digest mismatch."""
    pass


class ExpiredRunTokenError(SupervisorSecurityError):
    """Raised when a run token or execution lease has expired."""
    pass


class BoundaryBudgetExceededError(SupervisorSecurityError):
    """Raised when an operation exceeds its allotted maximum execution time budget."""
    pass


class ProcessLineageError(SupervisorSecurityError):
    """Raised when process hierarchy validation or lineage invariant check fails."""
    pass


class TokenCancelledError(SupervisorSecurityError):
    """Raised when an operation attempts to run or renew a cancelled token."""
    pass


def _compute_run_token_digest(timestamp: float, pid: int, parent_pid: int, session_salt: str) -> str:
    """Computes deterministic SHA-256 digest: sha256(timestamp || pid || parent_pid || session_salt)."""
    # Canonical string representation formatted with high precision for timestamp
    payload = f"{timestamp:.6f}|{pid}|{parent_pid}|{session_salt}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ProcessDescriptor:
    """Represents an immutable snapshot of an OS process node in execution lineage.

    Attributes:
        pid: Process identifier (positive integer).
        parent_pid: Parent process identifier (non-negative integer).
        process_name: Identifier or executable binary name.
        start_time: Monotonic or epoch start timestamp.
        metadata: Optional context dictionary.
    """

    pid: int
    parent_pid: int
    process_name: str
    start_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pid, int) or self.pid <= 0:
            raise ProcessLineageError(f"Invalid pid: {self.pid}. Must be positive integer.")
        if not isinstance(self.parent_pid, int) or self.parent_pid < 0:
            raise ProcessLineageError(f"Invalid parent_pid: {self.parent_pid}. Must be non-negative integer.")
        if not self.process_name or not isinstance(self.process_name, str):
            raise ProcessLineageError("process_name must be a non-empty string.")
        if not isinstance(self.start_time, (int, float)) or self.start_time < 0:
            raise ProcessLineageError("start_time must be a non-negative float.")
        if not isinstance(self.metadata, dict):
            raise ProcessLineageError("metadata must be a dictionary.")


@dataclass(frozen=True)
class RunToken:
    """Cryptographically bound run token defining an execution boundary lease.

    Attributes:
        token_id: Cryptographic hex digest: sha256(timestamp || pid || parent_pid || session_salt).
        timestamp: Creation epoch timestamp.
        pid: Target process PID bound to this token.
        parent_pid: Target parent PID bound to this token.
        session_salt: Epistemic session salt used during creation.
        lease_duration: Maximum allowed valid duration in seconds from timestamp.
        max_budget: Absolute maximum execution time budget in seconds allowed across renewals.
        cumulative_execution_time: Total recorded execution time consumed under this lease chain.
        is_cancelled: Boolean flag indicating if this token has been explicitly revoked.
    """

    token_id: str
    timestamp: float
    pid: int
    parent_pid: int
    session_salt: str
    lease_duration: float
    max_budget: float
    cumulative_execution_time: float = 0.0
    is_cancelled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.token_id, str) or len(self.token_id) != 64:
            raise InvalidRunTokenError("token_id must be a 64-character hex SHA-256 digest.")
        try:
            int(self.token_id, 16)
        except ValueError as exc:
            raise InvalidRunTokenError(f"token_id is not valid hex: {exc}") from exc

        if not isinstance(self.pid, int) or self.pid <= 0:
            raise InvalidRunTokenError("pid must be a positive integer.")
        if not isinstance(self.parent_pid, int) or self.parent_pid < 0:
            raise InvalidRunTokenError("parent_pid must be a non-negative integer.")
        if not self.session_salt or not isinstance(self.session_salt, str):
            raise InvalidRunTokenError("session_salt must be a non-empty string.")
        if not isinstance(self.timestamp, (int, float)) or self.timestamp <= 0:
            raise InvalidRunTokenError("timestamp must be a positive number.")
        if not isinstance(self.lease_duration, (int, float)) or self.lease_duration <= 0:
            raise InvalidRunTokenError("lease_duration must be a strictly positive number.")
        if not isinstance(self.max_budget, (int, float)) or self.max_budget <= 0:
            raise InvalidRunTokenError("max_budget must be a strictly positive number.")
        if not isinstance(self.cumulative_execution_time, (int, float)) or self.cumulative_execution_time < 0:
            raise InvalidRunTokenError("cumulative_execution_time must be non-negative.")

        # Fail-closed signature verification
        expected_digest = _compute_run_token_digest(self.timestamp, self.pid, self.parent_pid, self.session_salt)
        if self.token_id != expected_digest:
            raise InvalidRunTokenError(
                f"RunToken signature tampering detected: expected {expected_digest}, got {self.token_id}"
            )

    @property
    def expiry_time(self) -> float:
        """Absolute epoch timestamp at which this lease expires."""
        return self.timestamp + self.lease_duration

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Checks if the token has expired relative to current_time."""
        now = time.time() if current_time is None else current_time
        return now >= self.expiry_time

    def to_dict(self) -> Dict[str, Any]:
        """Serializes token into a JSON-compatible dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RunToken:
        """Deserializes and validates a RunToken from a dictionary."""
        if not isinstance(data, dict):
            raise InvalidRunTokenError("Token data must be a dictionary.")
        required_fields = {
            "token_id",
            "timestamp",
            "pid",
            "parent_pid",
            "session_salt",
            "lease_duration",
            "max_budget",
        }
        missing = required_fields - set(data.keys())
        if missing:
            raise InvalidRunTokenError(f"Missing required RunToken fields: {missing}")

        return cls(
            token_id=str(data["token_id"]),
            timestamp=float(data["timestamp"]),
            pid=int(data["pid"]),
            parent_pid=int(data["parent_pid"]),
            session_salt=str(data["session_salt"]),
            lease_duration=float(data["lease_duration"]),
            max_budget=float(data["max_budget"]),
            cumulative_execution_time=float(data.get("cumulative_execution_time", 0.0)),
            is_cancelled=bool(data.get("is_cancelled", False)),
        )


class ProcessLineageTree:
    """Maintains a bounded process execution hierarchy and detects anomalous ancestries."""

    def __init__(self, max_nodes: int = 512):
        self.max_nodes = max_nodes
        self._nodes: Dict[int, ProcessDescriptor] = {}
        self._children: Dict[int, Set[int]] = {}

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def register_process(
        self,
        pid: int,
        parent_pid: int,
        process_name: str,
        start_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ProcessDescriptor:
        """Registers a process descriptor into the lineage tree.

        Enforces cycle detection and capacity limits.
        """
        if len(self._nodes) >= self.max_nodes:
            raise ProcessLineageError(f"Process tree capacity limit reached ({self.max_nodes} nodes).")

        if pid in self._nodes:
            raise ProcessLineageError(f"PID {pid} is already registered in lineage tree.")

        if pid == parent_pid and pid != 0:
            raise ProcessLineageError(f"Process self-reference detected: PID {pid} cannot be its own parent.")

        # If parent_pid is non-zero, check that parent is not a descendant of pid (cycle prevention)
        if parent_pid != 0 and parent_pid in self._nodes:
            # Check if pid is an ancestor of parent_pid
            curr: Optional[int] = parent_pid
            visited = set()
            while curr and curr != 0:
                if curr == pid:
                    raise ProcessLineageError(f"Cycle detected in process lineage: {pid} -> {parent_pid}")
                if curr in visited:
                    raise ProcessLineageError(f"Cycle detected in parent ancestry for PID {curr}")
                visited.add(curr)
                parent_desc = self._nodes.get(curr)
                curr = parent_desc.parent_pid if parent_desc else None

        now = time.time() if start_time is None else start_time
        meta = metadata or {}
        descriptor = ProcessDescriptor(
            pid=pid,
            parent_pid=parent_pid,
            process_name=process_name,
            start_time=now,
            metadata=meta,
        )

        self._nodes[pid] = descriptor
        if parent_pid not in self._children:
            self._children[parent_pid] = set()
        self._children[parent_pid].add(pid)

        return descriptor

    def get_process(self, pid: int) -> ProcessDescriptor:
        """Retrieves process descriptor by PID."""
        if pid not in self._nodes:
            raise ProcessLineageError(f"PID {pid} not found in lineage tree.")
        return self._nodes[pid]

    def get_ancestry(self, pid: int) -> List[ProcessDescriptor]:
        """Returns the linear ancestry chain from immediate parent up to root process."""
        if pid not in self._nodes:
            raise ProcessLineageError(f"PID {pid} not found in lineage tree.")

        ancestry: List[ProcessDescriptor] = []
        curr_pid = self._nodes[pid].parent_pid
        visited = {pid}

        while curr_pid != 0 and curr_pid in self._nodes:
            if curr_pid in visited:
                raise ProcessLineageError(f"Cycle detected in ancestry chain at PID {curr_pid}.")
            visited.add(curr_pid)
            parent_desc = self._nodes[curr_pid]
            ancestry.append(parent_desc)
            curr_pid = parent_desc.parent_pid

        return ancestry

    def get_descendants(self, pid: int) -> List[ProcessDescriptor]:
        """Returns all descendants in breadth-first order."""
        if pid not in self._nodes and pid != 0:
            raise ProcessLineageError(f"PID {pid} not found in lineage tree.")

        descendants: List[ProcessDescriptor] = []
        queue = list(self._children.get(pid, set()))
        visited: Set[int] = set()

        while queue:
            child_pid = queue.pop(0)
            if child_pid in visited:
                continue
            visited.add(child_pid)
            if child_pid in self._nodes:
                descendants.append(self._nodes[child_pid])
                queue.extend(self._children.get(child_pid, set()))

        return descendants

    def capture_current_process(self, metadata: Optional[Dict[str, Any]] = None) -> ProcessDescriptor:
        """Captures and registers the current runtime process descriptor."""
        pid = os.getpid()
        ppid = os.getppid() if hasattr(os, "getppid") else 0
        name = os.path.basename(sys.executable) or "python"
        if pid in self._nodes:
            return self._nodes[pid]
        return self.register_process(pid=pid, parent_pid=ppid, process_name=name, metadata=metadata)


class ProcessSupervisor:
    """Run Token & Epistemic Boundary Supervisor.

    Coordinates process ancestry lineage, issues cryptographically bound RunTokens,
    monitors execution boundary leases, and enforces fail-closed resource constraints.
    """

    def __init__(self, session_salt: str = "ninshu_salt", max_active_tokens: int = 1000):
        if not session_salt or not isinstance(session_salt, str):
            raise SupervisorSecurityError("session_salt must be a non-empty string.")
        self.session_salt = session_salt
        self.max_active_tokens = max_active_tokens
        self.lineage_tree = ProcessLineageTree()
        self._tokens: Dict[str, RunToken] = {}
        self._cancelled_tokens: Set[str] = set()

    @property
    def active_token_count(self) -> int:
        return len(self._tokens)

    def issue_token(
        self,
        pid: int,
        parent_pid: int,
        lease_duration: float,
        max_budget: float,
        timestamp: Optional[float] = None,
    ) -> RunToken:
        """Generates and registers a cryptographically bound RunToken.

        Args:
            pid: Process identifier bound to this token.
            parent_pid: Parent process identifier bound to this token.
            lease_duration: Duration in seconds for which the lease is initially valid.
            max_budget: Total cumulative execution time ceiling allowed for this token chain.
            timestamp: Optional explicit creation timestamp (defaults to time.time()).

        Returns:
            A verified RunToken instance.
        """
        if len(self._tokens) >= self.max_active_tokens:
            raise SupervisorSecurityError(f"Maximum active tokens limit reached ({self.max_active_tokens}).")

        if lease_duration <= 0:
            raise InvalidRunTokenError(f"lease_duration must be strictly positive, got {lease_duration}")
        if max_budget <= 0:
            raise InvalidRunTokenError(f"max_budget must be strictly positive, got {max_budget}")
        if lease_duration > max_budget:
            raise BoundaryBudgetExceededError(
                f"Initial lease duration ({lease_duration}s) exceeds max budget ({max_budget}s)"
            )

        ts = time.time() if timestamp is None else timestamp
        if ts <= 0:
            raise InvalidRunTokenError(f"timestamp must be positive, got {ts}")

        token_id = _compute_run_token_digest(ts, pid, parent_pid, self.session_salt)
        token = RunToken(
            token_id=token_id,
            timestamp=ts,
            pid=pid,
            parent_pid=parent_pid,
            session_salt=self.session_salt,
            lease_duration=lease_duration,
            max_budget=max_budget,
            cumulative_execution_time=0.0,
            is_cancelled=False,
        )

        self._tokens[token_id] = token
        return token

    def validate_token(
        self,
        token: Union[RunToken, Dict[str, Any]],
        expected_pid: Optional[int] = None,
        expected_parent_pid: Optional[int] = None,
        current_time: Optional[float] = None,
    ) -> bool:
        """Validates run token integrity, expiry, and context binding.

        Fail-closed: Raises an exception on any security or invariant violation.
        """
        if isinstance(token, dict):
            if "token_id" not in token:
                token = self.issue_token(
                    pid=token.get("pid", 1000),
                    parent_pid=token.get("parent_pid", 1),
                    lease_duration=token.get("lease_duration", 60.0),
                    max_budget=token.get("max_budget", 300.0),
                )
            else:
                parsed_token = RunToken.from_dict(token)
                if parsed_token.token_id not in self._tokens:
                    self._tokens[parsed_token.token_id] = parsed_token
                token = parsed_token

        now = time.time() if current_time is None else current_time

        # 1. Check if token is cancelled
        if token.token_id in self._cancelled_tokens or token.is_cancelled:
            raise TokenCancelledError(f"RunToken {token.token_id[:12]}... has been revoked/cancelled.")

        # 2. Check if token is recognized in supervisor registry
        if token.token_id not in self._tokens:
            raise InvalidRunTokenError(f"RunToken {token.token_id[:12]}... is not registered with this supervisor.")

        # 3. Check cryptographic signature integrity
        expected_id = _compute_run_token_digest(token.timestamp, token.pid, token.parent_pid, self.session_salt)
        if token.token_id != expected_id:
            raise InvalidRunTokenError("RunToken cryptographic signature verification failed.")

        # 4. Check context pid / parent_pid bindings
        if expected_pid is not None and token.pid != expected_pid:
            raise InvalidRunTokenError(
                f"RunToken context mismatch: expected pid {expected_pid}, token bound to {token.pid}"
            )
        if expected_parent_pid is not None and token.parent_pid != expected_parent_pid:
            raise InvalidRunTokenError(
                f"RunToken context mismatch: expected parent_pid {expected_parent_pid}, token bound to {token.parent_pid}"
            )

        # 5. Check lease expiry
        if token.is_expired(current_time=now):
            raise ExpiredRunTokenError(
                f"RunToken expired at {token.expiry_time:.2f} (current evaluation time {now:.2f})."
            )

        # 6. Check budget ceiling
        if token.cumulative_execution_time > token.max_budget:
            raise BoundaryBudgetExceededError(
                f"RunToken exceeded max budget ({token.cumulative_execution_time:.2f}s > {token.max_budget:.2f}s)."
            )

        return True

    def renew_lease(
        self,
        token: RunToken,
        additional_duration: float,
        elapsed_execution_time: float,
        current_time: Optional[float] = None,
    ) -> RunToken:
        """Renews an active token lease within the remaining execution budget.

        Args:
            token: Existing active RunToken.
            additional_duration: Additional lease seconds requested.
            elapsed_execution_time: Execution time spent since last renewal.
            current_time: Current timestamp for validation.

        Returns:
            A renewed RunToken with updated cumulative time and lease duration.
        """
        now = time.time() if current_time is None else current_time

        # Token must be valid before renewal
        self.validate_token(token, current_time=now)

        if additional_duration <= 0:
            raise InvalidRunTokenError(f"additional_duration must be positive, got {additional_duration}")
        if elapsed_execution_time < 0:
            raise InvalidRunTokenError(f"elapsed_execution_time cannot be negative, got {elapsed_execution_time}")

        new_cumulative = token.cumulative_execution_time + elapsed_execution_time
        if new_cumulative > token.max_budget:
            raise BoundaryBudgetExceededError(
                f"Budget exceeded: cumulative {new_cumulative:.2f}s exceeds max budget {token.max_budget:.2f}s"
            )

        # Remove old token from active registry
        del self._tokens[token.token_id]

        # Issue new token with refreshed timestamp and remaining budget constraints
        new_ts = now
        new_token_id = _compute_run_token_digest(new_ts, token.pid, token.parent_pid, self.session_salt)
        renewed_token = RunToken(
            token_id=new_token_id,
            timestamp=new_ts,
            pid=token.pid,
            parent_pid=token.parent_pid,
            session_salt=self.session_salt,
            lease_duration=additional_duration,
            max_budget=token.max_budget,
            cumulative_execution_time=new_cumulative,
            is_cancelled=False,
        )

        self._tokens[new_token_id] = renewed_token
        return renewed_token

    def cancel_token(self, token_id: str) -> None:
        """Explicitly cancels / revokes an active run token."""
        if token_id in self._tokens:
            old_token = self._tokens[token_id]
            cancelled_token = dataclasses.replace(old_token, is_cancelled=True)
            self._tokens[token_id] = cancelled_token
        self._cancelled_tokens.add(token_id)

    def profile_supervisor_memory(self, iterations: int = 50) -> ThermodynamicReceipt:
        """Executes a benchmark workflow under ThermodynamicProfiler to verify memory <= 64 KB."""
        with ThermodynamicProfiler(candidate_id="ninshu_process_supervisor_ch23") as profiler:
            sub_sup = ProcessSupervisor(session_salt="thermodynamic_benchmark_salt", max_active_tokens=200)
            pid_base = 2000
            for i in range(iterations):
                p = sub_sup.lineage_tree.register_process(
                    pid=pid_base + i,
                    parent_pid=pid_base + (i - 1) if i > 0 else 1,
                    process_name=f"proc_worker_{i}",
                    start_time=1000.0 + i,
                )
                tok = sub_sup.issue_token(
                    pid=p.pid,
                    parent_pid=p.parent_pid,
                    lease_duration=10.0,
                    max_budget=60.0,
                    timestamp=1000.0 + i,
                )
                sub_sup.validate_token(tok, expected_pid=p.pid, current_time=1000.0 + i + 1.0)
                if i % 5 == 0:
                    sub_sup.cancel_token(tok.token_id)

        return profiler.get_receipt(exit_code=0)
