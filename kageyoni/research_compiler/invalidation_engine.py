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
    impacted_situations: List[str] = field(default_factory=list)
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
            "impacted_situations": self.impacted_situations,
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
        from ..persistence.unit_of_work import UnitOfWork
        with UnitOfWork(self.db):
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

        # Topology and invalidation belong to the shared graph. Domain effects
        # below remain here. Detect corrupt imported topology without recursing.
        from kageyoni.graph import CycleDetectedError
        try:
            graph._dag.topological_sort()
        except CycleDetectedError:
            report.cycle_detected = True
        invalidated_ids = graph.invalidate_claim(root_claim_id, reason)
        report.invalidated_child_claims = invalidated_ids

        # 2. Cascade into Durable SQLite Engine State if DB available
        if self.db:
            from ..persistence.unit_of_work import UnitOfWork
            all_affected_claim_ids = set(invalidated_ids)

            with UnitOfWork(self.db):
                cur = self.db.cursor()

                # 1. Check agency_research_packages
                try:
                    cur.execute("SELECT package_id, topic_model_json FROM agency_research_packages")
                    rows = cur.fetchall()
                    for row in rows:
                        pkg_id = row[0]
                        model_str = row[1]
                        refs = _extract_references(model_str)
                        if refs & all_affected_claim_ids:
                            report.impacted_packages.append(pkg_id)
                            try:
                                cur.execute("UPDATE agency_research_packages SET is_falsified = 1 WHERE package_id = ?", (pkg_id,))
                            except Exception:
                                pass
                except Exception:
                    pass

                # 2. Check agency_projects
                impacted_pkgs_set = set(report.impacted_packages)
                try:
                    cur.execute("SELECT project_id, metadata_json FROM agency_projects")
                    prows = cur.fetchall()
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

                # 3. Check agency_section_records
                impacted_projs_set = set(report.impacted_projects)
                try:
                    cur.execute("SELECT record_id, project_id, spoken_audio, visual_proof FROM agency_section_records")
                    srows = cur.fetchall()
                    for srow in srows:
                        rec_id, proj_id, spoken, visual = srow
                        if proj_id in impacted_projs_set or any(cid in (spoken or "") or cid in (visual or "") for cid in all_affected_claim_ids):
                            report.impacted_sections.append(rec_id)
                except Exception:
                    pass

                # 4. Check situation_records
                try:
                    cur.execute("SELECT record_key, payload_json FROM situation_records WHERE kind='situation'")
                    sit_rows = cur.fetchall()
                    for sit_row in sit_rows:
                        s_key = sit_row[0]
                        s_payload_str = sit_row[1]
                        refs = _extract_references(s_payload_str)
                        if refs & all_affected_claim_ids:
                            report.impacted_situations.append(s_key)
                            try:
                                s_data = json.loads(s_payload_str)
                                s_data["status"] = "invalidated"
                                s_data.setdefault("contradictions", {})[root_claim_id] = [reason]
                                cur.execute(
                                    "UPDATE situation_records SET payload_json=? WHERE kind='situation' AND record_key=?",
                                    (json.dumps(s_data, sort_keys=True), s_key)
                                )
                            except Exception:
                                pass
                except Exception:
                    pass

                # 5. Record Retraction in Append-Only Audit Table
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

