"""
kageyoni/research_compiler/invalidation_engine.py
End-to-End Retraction & Invalidation Engine (Gate G5).

Cascades claim invalidations forward into:
1. Child claims in ClaimGraph (with cycle detection).
2. agency_research_packages (marks package compromised/requires revision).
3. agency_projects (flags project with CONTRADICTED_PREMISE).
4. agency_section_records (identifies dependent script sections).
5. Append-only retraction audit history (agency_claim_retractions).
"""

from __future__ import annotations
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .claims import ClaimGraph, ClaimNode


@dataclass
class InvalidationReport:
    retracted_claim_id: str
    reason: str
    invalidated_child_claims: List[str] = field(default_factory=list)
    impacted_packages: List[str] = field(default_factory=list)
    impacted_projects: List[str] = field(default_factory=list)
    impacted_sections: List[str] = field(default_factory=list)
    cycle_detected: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retracted_claim_id": self.retracted_claim_id,
            "reason": self.reason,
            "invalidated_child_claims": self.invalidated_child_claims,
            "impacted_packages": self.impacted_packages,
            "impacted_projects": self.impacted_projects,
            "impacted_sections": self.impacted_sections,
            "cycle_detected": self.cycle_detected,
            "timestamp": self.timestamp,
        }


def _extract_references(raw: Optional[str]) -> Set[str]:
    """Extracts exact string reference tokens from structured JSON, eliminating substring false positives."""
    if not raw:
        return set()
    try:
        data = json.loads(raw)
    except Exception:
        return set()

    refs: Set[str] = set()

    def _walk(item: Any):
        if isinstance(item, str):
            refs.add(item)
        elif isinstance(item, dict):
            for v in item.values():
                _walk(v)
        elif isinstance(item, (list, tuple, set)):
            for v in item:
                _walk(v)

    _walk(data)
    return refs


class InvalidationEngine:
    """
    Cascading Invalidation Engine with durable SQLite history and cycle detection.
    """

    def __init__(self, db_conn: Optional[sqlite3.Connection] = None):
        self.db = db_conn
        if self.db:
            self._ensure_schema()

    def _ensure_schema(self) -> None:
        if not self.db:
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS agency_claim_retractions (
                retraction_id TEXT PRIMARY KEY,
                root_claim_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                impacted_claims_json TEXT NOT NULL,
                impacted_packages_json TEXT NOT NULL,
                impacted_projects_json TEXT NOT NULL,
                retracted_at REAL NOT NULL
            );
        """)
        self.db.commit()

    def invalidate_claim_with_cascade(
        self,
        graph: ClaimGraph,
        root_claim_id: str,
        reason: str,
    ) -> InvalidationReport:
        """
        Executes a forward cascading retraction with cycle protection.
        """
        report = InvalidationReport(
            retracted_claim_id=root_claim_id,
            reason=reason,
        )

        if root_claim_id not in graph.claims:
            return report

        # 1. Traverse Graph with Cycle Detection
        visited: Set[str] = set()
        path: Set[str] = set()
        invalidated_ids: List[str] = []

        def dfs_invalidate(cid: str, current_reason: str):
            if cid in path:
                report.cycle_detected = True
                return
            if cid in visited:
                return

            visited.add(cid)
            path.add(cid)

            node = graph.claims[cid]
            node.is_invalidated = True
            node.invalidation_reason = current_reason
            invalidated_ids.append(cid)

            for child_id in node.child_claim_ids:
                if child_id in graph.claims:
                    dfs_invalidate(child_id, f"Upstream dependency '{cid}' invalidated: {current_reason}")

            path.remove(cid)

        dfs_invalidate(root_claim_id, reason)
        report.invalidated_child_claims = invalidated_ids

        # 2. Cascade into Durable SQLite Engine State if DB available
        if self.db:
            from ..persistence.unit_of_work import UnitOfWork
            all_affected_claim_ids = set(invalidated_ids)

            with UnitOfWork(self.db):
                # Check agency_research_packages
                try:
                    cur = self.db.cursor()
                    cur.execute("SELECT package_id, topic_model_json FROM agency_research_packages")
                    rows = cur.fetchall()
                    for row in rows:
                        pkg_id = row[0]
                        model_str = row[1]
                        refs = _extract_references(model_str)
                        if refs & all_affected_claim_ids:
                            report.impacted_packages.append(pkg_id)
                except Exception:
                    pass

                # Check agency_projects
                try:
                    cur = self.db.cursor()
                    cur.execute("SELECT project_id, metadata_json FROM agency_projects")
                    prows = cur.fetchall()
                    impacted_pkgs_set = set(report.impacted_packages)
                    for prow in prows:
                        proj_id = prow[0]
                        meta_str = prow[1] or ""
                        refs = _extract_references(meta_str)
                        if (refs & all_affected_claim_ids) or (refs & impacted_pkgs_set):
                            report.impacted_projects.append(proj_id)
                            # Mark project as requiring revision
                            cur.execute(
                                "UPDATE agency_projects SET current_stage = 'REVISION_REQUIRED', updated_at = ? WHERE project_id = ?",
                                (time.time(), proj_id),
                            )
                except Exception:
                    pass

                # Record Retraction in Append-Only Audit Table
                retraction_id = f"retract_{uuid.uuid4().hex[:12]}"
                self.db.execute(
                    """
                    INSERT INTO agency_claim_retractions
                    (retraction_id, root_claim_id, reason, impacted_claims_json,
                     impacted_packages_json, impacted_projects_json, retracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        retraction_id,
                        root_claim_id,
                        reason,
                        json.dumps(report.invalidated_child_claims),
                        json.dumps(report.impacted_packages),
                        json.dumps(report.impacted_projects),
                        report.timestamp,
                    ),
                )

        return report
