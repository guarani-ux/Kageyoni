"""Kageyoni causal world-state engine.

The engine owns durable state, validation, random outcomes, simulation time,
transactions, and replay receipts. A host/skill owns semantic interpretation
and narration. No network or model API is required.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import secrets
import shutil
import sqlite3
import time
import uuid
from pathlib import Path
from .resources import schema_path
from typing import Any, Iterable

from .model import DOMAINS, REQUIRED, STATUSES, schema
from .will import (
    CONTRACT_VERSION,
    WillContractError,
    contract_refs,
    validate_contract,
)


def encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(encoded(value).encode("utf-8")).hexdigest()


_REJECTION_CLASS_KEYWORDS = [
    ("MALFORMED_REQUEST", [
        "invalid enum", "malformed", "missing key", "missing field", "unknown op", "invalid op",
        "unknown domain", "schema", "syntax", "unexpected field", "bad format", "json_valid",
        "unknown field", "invalid change", "missing or repeated", "unsupported change", "new evidence required"
    ]),
    ("INSUFFICIENT_AUTHORITY", [
        "authority", "unauthorized", "forbidden", "permission", "source must exist", "not authorized"
    ]),
    ("TEMPORARY_STATE_BLOCK", [
        "revision", "stale", "clock", "phase", "timing", "exhausted", "cooldown", "outdated"
    ]),
    ("PREREQUISITE_MISSING", [
        "locked", "prerequisite", "requires", "uncertified", "unsterilized", "seal", "ward", "quarantine"
    ]),
]


def default_rejection_class(msg: str) -> str:
    low = str(msg).lower()
    for cat, kws in _REJECTION_CLASS_KEYWORDS:
        if any(k in low for k in kws):
            return cat
    return "HARD_INVARIANT_VIOLATION"


class Rejected(ValueError):
    def __init__(
        self,
        message: str,
        rejection_class: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.rejection_class = rejection_class or default_rejection_class(message)
        self.details = details or {}


def require(
    condition: Any,
    message: str,
    rejection_class: str | None = None,
    details: dict | None = None,
) -> None:
    if not condition:
        raise Rejected(message, rejection_class=rejection_class, details=details)


_PROPERTY_STATES = {"known", "unknown", "absent", "not_applicable", "disputed"}
_PROPERTY_TYPES = {"number", "integer", "text", "boolean", "reference", "structured"}
_LIFECYCLE = {"proposed", "active", "deprecated", "retired"}
_EVENT_KINDS = {
    "import", "scene", "action", "failed_action", "decision", "correction",
    "rewind", "advance_time", "world_event", "property_assignment",
    "consequence", "process", "observation", "maintenance", "will_attempt",
}
_AUX_TABLES = {"property", "process", "facet", "consequence", "run", "resolution", "observation", "will_attempt"}


class Engine:
    """SQLite-backed, branch-local, append-only event engine."""

    @classmethod
    def create(cls, path: str | Path, *, seed: Any = None, read_only: bool = False) -> Engine:
        return cls(path, read_only=read_only)

    def __init__(self, path: str | Path, *, read_only: bool = False):
        self.path = str(path)
        if read_only:
            self.db = sqlite3.connect(Path(self.path).resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=10)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA query_only=ON")
            return
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        # Portable campaign files use a rollback journal. WAL checkpoints in the
        # current hosted filesystem failed reopen integrity after large scene writes.
        # A successful in-process check is not sufficient delivery verification.
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        try:
            self._open_or_upgrade()
        except Exception:
            self.db.close()
            raise

    def transaction(self):
        """Context manager providing an atomic UnitOfWork transaction boundary."""
        from .persistence.unit_of_work import UnitOfWork
        return UnitOfWork(self.db)

    def _open_or_upgrade(self) -> None:
        exists = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='schema_version'"
        ).fetchone()
        if not exists:
            self.db.executescript(schema())
        version = int(self.db.execute("SELECT version FROM schema_version").fetchone()[0])
        if version == 1:
            # Preserve a verified recovery candidate before applying the legacy migration.
            self._backup_before_migration()
            migration = schema_path("migration_002.sql")
            self.db.executescript(migration.read_text(encoding="utf-8"))
            version = 2
        require(version == 2, f"unsupported schema version {version}")
        self._ensure_runtime_schema()
        self._seed_engine_versions()
        from .decisions import install as install_decisions
        install_decisions(self)
        from .personality import install as install_personality
        install_personality(self)
        from .writing import install as install_writing
        install_writing(self)

    def _backup_before_migration(self) -> None:
        source = Path(self.path)
        if not source.exists() or source.stat().st_size == 0:
            return
        destination = source.with_name(source.name + ".pre-v2.bak")
        if destination.exists():
            return
        out = sqlite3.connect(destination)
        try:
            self.db.backup(out)
        finally:
            out.close()

    def _backup_before_versioned_migration(self, version: int) -> None:
        """Create a non-destructive recovery copy before a runtime migration."""
        source = Path(self.path)
        if not source.exists() or source.stat().st_size == 0:
            return
        destination = source.with_name(f"{source.name}.pre-v{version}.bak")
        if destination.exists():
            return
        out = sqlite3.connect(destination)
        try:
            self.db.backup(out)
        finally:
            out.close()

    def _ensure_runtime_schema(self) -> None:
        migration = schema_path("migration_003.sql")
        runtime_ready = self.db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='engine_versions'"
        ).fetchone()
        if not runtime_ready and migration.exists():
            script = migration.read_text(encoding="utf-8")
            for attempt in range(40):
                try:
                    self.db.executescript(script)
                    break
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 39:
                        raise
                    time.sleep(0.05)
        # A v2 database may have been produced before the runtime migration.
        # These statements are harmless after migration_003 and make the upgrade
        # path self-healing if a prior migration was interrupted.
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS engine_versions(
          component TEXT PRIMARY KEY, version TEXT NOT NULL, checksum TEXT,
          compatible_engine TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS property_changes(
          event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
          branch TEXT NOT NULL, entity_id TEXT NOT NULL, property_id TEXT NOT NULL,
          definition_version INTEGER NOT NULL, before_json TEXT, after_json TEXT,
          PRIMARY KEY(event_id,ordinal)
        );
        CREATE TABLE IF NOT EXISTS property_operations(
          id TEXT PRIMARY KEY, operation TEXT NOT NULL, property_id TEXT NOT NULL,
          definition_version INTEGER, before_json TEXT, after_json TEXT,
          actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS consequence_runs(
          consequence_id TEXT NOT NULL REFERENCES consequences(id), run_key TEXT NOT NULL,
          event_id TEXT NOT NULL REFERENCES events(id), status TEXT NOT NULL,
          detail_json TEXT NOT NULL CHECK(json_valid(detail_json)),
          PRIMARY KEY(consequence_id,run_key)
        );
        CREATE TABLE IF NOT EXISTS processes(
          branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL,
          process_kind TEXT NOT NULL, state TEXT NOT NULL,
          subjects_json TEXT NOT NULL, scope_json TEXT NOT NULL,
          origin_event TEXT REFERENCES events(id), rule_id TEXT, rule_version INTEGER,
          conditions_json TEXT NOT NULL, subscriptions_json TEXT NOT NULL,
          last_tick REAL, next_tick REAL, interval_value REAL, interval_unit TEXT,
          granularity TEXT NOT NULL DEFAULT 'exact', rng_slot TEXT, pending_judgment TEXT,
          visibility TEXT NOT NULL DEFAULT 'gm', metadata_json TEXT NOT NULL,
          updated_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
        );
        CREATE TABLE IF NOT EXISTS process_changes(
          event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
          branch TEXT NOT NULL, process_id TEXT NOT NULL, before_json TEXT, after_json TEXT,
          PRIMARY KEY(event_id,ordinal)
        );
        CREATE TABLE IF NOT EXISTS entity_facet_changes(
          event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
          branch TEXT NOT NULL, entity_id TEXT NOT NULL, facet TEXT NOT NULL,
          before_json TEXT, after_json TEXT, PRIMARY KEY(event_id,ordinal)
        );
        CREATE TABLE IF NOT EXISTS process_runs(
          branch TEXT NOT NULL, process_id TEXT NOT NULL, run_key TEXT NOT NULL,
          event_id TEXT, from_tick REAL, to_tick REAL, rng_result_json,
          outcome_json TEXT NOT NULL, status TEXT NOT NULL,
          PRIMARY KEY(branch,process_id,run_key)
        );
        CREATE TABLE IF NOT EXISTS process_subscriptions(
          branch TEXT NOT NULL, process_id TEXT NOT NULL, event_kind TEXT NOT NULL,
          PRIMARY KEY(branch,process_id,event_kind)
        );
        CREATE TABLE IF NOT EXISTS attention_scores(
          branch TEXT NOT NULL, process_id TEXT NOT NULL, viewer_id TEXT, score REAL NOT NULL,
          factors_json TEXT NOT NULL, computed_revision INTEGER NOT NULL,
          PRIMARY KEY(branch,process_id,viewer_id)
        );
        CREATE TABLE IF NOT EXISTS registry_entries(
          kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
          locator TEXT NOT NULL, status TEXT NOT NULL, readers_json TEXT NOT NULL,
          writers_json TEXT NOT NULL, compatibility_json TEXT NOT NULL, source_hash TEXT,
          declared_by TEXT NOT NULL, PRIMARY KEY(kind,stable_id,version)
        );
        CREATE TABLE IF NOT EXISTS registry_dependencies(
          kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
          depends_kind TEXT NOT NULL, depends_id TEXT NOT NULL, depends_version TEXT,
          relation TEXT NOT NULL,
          PRIMARY KEY(kind,stable_id,version,depends_kind,depends_id,depends_version,relation)
        );
        CREATE TABLE IF NOT EXISTS module_manifests(
          module_id TEXT PRIMARY KEY, module_version TEXT NOT NULL, entry_skill TEXT NOT NULL,
          triggers_json TEXT NOT NULL, required_context_json TEXT NOT NULL, commands_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL, compatibility_json TEXT NOT NULL,
          visibility TEXT NOT NULL, source_hash TEXT, status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS event_aux_changes(
          event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
          kind TEXT NOT NULL, state_key TEXT NOT NULL, before_json TEXT, after_json TEXT,
          PRIMARY KEY(event_id,ordinal)
        );
        CREATE TABLE IF NOT EXISTS migration_checks(
          version INTEGER PRIMARY KEY, predecessor INTEGER, script_name TEXT NOT NULL,
          checksum TEXT NOT NULL, engine_min TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS event_resolutions(
          event_id TEXT PRIMARY KEY REFERENCES events(id),
          resolution_json TEXT NOT NULL CHECK(json_valid(resolution_json)),
          mechanical INTEGER NOT NULL CHECK(mechanical IN (0,1)),
          judgment_json TEXT NOT NULL CHECK(json_valid(judgment_json))
        );
        CREATE TABLE IF NOT EXISTS observations(
          id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id),
          event_id TEXT NOT NULL REFERENCES events(id), observer_id TEXT NOT NULL,
          subject_id TEXT NOT NULL, assertion TEXT NOT NULL, certainty TEXT NOT NULL,
          visibility TEXT NOT NULL, audience_json TEXT NOT NULL CHECK(json_valid(audience_json))
        );
        CREATE TABLE IF NOT EXISTS entity_profiles(
          branch TEXT NOT NULL REFERENCES branches(id), entity_id TEXT NOT NULL,
          identity_label TEXT, nature TEXT NOT NULL, composition_json TEXT NOT NULL,
          agency_mode TEXT NOT NULL, control_mode TEXT NOT NULL, classification_json TEXT NOT NULL,
          visibility TEXT NOT NULL DEFAULT 'gm', audience_json TEXT NOT NULL,
          source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,entity_id)
        );
        CREATE TABLE IF NOT EXISTS entity_links(
          branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, whole_id TEXT NOT NULL, part_id TEXT NOT NULL,
          relation TEXT NOT NULL, valid_from_event TEXT REFERENCES events(id), valid_until_event TEXT,
          source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
        );
        CREATE TABLE IF NOT EXISTS classification_claims(
          branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, subject_id TEXT NOT NULL, claimant_id TEXT NOT NULL,
          classification TEXT NOT NULL, mechanism TEXT, force TEXT NOT NULL, status TEXT NOT NULL,
          source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
        );
        CREATE INDEX IF NOT EXISTS processes_due ON processes(branch,state,next_tick);
        CREATE INDEX IF NOT EXISTS property_values_entity ON property_values(branch,entity_id);
        CREATE INDEX IF NOT EXISTS event_aux_lookup ON event_aux_changes(kind,state_key);
        """)
        # Add columns that early v2 files omitted. SQLite cannot add a CHECK
        # constraint safely here; value validation is performed by the engine.
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(processes)")}
        if cols and "metadata_json" not in cols:
            self.db.execute("ALTER TABLE processes ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'")
        self.db.execute(
            "INSERT OR IGNORE INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(3,2,'migration_003.sql',?,'3')",
            (hashlib.sha256(migration.read_bytes()).hexdigest() if migration.exists() else "runtime",),
        )
        # Will contracts are an additive runtime migration.  The predecessor
        # and checksum are persisted so a later engine can reject an unknown
        # or reordered upgrade instead of guessing.
        will_migration = schema_path("migration_004.sql")
        applied = self.db.execute("SELECT checksum FROM migration_checks WHERE version=4").fetchone()
        expected_checksum = hashlib.sha256(will_migration.read_bytes()).hexdigest() if will_migration.exists() else "runtime"
        if applied is None:
            predecessor = self.db.execute("SELECT MAX(version) FROM migration_checks").fetchone()[0]
            require(predecessor in (3, None), "Will migration predecessor mismatch")
            require(will_migration.exists(), "Will migration script is missing")
            self._backup_before_versioned_migration(4)
            self.db.executescript(will_migration.read_text(encoding="utf-8"))
            self.db.execute(
                "INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(4,3,'migration_004.sql',?,'4')",
                (expected_checksum,),
            )
        else:
            require(applied[0] == expected_checksum, "Will migration checksum mismatch")
        # Independent additive character component: existing runtime/API stay compatible.
        character_migration = schema_path("migration_005.sql")
        checksum = hashlib.sha256(character_migration.read_bytes()).hexdigest()
        applied = self.db.execute("SELECT checksum FROM migration_checks WHERE version=5").fetchone()
        if applied:
            require(applied[0] == checksum, "character migration checksum mismatch")
        else:
            require(self.db.execute("SELECT MAX(version) FROM migration_checks").fetchone()[0] == 4,
                    "character migration predecessor mismatch")
            self._backup_before_versioned_migration(5)
            try:
                self.db.executescript("BEGIN IMMEDIATE;\n" + character_migration.read_text())
                require(not self.db.execute("PRAGMA foreign_key_check").fetchall(), "character migration foreign key failure")
                require(self.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "character migration integrity failure")
                self.db.execute("INSERT INTO migration_checks(version,predecessor,script_name,checksum,engine_min) VALUES(5,4,'migration_005.sql',?,'4')", (checksum,))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        require(self.db.execute("SELECT version FROM engine_versions WHERE component='character_schema'").fetchone()[0] == '1',
                "unsupported character schema")

    def _seed_engine_versions(self) -> None:
        rows = [
            ("runtime_schema", "4"),
            ("property_registry", "1"),
            ("resolution_rules", "1"),
            ("story_state", "1"),
            ("workflow_api", "3"),
        ]
        for component, version in rows:
            self.db.execute(
                "INSERT OR IGNORE INTO engine_versions(component,version) VALUES(?,?)",
                (component, version),
            )
        modules = {
            "kageyoni.combat": ["combat", "action", "conflict"],
            "kageyoni.travel": ["travel", "route", "journey"],
            "kageyoni.discovery": ["discover", "search", "observation"],
            "kageyoni.training": ["train", "practice", "learn"],
            "kageyoni.social": ["negotiate", "relationship", "collective"],
            "kageyoni.downtime": ["rest", "recover", "wait"],
        }
        for module_id, triggers in modules.items():
            prior = self.db.execute("SELECT * FROM module_manifests WHERE module_id=?", (module_id,)).fetchone()
            # Known built-in routing modules survived the runtime upgrade via
            # INSERT OR IGNORE. Refresh only their exact legacy compatibility.
            if prior and json.loads(prior["compatibility_json"]) == {"runtime_schema":"3", "workflow_api":"2"}:
                self.register_module(module_id, prior["module_version"], prior["entry_skill"],
                    json.loads(prior["triggers_json"]), json.loads(prior["required_context_json"]),
                    json.loads(prior["commands_json"]), json.loads(prior["dependencies_json"]),
                    {"runtime_schema":"4", "workflow_api":"3"}, prior["visibility"], prior["source_hash"], prior["status"])
            self.db.execute(
                """INSERT OR IGNORE INTO module_manifests
                   (module_id,module_version,entry_skill,triggers_json,required_context_json,commands_json,dependencies_json,compatibility_json,visibility,source_hash,status)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (module_id, "1", "Kageyoni Play", encoded(triggers), encoded(["branch revision", "participant context"]), encoded(["propose_action", "apply"]), encoded([]), encoded({"runtime_schema": "4", "workflow_api": "3"}), "scene", None, "active"),
            )
            self.db.execute(
                """INSERT OR IGNORE INTO registry_entries
                   (kind,stable_id,version,locator,status,readers_json,writers_json,compatibility_json,source_hash,declared_by)
                   VALUES('module',?,?,?,?,?,?,?,?,?)""",
                (module_id, "1", f"module:{module_id}", "verified", encoded(["context"]), encoded(["apply"]), encoded({"runtime_schema": "4", "workflow_api": "3"}), None, "engine"),
            )
        # Stable navigation entries keep the agent from scanning the whole
        # project to find an authoritative domain or command implementation.
        for domain in DOMAINS:
            self.db.execute(
                """INSERT OR IGNORE INTO registry_entries
                   (kind,stable_id,version,locator,status,readers_json,writers_json,compatibility_json,source_hash,declared_by)
                   VALUES('domain',?,?,?,?,?,?,?,?,?)""",
                (domain, "1", f"kageyoni/model.py:DOMAINS[{domain!r}]", "verified", encoded(["Engine.context", "Engine.get"]), encoded(["Engine.apply"]), encoded({"runtime_schema": "4"}), None, "engine"),
            )
        commands = {
            "personality_context": "kageyoni/personality.py:brief",
            "personality_evaluate": "kageyoni/personality.py:evaluate",
            "personality_record": "kageyoni/personality.py:record",
            "dialogue_propose": "kageyoni/personality.py:dialogue_propose",
            "decision_propose": "kageyoni/decisions.py:propose",
            "decision_commit": "kageyoni/decisions.py:commit",
            "decision_read": "kageyoni/decisions.py:inspect",
            "decision_settle": "kageyoni/decisions.py:settle",
            "character_create": "kageyoni/characters.py:create",
            "character_read": "kageyoni/characters.py:read",
            "character_readiness": "kageyoni/characters.py:readiness",
            "session": "kageyoni/workflows.py:Workflows.open_session",
            "context": "kageyoni/engine.py:Engine.context",
            "opportunities": "kageyoni/engine.py:Engine.opportunities",
            "workflow": "kageyoni/workflows.py:Workflows.prepare",
            "apply": "kageyoni/engine.py:Engine.apply",
            "preview": "kageyoni/engine.py:Engine.apply(preview=True)",
            "advance_simulation": "kageyoni/engine.py:Engine.advance_simulation",
            "apply_consequences": "kageyoni/engine.py:Engine.apply_consequences",
            "history": "kageyoni/engine.py:Engine.causal_history",
            "replay": "kageyoni/engine.py:Engine.replay",
            "properties": "kageyoni/engine.py:Engine.properties",
            "processes": "kageyoni/engine.py:Engine.list_processes",
            "dependencies": "kageyoni/engine.py:Engine.impact",
            "registry": "kageyoni/engine.py:Engine.validate_registry",
            "backup": "kageyoni/engine.py:Engine.backup",
            "restore": "kageyoni/engine.py:Engine.restore",
            "fork": "kageyoni/engine.py:Engine.fork",
            "snapshot": "kageyoni/engine.py:Engine.register_snapshot",
            "maintain": "kageyoni/workflows.py:Workflows.maintain",
            "will_prepare": "kageyoni/engine.py:Engine.prepare_will_attempt",
            "will_apply": "kageyoni/engine.py:Engine.apply_will_attempt",
            "will_contract": "kageyoni/engine.py:Engine.get_will_contract",
        }
        for command, locator in commands.items():
            self.db.execute(
                """INSERT OR IGNORE INTO registry_entries
                   (kind,stable_id,version,locator,status,readers_json,writers_json,compatibility_json,source_hash,declared_by)
                   VALUES('command',?,?,?,?,?,?,?,?,?)""",
                (command, "3", locator, "verified", encoded(["Workflows", "agent"]), encoded(["Engine"]), encoded({"runtime_schema": "4", "workflow_api": "3"}), None, "engine"),
            )
        for migration_name, predecessor in (("migration_002.sql", "1"), ("migration_003.sql", "2"), ("migration_004.sql", "3"), ("migration_005.sql", "4"), ("migration_006.sql", "5"), ("migration_007.sql", "6")):
            self.db.execute(
                """INSERT OR IGNORE INTO registry_entries
                   (kind,stable_id,version,locator,status,readers_json,writers_json,compatibility_json,source_hash,declared_by)
                   VALUES('migration',?,?,?,?,?,?,?,?,?)""",
                (migration_name, predecessor, migration_name, "verified", encoded(["Maintain"]), encoded(["Engine._open_or_upgrade"]), encoded({"runtime_schema": "4"}), None, "engine"),
            )

    def close(self) -> None:
        self.db.close()

    def branch(self, branch: str) -> dict:
        row = self.db.execute("SELECT * FROM branches WHERE id=?", (branch,)).fetchone()
        require(row is not None, "unknown branch")
        return dict(row)

    def _decode_record(self, row: sqlite3.Row | dict) -> dict:
        r = dict(row)
        r["audience"] = json.loads(r.pop("audience_json"))
        r["evidence"] = json.loads(r.pop("evidence_json"))
        drow = self.db.execute(
            f'SELECT * FROM "{r["domain"]}" WHERE branch=? AND id=?',
            (r["branch"], r["id"]),
        ).fetchone()
        require(drow is not None, f"missing projection for {r['id']}")
        d = dict(drow)
        d.pop("branch", None)
        d.pop("id", None)
        for key, kind in DOMAINS[r["domain"]].items():
            if kind == "json" and d.get(key) is not None:
                d[key] = json.loads(d[key])
        r["data"] = d
        return r

    def get(self, branch: str, id: str) -> dict | None:
        row = self.db.execute(
            "SELECT * FROM records WHERE branch=? AND id=?", (branch, id)
        ).fetchone()
        return self._decode_record(row) if row else None

    def state(self, branch: str = "main") -> list[dict]:
        self.branch(branch)
        return [
            self._decode_record(r)
            for r in self.db.execute(
                "SELECT * FROM records WHERE branch=? ORDER BY id", (branch,)
            )
        ]

    def _entity_facets(self, branch: str, entity_id: str) -> set[str]:
        entity = self.get(branch, entity_id)
        if not entity:
            return set()
        facets = {entity["domain"]}
        if entity["domain"] == "character":
            facets.add(entity["data"].get("entity_kind", "unknown"))
        rows = self.db.execute(
            "SELECT facet FROM entity_facets WHERE branch=? AND entity_id=?",
            (branch, entity_id),
        ).fetchall()
        facets.update(r[0] for r in rows)
        return {x for x in facets if x}

    def _property_dict(self, row: sqlite3.Row | dict) -> dict:
        p = dict(row)
        if p.get("json_value") is not None:
            try:
                p["value"] = json.loads(p["json_value"])
            except json.JSONDecodeError:
                p["value"] = p["json_value"]
        elif p.get("text_value") is not None:
            p["value"] = p["text_value"] == "true" if p.get("definition_type") == "boolean" else p["text_value"]
        else:
            p["value"] = p.get("number_value")
        p.pop("json_value", None)
        return p

    def property_value(
        self, branch: str, entity_id: str, property_id: str, definition_version: int
    ) -> dict | None:
        row = self.db.execute(
            """SELECT v.*, d.value_type AS definition_type, d.unit AS definition_unit
               FROM property_values v
               JOIN property_definitions d USING(property_id,definition_version)
               WHERE v.branch=? AND v.entity_id=? AND v.property_id=? AND v.definition_version=?""",
            (branch, entity_id, property_id, definition_version),
        ).fetchone()
        return self._property_dict(row) if row else None

    def properties(
        self, branch: str = "main", entity_id: str | None = None,
        viewer: str | None = None, property_id: str | None = None
    ) -> list[dict]:
        params: list[Any] = [branch]
        sql = "SELECT v.*, d.value_type AS definition_type, d.unit AS definition_unit FROM property_values v JOIN property_definitions d USING(property_id,definition_version) WHERE v.branch=?"
        if entity_id is not None:
            sql += " AND v.entity_id=?"; params.append(entity_id)
        if property_id is not None:
            sql += " AND v.property_id=?"; params.append(property_id)
        rows = [self._property_dict(r) for r in self.db.execute(sql, params)]
        if viewer is None:
            return rows
        visible = []
        for row in rows:
            if row["visibility"] == "public":
                visible.append(row)
            elif row["visibility"] == "restricted":
                audience = (json.loads(row["context_json"]).get("audience", []) if row.get("context_json") else [])
                if viewer in audience:
                    visible.append(row)
        return visible

    def _visible(self, row: dict, viewer: str | None) -> bool:
        if viewer is None or row.get("visibility") == "public":
            return True
        if row.get("visibility") != "restricted":
            return False
        try:
            audience = row.get("audience")
            if audience is None:
                audience = json.loads(row.get("audience_json") or "[]")
            return viewer in audience
        except Exception:
            return False

    def context(
        self, branch: str = "main", domain: str | None = None, ids: Iterable[str] | None = None,
        viewer: str | None = None, scene: str | None = None, include_properties: bool = True,
        include_processes: bool = True, attention_for: str | None = None
    ) -> dict:
        require(domain is None or domain in DOMAINS, "unknown domain")
        records = self.state(branch)
        if viewer is not None:
            viewer_row = self.get(branch, viewer)
            require(viewer_row is not None and viewer_row["domain"] == "character", "unknown viewer")
            records = [r for r in records if self._visible(r, viewer)]
        if scene:
            found = [r for r in records if r["id"] == scene and r["domain"] == "scene"]
            require(found, "scene unavailable")
            wanted = {scene, found[0]["data"].get("location")}
            for r in records:
                if r["domain"] == "participation" and r["data"].get("scene") == scene:
                    wanted.update({r["id"], r["data"].get("character")})
            for _ in range(3):
                for r in records:
                    refs = {
                        r["data"].get(k)
                        for k, t in DOMAINS[r["domain"]].items()
                        if t.startswith("ref:")
                    }
                    if r["id"] in wanted or refs.intersection(wanted):
                        wanted.add(r["id"])
                        wanted.update(refs - {None})
            records = [r for r in records if r["id"] in wanted]
        if domain:
            records = [r for r in records if r["domain"] == domain]
        if ids is not None:
            ids = set(ids); records = [r for r in records if r["id"] in ids]
        if viewer is not None:
            visible_ids = {r["id"] for r in records}
            for r in records:
                r.pop("evidence", None); r.pop("audience", None); r.pop("updated_event", None)
                for k, t in DOMAINS[r["domain"]].items():
                    if t.startswith("ref:") and r["data"].get(k) not in visible_ids:
                        r["data"][k] = None
                if r["domain"] == "dialogue_turn":
                    r["data"]["listeners"] = [rid for rid in r["data"]["listeners"] if rid in visible_ids]
                # A Will contract can contain nested target/ancestry/effect
                # references that are not represented by a domain column.  Do
                # not leak those IDs through a public context projection.
                if r["domain"].startswith("will_") and isinstance(r["data"].get("contract"), dict):
                    nested_ids: set[str] = set()
                    def collect(value: Any, key: str | None = None) -> None:
                        if isinstance(value, dict):
                            if set(value) == {"id", "version"} and isinstance(value.get("id"), str):
                                nested_ids.add(value["id"])
                            for child_key, child in value.items():
                                collect(child, child_key)
                        elif isinstance(value, list):
                            for child in value:
                                collect(child, key)
                        elif isinstance(value, str) and key in {"targets", "anchor_records", "residue_records", "process_ids", "consequence_ids", "supporting_events", "source_event", "start_clock"}:
                            nested_ids.add(value)
                    collect(r["data"]["contract"])
                    hidden = {rid for rid in nested_ids if rid not in visible_ids and rid not in {r["id"], "fixture"}}
                    if hidden:
                        contract = r["data"]["contract"]
                        r["data"]["contract"] = {
                            "schema_version": contract.get("schema_version"),
                            "id": contract.get("id"),
                            "version": contract.get("version"),
                            "design_status": contract.get("design_status"),
                            "redacted": True,
                        }
        result = {
            "branch": branch,
            "revision": self.branch(branch)["revision"],
            "records": records,
            "perspective": "gm" if viewer is None else viewer,
            "runtime_versions": {
                r["component"]: r["version"]
                for r in self.db.execute("SELECT component,version FROM engine_versions")
            },
        }
        if include_properties:
            result["properties"] = self.properties(branch, viewer=viewer)
        result["entity_profiles"] = self.entity_profiles(branch, viewer=viewer)
        result["observations"] = self.observations(branch, viewer=viewer)
        if include_processes:
            procs = self.list_processes(branch, viewer=viewer)
            if attention_for:
                result["processes"] = self.rank_relevance(branch, attention_for, procs)
            else:
                result["processes"] = procs
        return result

    def opportunities(self, branch: str = "main", actor: str | None = None, viewer: str | None = None, scene: str | None = None) -> dict:
        """Return situation-derived options and constraints without closing the action space."""
        require(isinstance(actor, str) and actor, "actor required")
        subject = self.get(branch, actor)
        require(subject is not None and subject["domain"] == "character", "opportunity actor must be a character")
        visible = self.context(branch, viewer=viewer, scene=scene)
        records = visible["records"]
        by_domain = {}
        for record in records:
            by_domain.setdefault(record["domain"], []).append(record)
        location = subject["data"].get("location")
        opportunities = [{
            "id": "open-action",
            "kind": "open",
            "label": "Propose an action in your own words",
            "preconditions": [{"kind": "context", "value": "GM establishes feasibility"}],
            "stakes": "Must be stated or judged in context",
            "costs": [], "uncertainty": "Only introduced when an authorized attempt needs it",
            "affected_entities": [actor], "source": "engine:open-action",
        }]
        constraints = []
        for route in by_domain.get("route", []):
            if route["data"].get("origin") == location or route["data"].get("destination") == location:
                opportunities.append({
                    "id": f"route:{route['id']}", "kind": "route", "label": f"Consider route {route['id']}",
                    "preconditions": [{"kind": "route_access", "record": route["id"], "value": route["data"].get("access")}],
                    "stakes": route["data"].get("conditions"), "costs": [{"kind": "time", "value": route["data"].get("duration")}],
                    "uncertainty": "navigation and hazards require a resolution if contested",
                    "affected_entities": [route["id"], actor], "source": route["id"],
                })
                if route["data"].get("access") not in ("open", "conditional"):
                    constraints.append({"kind": "route", "record": route["id"], "reason": "route is not open"})
        for env in by_domain.get("environment", []):
            if env["data"].get("location") == location:
                constraints.append({"kind": "environment", "record": env["id"], "condition": env["data"].get("rule"), "effects": "GM or a declared rule determines stage-specific effects"})
        for record in by_domain.get("character", []):
            if record["id"] == actor and record["data"].get("condition") not in (None, "ready", "unknown"):
                constraints.append({"kind": "condition", "record": actor, "value": record["data"].get("condition")})
        for process in self.list_processes(branch, viewer=viewer):
            if actor in process.get("subjects", []) or process.get("scope", {}).get("location") == location:
                constraints.append({"kind": "process", "id": process["id"], "state": process["state"], "next_tick": process.get("next_tick")})
        from .personality import opportunity_context
        personality = opportunity_context(self, branch, actor, viewer, scene)
        return {
            "personality": personality,
            "branch": branch, "revision": self.branch(branch)["revision"], "actor": actor,
            "location": location, "scene": scene, "opportunities": opportunities,
            "constraints": constraints, "unknowns": ["unlisted consequences and unsupported mechanics remain GM judgment"],
            "open_action_supported": True,
        }

    def _validate_record(self, r: dict) -> None:
        domain = r["domain"]
        require(domain in DOMAINS, "unknown domain")
        require(r["status"] in STATUSES, "invalid epistemic status")
        require(r["visibility"] in ("public", "restricted", "gm"), "invalid visibility")
        require(isinstance(r["audience"], list) and all(isinstance(x, str) for x in r["audience"]), "invalid audience")
        require(r["visibility"] != "restricted" or bool(r["audience"]), "restricted record requires audience")
        require(isinstance(r["evidence"], list) and bool(r["evidence"]), "evidence required")
        for evidence in r["evidence"]:
            require(isinstance(evidence, dict) and isinstance(evidence.get("note"), str) and evidence["note"].strip(), "evidence note required")
            if evidence.get("source"):
                source = self.db.execute("SELECT content FROM sources WHERE id=?", (evidence["source"],)).fetchone()
                require(source is not None, "unknown evidence source")
                require(isinstance(evidence.get("quote"), str) and evidence["quote"] and evidence["quote"] in source[0], "evidence quote not found")
            else:
                require("quote" not in evidence, "quote requires source")
        require(set(r["data"]) <= set(DOMAINS[domain]), "unknown field")
        for field in REQUIRED[domain]:
            require(r["data"].get(field) is not None and r["data"].get(field) != "", f"missing {domain}.{field}")
        for field, kind in DOMAINS[domain].items():
            value = r["data"].get(field)
            if value is None:
                continue
            if kind in ("number", "integer"):
                require(type(value) in ((int, float) if kind == "number" else (int,)) and math.isfinite(value), f"invalid number {field}")
            elif kind == "json":
                require(isinstance(value, (dict, list)), f"invalid json {field}")
            else:
                require(isinstance(value, str), f"invalid text {field}")
            if kind.startswith("enum:"):
                require(value in kind[5:].split("|"), f"invalid enum {field}")
        for field in ("round", "actions_remaining", "quantity", "elapsed"):
            if field in r["data"] and r["data"][field] is not None:
                require(r["data"][field] >= 0, f"negative {field}")
        if domain == "resource" and r["data"].get("quantity") is not None:
            require(r["data"]["quantity"] >= 0, "negative resource")
        if domain == "objective" and r["data"].get("progress") is not None:
            require(0 <= r["data"]["progress"] <= 1, "progress out of range")
        for field in ("equipped", "survives_rewind"):
            if field in r["data"]:
                require(r["data"][field] in (0, 1), "invalid boolean")
        if domain == "thread":
            require(r["data"]["phase"] != "answered" or bool(r["data"].get("answer")), "answer required")
        if domain == "progression" and r["data"]["phase"] in ("demonstrated", "retained"):
            require(bool(r["data"].get("demonstrated")) and bool(r["data"].get("cost")), "progression demonstration and cost assessment required")
        if domain == "office":
            require((r["data"]["phase"] != "occupied" or r["data"].get("holder")) and (r["data"]["phase"] != "vacant" or not r["data"].get("holder")), "office holder contradicts phase")
        if domain.startswith("will_"):
            try:
                validate_contract(domain, r["data"].get("contract"), r["id"], r["version"])
            except WillContractError as exc:
                raise Rejected(str(exc)) from exc
        from .characters import validate as validate_character
        validate_character(r, require)
        from .personality import validate_record as validate_personality
        validate_personality(r)
        from .writing import validate_record as validate_writing
        validate_writing(r)

    def _write(self, r: dict, create: bool) -> None:
        require(create or r["domain"] not in ("writing_delivery","dialogue_reception"), "writing history is immutable; create a superseding record")
        args = (
            r["branch"], r["id"], r["domain"], r["version"], r["status"],
            r["visibility"], encoded(r["audience"]), encoded(r["evidence"]), r["updated_event"],
        )
        if create:
            self.db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)", args)
        else:
            self.db.execute(
                "UPDATE records SET domain=?,version=?,status=?,visibility=?,audience_json=?,evidence_json=?,updated_event=? WHERE branch=? AND id=?",
                args[2:] + args[:2],
            )
        fields = list(DOMAINS[r["domain"]])
        vals = [
            encoded(r["data"].get(f)) if DOMAINS[r["domain"]][f] == "json" and r["data"].get(f) is not None else r["data"].get(f)
            for f in fields
        ]
        columns = ",".join(f'"{f}"' for f in fields)
        if create:
            self.db.execute(
                f'INSERT INTO "{r["domain"]}"(branch,id,{columns}) VALUES({",".join("?" for _ in range(2 + len(fields)))})',
                [r["branch"], r["id"]] + vals,
            )
        else:
            set_clause = ",".join(f'"{f}"=?' for f in fields)
            self.db.execute(
                f'UPDATE "{r["domain"]}" SET {set_clause} WHERE branch=? AND id=?',
                vals + [r["branch"], r["id"]],
            )

    def _record_at_version(self, branch: str, record_id: str, version: int) -> dict | None:
        """Return an exact historical record image retained in ``changes``."""
        current = self.get(branch, record_id)
        if current and current["version"] == version:
            return current
        history = self.db.execute(
            "SELECT record_json FROM will_contract_history WHERE branch=? AND record_id=? AND version=?",
            (branch, record_id, version),
        ).fetchone()
        if history:
            return json.loads(history[0])
        rows = self.db.execute(
            """SELECT c.after_json FROM changes c JOIN events e ON e.id=c.event_id
               WHERE e.branch=? AND c.record_id=? ORDER BY e.revision,c.ordinal""",
            (branch, record_id),
        )
        for row in rows:
            image = json.loads(row[0])
            if image.get("version") == version:
                return image
        return None

    def get_will_contract(self, branch: str, domain: str, record_id: str, version: int | None = None) -> dict:
        """Read an exact Will contract version; never silently substitute latest."""
        require(domain.startswith("will_"), "Will contract domain required")
        require(domain in DOMAINS, "unknown Will domain")
        record = self.get(branch, record_id) if version is None else self._record_at_version(branch, record_id, int(version))
        require(record is not None and record["domain"] == domain, "Will record not found")
        target_version = int(record["version"])
        contract = record["data"].get("contract")
        try:
            return copy.deepcopy(validate_contract(domain, contract, record_id, target_version))
        except WillContractError as exc:
            raise Rejected(str(exc)) from exc

    def _will_record_ref(self, branch: str, expected_domain: str, value: dict, path: str) -> dict:
        require(isinstance(value, dict) and set(value) == {"id", "version"}, f"{path} must be an exact reference")
        require(type(value["version"]) is int and value["version"] > 0, f"{path}.version is required")
        record = self._record_at_version(branch, value["id"], value["version"])
        require(record is not None and record.get("domain") == expected_domain, f"{path} does not resolve to {expected_domain}")
        return record

    def _validate_will_references(self, branch: str, records: dict[str, dict]) -> None:
        """Validate exact cross-record/rule references and Will invariants."""
        will_records = {r["id"]: r for r in records.values() if r["domain"].startswith("will_")}
        ancestry: dict[tuple[str, int], list[tuple[str, int]]] = {}
        for r in will_records.values():
            domain = r["domain"]
            contract = r["data"]["contract"]
            try:
                refs = contract_refs(domain, contract)
            except (KeyError, TypeError, WillContractError) as exc:
                raise Rejected(f"invalid {domain} dependency: {exc}") from exc
            for kind, ref, path in refs:
                if kind == "rule":
                    require(isinstance(ref, dict) and type(ref.get("version")) is int, f"{path} needs a versioned rule")
                    require(self.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id=? AND rule_version=?", (ref["id"], ref["version"])).fetchone() is not None, f"unknown rule dependency {ref['id']}@{ref['version']}")
                elif kind in DOMAINS:
                    self._will_record_ref(branch, kind, ref, path)
            key = (r["id"], r["version"])
            if domain == "will_definition":
                ancestry[key] = [(a["parent"]["id"], a["parent"]["version"]) for a in contract.get("ancestry", []) if a.get("relation") == "derived_from"]
            if domain == "will_expression":
                definition = self._will_record_ref(branch, "will_definition", contract["definition"], f"{r['id']}.definition")
                require(r["data"].get("definition") == definition["id"], f"{r['id']}.definition does not match contract")
                bearer = records.get(r["data"]["bearer"])
                require(bearer is not None and bearer["domain"] in {"character", "location", "faction"}, f"{r['id']} has invalid bearer")
                if r["data"].get("legacy_will") is not None:
                    legacy = records.get(r["data"]["legacy_will"])
                    require(legacy is not None and legacy["domain"] == "will", f"{r['id']} legacy Will reference is invalid")
            elif domain == "will_technique":
                expression = self._will_record_ref(branch, "will_expression", contract["expression"], f"{r['id']}.expression")
                require(r["data"].get("expression") == expression["id"], f"{r['id']} expression does not match contract")
                if r["data"].get("ability") is not None:
                    require(records.get(r["data"]["ability"], {}).get("domain") == "ability", f"{r['id']} ability reference is invalid")
            elif domain == "will_awakening":
                self._will_record_ref(branch, "will_expression", contract["expression"], f"{r['id']}.expression")
            elif domain == "will_development":
                self._will_record_ref(branch, "will_expression", contract["expression"], f"{r['id']}.expression")
                if r["data"].get("progression") is not None:
                    require(records.get(r["data"]["progression"], {}).get("domain") == "progression", f"{r['id']} progression reference is invalid")
                for event_id in contract.get("supporting_events", []):
                    require(self.db.execute("SELECT 1 FROM events WHERE branch=? AND id=?", (branch, event_id)).fetchone() is not None, f"{r['id']} supporting event is missing")
            elif domain == "will_effect":
                self._will_record_ref(branch, "will_expression", contract["expression"], f"{r['id']}.expression")
                self._will_record_ref(branch, "will_technique", contract["technique"], f"{r['id']}.technique")
                require(self.db.execute("SELECT 1 FROM events WHERE branch=? AND id=?", (branch, contract["source_event"])).fetchone() is not None, f"{r['id']} source event is missing")
                require(records.get(contract["start_clock"], {}).get("domain") == "clock", f"{r['id']} start_clock is invalid")
                for ref_id in contract.get("targets", []) + contract.get("anchor_records", []) + contract.get("residue_records", []):
                    require(ref_id in records, f"{r['id']} target/anchor/residue record is missing")
                for process_id in contract.get("process_ids", []):
                    require(self.db.execute("SELECT 1 FROM processes WHERE branch=? AND id=?", (branch, process_id)).fetchone() is not None, f"{r['id']} process is missing")
                for consequence_id in contract.get("consequence_ids", []):
                    require(self.db.execute("SELECT 1 FROM consequences WHERE branch=? AND id=?", (branch, consequence_id)).fetchone() is not None, f"{r['id']} consequence is missing")
        visiting: set[tuple[str, int]] = set(); visited: set[tuple[str, int]] = set()
        def visit(node: tuple[str, int]) -> None:
            require(node not in visiting, "Will ancestry cycle")
            if node in visited:
                return
            visiting.add(node)
            for parent in ancestry.get(node, []):
                self._will_record_ref(branch, "will_definition", {"id": parent[0], "version": parent[1]}, "Will ancestry")
                visit(parent)
            visiting.remove(node); visited.add(node)
        for node in ancestry:
            visit(node)

    def _validate_world(self, branch: str) -> None:
        records = {r["id"]: r for r in self.state(branch)}
        for r in records.values():
            self._validate_record(r)
            for field, kind in DOMAINS[r["domain"]].items():
                value = r["data"].get(field)
                if kind.startswith("ref:") and value is not None:
                    require(value in records and records[value]["domain"] in kind[4:].split("|"), f"wrong or missing reference {r['id']}.{field}")
            for viewer in r["audience"]:
                require(viewer in records and records[viewer]["domain"] == "character", "invalid audience character")
            if r["domain"] == "location":
                seen = {r["id"]}; parent = r["data"].get("parent")
                while parent:
                    require(parent in records, "missing location parent")
                    require(parent not in seen, "location cycle")
                    seen.add(parent); parent = records[parent]["data"].get("parent")
            if r["domain"] == "loot" and r["data"]["discovery"] == "claimed":
                require(r["data"].get("claimant") is not None, "claimed loot needs claimant")
                require(any(x["domain"] == "loadout" and x["data"]["item"] == r["data"]["item"] and x["data"]["holder"] == r["data"]["claimant"] for x in records.values()), "claim requires custody")
            if r["domain"] == "participation":
                char = records[r["data"]["character"]]["data"]; scene = records[r["data"]["scene"]]["data"]
                if scene["phase"] != "closed":
                    require(char.get("location") == scene["location"], "participant not at scene location")
        from .characters import validate_world as validate_characters
        validate_characters(records, require)
        from .personality import validate_world as validate_personalities
        validate_personalities(self, branch, records)
        from .writing import validate_world as validate_writing_world
        validate_writing_world(records)
        edges: dict[str, list[str]] = {}
        for r in records.values():
            if r["domain"] == "dependency" and r["data"]["relation"] == "requires":
                edges.setdefault(r["data"]["objective"], []).append(r["data"]["prerequisite"])
        def visit(node: str, path: set[str]) -> None:
            require(node not in path, "objective dependency cycle")
            for child in edges.get(node, []):
                visit(child, path | {node})
        for node in edges:
            visit(node, set())
        for row in self.db.execute("SELECT * FROM property_values WHERE branch=?", (branch,)):
            require(self.get(branch, row["entity_id"]) is not None, "property subject missing")
            self._validate_property_assignment(branch, dict(row), stored=True)
        for row in self.db.execute("SELECT * FROM processes WHERE branch=?", (branch,)):
            self._validate_process(dict(row), branch, stored=True)
        self._validate_will_references(branch, records)

    def _definition(self, property_id: str, version: int) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT * FROM property_definitions WHERE property_id=? AND definition_version=?",
            (property_id, version),
        ).fetchone()
        require(row is not None, "unknown property definition")
        return row

    def _property_value_parts(self, definition: sqlite3.Row, state: str, value: Any, unit: str | None) -> tuple[Any, Any, Any]:
        number = text_value = json_value = None
        if state != "known":
            require(value is None, "non-known property cannot carry a value")
            return number, text_value, json_value
        kind = definition["value_type"]
        if kind == "number":
            require(type(value) in (int, float) and math.isfinite(value), "property needs finite number")
            number = float(value)
        elif kind == "integer":
            require(type(value) is int, "property needs integer")
            number = value
        elif kind == "text":
            require(isinstance(value, str), "property needs text")
            text_value = value
        elif kind == "boolean":
            require(type(value) is bool, "property needs boolean")
            text_value = "true" if value else "false"
        elif kind == "reference":
            require(isinstance(value, str) and bool(value), "property needs reference")
            text_value = value
        else:
            require(isinstance(value, (dict, list)), "property needs structured value")
            json_value = encoded(value)
        if definition["unit"] is not None:
            require(unit == definition["unit"], f"incompatible unit: expected {definition['unit']}")
        elif unit is not None:
            require(isinstance(unit, str) and bool(unit), "invalid unit")
        constraints = json.loads(definition["constraints_json"])
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "min" in constraints: require(value >= constraints["min"], "property below minimum")
            if "max" in constraints: require(value <= constraints["max"], "property above maximum")
        if "allowed" in constraints and state == "known":
            require(value in constraints["allowed"], "property value is not permitted")
        return number, text_value, json_value

    def _validate_property_assignment(self, branch: str, assignment: dict, stored: bool = False) -> None:
        state = assignment["state"]; require(state in _PROPERTY_STATES, "invalid property state")
        definition = self._definition(assignment["property_id"], int(assignment["definition_version"]))
        lifecycle = self.db.execute(
            "SELECT state FROM property_lifecycle WHERE property_id=? AND definition_version=? ORDER BY sequence DESC LIMIT 1",
            (assignment["property_id"], assignment["definition_version"]),
        ).fetchone()
        require(lifecycle is not None, "property has no lifecycle")
        if not stored:
            require(lifecycle[0] not in ("retired", "deprecated"), "property is not active")
        entity = self.get(branch, assignment["entity_id"]); require(entity is not None, "unknown property subject")
        applicability = json.loads(definition["applicability_json"])
        if isinstance(applicability, dict):
            allowed_facets = set(applicability.get("facets", []))
        else:
            allowed_facets = set(applicability or [])
        if allowed_facets:
            require(bool(self._entity_facets(branch, assignment["entity_id"]) & allowed_facets), "property is not applicable to entity")
        context = assignment.get("context_json", assignment.get("context", {}))
        if isinstance(context, str):
            context = json.loads(context)
        require(isinstance(context, dict), "invalid property context")
        if assignment.get("visibility", "gm") == "restricted":
            require(isinstance(context.get("audience", []), list) and context.get("audience"), "restricted property needs audience")
        if stored:
            value = assignment.get("number_value") if definition["value_type"] in ("number", "integer") else assignment.get("text_value")
            if definition["value_type"] in ("structured",):
                value = json.loads(assignment["json_value"]) if assignment.get("json_value") else None
            elif definition["value_type"] == "boolean" and assignment.get("text_value") is not None:
                value = assignment.get("text_value") == "true"
            elif definition["value_type"] == "integer" and isinstance(value, float) and value.is_integer():
                value = int(value)
            self._property_value_parts(definition, state, value, assignment.get("unit"))
        else:
            self._property_value_parts(definition, state, assignment.get("value"), assignment.get("unit"))

    def _property_json(self, branch: str, assignment: dict, event_id: str | None = None) -> dict:
        context = assignment.get("context", {})
        require(isinstance(context, dict), "invalid property context")
        definition = self._definition(assignment["property_id"], int(assignment["definition_version"]))
        number, text_value, json_value = self._property_value_parts(
            definition, assignment["state"], assignment.get("value"), assignment.get("unit")
        )
        return {
            "branch": branch, "entity_id": assignment["entity_id"], "property_id": assignment["property_id"],
            "definition_version": int(assignment["definition_version"]), "state": assignment["state"],
            "number_value": number, "text_value": text_value, "json_value": json_value,
            "unit": assignment.get("unit"), "context_json": encoded(context),
            "valid_from_event": event_id, "valid_until_event": assignment.get("valid_until_event"),
            "epistemic_status": assignment.get("epistemic_status", "proposed"),
            "visibility": assignment.get("visibility", "gm"),
        }

    def _apply_property(self, branch: str, assignment: dict, event_id: str) -> tuple[dict | None, dict]:
        self._validate_property_assignment(branch, assignment)
        key = (branch, assignment["entity_id"], assignment["property_id"], int(assignment["definition_version"]))
        old_row = self.db.execute(
            "SELECT * FROM property_values WHERE branch=? AND entity_id=? AND property_id=? AND definition_version=?",
            key,
        ).fetchone()
        old = dict(old_row) if old_row else None
        new = self._property_json(branch, assignment, event_id)
        self.db.execute(
            """INSERT INTO property_values
               (branch,entity_id,property_id,definition_version,state,number_value,text_value,json_value,unit,context_json,valid_from_event,valid_until_event,epistemic_status,visibility)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(branch,entity_id,property_id,definition_version) DO UPDATE SET
                 state=excluded.state,number_value=excluded.number_value,text_value=excluded.text_value,
                 json_value=excluded.json_value,unit=excluded.unit,context_json=excluded.context_json,
                 valid_from_event=excluded.valid_from_event,valid_until_event=excluded.valid_until_event,
                 epistemic_status=excluded.epistemic_status,visibility=excluded.visibility""",
            tuple(new[k] for k in ("branch","entity_id","property_id","definition_version","state","number_value","text_value","json_value","unit","context_json","valid_from_event","valid_until_event","epistemic_status","visibility")),
        )
        return old, new

    def _process_from_input(self, branch: str, p: dict, event_id: str | None = None) -> dict:
        require(isinstance(p, dict), "process must be an object")
        require(isinstance(p.get("id"), str) and p["id"], "process id required")
        require(p.get("process_kind") or p.get("kind"), "process kind required")
        kind = p.get("process_kind", p.get("kind"))
        state = p.get("state", "active")
        require(state in {"active","paused","due","blocked","completed","cancelled"}, "invalid process state")
        return {
            "branch": branch, "id": p["id"], "process_kind": kind, "state": state,
            "subjects_json": encoded(p.get("subjects", p.get("subjects_json", [])) if not isinstance(p.get("subjects", p.get("subjects_json", [])), str) else json.loads(p["subjects_json"])),
            "scope_json": encoded(p.get("scope", p.get("scope_json", {})) if not isinstance(p.get("scope", p.get("scope_json", {})), str) else json.loads(p["scope_json"])),
            "origin_event": event_id or p.get("origin_event"), "rule_id": p.get("rule_id"),
            "rule_version": p.get("rule_version"), "conditions_json": encoded(p.get("conditions", p.get("conditions_json", {})) if not isinstance(p.get("conditions", p.get("conditions_json", {})), str) else json.loads(p["conditions_json"])),
            "subscriptions_json": encoded(p.get("subscriptions", p.get("subscriptions_json", [])) if not isinstance(p.get("subscriptions", p.get("subscriptions_json", [])), str) else json.loads(p["subscriptions_json"])),
            "last_tick": p.get("last_tick"), "next_tick": p.get("next_tick"), "interval_value": p.get("interval_value"),
            "interval_unit": p.get("interval_unit"), "granularity": p.get("granularity", "exact"),
            "rng_slot": p.get("rng_slot"), "pending_judgment": p.get("pending_judgment"),
            "visibility": p.get("visibility", "gm"), "metadata_json": encoded(p.get("metadata", p.get("metadata_json", {})) if not isinstance(p.get("metadata", p.get("metadata_json", {})), str) else json.loads(p["metadata_json"])),
            "updated_event": event_id or p.get("updated_event"),
        }

    def _process_json(self, row: sqlite3.Row | dict) -> dict:
        p = dict(row)
        for col, target in (("subjects_json","subjects"),("scope_json","scope"),("conditions_json","conditions"),("subscriptions_json","subscriptions"),("metadata_json","metadata")):
            raw = p.pop(col, "{}")
            p[target] = json.loads(raw or ("[]" if target in ("subjects","subscriptions") else "{}"))
        return p

    def _validate_process(self, p: dict, branch: str, stored: bool = False) -> None:
        require(p.get("state") in {"active","paused","due","blocked","completed","cancelled"}, "invalid process state")
        require(p.get("granularity", "exact") in {"exact","threshold","aggregate","judgment"}, "invalid process granularity")
        require(p.get("visibility", "gm") in {"public","restricted","gm"}, "invalid process visibility")
        if p.get("rule_id") is not None:
            require(self.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id=? AND rule_version=?", (p["rule_id"], p["rule_version"])).fetchone() is not None, "process rule not found")
        if p.get("next_tick") is not None:
            require(type(p["next_tick"]) in (int,float) and math.isfinite(p["next_tick"]), "invalid process due time")
        if not stored:
            for x in p.get("subjects", []):
                require(self.get(branch, x) is not None, "process subject not found")

    def _read_resolution(self, resolution: dict | None) -> dict | None:
        if resolution is None:
            return None
        require(isinstance(resolution, dict), "resolution must be an object")
        allowed = {"permission","probability","magnitude","cost","timing","consequences","difficulty","modifier","roll_id","roll_result","roll","feasible","judgment","judgment_required","outcome","inputs","rules","rule_results","rule_versions","mechanical"}
        require(set(resolution) <= allowed, "unknown resolution field")
        require(isinstance(resolution.get("feasible", True), bool), "resolution feasibility must be boolean")
        if "permission" in resolution:
            require(isinstance(resolution["permission"], dict), "permission stage must be object")
        if "probability" in resolution:
            require(isinstance(resolution["probability"], dict), "probability stage must be object")
        return resolution

    def _validate_dependency(self, branch: str, dep: dict) -> None:
        require(isinstance(dep, dict) and {"kind","ref_id","usage"} <= set(dep), "invalid event dependency")
        kind, ref_id = dep["kind"], dep["ref_id"]
        if kind == "rule":
            version = dep.get("version")
            require(version is not None and self.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id=? AND rule_version=?", (ref_id, int(version))).fetchone() is not None, "unknown rule dependency")
        elif kind == "property":
            version = dep.get("version")
            require(version is not None and self.db.execute("SELECT 1 FROM property_definitions WHERE property_id=? AND definition_version=?", (ref_id, int(version))).fetchone() is not None, "unknown property dependency")
        elif kind == "record":
            version = dep.get("version")
            require(version is not None and self._record_at_version(branch, ref_id, int(version)) is not None, "unknown record dependency")
        elif kind == "module":
            row = self.db.execute("SELECT * FROM module_manifests WHERE module_id=?", (ref_id,)).fetchone()
            require(row is not None, "unknown module dependency")
            require(dep.get("version") is not None and str(dep["version"]) == str(row["module_version"]), "module version mismatch")
            compatibility = json.loads(row["compatibility_json"])
            current = {r["component"]: r["version"] for r in self.db.execute("SELECT component,version FROM engine_versions")}
            for component, required_version in compatibility.items():
                require(str(current.get(component)) == str(required_version), f"module incompatible with {component} {required_version}")
        else:
            require(isinstance(ref_id, str) and ref_id, "invalid dependency reference")

    def _aux_state_key(self, kind: str, row: dict) -> str:
        if kind == "property":
            return f"{row['branch']}:{row['entity_id']}:{row['property_id']}:{row['definition_version']}"
        if kind == "process":
            return f"{row['branch']}:{row['id']}"
        if kind == "facet":
            return f"{row['branch']}:{row['entity_id']}:{row['facet']}"
        if kind == "consequence":
            return f"{row['branch']}:{row['id']}"
        return digest(row)

    def _replay_state_key(self, kind: str, row: dict) -> str:
        """Stable key for a snapshot row or an event auxiliary image."""
        branch = row.get("branch", "")
        if kind in {"property", "process", "facet", "consequence"}:
            return self._aux_state_key(kind, row)
        if kind in {"profile", "link", "classification"}:
            return f"{branch}:{row.get('entity_id', row.get('id'))}"
        if kind in {"choice", "observation"}:
            return f"{branch}:{row.get('id')}"
        if kind == "run":
            return f"{branch}:{row.get('process_id')}:{row.get('run_key')}"
        if kind == "consequence_run":
            return f"{branch}:{row.get('consequence_id')}:{row.get('run_key')}"
        if kind == "resolution":
            return str(row.get("event_id"))
        if kind == "will_attempt":
            return f"{branch}:{row.get('attempt_id')}"
        if kind == "will_history":
            return f"{branch}:{row.get('record_id')}:{row.get('version')}"
        return f"{kind}:{digest(row)}"

    def _insert_aux(self, event_id: str, ordinal: int, kind: str, key: str, before: Any, after: Any) -> None:
        self.db.execute(
            "INSERT INTO event_aux_changes(event_id,ordinal,kind,state_key,before_json,after_json) VALUES(?,?,?,?,?,?)",
            (event_id, ordinal, kind, key, encoded(before) if before is not None else None, encoded(after) if after is not None else None),
        )

    def _current_process(self, branch: str, process_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM processes WHERE branch=? AND id=?", (branch, process_id)).fetchone()
        return self._process_json(row) if row else None

    def _write_process(self, p: dict, create: bool) -> None:
        cols = [
            "branch","id","process_kind","state","subjects_json","scope_json","origin_event","rule_id","rule_version",
            "conditions_json","subscriptions_json","last_tick","next_tick","interval_value","interval_unit",
            "granularity","rng_slot","pending_judgment","visibility","metadata_json","updated_event",
        ]
        vals = [p.get(c) for c in cols]
        if create:
            self.db.execute(f"INSERT INTO processes({','.join(cols)}) VALUES({','.join('?' for _ in cols)})", vals)
        else:
            sets = ",".join(f"{c}=?" for c in cols[2:])
            self.db.execute(f"UPDATE processes SET {sets} WHERE branch=? AND id=?", vals[2:] + [p["branch"], p["id"]])

    def list_processes(self, branch: str = "main", viewer: str | None = None) -> list[dict]:
        rows = [self._process_json(r) for r in self.db.execute("SELECT * FROM processes WHERE branch=? ORDER BY id", (branch,))]
        if viewer is None:
            return rows
        return [p for p in rows if p["visibility"] == "public" or (p["visibility"] == "restricted" and viewer in p.get("scope", {}).get("audience", []))]

    def entity_profiles(self, branch: str = "main", viewer: str | None = None) -> list[dict]:
        rows = []
        for row in self.db.execute("SELECT * FROM entity_profiles WHERE branch=? ORDER BY entity_id", (branch,)):
            p = dict(row)
            p["composition"] = json.loads(p.pop("composition_json"))
            p["classification"] = json.loads(p.pop("classification_json"))
            p["audience"] = json.loads(p.pop("audience_json"))
            if viewer is None or p["visibility"] == "public" or (p["visibility"] == "restricted" and viewer in p["audience"]):
                if viewer is not None:
                    p.pop("audience", None)
                rows.append(p)
        return rows

    def observations(self, branch: str = "main", viewer: str | None = None) -> list[dict]:
        rows = []
        for row in self.db.execute("SELECT * FROM observations WHERE branch=? ORDER BY id", (branch,)):
            o = dict(row); o["audience"] = json.loads(o.pop("audience_json"))
            if viewer is None or o["visibility"] == "public" or (o["visibility"] == "restricted" and viewer in o["audience"]):
                if viewer is not None:
                    o.pop("audience", None)
                rows.append(o)
        return rows

    def _validate_consequence(self, con: dict, branch: str) -> None:
        require(isinstance(con, dict) and {"id","subject_id","effect","trigger"} <= set(con), "invalid consequence")
        require(isinstance(con["id"], str) and con["id"], "consequence id required")
        require(isinstance(con["effect"], dict) and isinstance(con["trigger"], dict), "consequence effect and trigger must be objects")
        require(self.get(branch, con["subject_id"]) is not None or con.get("subject_id") in {"world","environment"}, "consequence subject not found")

    def apply(self, command: dict, preview: bool = False) -> dict:
        require(isinstance(command, dict), "command must be object")
        if str(command.get('request_id','')).startswith('decision:'):
            require(getattr(self,'_coordinated_decision',None)==digest(command), 'use decision-commit for reserved decisions')
        if str(command.get("request_id", "")).startswith(("writing:", "writing-reception:")):
            require(getattr(self,"_writing_command",None)==digest(command), "use writing workflows for reserved writing commands")
        allowed = {
            "api_version","branch","expected_revision","request_id","kind","actor","narrative","changes",
            "causes","clock_id","tick","roll_ids","dependencies","consequences","choice","properties",
            "facet_changes","processes","consequence_runs","resolution","judgment","observations",
            "process_runs","profiles","entity_links","classification_claims","assumptions","visibility","will_attempt",
            "requirements",
        }
        require(set(command) <= allowed, "unknown command field")
        require(command.get("api_version") in (1, 2, 3), "unsupported API version")
        for key in ("branch","request_id","kind","actor","narrative"):
            require(isinstance(command.get(key), str) and command[key].strip(), f"missing {key}")
        require(command["kind"] in _EVENT_KINDS, "invalid event kind")
        require(type(command.get("expected_revision")) is int, "expected revision required")
        require(isinstance(command.get("changes", []), list), "changes required")
        aux_present = any(command.get(k) for k in ("properties","facet_changes","processes","consequence_runs","resolution","observations","process_runs","profiles","entity_links","classification_claims","will_attempt"))
        require(bool(command.get("changes")) or aux_present or command["kind"] == "failed_action" or command.get("dependencies") or command.get("consequences") or command.get("choice"), "empty event")
        branch = command["branch"]
        try:
            payload_hash = digest(command)
        except (TypeError, ValueError) as exc:
            raise Rejected("command is not finite JSON") from exc
        from .persistence.unit_of_work import UnitOfWork
        transaction = UnitOfWork(self.db)
        transaction.__enter__()
        try:
            existing = self.db.execute(
                "SELECT payload_hash,receipt_json FROM events WHERE branch=? AND request_id=?",
                (branch, command["request_id"]),
            ).fetchone()
            if existing:
                require(existing[0] == payload_hash, "request key reused with different payload")
                transaction.rollback()
                result = json.loads(existing[1]); result["replayed"] = True
                return result
            meta = self.branch(branch)
            require(meta["revision"] == command["expected_revision"], "stale branch revision")
            will_attempt_row = self._validate_will_apply_command(branch, command) if command["kind"] == "will_attempt" else None
            causes = command.get("causes", [])
            require(isinstance(causes, list) and all(isinstance(x, str) for x in causes), "causes must be list of IDs")
            require(isinstance(command.get("roll_ids", []), list) and all(isinstance(x, str) for x in command.get("roll_ids", [])), "roll IDs must be list")
            for cause in causes:
                require(self.db.execute("SELECT 1 FROM events WHERE id=? AND branch=?", (cause, branch)).fetchone() is not None, "cause must exist in this branch")
            if command["kind"] in ("correction", "rewind"):
                require(bool(causes), "correction or rewind needs cause")
            for roll_id in command.get("roll_ids", []):
                require(self.db.execute("SELECT 1 FROM rolls WHERE branch=? AND id=?", (branch, roll_id)).fetchone() is not None, "unknown roll")
                require(self.db.execute("SELECT 1 FROM roll_uses WHERE branch=? AND id=?", (branch, roll_id)).fetchone() is None, "roll already spent")
            clock_id, tick = command.get("clock_id"), command.get("tick")
            require((clock_id is None) == (tick is None), "clock and tick required together")
            if clock_id:
                clock = self.get(branch, clock_id)
                require(clock is not None and clock["domain"] == "clock", "invalid event clock")
                require(type(tick) in (int,float) and math.isfinite(tick), "invalid event tick")
                require(command["kind"] == "rewind" or tick >= clock["data"]["tick"], "time moved backwards without rewind")
            previous = self.db.execute("SELECT event_hash FROM events WHERE branch=? ORDER BY revision DESC LIMIT 1", (branch,)).fetchone()
            prev_hash = previous[0] if previous else ""
            event_id, revision = str(uuid.uuid4()), meta["revision"] + 1
            pending: list[tuple[dict | None, dict]] = []
            seen: set[str] = set()
            for change in command.get("changes", []):
                require(isinstance(change, dict) and set(change) <= {"op","id","domain","expected_version","data","status","visibility","audience","evidence"}, "invalid change fields")
                rid = change.get("id"); require(isinstance(rid, str) and rid and rid not in seen, "missing or repeated record ID"); seen.add(rid)
                old = self.get(branch, rid); op = change.get("op")
                require(op in ("create","patch"), "unsupported change operation")
                if op == "create":
                    require(old is None, "record already exists"); require(change.get("expected_version", 0) == 0, "new record version must be zero")
                    r = {"branch": branch, "id": rid, "domain": change.get("domain"), "version": 1, "status": change.get("status", "unknown"), "visibility": change.get("visibility", "gm"), "audience": change.get("audience", []), "evidence": change.get("evidence", []), "data": change.get("data", {}), "updated_event": event_id}
                else:
                    require(old is not None, "record missing"); require(change.get("expected_version") == old["version"], "stale record version")
                    require(change.get("domain", old["domain"]) == old["domain"], "cannot change domain")
                    r = copy.deepcopy(old); r["version"] += 1; r["updated_event"] = event_id
                    require(isinstance(change.get("data", {}), dict), "data must be object"); r["data"].update(change.get("data", {}))
                    for key in ("status","visibility","audience"):
                        if key in change: r[key] = change[key]
                    require(bool(change.get("evidence")), "new evidence required for patch"); r["evidence"] = change["evidence"]
                    if old["domain"] == "clock" and r["data"].get("tick") < old["data"].get("tick"):
                        require(command["kind"] == "rewind", "clock reversal needs rewind")
                self._validate_record(r)
                r["data"] = {f: r["data"].get(f) for f in DOMAINS[r["domain"]]}
                pending.append((old, r))
            # Validate explicit command requirements if supplied
            for req in command.get("requirements", []):
                require(isinstance(req, dict), "requirement must be object", rejection_class="MALFORMED_REQUEST")
                req_id = req.get("record_id") or req.get("id")
                req_field = req.get("field", "condition")
                req_equals = req.get("equals")
                target_rec = self.get(branch, req_id)
                require(target_rec is not None, f"Required record '{req_id}' missing in world state", rejection_class="PREREQUISITE_MISSING", details={"required_record": req_id, "field": req_field, "expected": req_equals, "actual": None})
                actual_val = target_rec["data"].get(req_field)
                require(actual_val == req_equals, f"Requirement not met for '{req_id}': expected {req_field}='{req_equals}', got '{actual_val}'", rejection_class="PREREQUISITE_MISSING", details={"required_record": req_id, "field": req_field, "expected": req_equals, "actual": actual_val})
            # Evaluate mechanical world rules for physical and environmental invariants
            all_state = self.state(branch)
            world_rules = [w for w in all_state if w["domain"] == "world_rule" and w["data"].get("resolution") == "mechanical"]
            for wr in world_rules:
                stmt_text = wr["data"].get("statement", "")
                if stmt_text.startswith("{") and stmt_text.endswith("}"):
                    try:
                        rule_spec = json.loads(stmt_text)
                    except Exception:
                        rule_spec = None
                    if isinstance(rule_spec, dict):
                        target_id = rule_spec.get("target_id")
                        prohibited_ops = rule_spec.get("prohibited_ops", ["patch"])
                        for ch in command.get("changes", []):
                            if ch.get("id") == target_id and ch.get("op") in prohibited_ops:
                                req_id = rule_spec.get("required_record")
                                req_field = rule_spec.get("required_field", "condition")
                                req_val = rule_spec.get("required_equals")
                                if req_id:
                                    req_rec = self.get(branch, req_id)
                                    req_actual = req_rec["data"].get(req_field) if req_rec else None
                                    if req_actual != req_val:
                                        msg = rule_spec.get("rejection_message") or f"World rule '{wr['data'].get('name')}' prerequisite missing: {req_id}.{req_field} == {req_val}"
                                        rej_cls = rule_spec.get("rejection_class", "PREREQUISITE_MISSING")
                                        raise Rejected(msg, rejection_class=rej_cls, details={"rule_id": wr["id"], "target_id": target_id, "required_record": req_id, "field": req_field, "expected": req_val, "actual": req_actual})
                                elif rule_spec.get("prohibit_direct_breach"):
                                    msg = rule_spec.get("rejection_message") or f"World rule '{wr['data'].get('name')}' prohibits direct modification."
                                    rej_cls = rule_spec.get("rejection_class", "HARD_INVARIANT_VIOLATION")
                                    raise Rejected(msg, rejection_class=rej_cls, details={"rule_id": wr["id"], "target_id": target_id})
            event_hash = digest({"previous": prev_hash, "payload_hash": payload_hash, "changes": pending})
            resolution = self._read_resolution(command.get("resolution"))
            # Validate declared dependencies before inserting the event row.
            # The surrounding transaction still protects later checks, but a
            # mismatched skill/rule interface should fail before any durable
            # event or projection mutation is attempted.
            for dep in command.get("dependencies", []):
                self._validate_dependency(branch, dep)
            explicit_process_ids = {p.get("id") for p in command.get("processes", []) if isinstance(p, dict) and p.get("id")}
            triggered_process_ids = [
                row["id"] for row in self.db.execute(
                    """SELECT p.id FROM processes p
                       JOIN process_subscriptions s ON s.branch=p.branch AND s.process_id=p.id
                       WHERE p.branch=? AND p.state='active' AND s.event_kind=? ORDER BY p.id""",
                    (branch, command["kind"]),
                ) if row["id"] not in explicit_process_ids
            ]
            receipt = {
                "event_id": event_id, "branch": branch, "revision": revision,
                "request_id": command["request_id"], "event_hash": event_hash,
                "changed": [r["id"] for _, r in pending],
                "changed_properties": [
                    {"entity_id": a.get("entity_id"), "property_id": a.get("property_id"), "definition_version": a.get("definition_version")}
                    for a in command.get("properties", [])
                ],
                "changed_processes": [p.get("id") for p in command.get("processes", [])],
                "changed_profiles": [p.get("entity_id") for p in command.get("profiles", [])],
                "changed_links": [p.get("id") for p in command.get("entity_links", [])],
                "changed_classifications": [p.get("id") for p in command.get("classification_claims", [])],
                "triggered_processes": triggered_process_ids,
                "will_attempt_id": command.get("will_attempt", {}).get("attempt_id") if will_attempt_row else None,
                "replayed": False, "committed": not preview,
                "aux_digest": digest({k: command.get(k) for k in ("properties", "facet_changes", "processes", "consequence_runs", "resolution", "observations", "process_runs", "profiles", "entity_links", "classification_claims", "choice", "will_attempt")}),
            }
            self.db.execute(
                """INSERT INTO events(id,branch,revision,request_id,payload_hash,command_json,kind,actor,narrative,
                   clock_id,tick,causes_json,prev_hash,event_hash,receipt_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (event_id, branch, revision, command["request_id"], payload_hash, encoded(command), command["kind"], command["actor"], command["narrative"], clock_id, tick, encoded(causes), prev_hash, event_hash, encoded(receipt)),
            )
            for roll_id in command.get("roll_ids", []):
                self.db.execute("INSERT INTO roll_uses VALUES(?,?,?)", (branch, roll_id, event_id))
            for dep in command.get("dependencies", []):
                self.db.execute("INSERT INTO event_dependencies VALUES(?,?,?,?,?)", (event_id, dep["kind"], dep["ref_id"], str(dep.get("version")) if dep.get("version") is not None else None, dep["usage"]))
            # Will contract references are engine-mediated dependencies.  The
            # prose inside a contract is intentionally not scanned; only the
            # typed references declared by the contract validator are
            # recorded.
            for _, r in pending:
                if not r["domain"].startswith("will_"):
                    continue
                for kind, ref_value, _path in contract_refs(r["domain"], r["data"]["contract"]):
                    if not isinstance(ref_value, dict) or ref_value.get("version") is None:
                        continue
                    self.db.execute(
                        "INSERT OR IGNORE INTO event_dependencies VALUES(?,?,?,?,?)",
                        (event_id, kind, ref_value["id"], str(ref_value["version"]), "will_contract"),
                    )
            for con in command.get("consequences", []):
                self._validate_consequence(con, branch)
                self.db.execute(
                    "INSERT INTO consequences(id,branch,source_event,subject_id,effect_json,trigger_json,status,apply_once) VALUES(?,?,?,?,?,?,?,?)",
                    (con["id"], branch, event_id, con["subject_id"], encoded(con["effect"]), encoded(con["trigger"]), con.get("status","pending"), int(con.get("apply_once", 1))),
                )
            choice = command.get("choice")
            if choice is not None:
                require(isinstance(choice, dict) and {"id","actor_id","intent","options","selected","knowledge","agency_state"} <= set(choice), "invalid choice")
                require(self.get(branch, choice["actor_id"]) is not None, "choice actor not found")
                self.db.execute(
                    "INSERT INTO choices VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (choice["id"], branch, event_id, choice["actor_id"], choice["intent"], choice.get("method"), choice["agency_state"], encoded(choice["options"]), encoded(choice["selected"]), encoded(choice["knowledge"])),
                )
            # Materialize record projections before auxiliary assignments so a
            # newly created entity may receive a property or process in the
            # same atomic event.
            will_history_aux: list[tuple[str, dict | None, dict]] = []
            for i, (old, r) in enumerate(pending):
                self._write(r, old is None)
                self.db.execute("INSERT INTO changes VALUES(?,?,?,?,?)", (event_id, i, r["id"], encoded(old) if old else None, encoded(r)))
                if r["domain"].startswith("will_"):
                    prior_history = self.db.execute(
                        "SELECT record_json FROM will_contract_history WHERE branch=? AND record_id=? AND version=?",
                        (branch, r["id"], r["version"]),
                    ).fetchone()
                    self.db.execute(
                        "INSERT OR IGNORE INTO will_contract_history(branch,record_id,domain,version,record_json,source_event) VALUES(?,?,?,?,?,?)",
                        (branch, r["id"], r["domain"], r["version"], encoded(r), event_id),
                    )
                    will_history_aux.append((f"{branch}:{r['id']}:{r['version']}", json.loads(prior_history[0]) if prior_history else None, r))
            aux_ordinal = 0
            # Seed the replay stream with auxiliary rows created by this event.
            # These images keep a branch rebuildable without inferring state
            # from the narrative or from the current projections.
            for con in command.get("consequences", []):
                row = self.db.execute("SELECT * FROM consequences WHERE id=? AND branch=?", (con["id"], branch)).fetchone()
                self._insert_aux(event_id, aux_ordinal, "consequence", f"{branch}:{con['id']}", None, dict(row)); aux_ordinal += 1
            if choice is not None:
                row = self.db.execute("SELECT * FROM choices WHERE id=?", (choice["id"],)).fetchone()
                self._insert_aux(event_id, aux_ordinal, "choice", f"{branch}:{choice['id']}", None, dict(row)); aux_ordinal += 1
            for history_key, before_history, after_history in will_history_aux:
                self._insert_aux(event_id, aux_ordinal, "will_history", history_key, before_history, after_history); aux_ordinal += 1
            for profile in command.get("profiles", []):
                require(isinstance(profile, dict) and isinstance(profile.get("entity_id"), str), "invalid entity profile")
                require(self.get(branch, profile["entity_id"]) is not None, "profile subject not found")
                require(profile.get("nature") in {"person","structure","substance","collective","place","field","manifestation","other"}, "invalid entity nature")
                require(profile.get("agency_mode") in {"individual","collective","emergent","absent","unknown"}, "invalid agency mode")
                require(profile.get("control_mode") in {"player","npc","world","unknown"}, "invalid control mode")
                visibility = profile.get("visibility", "gm")
                audience = profile.get("audience", [])
                require(visibility in {"public","restricted","gm"}, "invalid profile visibility")
                require(visibility != "restricted" or audience, "restricted profile needs audience")
                old = self.db.execute("SELECT * FROM entity_profiles WHERE branch=? AND entity_id=?", (branch,profile["entity_id"])).fetchone()
                after = {
                    "branch": branch, "entity_id": profile["entity_id"], "identity_label": profile.get("identity_label"),
                    "nature": profile["nature"], "composition_json": encoded(profile.get("composition", {})),
                    "agency_mode": profile["agency_mode"], "control_mode": profile["control_mode"],
                    "classification_json": encoded(profile.get("classification", [])), "visibility": visibility,
                    "audience_json": encoded(audience), "source_event": event_id,
                }
                self.db.execute("""INSERT INTO entity_profiles(branch,entity_id,identity_label,nature,composition_json,agency_mode,control_mode,classification_json,visibility,audience_json,source_event)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(branch,entity_id) DO UPDATE SET identity_label=excluded.identity_label,nature=excluded.nature,composition_json=excluded.composition_json,agency_mode=excluded.agency_mode,control_mode=excluded.control_mode,classification_json=excluded.classification_json,visibility=excluded.visibility,audience_json=excluded.audience_json,source_event=excluded.source_event""", tuple(after[k] for k in ("branch","entity_id","identity_label","nature","composition_json","agency_mode","control_mode","classification_json","visibility","audience_json","source_event")))
                self._insert_aux(event_id, aux_ordinal, "profile", f"{branch}:{profile['entity_id']}", dict(old) if old else None, after); aux_ordinal += 1
            for link in command.get("entity_links", []):
                require(isinstance(link, dict) and {"id","whole_id","part_id","relation"} <= set(link), "invalid entity link")
                require(self.get(branch, link["whole_id"]) is not None and self.get(branch, link["part_id"]) is not None, "entity link reference missing")
                require(link["relation"] in {"contains","member_of","component_of","split_from","merged_from","succeeds"}, "invalid entity link relation")
                old = self.db.execute("SELECT * FROM entity_links WHERE branch=? AND id=?", (branch,link["id"])).fetchone()
                after = {"branch":branch,"id":link["id"],"whole_id":link["whole_id"],"part_id":link["part_id"],"relation":link["relation"],"valid_from_event":link.get("valid_from_event",event_id),"valid_until_event":link.get("valid_until_event"),"source_event":event_id}
                self.db.execute("""INSERT INTO entity_links(branch,id,whole_id,part_id,relation,valid_from_event,valid_until_event,source_event) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(branch,id) DO UPDATE SET whole_id=excluded.whole_id,part_id=excluded.part_id,relation=excluded.relation,valid_until_event=excluded.valid_until_event,source_event=excluded.source_event""", tuple(after[k] for k in ("branch","id","whole_id","part_id","relation","valid_from_event","valid_until_event","source_event")))
                self._insert_aux(event_id, aux_ordinal, "link", f"{branch}:{link['id']}", dict(old) if old else None, after); aux_ordinal += 1
            for claim in command.get("classification_claims", []):
                require(isinstance(claim, dict) and {"id","subject_id","claimant_id","classification","force","status"} <= set(claim), "invalid classification claim")
                require(self.get(branch, claim["subject_id"]) is not None and self.get(branch, claim["claimant_id"]) is not None, "classification reference missing")
                old = self.db.execute("SELECT * FROM classification_claims WHERE branch=? AND id=?", (branch,claim["id"])).fetchone()
                after = {"branch":branch,"id":claim["id"],"subject_id":claim["subject_id"],"claimant_id":claim["claimant_id"],"classification":claim["classification"],"mechanism":claim.get("mechanism"),"force":claim["force"],"status":claim["status"],"source_event":event_id}
                self.db.execute("""INSERT INTO classification_claims(branch,id,subject_id,claimant_id,classification,mechanism,force,status,source_event) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(branch,id) DO UPDATE SET subject_id=excluded.subject_id,claimant_id=excluded.claimant_id,classification=excluded.classification,mechanism=excluded.mechanism,force=excluded.force,status=excluded.status,source_event=excluded.source_event""", tuple(after[k] for k in ("branch","id","subject_id","claimant_id","classification","mechanism","force","status","source_event")))
                self._insert_aux(event_id, aux_ordinal, "classification", f"{branch}:{claim['id']}", dict(old) if old else None, after); aux_ordinal += 1
            property_seen = set()
            for assignment in command.get("properties", []):
                require(isinstance(assignment, dict), "property assignment must be an object")
                property_key = (branch, assignment.get("entity_id"), assignment.get("property_id"), assignment.get("definition_version"))
                require(property_key not in property_seen, "duplicate property assignment")
                property_seen.add(property_key)
                old, new = self._apply_property(branch, assignment, event_id)
                self.db.execute(
                    "INSERT INTO property_changes VALUES(?,?,?,?,?,?,?,?)",
                    (event_id, aux_ordinal, branch, assignment["entity_id"], assignment["property_id"], assignment["definition_version"], encoded(old) if old else None, encoded(new)),
                )
                self._insert_aux(event_id, aux_ordinal, "property", self._aux_state_key("property", new), old, new)
                aux_ordinal += 1
            facet_seen = set()
            for fc in command.get("facet_changes", []):
                require(isinstance(fc, dict) and {"entity_id","facet","op"} <= set(fc), "invalid facet change")
                key = (branch, fc["entity_id"], fc["facet"]); require(key not in facet_seen, "duplicate facet change"); facet_seen.add(key)
                require(self.get(branch, fc["entity_id"]) is not None, "facet subject not found")
                before = self.db.execute("SELECT branch,entity_id,facet,source_event FROM entity_facets WHERE branch=? AND entity_id=? AND facet=?", key).fetchone()
                if fc["op"] == "add":
                    require(before is None, "facet already exists")
                    self.db.execute("INSERT INTO entity_facets VALUES(?,?,?,?)", (branch, fc["entity_id"], fc["facet"], event_id))
                    after = {"branch": branch, "entity_id": fc["entity_id"], "facet": fc["facet"]}
                elif fc["op"] == "remove":
                    require(before is not None, "facet missing")
                    self.db.execute("DELETE FROM entity_facets WHERE branch=? AND entity_id=? AND facet=?", key)
                    after = None
                else:
                    raise Rejected("invalid facet operation")
                self.db.execute(
                    "INSERT INTO entity_facet_changes VALUES(?,?,?,?,?,?,?)",
                    (event_id, aux_ordinal, branch, fc["entity_id"], fc["facet"], encoded(dict(before)) if before else None, encoded(after) if after else None),
                )
                self._insert_aux(event_id, aux_ordinal, "facet", f"{branch}:{fc['entity_id']}:{fc['facet']}", dict(before) if before else None, after)
                aux_ordinal += 1
            for process in command.get("processes", []):
                op = process.get("op", "upsert")
                pid = process.get("id")
                old = self._current_process(branch, pid) if pid else None
                if op == "create":
                    require(old is None, "process already exists")
                    p = self._process_from_input(branch, process, event_id); self._validate_process(p, branch)
                    self._write_process(p, True)
                elif op in ("update","upsert"):
                    if old is None:
                        require(op == "upsert", "process missing")
                        p = self._process_from_input(branch, process, event_id)
                        self._validate_process(p, branch); self._write_process(p, True)
                    else:
                        p = dict(old)
                        p["branch"], p["id"], p["origin_event"], p["updated_event"] = branch, pid, old.get("origin_event") or event_id, event_id
                        aliases = {
                            "kind":"process_kind", "subjects":"subjects_json", "scope":"scope_json",
                            "conditions":"conditions_json", "subscriptions":"subscriptions_json", "metadata":"metadata_json",
                        }
                        for key, value in process.items():
                            if key in ("op", "id"):
                                continue
                            target = aliases.get(key, key)
                            if target in ("subjects_json","scope_json","conditions_json","subscriptions_json","metadata_json") and not isinstance(value, str):
                                value = encoded(value)
                            if target in p:
                                p[target] = value
                        # `_current_process` exposes decoded JSON fields for
                        # callers; restore storage columns before the write.
                        for raw, decoded in (("subjects_json", "subjects"), ("scope_json", "scope"), ("conditions_json", "conditions"), ("subscriptions_json", "subscriptions"), ("metadata_json", "metadata")):
                            if raw not in p:
                                p[raw] = encoded(p.get(decoded, [] if decoded in ("subjects", "subscriptions") else {}))
                        self._validate_process(p, branch, stored=False); self._write_process(p, False)
                elif op == "cancel":
                    require(old is not None, "process missing")
                    p = dict(old); p["state"] = "cancelled"; p["updated_event"] = event_id
                    self._write_process(p, False)
                else:
                    raise Rejected("invalid process operation")
                after = self._current_process(branch, pid)
                self._insert_aux(event_id, aux_ordinal, "process", f"{branch}:{pid}", old, after)
                aux_ordinal += 1
                self.db.execute("DELETE FROM process_subscriptions WHERE branch=? AND process_id=?", (branch, pid))
                for event_kind in after.get("subscriptions", []):
                    self.db.execute("INSERT INTO process_subscriptions VALUES(?,?,?)", (branch, pid, event_kind))
            # Event subscriptions are an index for mandatory process work. A
            # matching event marks the process due in this same transaction;
            # its declared effect is still resolved by advance_simulation.
            for pid in triggered_process_ids:
                old = self._current_process(branch, pid)
                if old is None or old["state"] != "active":
                    continue
                event_process = dict(old)
                event_process["state"] = "due"
                event_process["pending_judgment"] = None
                new = self._process_from_input(branch, event_process, event_id)
                self._validate_process(new, branch)
                self._write_process(new, False)
                self._insert_aux(event_id, aux_ordinal, "process", f"{branch}:{pid}", old, self._current_process(branch, pid)); aux_ordinal += 1
            for run in command.get("process_runs", []):
                require(isinstance(run, dict) and {"process_id","run_key","outcome"} <= set(run), "invalid process run")
                self.db.execute(
                    "INSERT INTO process_runs(branch,process_id,run_key,event_id,from_tick,to_tick,rng_result_json,outcome_json,status) VALUES(?,?,?,?,?,?,?,?,?)",
                    (branch, run["process_id"], run["run_key"], event_id, run.get("from_tick"), run.get("to_tick"), encoded(run.get("rng_result")) if run.get("rng_result") is not None else None, encoded(run["outcome"]), run.get("status", "resolved")),
                )
                self._insert_aux(event_id, aux_ordinal, "run", f"{branch}:{run['process_id']}:{run['run_key']}", None, run)
                aux_ordinal += 1
            for observation in command.get("observations", []):
                require(isinstance(observation, dict) and {"id","observer_id","subject_id","assertion","certainty"} <= set(observation), "invalid observation")
                self.db.execute(
                    "INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)",
                    (observation["id"], branch, event_id, observation["observer_id"], observation["subject_id"], observation["assertion"], observation["certainty"], observation.get("visibility","restricted"), encoded(observation.get("audience", [observation["observer_id"]]))),
                )
                self._insert_aux(event_id, aux_ordinal, "observation", observation["id"], None, observation)
                aux_ordinal += 1
            if resolution is not None:
                self.db.execute(
                    "INSERT INTO event_resolutions VALUES(?,?,?,?)",
                    (event_id, encoded(resolution), int(bool(resolution.get("mechanical", True))), encoded(command.get("judgment", {}))),
                )
                self._insert_aux(event_id, aux_ordinal, "resolution", event_id, None, resolution); aux_ordinal += 1
            if will_attempt_row is not None:
                before = dict(will_attempt_row)
                self.db.execute(
                    "UPDATE will_attempts SET status='committed',event_id=? WHERE branch=? AND attempt_id=?",
                    (event_id, branch, will_attempt_row["attempt_id"]),
                )
                after = dict(self._will_attempt_row(branch, will_attempt_row["attempt_id"]))
                self._insert_aux(event_id, aux_ordinal, "will_attempt", f"{branch}:{will_attempt_row['attempt_id']}", before, after); aux_ordinal += 1
            self._validate_world(branch)
            if clock_id:
                require(self.get(branch, clock_id)["data"]["tick"] == tick, "event tick must match resulting clock")
            for run in command.get("consequence_runs", []):
                require(isinstance(run, dict) and {"consequence_id","run_key","status","detail"} <= set(run), "invalid consequence run")
                row = self.db.execute("SELECT * FROM consequences WHERE id=? AND branch=?", (run["consequence_id"], branch)).fetchone()
                require(row is not None, "unknown consequence")
                existing_run = self.db.execute("SELECT 1 FROM consequence_runs WHERE consequence_id=? AND run_key=?", (run["consequence_id"], run["run_key"])).fetchone()
                if existing_run:
                    continue
                self.db.execute("INSERT INTO consequence_runs VALUES(?,?,?,?,?)", (run["consequence_id"], run["run_key"], event_id, run["status"], encoded(run["detail"])))
                if run["status"] in ("applied","cancelled","contested"):
                    self.db.execute("UPDATE consequences SET status=?,applied_event=? WHERE id=?", (run["status"], event_id, run["consequence_id"]))
                self._insert_aux(event_id, aux_ordinal, "consequence", f"{branch}:{run['consequence_id']}", dict(row), dict(run)); aux_ordinal += 1
            if command.get("assumptions"):
                require(isinstance(command["assumptions"], list), "assumptions must be a list")
            self.db.execute("UPDATE branches SET revision=? WHERE id=?", (revision, branch))
            if preview:
                transaction.rollback()
            else:
                transaction.commit()
            return receipt
        except Exception:
            transaction.rollback()
            raise

    def fork(self, parent: str, child: str, expected_revision: int) -> dict:
        require(isinstance(child, str) and child, "branch name required")
        with self.transaction():
            require(self.branch(parent)["revision"] == expected_revision, "stale fork revision")
            self.db.execute("INSERT INTO branches VALUES(?,?,?,0)", (child, parent, expected_revision))
            for r in self.state(parent):
                rr = copy.deepcopy(r); rr["branch"] = child
                self._write(rr, True)
            for row in self.db.execute("SELECT * FROM property_values WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self.db.execute(
                    "INSERT INTO property_values VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    tuple(vals[k] for k in ("branch","entity_id","property_id","definition_version","state","number_value","text_value","json_value","unit","context_json","valid_from_event","valid_until_event","epistemic_status","visibility")),
                )
            for row in self.db.execute("SELECT * FROM entity_facets WHERE branch=?", (parent,)):
                self.db.execute("INSERT INTO entity_facets VALUES(?,?,?,?)", (child,row["entity_id"],row["facet"],row["source_event"]))
            for row in self.db.execute("SELECT * FROM processes WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self._write_process(vals, True)
            for row in self.db.execute("SELECT * FROM process_subscriptions WHERE branch=?", (parent,)):
                self.db.execute("INSERT INTO process_subscriptions VALUES(?,?,?)", (child,row["process_id"],row["event_kind"]))
            for row in self.db.execute("SELECT * FROM consequences WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                vals["id"] = f"{child}:{row['id']}"
                self.db.execute(
                    "INSERT INTO consequences VALUES(?,?,?,?,?,?,?,?,?)",
                    tuple(vals[k] for k in ("id","branch","source_event","subject_id","effect_json","trigger_json","status","apply_once","applied_event")),
                )
            consequence_ids = {row["id"]: f"{child}:{row['id']}" for row in self.db.execute("SELECT id FROM consequences WHERE branch=?", (parent,))}
            for row in self.db.execute("SELECT * FROM choices WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child; vals["id"] = f"{child}:{row['id']}"
                self.db.execute(
                    "INSERT INTO choices VALUES(?,?,?,?,?,?,?,?,?,?)",
                    tuple(vals[k] for k in ("id","branch","event_id","actor_id","intent","method","agency_state","options_json","selected_json","knowledge_json")),
                )
            for row in self.db.execute("SELECT * FROM process_runs WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self.db.execute(
                    "INSERT INTO process_runs VALUES(?,?,?,?,?,?,?,?,?)",
                    tuple(vals[k] for k in ("branch","process_id","run_key","event_id","from_tick","to_tick","rng_result_json","outcome_json","status")),
                )
            for row in self.db.execute("SELECT cr.*, c.branch AS branch FROM consequence_runs cr JOIN consequences c ON c.id=cr.consequence_id WHERE c.branch=?", (parent,)):
                vals = dict(row); vals["consequence_id"] = consequence_ids[row["consequence_id"]]
                self.db.execute(
                    "INSERT INTO consequence_runs VALUES(?,?,?,?,?)",
                    tuple(vals[k] for k in ("consequence_id","run_key","event_id","status","detail_json")),
                )
            for row in self.db.execute("SELECT * FROM entity_profiles WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self.db.execute("INSERT INTO entity_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?)", tuple(vals[k] for k in ("branch","entity_id","identity_label","nature","composition_json","agency_mode","control_mode","classification_json","visibility","audience_json","source_event")))
            for row in self.db.execute("SELECT * FROM entity_links WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self.db.execute("INSERT INTO entity_links VALUES(?,?,?,?,?,?,?,?)", tuple(vals[k] for k in ("branch","id","whole_id","part_id","relation","valid_from_event","valid_until_event","source_event")))
            for row in self.db.execute("SELECT * FROM classification_claims WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                self.db.execute("INSERT INTO classification_claims VALUES(?,?,?,?,?,?,?,?,?)", tuple(vals[k] for k in ("branch","id","subject_id","claimant_id","classification","mechanism","force","status","source_event")))
            for row in self.db.execute("SELECT * FROM will_contract_history WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child
                record_image = json.loads(vals["record_json"]); record_image["branch"] = child
                self.db.execute(
                    "INSERT INTO will_contract_history(branch,record_id,domain,version,record_json,source_event) VALUES(?,?,?,?,?,?)",
                    (child, vals["record_id"], vals["domain"], vals["version"], encoded(record_image), vals["source_event"]),
                )
            for row in self.db.execute("SELECT * FROM observations WHERE branch=?", (parent,)):
                vals = dict(row); vals["branch"] = child; vals["id"] = f"{child}:{row['id']}"
                self.db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?)", tuple(vals[k] for k in ("id","branch","event_id","observer_id","subject_id","assertion","certainty","visibility","audience_json")))
            for row in self.db.execute("SELECT * FROM rolls WHERE branch=?", (parent,)):
                self.db.execute("INSERT INTO rolls VALUES(?,?,?,?,?,?,?)", (child,row["id"],row["sides"],row["target"],row["modifier"],row["result"],row["reason"]))
            for row in self.db.execute("SELECT * FROM roll_uses WHERE branch=?", (parent,)):
                self.db.execute("INSERT INTO roll_uses VALUES(?,?,?)", (child,row["id"],row["event_id"]))
            for row in self.db.execute('SELECT * FROM decision_proposals WHERE branch=?',(parent,)):
                self.db.execute('INSERT INTO decision_proposals VALUES(?,?,?,?,?,?,?)',(child,row['id'],row['spec_hash'],row['state_hash'],row['spec_json'],row['compiled_json'],row['roll']))
            state = self._snapshot_payload(child)
            self.db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)", ("fork:"+child, child, 0, encoded(state), digest(state)))
            return {"branch": child, "parent": parent, "fork_revision": expected_revision, "revision": 0}

    def _snapshot_payload(self, branch: str) -> dict:
        return {
            "decisions": [dict(r) for r in self.db.execute('SELECT * FROM decision_proposals WHERE branch=?',(branch,))] if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='decision_proposals'").fetchone() else [],
            "records": self.state(branch),
            "properties": [dict(r) for r in self.db.execute("SELECT * FROM property_values WHERE branch=?", (branch,))],
            "facets": [dict(r) for r in self.db.execute("SELECT * FROM entity_facets WHERE branch=?", (branch,))],
            "processes": [dict(r) for r in self.db.execute("SELECT * FROM processes WHERE branch=?", (branch,))],
            "consequences": [dict(r) for r in self.db.execute("SELECT * FROM consequences WHERE branch=?", (branch,))],
            "choices": [dict(r) for r in self.db.execute("SELECT * FROM choices WHERE branch=?", (branch,))],
            "process_runs": [dict(r) for r in self.db.execute("SELECT * FROM process_runs WHERE branch=?", (branch,))],
            "consequence_runs": [dict(r) for r in self.db.execute("SELECT cr.*, c.branch AS branch FROM consequence_runs cr JOIN consequences c ON c.id=cr.consequence_id WHERE c.branch=?", (branch,))],
            "observations": [dict(r) for r in self.db.execute("SELECT * FROM observations WHERE branch=?", (branch,))],
            "profiles": [dict(r) for r in self.db.execute("SELECT * FROM entity_profiles WHERE branch=?", (branch,))],
            "links": [dict(r) for r in self.db.execute("SELECT * FROM entity_links WHERE branch=?", (branch,))],
            "classifications": [dict(r) for r in self.db.execute("SELECT * FROM classification_claims WHERE branch=?", (branch,))],
            "will_history": [dict(r) for r in self.db.execute("SELECT * FROM will_contract_history WHERE branch=?", (branch,))],
        }

    def roll(self, branch: str, id: str, sides: int, target: int, modifier: int, reason: str) -> dict:
        self.branch(branch)
        require(all(type(x) is int for x in (sides,target,modifier)) and 2 <= sides <= 1_000_000, "invalid dice")
        require(isinstance(id, str) and id and isinstance(reason, str) and reason, "roll ID and reason required")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT * FROM rolls WHERE branch=? AND id=?", (branch,id)).fetchone()
            if old:
                require((old["sides"],old["target"],old["modifier"],old["reason"]) == (sides,target,modifier,reason), "roll ID reused with different declaration")
                self.db.rollback(); return dict(old)
            result = secrets.randbelow(sides) + 1
            self.db.execute("INSERT INTO rolls VALUES(?,?,?,?,?,?,?)", (branch,id,sides,target,modifier,result,reason))
            self.db.commit()
            return {"branch":branch,"id":id,"sides":sides,"target":target,"modifier":modifier,"result":result,"reason":reason}
        except Exception:
            self.db.rollback(); raise

    def resolve_action(self, branch: str, spec: dict) -> dict:
        """Resolve mechanical stages without committing a fictional event."""
        require(isinstance(spec, dict), "action specification must be an object")
        require(isinstance(spec.get("actor"), str), "action actor required")
        require(self.get(branch, spec["actor"]) is not None, "action actor not found")
        permission = spec.get("permission", {"allowed": True, "reasons": []})
        require(isinstance(permission, dict) and isinstance(permission.get("allowed", True), bool), "invalid permission stage")
        if not permission.get("allowed", True):
            return {"feasible": False, "permission": permission, "probability": None, "magnitude": None, "cost": spec.get("cost", []), "timing": spec.get("timing", {}), "consequences": spec.get("consequences", []), "roll": None}
        difficulty = spec.get("difficulty")
        require(type(difficulty) is int, "difficulty required before rolling")
        contributions = spec.get("contributions", [])
        require(isinstance(contributions, list), "contributions must be a list")
        stages = {"probability": 0, "magnitude": 0, "cost": [], "timing": spec.get("timing", {})}
        seen = set()
        for c in contributions:
            require(isinstance(c, dict) and {"id","stage","value"} <= set(c), "invalid contribution")
            require(c["id"] not in seen, "duplicate contribution")
            seen.add(c["id"])
            require(c["stage"] in {"probability","magnitude","cost","timing","permission","consequence"}, "invalid contribution stage")
            if c["stage"] == "probability":
                require(type(c["value"]) in (int,float) and math.isfinite(c["value"]), "probability contribution must be numeric")
                stages["probability"] += c["value"]
            elif c["stage"] == "magnitude":
                require(type(c["value"]) in (int,float) and math.isfinite(c["value"]), "magnitude contribution must be numeric")
                stages["magnitude"] += c["value"]
            elif c["stage"] == "cost":
                stages["cost"].append(c["value"])
        modifier = spec.get("modifier", 0) + stages["probability"]
        require(type(modifier) in (int,float) and math.isfinite(modifier), "invalid probability modifier")
        rule_results = []
        for rule in spec.get("rules", []):
            require(isinstance(rule, dict) and {"id", "version"} <= set(rule), "rule reference requires id and version")
            rule_results.append(self.evaluate_rule(
                rule["id"], int(rule["version"]), branch,
                subject_id=rule.get("subject_id", spec["actor"]), inputs=rule.get("inputs"),
            ))
        roll_id = spec.get("roll_id")
        roll = None
        if spec.get("requires_roll", True):
            require(isinstance(roll_id, str) and roll_id, "stable roll_id required")
            roll = self.roll(branch, roll_id, int(spec.get("sides",20)), difficulty, int(modifier), spec.get("reason","authorized action"))
        total = (roll["result"] + modifier) if roll else modifier
        success = total >= difficulty
        return {
            "feasible": True, "permission": permission,
            "probability": {"difficulty": difficulty, "modifier": modifier, "roll_total": total, "success": success},
            "magnitude": {"base": spec.get("base_magnitude", 0), "contribution": stages["magnitude"], "success": success},
            "cost": list(spec.get("cost", [])) + stages["cost"],
            "timing": stages["timing"], "consequences": spec.get("consequences", []),
            "roll": roll, "inputs": spec.get("inputs", []), "rules": spec.get("rules", []), "rule_results": rule_results,
        }

    # ------------------------------------------------------------------
    # Versioned Will admission and resolution
    # ------------------------------------------------------------------

    def _will_snapshot_hash(self, branch: str, actor: str, expression: dict, technique: dict, targets: list[str]) -> str:
        """Hash only state an authorized Will attempt is allowed to read."""
        ids = []
        for rid in [actor, expression["id"], technique["id"], *targets]:
            if rid not in ids:
                ids.append(rid)
        records = []
        for rid in ids:
            row = self.get(branch, rid)
            require(row is not None, f"Will input record missing: {rid}")
            records.append(row)
        props = []
        for rid in ids:
            props.extend(self.properties(branch, entity_id=rid))
        return digest({"branch": branch, "actor": actor, "records": records, "properties": props})

    def _will_role_subject(self, actor: str, targets: list[str], role: str) -> str:
        if role in {"actor", "bearer", "self"}:
            return actor
        if role == "target":
            require(targets, "Will target is required")
            return targets[0]
        if role.startswith("target:"):
            try:
                index = int(role.split(":", 1)[1])
            except ValueError as exc:
                raise Rejected(f"invalid Will target role {role}") from exc
            require(0 <= index < len(targets), f"Will target role {role} is unavailable")
            return targets[index]
        raise Rejected(f"unsupported Will subject role {role}")

    def _will_judgment(self, judgments: list[dict], scope: str) -> dict | None:
        for judgment in judgments:
            if isinstance(judgment, dict) and judgment.get("scope") == scope:
                return judgment
        return None

    def _will_condition(self, branch: str, actor: str, item: dict, judgments: list[dict], scope: str) -> tuple[bool, str | None, dict | None]:
        """Evaluate a typed condition without turning missing semantics into truth."""
        mode = item.get("mode")
        if mode == "judgment":
            judgment = self._will_judgment(judgments, scope)
            if judgment is None:
                return False, "judgment_required", None
            decision = str(judgment.get("decision", "")).strip().lower()
            if decision not in {"allow", "allowed", "true", "yes", "satisfied", "pass", "success"}:
                return False, "judgment_denied", judgment
            return True, None, judgment
        rule = item.get("rule")
        require(isinstance(rule, dict), f"{scope} rule reference is required")
        result = self.evaluate_rule(rule["id"], int(rule["version"]), branch, subject_id=actor)
        if not result.get("mechanical"):
            return False, "judgment_required", result
        value = result.get("output", {}).get("value")
        if value is True:
            return True, None, result
        if value is False:
            return False, "condition_false", result
        return False, "judgment_required", result

    def _will_cost_properties(self, branch: str, actor: str, targets: list[str], technique: dict, outcome: str) -> tuple[list[dict], list[dict]]:
        """Compile declared resource costs; no implicit health or freedom cost exists."""
        assignments: list[dict] = []
        contributions: set[tuple[str, int, str, str]] = set()
        for cost in technique["data"]["contract"].get("costs", []):
            if cost["when"] not in {"attempt", "success", "failure", "release"}:
                continue
            if cost["when"] == "success" and outcome != "success":
                continue
            if cost["when"] == "failure" and outcome not in {"failure", "interrupted"}:
                continue
            resource = cost["resource"]
            key = (resource["property_id"], int(resource["definition_version"]), resource["subject_role"], resource["stage"])
            require(key not in contributions, "duplicate Will cost contribution")
            contributions.add(key)
            subject = self._will_role_subject(actor, targets, resource["subject_role"])
            current = self.property_value(branch, subject, resource["property_id"], int(resource["definition_version"]))
            require(current is not None and current["state"] == "known", f"Will cost input is unknown: {resource['property_id']}")
            require(isinstance(current.get("value"), (int, float)) and not isinstance(current.get("value"), bool), "Will cost input must be numeric")
            amount = cost["amount"]
            require(current.get("unit") == amount["unit"], f"incompatible Will cost unit for {resource['property_id']}")
            remaining = current["value"] - amount["value"]
            if remaining < 0:
                policy = cost["insufficient_policy"]
                if policy == "block":
                    return [], [{"cost_id": cost["id"], "reason": "insufficient_resource", "subject": subject}]
                if policy == "interrupt":
                    continue
            assignments.append({
                "entity_id": subject, "property_id": resource["property_id"],
                "definition_version": int(resource["definition_version"]), "state": "known",
                "value": remaining, "unit": amount["unit"], "context": json.loads(current["context_json"]),
                "epistemic_status": "derived", "visibility": current["visibility"],
            })
        return assignments, []

    def _will_compile_resolver(self, branch: str, actor: str, targets: list[str], effect: dict, resolver: dict, effect_index: int) -> dict:
        """Compile one registered mechanical resolver into engine-owned writes."""
        row = self.db.execute("SELECT * FROM rule_definitions WHERE rule_id=? AND rule_version=?", (resolver["id"], resolver["version"])).fetchone()
        require(row is not None, "unknown Will resolver")
        require(bool(row["mechanical"]), "Will resolver requires mechanical rule")
        definition = json.loads(row["definition_json"])
        kind = definition.get("kind")
        template = definition.get("template")
        require(isinstance(template, dict), "Will resolver template is missing")
        if kind == "will_patch":
            target_role = template.get("target_role", effect.get("target_role"))
            rid = self._will_role_subject(actor, targets, target_role)
            record = self.get(branch, rid)
            require(record is not None, "Will patch target is missing")
            data = template.get("data")
            require(isinstance(data, dict), "Will patch template data is missing")
            return {"changes": [{"op": "patch", "id": rid, "expected_version": record["version"], "data": copy.deepcopy(data), "evidence": [{"note": f"Will resolver {resolver['id']}@{resolver['version']} effect {effect_index}"}]}]}
        if kind == "will_property":
            target_role = template.get("subject_role", effect.get("target_role"))
            subject = self._will_role_subject(actor, targets, target_role)
            assignment = copy.deepcopy(template.get("assignment", {}))
            require(isinstance(assignment, dict), "Will property template assignment is missing")
            assignment["entity_id"] = subject
            require({"property_id", "definition_version", "state", "value", "unit"} <= set(assignment), "Will property template is incomplete")
            assignment.setdefault("context", {})
            assignment.setdefault("epistemic_status", "derived")
            assignment.setdefault("visibility", "gm")
            return {"properties": [assignment]}
        if kind == "will_consequence":
            target_role = template.get("subject_role", effect.get("target_role"))
            subject = self._will_role_subject(actor, targets, target_role)
            con = copy.deepcopy(template.get("consequence", {}))
            require(isinstance(con, dict) and {"id", "effect", "trigger"} <= set(con), "Will consequence template is incomplete")
            con["subject_id"] = subject
            return {"consequences": [con]}
        if kind == "will_process":
            process = copy.deepcopy(template.get("process", {}))
            require(isinstance(process, dict) and isinstance(process.get("id"), str), "Will process template is incomplete")
            if "subjects" in process:
                process["subjects"] = [self._will_role_subject(actor, targets, x) if isinstance(x, str) and x in {"actor", "target", "self"} else x for x in process["subjects"]]
            process["op"] = "create"
            return {"processes": [process]}
        if kind == "will_observation":
            observation = copy.deepcopy(template.get("observation", {}))
            require(isinstance(observation, dict) and {"id", "subject_role", "assertion", "certainty"} <= set(observation), "Will observation template is incomplete")
            observation["observer_id"] = actor
            observation["subject_id"] = self._will_role_subject(actor, targets, observation.pop("subject_role"))
            return {"observations": [observation]}
        raise Rejected("unsupported Will mechanical resolver; GM judgment required")

    def _will_attempt_row(self, branch: str, attempt_id: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM will_attempts WHERE branch=? AND attempt_id=?", (branch, attempt_id)).fetchone()

    def prepare_will_attempt(self, branch: str, attempt: dict) -> dict:
        """Admit and resolve a Will attempt without creating a fictional event."""
        require(isinstance(attempt, dict), "Will attempt must be an object")
        allowed = {"request_id", "attempt_id", "expected_revision", "actor", "expression", "technique", "intent", "targets", "permission_checks", "contest", "randomness", "outcome_bindings", "judgments", "evidence_note"}
        require(set(attempt) <= allowed, "unknown Will attempt field")
        for key in ("request_id", "attempt_id", "actor", "intent"):
            require(isinstance(attempt.get(key), str) and attempt[key].strip(), f"Will attempt {key} is required")
        require(isinstance(attempt.get("expression"), dict) and set(attempt["expression"]) == {"id", "version"}, "Will expression reference required")
        require(isinstance(attempt.get("technique"), dict) and set(attempt["technique"]) == {"id", "version"}, "Will technique reference required")
        targets = attempt.get("targets", []); require(isinstance(targets, list) and all(isinstance(x, str) and x for x in targets), "Will targets must be IDs")
        meta = self.branch(branch); expected = meta["revision"] if attempt.get("expected_revision") is None else attempt["expected_revision"]
        require(type(expected) is int and expected >= 0, "Will expected_revision is required")
        require(expected == meta["revision"], "stale branch revision")
        actor = self.get(branch, attempt["actor"]); require(actor is not None and actor["domain"] == "character", "Will actor must be a character")
        expression = self._will_record_ref(branch, "will_expression", attempt["expression"], "expression")
        technique = self._will_record_ref(branch, "will_technique", attempt["technique"], "technique")
        require(expression["data"]["bearer"] == attempt["actor"], "actor does not bear this Will expression")
        require(technique["data"]["expression"] == expression["id"], "technique is not part of expression")
        expression_contract = self.get_will_contract(branch, "will_expression", expression["id"], expression["version"])
        technique_contract = self.get_will_contract(branch, "will_technique", technique["id"], technique["version"])
        require(technique_contract["design_status"] == "accepted", "technique is not accepted for mechanical use")
        require(technique_contract["practice_status"] != "unavailable", "technique is unavailable")
        for target in targets:
            require(self.get(branch, target) is not None, f"Will target not found: {target}")
        # Scope and role feasibility are known before an outcome is rolled.
        # Rejecting an out-of-scope target here prevents a reserved random
        # result from being stranded by an impossible action.
        for effect in technique_contract.get("effects", []):
            target = self._will_role_subject(attempt["actor"], targets, effect["target_role"])
            allowed_kinds = set(effect.get("scope", {}).get("target_kinds", []))
            if allowed_kinds:
                require(bool(self._entity_facets(branch, target) & allowed_kinds), f"Will target {target} is outside effect scope")
        snapshot_hash = self._will_snapshot_hash(branch, attempt["actor"], expression, technique, targets)
        stored = self._will_attempt_row(branch, attempt["attempt_id"])
        if stored:
            normalized = json.loads(stored["attempt_json"])
            incoming = dict(attempt); incoming["expected_revision"] = expected; incoming["input_snapshot_hash"] = snapshot_hash
            require(digest(normalized) == digest(incoming), "attempt ID reused with changed inputs")
            result = json.loads(stored["compiled_json"])
            result["attempt_id"] = attempt["attempt_id"]; result["status"] = stored["status"]; result["replayed"] = True
            result.setdefault("outcome", result.get("resolution", {}).get("outcome"))
            result.setdefault("roll", result.get("resolution", {}).get("roll"))
            return result
        require(self.db.execute("SELECT 1 FROM will_attempts WHERE branch=? AND prepare_request_id=?", (branch, attempt["request_id"])).fetchone() is None, "Will prepare request already used")
        judgments = attempt.get("judgments", []); require(isinstance(judgments, list), "Will judgments must be a list")
        # Trigger and explicitly supplied permission conditions run before any
        # dice reservation or cost compilation.
        checks = [technique_contract["trigger"], *attempt.get("permission_checks", [])]
        for i, check in enumerate(checks):
            require(isinstance(check, dict), "Will permission check must be an object")
            ok, reason, detail = self._will_condition(branch, attempt["actor"], check, judgments, check.get("id", f"permission:{i}"))
            if not ok:
                normalized = dict(attempt); normalized.update(expected_revision=expected, input_snapshot_hash=snapshot_hash)
                blocked = {"attempt": normalized, "status": "blocked", "reason": reason, "detail": detail, "resolution": {"feasible": False, "permission": {"allowed": False, "reason": reason}}, "compiled": {"changes": [], "properties": [], "processes": [], "consequences": [], "observations": [], "roll_ids": [], "dependencies": [], "resolution": {"feasible": False, "permission": {"allowed": False, "reason": reason}}, "judgment": {"required": reason == "judgment_required"}}}
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    self.db.execute("INSERT INTO will_attempts(branch,attempt_id,prepare_request_id,actor,expression_id,expression_version,technique_id,technique_version,expected_revision,input_snapshot_hash,attempt_json,compiled_json,status,roll_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (branch,attempt["attempt_id"],attempt["request_id"],attempt["actor"],expression["id"],expression["version"],technique["id"],technique["version"],expected,snapshot_hash,encoded(normalized),encoded(blocked["compiled"]),"blocked",None))
                    self.db.commit()
                except Exception:
                    self.db.rollback(); raise
                return {"attempt_id": attempt["attempt_id"], "status": "blocked", "reason": reason, "judgment_required": reason == "judgment_required", "resolution": blocked["resolution"], "replayed": False}
        randomness = attempt.get("randomness", {"mode": "none", "roll_id": None, "difficulty": None, "modifier": 0})
        require(isinstance(randomness, dict), "Will randomness must be an object")
        require(set(randomness) <= {"mode", "roll_id", "difficulty", "modifier"}, "unknown randomness field")
        mode = randomness.get("mode", "none"); require(mode in {"none", "d20"}, "invalid Will randomness mode")
        modifier = randomness.get("modifier", 0); require(type(modifier) is int, "Will modifier must be an integer")
        roll = None; outcome = None; roll_ids: list[str] = []
        if mode == "d20":
            require(isinstance(randomness.get("roll_id"), str) and randomness["roll_id"], "stable Will roll_id required")
            require(type(randomness.get("difficulty")) is int, "Will difficulty is required before rolling")
            roll = self.roll(branch, randomness["roll_id"], 20, randomness["difficulty"], modifier, f"Will attempt {attempt['attempt_id']}")
            roll_ids = [roll["id"]]
            outcome = "success" if roll["result"] + modifier >= randomness["difficulty"] else "failure"
        else:
            judgment = self._will_judgment(judgments, "outcome")
            if judgment is None:
                normalized = dict(attempt); normalized.update(expected_revision=expected, input_snapshot_hash=snapshot_hash)
                blocked = {"changes": [], "properties": [], "processes": [], "consequences": [], "observations": [], "roll_ids": [], "dependencies": [], "resolution": {"feasible": True, "judgment_required": True}, "judgment": {"required": "outcome"}}
                self.db.execute("BEGIN IMMEDIATE")
                try:
                    self.db.execute("INSERT INTO will_attempts(branch,attempt_id,prepare_request_id,actor,expression_id,expression_version,technique_id,technique_version,expected_revision,input_snapshot_hash,attempt_json,compiled_json,status,roll_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (branch,attempt["attempt_id"],attempt["request_id"],attempt["actor"],expression["id"],expression["version"],technique["id"],technique["version"],expected,snapshot_hash,encoded(normalized),encoded(blocked),"blocked",None))
                    self.db.commit()
                except Exception:
                    self.db.rollback(); raise
                return {"attempt_id": attempt["attempt_id"], "status": "blocked", "reason": "judgment_required", "judgment_required": True, "resolution": blocked["resolution"], "replayed": False}
            outcome = str(judgment.get("decision", "")).lower()
            require(outcome in {"success", "partial", "failure", "interrupted"}, "outcome judgment must be success, partial, failure, or interrupted")
        bindings = attempt.get("outcome_bindings", [])
        require(isinstance(bindings, list) and bindings, "Will outcome_bindings are required")
        selected = [b for b in bindings if isinstance(b, dict) and b.get("outcome") == outcome]
        require(len(selected) == 1, "exactly one outcome binding must match resolved outcome")
        selected = selected[0]
        expected_cost_ids = {
            c["id"] for c in technique_contract.get("costs", [])
            if c["when"] == "attempt" or c["when"] == "release"
            or (c["when"] == "success" and outcome == "success")
            or (c["when"] == "failure" and outcome in {"failure", "interrupted"})
        }
        require(isinstance(selected.get("cost_ids", []), list) and all(isinstance(x, str) and x for x in selected.get("cost_ids", [])), "outcome binding cost_ids must be string IDs")
        declared_cost_ids = set(selected.get("cost_ids", []))
        require(declared_cost_ids == expected_cost_ids, "outcome binding cost IDs do not match the technique contract")
        effect_indexes = selected.get("effect_indexes", []); require(isinstance(effect_indexes, list) and all(type(i) is int and i >= 0 for i in effect_indexes), "invalid Will effect indexes")
        require(all(i < len(technique_contract["effects"]) for i in effect_indexes), "Will effect index out of range")
        compiled = {"changes": [], "properties": [], "processes": [], "consequences": [], "observations": [], "roll_ids": roll_ids, "dependencies": [], "resolution": {"feasible": True, "outcome": outcome, "roll": roll}, "judgment": {"items": judgments}}
        # The effect and cost templates are engine-owned.  No state delta is
        # accepted from this request; a GM can only supply a bounded judgment.
        for index in effect_indexes:
            effect = technique_contract["effects"][index]
            target = self._will_role_subject(attempt["actor"], targets, effect["target_role"])
            allowed_kinds = set(effect.get("scope", {}).get("target_kinds", []))
            if allowed_kinds:
                facets = self._entity_facets(branch, target)
                require(bool(facets & allowed_kinds), f"Will target {target} is outside effect scope")
            if effect.get("authority") != "mechanical" or not effect.get("resolver"):
                judgment = self._will_judgment(judgments, f"effect:{index}")
                require(judgment is not None, f"effect:{index} requires GM judgment")
                continue
            part = self._will_compile_resolver(branch, attempt["actor"], targets, effect, effect["resolver"], index)
            for key in ("changes", "properties", "processes", "consequences", "observations"):
                compiled[key].extend(part.get(key, []))
            compiled["dependencies"].append({"kind": "rule", "ref_id": effect["resolver"]["id"], "version": str(effect["resolver"]["version"]), "usage": "reads"})
        costs, blocked_costs = self._will_cost_properties(branch, attempt["actor"], targets, technique, outcome)
        if blocked_costs:
            normalized = dict(attempt); normalized.update(expected_revision=expected, input_snapshot_hash=snapshot_hash)
            blocked = {"changes": [], "properties": [], "processes": [], "consequences": [], "observations": [], "roll_ids": roll_ids, "dependencies": compiled["dependencies"], "resolution": {"feasible": False, "outcome": "blocked", "costs": blocked_costs}, "judgment": {"required": "cost"}}
            self.db.execute("BEGIN IMMEDIATE")
            try:
                self.db.execute("INSERT INTO will_attempts(branch,attempt_id,prepare_request_id,actor,expression_id,expression_version,technique_id,technique_version,expected_revision,input_snapshot_hash,attempt_json,compiled_json,status,roll_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (branch,attempt["attempt_id"],attempt["request_id"],attempt["actor"],expression["id"],expression["version"],technique["id"],technique["version"],expected,snapshot_hash,encoded(normalized),encoded(blocked),"blocked",roll["id"] if roll else None))
                self.db.commit()
            except Exception:
                self.db.rollback(); raise
            return {"attempt_id": attempt["attempt_id"], "status": "blocked", "reason": "insufficient_resource", "resolution": blocked["resolution"], "replayed": False}
        compiled["properties"].extend(costs)
        # Duplicate writes from two differently-labelled contributions are not
        # stackable unless they address different properties/stages.
        seen_writes: set[tuple] = set()
        for assignment in compiled["properties"]:
            key = (assignment.get("entity_id"), assignment.get("property_id"), assignment.get("definition_version"))
            require(key not in seen_writes, "duplicate Will property contribution")
            seen_writes.add(key)
        normalized = dict(attempt); normalized.update(expected_revision=expected, input_snapshot_hash=snapshot_hash)
        compiled["attempt_id"] = attempt["attempt_id"]; compiled["status"] = "prepared"; compiled["input_snapshot_hash"] = snapshot_hash
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO will_attempts(branch,attempt_id,prepare_request_id,actor,expression_id,expression_version,technique_id,technique_version,expected_revision,input_snapshot_hash,attempt_json,compiled_json,status,roll_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (branch,attempt["attempt_id"],attempt["request_id"],attempt["actor"],expression["id"],expression["version"],technique["id"],technique["version"],expected,snapshot_hash,encoded(normalized),encoded(compiled),"prepared",roll["id"] if roll else None))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return {"attempt_id": attempt["attempt_id"], "status": "prepared", "outcome": outcome, "resolution": compiled["resolution"], "roll": roll, "replayed": False}

    def _validate_will_apply_command(self, branch: str, command: dict) -> sqlite3.Row:
        envelope = command.get("will_attempt")
        require(isinstance(envelope, dict) and {"attempt_id", "compiled_digest"} <= set(envelope), "Will attempt envelope required")
        row = self._will_attempt_row(branch, envelope["attempt_id"])
        require(row is not None, "unknown Will attempt")
        require(row["status"] == "prepared", "Will attempt is not pending")
        compiled = json.loads(row["compiled_json"])
        require(digest(compiled) == envelope["compiled_digest"], "Will compiled resolution was altered")
        require(command.get("expected_revision") == row["expected_revision"], "stale Will attempt revision")
        expected_hash = self._will_snapshot_hash(branch, row["actor"], self.get(branch, row["expression_id"]), self.get(branch, row["technique_id"]), json.loads(row["attempt_json"]).get("targets", []))
        require(expected_hash == row["input_snapshot_hash"], "Will input state changed after preparation")
        supplied = {k: command.get(k, []) for k in ("changes", "properties", "processes", "consequences", "observations", "roll_ids", "dependencies")}
        expected = {k: compiled.get(k, []) for k in supplied}
        require(digest(supplied) == digest(expected), "caller-injected Will state delta rejected")
        require(command.get("resolution") == compiled.get("resolution"), "caller-altered Will outcome rejected")
        return row

    def apply_will_attempt(
        self, branch: str, attempt_id: str, request_id: str, actor: str, narrative: str,
        expected_revision: int | None = None,
    ) -> dict:
        """Commit the exact prepared Will result as one atomic event."""
        row = self._will_attempt_row(branch, attempt_id)
        require(row is not None, "unknown Will attempt")
        require(row["actor"] == actor, "Will actor mismatch")
        if row["status"] == "committed":
            require(row["event_id"] is not None, "committed Will attempt has no event")
            receipt = self.db.execute("SELECT receipt_json FROM events WHERE id=?", (row["event_id"],)).fetchone()
            require(receipt is not None, "committed Will event is missing")
            result = json.loads(receipt[0]); result["replayed"] = True
            return result
        require(row["status"] == "prepared", f"Will attempt is {row['status']}")
        current = self.branch(branch)
        expected = current["revision"] if expected_revision is None else expected_revision
        require(expected == row["expected_revision"], "stale Will attempt revision")
        compiled = json.loads(row["compiled_json"])
        return self.apply({
            "api_version": 3, "branch": branch, "expected_revision": expected,
            "request_id": request_id, "kind": "will_attempt", "actor": actor,
            "narrative": narrative, "changes": compiled.get("changes", []),
            "properties": compiled.get("properties", []), "processes": compiled.get("processes", []),
            "consequences": compiled.get("consequences", []), "observations": compiled.get("observations", []),
            "roll_ids": compiled.get("roll_ids", []), "dependencies": compiled.get("dependencies", []),
            "resolution": compiled.get("resolution"), "judgment": compiled.get("judgment", {}),
            "will_attempt": {"attempt_id": attempt_id, "compiled_digest": digest(compiled)},
        })

    def define_property(self, property_id: str, version: int, label: str, meaning: str, value_type: str, applicability: Any, constraints: Any, lifecycle: str = "proposed", unit: str | None = None, origin: str = "design") -> dict:
        require(isinstance(property_id, str) and property_id and isinstance(version, int) and version > 0, "invalid property identity")
        require(value_type in _PROPERTY_TYPES, "invalid property type")
        require(lifecycle in _LIFECYCLE, "invalid property lifecycle")
        require(isinstance(applicability, (list,dict)), "invalid property applicability")
        require(isinstance(constraints, dict), "invalid property constraints")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO property_definitions VALUES(?,?,?,?,?,?,?,?,?)",
                (property_id, version, label, meaning, value_type, unit, encoded(applicability), encoded(constraints), origin),
            )
            self.db.execute(
                "INSERT INTO property_lifecycle(property_id,definition_version,state,reason) VALUES(?,?,?,?)",
                (property_id, version, lifecycle, "registered through engine"),
            )
            self.db.execute(
                "INSERT INTO property_operations(id,operation,property_id,definition_version,before_json,after_json,actor,reason) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "define", property_id, version, None, encoded({"state": lifecycle}), "system", "property registry change"),
            )
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        self.register_component("property", property_id, str(version), f"property:{property_id}:{version}", status="verified" if lifecycle == "active" else "declared", readers=["engine"], writers=["event"], compatibility={"runtime_schema":"4"}, declared_by="property-registry")
        return {"property_id": property_id, "definition_version": version, "state": lifecycle, "unit": unit}

    def revise_property(self, property_id: str, old_version: int, new_version: int, **definition: Any) -> dict:
        require(new_version > old_version, "new property version must increase")
        old = self._definition(property_id, old_version)
        result = self.define_property(property_id, new_version, definition["label"], definition["meaning"], definition["value_type"], definition["applicability"], definition.get("constraints", {}), definition.get("lifecycle", "proposed"), definition.get("unit"), definition.get("origin", "design"))
        self.register_component("property", property_id, str(new_version), f"property:{property_id}:{new_version}", status="verified", readers=["engine"], writers=["event"], compatibility={"runtime_schema":"4"}, declared_by="property-registry")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO registry_dependencies(kind,stable_id,version,depends_kind,depends_id,depends_version,relation) VALUES('property',?,?,?,?,?,'replaces')",
                (property_id, str(new_version), "property", property_id, str(old_version)),
            )
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return result

    def retire_property(self, property_id: str, version: int, reason: str, actor: str = "system", replacement: tuple[str,int] | None = None) -> dict:
        self._definition(property_id, version)
        deps = self.property_dependencies(property_id, version)
        if deps and replacement is None:
            raise Rejected("property has downstream dependencies; provide replacement mapping")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "INSERT INTO property_lifecycle(property_id,definition_version,state,reason) VALUES(?,?,?,?)",
                (property_id, version, "retired", reason),
            )
            self.db.execute(
                "INSERT INTO property_operations(id,operation,property_id,definition_version,before_json,after_json,actor,reason) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "retire", property_id, version, None, encoded({"replacement": replacement}), actor, reason),
            )
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return {"property_id":property_id,"definition_version":version,"state":"retired","dependencies":deps}

    def set_property(self, branch: str, entity_id: str, property_id: str, definition_version: int, state: str, value: Any = None, unit: str | None = None, context: dict | None = None, epistemic_status: str = "proposed", visibility: str = "gm", source_event: str | None = None) -> dict:
        """Compatibility/admin assignment.

        Play writes should use apply(..., properties=[...]) so the assignment is
        part of an event. This method records an administrative operation and is
        retained for old callers and registry setup.
        """
        assignment = {"entity_id":entity_id,"property_id":property_id,"definition_version":definition_version,"state":state,"value":value,"unit":unit,"context":context or {},"epistemic_status":epistemic_status,"visibility":visibility}
        self._validate_property_assignment(branch, assignment)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.property_value(branch, entity_id, property_id, definition_version)
            new = self._property_json(branch, assignment, source_event)
            self.db.execute(
                """INSERT INTO property_values
                   (branch,entity_id,property_id,definition_version,state,number_value,text_value,json_value,unit,context_json,valid_from_event,valid_until_event,epistemic_status,visibility)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(branch,entity_id,property_id,definition_version) DO UPDATE SET
                   state=excluded.state,number_value=excluded.number_value,text_value=excluded.text_value,json_value=excluded.json_value,
                   unit=excluded.unit,context_json=excluded.context_json,valid_from_event=excluded.valid_from_event,
                   valid_until_event=excluded.valid_until_event,epistemic_status=excluded.epistemic_status,visibility=excluded.visibility""",
                tuple(new[k] for k in ("branch","entity_id","property_id","definition_version","state","number_value","text_value","json_value","unit","context_json","valid_from_event","valid_until_event","epistemic_status","visibility")),
            )
            self.db.execute(
                "INSERT INTO property_operations(id,operation,property_id,definition_version,before_json,after_json,actor,reason) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), "assign", property_id, definition_version, encoded(old) if old else None, encoded(new), "compatibility", "direct assignment; use event-mediated properties for play"),
            )
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return self.property_value(branch, entity_id, property_id, definition_version)

    def add_rule(self, rule_id: str, version: int, name: str, inputs: Any, outputs: Any, mechanical: bool, definition: dict, dependencies: Iterable[tuple] = ()) -> dict:
        require(isinstance(definition, dict), "rule definition must be an object")
        deps = list(dependencies)
        if definition.get("kind") == "personality":
            from .personality import validate_policy, validate_policy_references
            require(mechanical is True, "personality weight evaluation is mechanical; semantic authorship remains judgment")
            validate_policy(definition, inputs, outputs, deps)
            validate_policy_references(self, definition)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute("INSERT INTO rule_definitions VALUES(?,?,?,?,?,?,?)", (rule_id, version, name, encoded(inputs), encoded(outputs), int(mechanical), encoded(definition)))
            for prop, pver, usage in deps:
                self._definition(prop, int(pver))
                require(usage in ("reads","writes","derives"), "invalid rule dependency usage")
                self.db.execute("INSERT INTO rule_dependencies VALUES(?,?,?,?,?)", (rule_id, version, prop, pver, usage))
            self._validate_rule_cycles()
            if definition.get("kind") == "personality":
                # Record dependencies of the restricted, executable condition DSL.
                from .personality import policy_domains
                self.db.execute('INSERT INTO registry_entries VALUES(?,?,?,?,?,?,?,?,?,?)', ('rule',rule_id,str(version),f'rule:{rule_id}:{version}','verified',encoded(['Engine.evaluate_rule']),encoded(['Engine.add_rule']),encoded({'runtime_schema':'4','personality_interface':'1'}),None,'engine'))
                for domain in policy_domains(definition):
                    self.db.execute("INSERT INTO registry_dependencies VALUES(?,?,?,?,?,?,?)", ("rule",rule_id,str(version),"domain",domain,"1","verified condition read"))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        compatibility={"runtime_schema":"4"}
        if definition.get('kind')=='personality': compatibility['personality_interface']='1'
        self.register_component("rule", rule_id, str(version), f"rule:{rule_id}:{version}", status="verified", readers=["engine"], writers=["event"], compatibility=compatibility, declared_by="engine")
        return {"rule_id": rule_id, "rule_version": version}

    def evaluate_rule(self, rule_id: str, version: int, branch: str, subject_id: str | None = None, inputs: dict | None = None) -> dict:
        row = self.db.execute("SELECT * FROM rule_definitions WHERE rule_id=? AND rule_version=?", (rule_id, version)).fetchone()
        require(row is not None, "unknown rule")
        definition = json.loads(row["definition_json"])
        if definition.get("kind") == "personality":
            from .personality import evaluate
            return evaluate(self, rule_id, version, branch, subject_id, inputs)
        supplied = dict(inputs or {})
        values = {}
        for prop in json.loads(row["inputs_json"]):
            if prop in supplied:
                values[prop] = supplied[prop]
                continue
            pver = self.db.execute("SELECT property_version FROM rule_dependencies WHERE rule_id=? AND rule_version=? AND property_id=? AND usage='reads' ORDER BY property_version DESC LIMIT 1", (rule_id,version,prop)).fetchone()
            if pver and subject_id:
                pv = self.property_value(branch, subject_id, prop, pver[0])
                require(pv is not None and pv["state"] == "known", f"missing rule input {prop}")
                values[prop] = pv["value"]
        kind = definition.get("kind", "judgment")
        if kind == "threshold":
            prop = definition.get("property") or (json.loads(row["inputs_json"])[0] if json.loads(row["inputs_json"]) else None)
            require(prop in values, "threshold input missing")
            threshold = definition.get("threshold")
            require(type(threshold) in (int,float), "threshold missing")
            op = definition.get("operator", ">=")
            lhs = values[prop]
            result = {">=": lhs >= threshold, ">": lhs > threshold, "<=": lhs <= threshold, "<": lhs < threshold, "==": lhs == threshold}.get(op)
            require(result is not None, "unsupported threshold operator")
            output = {"value": result, "property": prop, "threshold": threshold}
        elif kind == "sum":
            output = {"value": sum(v for v in values.values() if isinstance(v,(int,float))), "inputs": values}
        elif kind == "contextual":
            output = {"value": definition.get("outcome", "requires_gm_judgment"), "inputs": values}
        else:
            output = {"value": None, "requires_judgment": True, "inputs": values}
        return {"rule_id": rule_id, "rule_version": version, "mechanical": bool(row["mechanical"]), "kind": kind, "inputs": values, "output": output}

    def _validate_rule_cycles(self) -> None:
        graph: dict[str,set[str]] = {}
        for row in self.db.execute("SELECT * FROM rule_dependencies WHERE usage IN ('reads','derives')"):
            graph.setdefault(f"prop:{row['property_id']}", set())
        for rule in self.db.execute("SELECT * FROM rule_definitions"):
            outputs = json.loads(rule["outputs_json"])
            inputs = [r["property_id"] for r in self.db.execute("SELECT property_id FROM rule_dependencies WHERE rule_id=? AND rule_version=? AND usage IN ('reads','derives')", (rule["rule_id"],rule["rule_version"]))]
            for output in outputs:
                for inp in inputs:
                    graph.setdefault(f"prop:{output}", set()).add(f"prop:{inp}")
        def dfs(node: str, visiting: set[str], visited: set[str]) -> None:
            require(node not in visiting, "rule dependency cycle")
            if node in visited: return
            for child in graph.get(node, set()): dfs(child, visiting | {node}, visited)
            visited.add(node)
        visited: set[str] = set()
        for node in graph: dfs(node, set(), visited)

    def property_dependencies(self, property_id: str, version: int | None = None) -> list[dict]:
        params: list[Any] = [property_id]
        sql = """SELECT rule_id,rule_version,property_id,property_version,usage
                 FROM rule_dependencies WHERE property_id=?"""
        if version is not None:
            sql += " AND property_version=?"; params.append(version)
        rows = [dict(r) for r in self.db.execute(sql, params)]
        rows += [
            {"kind": r["kind"], "stable_id": r["stable_id"], "version": r["version"], "relation": r["relation"]}
            for r in self.db.execute("SELECT * FROM registry_dependencies WHERE depends_kind='property' AND depends_id=? AND (depends_version IS NULL OR depends_version=?)", (property_id, str(version) if version is not None else str(version or "")))
        ]
        rows += [
            {"event_id": r["event_id"], "usage": r["usage"], "version": r["version"]}
            for r in self.db.execute("SELECT * FROM event_dependencies WHERE kind='property' AND ref_id=?", (property_id,))
        ]
        return rows

    def dependencies(self, property_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute("SELECT rule_id,rule_version,usage FROM rule_dependencies WHERE property_id=?", (property_id,))]

    def register_component(self, kind: str, stable_id: str, version: str, locator: str, status: str = "declared", readers: list[str] | None = None, writers: list[str] | None = None, compatibility: dict | None = None, source_hash: str | None = None, declared_by: str = "engine") -> dict:
        require(status in ("declared","verified","uncertain","retired"), "invalid registry status")
        self.db.execute(
            """INSERT INTO registry_entries VALUES(?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(kind,stable_id,version) DO UPDATE SET locator=excluded.locator,status=excluded.status,
               readers_json=excluded.readers_json,writers_json=excluded.writers_json,compatibility_json=excluded.compatibility_json,
               source_hash=excluded.source_hash,declared_by=excluded.declared_by""",
            (kind,stable_id,version,locator,status,encoded(readers or []),encoded(writers or []),encoded(compatibility or {}),source_hash,declared_by),
        )
        self.db.commit()
        return {"kind":kind,"stable_id":stable_id,"version":version,"status":status,"locator":locator}

    def add_registry_dependency(self, kind: str, stable_id: str, version: str, depends_kind: str, depends_id: str, depends_version: str | None, relation: str = "uses") -> dict:
        require(self.db.execute("SELECT 1 FROM registry_entries WHERE kind=? AND stable_id=? AND version=?", (kind,stable_id,version)).fetchone() is not None, "registry entry missing")
        self.db.execute("INSERT INTO registry_dependencies VALUES(?,?,?,?,?,?,?)", (kind,stable_id,version,depends_kind,depends_id,depends_version,relation))
        self._validate_registry_cycles()
        self.db.commit()
        return {"ok":True}

    def _validate_registry_cycles(self) -> None:
        graph: dict[tuple[str,str,str],set[tuple[str,str,str]]] = {}
        for r in self.db.execute("SELECT * FROM registry_dependencies"):
            a=(r["kind"],r["stable_id"],r["version"]); b=(r["depends_kind"],r["depends_id"],r["depends_version"] or "")
            graph.setdefault(a,set()).add(b)
        def dfs(node: tuple[str,str,str], stack: set[tuple[str,str,str]], done: set[tuple[str,str,str]]) -> None:
            require(node not in stack, "dependency cycle")
            if node in done: return
            for child in graph.get(node,set()): dfs(child, stack | {node}, done)
            done.add(node)
        done: set[tuple[str,str,str]] = set()
        for node in graph: dfs(node,set(),done)

    def impact(self, kind: str, stable_id: str, version: str | None = None) -> dict:
        rows = []
        for r in self.db.execute("SELECT * FROM registry_dependencies WHERE depends_kind=? AND depends_id=?", (kind,stable_id)):
            if version is None or r["depends_version"] in (None, version):
                rows.append(dict(r))
        if kind == "property":
            rows.extend(self.property_dependencies(stable_id, int(version) if version and version.isdigit() else None))
        else:
            rows.extend(dict(r) for r in self.db.execute("SELECT * FROM event_dependencies WHERE kind=? AND ref_id=?", (kind,stable_id)) if version is None or r['version']==version)
        if kind == "rule":
            rows.extend({'kind':'personality_profile','branch':r['branch'],'id':r['id'],'policy_version':r['policy_version']} for r in self.db.execute('SELECT * FROM personality_profile WHERE policy_id=?',(stable_id,)) if version is None or str(r['policy_version'])==version)
        return {"target":{"kind":kind,"id":stable_id,"version":version},"dependents":rows}

    def register_module(self, module_id: str, module_version: str, entry_skill: str, triggers: list, required_context: list, commands: list, dependencies: list, compatibility: dict, visibility: str = "scene", source_hash: str | None = None, status: str = "active") -> dict:
        self.db.execute(
            "INSERT INTO module_manifests VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(module_id) DO UPDATE SET module_version=excluded.module_version,entry_skill=excluded.entry_skill,triggers_json=excluded.triggers_json,required_context_json=excluded.required_context_json,commands_json=excluded.commands_json,dependencies_json=excluded.dependencies_json,compatibility_json=excluded.compatibility_json,visibility=excluded.visibility,source_hash=excluded.source_hash,status=excluded.status",
            (module_id,module_version,entry_skill,encoded(triggers),encoded(required_context),encoded(commands),encoded(dependencies),encoded(compatibility),visibility,source_hash,status),
        )
        self.register_component("module",module_id,module_version,f"module:{module_id}",status="verified",readers=required_context,writers=commands,compatibility=compatibility,source_hash=source_hash,declared_by=entry_skill)
        return {"module_id":module_id,"version":module_version,"status":status}

    def validate_registry(self) -> dict:
        errors = []
        for row in self.db.execute("SELECT * FROM registry_entries"):
            try:
                if row["kind"] == "rule":
                    rid, ver = row["stable_id"], int(row["version"])
                    require(self.db.execute("SELECT 1 FROM rule_definitions WHERE rule_id=? AND rule_version=?", (rid,ver)).fetchone() is not None, "missing rule implementation")
                if row["kind"] == "module":
                    require(self.db.execute("SELECT 1 FROM module_manifests WHERE module_id=?", (row["stable_id"],)).fetchone() is not None, "missing module manifest")
            except Rejected as exc:
                errors.append({"entry":dict(row),"error":str(exc)})
        try:
            self._validate_registry_cycles()
        except Rejected as exc:
            errors.append({"error":str(exc)})
        return {"ok":not errors,"errors":errors,"entries":self.db.execute("SELECT count(*) FROM registry_entries").fetchone()[0]}

    def create_process(self, branch: str, process: dict, request_id: str, actor: str, narrative: str, expected_revision: int | None = None, causes: list[str] | None = None) -> dict:
        meta = self.branch(branch)
        command = {
            "api_version": 2, "branch": branch, "expected_revision": meta["revision"] if expected_revision is None else expected_revision,
            "request_id": request_id, "kind": "process", "actor": actor, "narrative": narrative,
            "changes": [], "processes": [dict(process, op="create")], "causes": causes or [],
        }
        receipt = self.apply(command)
        self.register_component(
            "process", process["id"], "1", f"process:{process['id']}",
            status="verified", readers=["Engine.list_processes", "Engine.advance_simulation"],
            writers=["Engine.apply", "Engine.advance_simulation"],
            compatibility={"runtime_schema": "4"}, declared_by="engine",
        )
        return receipt

    def _due_process_effect(self, branch: str, p: dict, from_tick: float, to_tick: float) -> tuple[list[dict], list[dict], dict | None]:
        metadata = p.get("metadata", {})
        effect = metadata.get("effect", {})
        changes: list[dict] = []; properties: list[dict] = []
        if not effect:
            return changes, properties, None
        kind = effect.get("kind")
        if kind == "record_patch":
            rid = effect.get("record_id"); rec = self.get(branch, rid)
            require(rec is not None, "process effect record missing")
            data = dict(effect.get("data", {}))
            changes.append({"op":"patch","id":rid,"expected_version":rec["version"],"data":data,"evidence":[{"note":f"process {p['id']} deterministic effect"}]})
        elif kind == "property_delta":
            entity_id = effect.get("entity_id"); prop = effect.get("property_id"); ver = int(effect.get("definition_version", 1))
            current = self.property_value(branch, entity_id, prop, ver)
            require(current is not None and current["state"] == "known" and isinstance(current["value"], (int,float)), "process property input requires known numeric value")
            delta = effect.get("delta_per_unit", 0) * (to_tick - from_tick)
            properties.append({"entity_id":entity_id,"property_id":prop,"definition_version":ver,"state":"known","value":current["value"] + delta,"unit":current.get("unit"),"context":json.loads(current["context_json"]),"epistemic_status":"derived","visibility":current["visibility"]})
        elif kind in ("judgment", "text"):
            return changes, properties, {"reason": effect.get("reason", "process requires GM judgment")}
        else:
            return changes, properties, {"reason": "unsupported process effect"}
        return changes, properties, None

    def advance_simulation(self, branch: str, clock_id: str, target_tick: float, request_id: str, actor: str, narrative: str, expected_revision: int | None = None, limit: int = 100, prepare_only: bool = False) -> dict:
        meta = self.branch(branch); expected = meta["revision"] if expected_revision is None else expected_revision
        clock = self.get(branch, clock_id); require(clock is not None and clock["domain"] == "clock", "clock required")
        require(type(target_tick) in (int,float) and math.isfinite(target_tick) and target_tick >= clock["data"]["tick"], "simulation cannot move backwards")
        changes = [{"op":"patch","id":clock_id,"expected_version":clock["version"],"data":{"tick":target_tick},"evidence":[{"note":"explicit simulation time advancement"}]}]
        for r in self.state(branch):
            if r["domain"] == "schedule" and r["data"].get("clock") == clock_id and r["data"].get("phase") == "pending" and r["data"].get("due") <= target_tick:
                changes.append({"op":"patch","id":r["id"],"expected_version":r["version"],"data":{"phase":"due"},"evidence":[{"note":"schedule reached due time"}]})
        processes = []; properties = []; runs = []; blocked = []
        rows = self.list_processes(branch)
        require(len(rows) <= limit or limit > 0, "process limit must be positive")
        for p in rows[:limit]:
            if p["state"] not in ("active", "due"):
                continue
            if p["state"] == "active" and p.get("next_tick") is None:
                continue
            if p.get("next_tick") is not None and p["next_tick"] > target_tick:
                continue
            from_tick = p.get("last_tick")
            if from_tick is None:
                from_tick = clock["data"]["tick"]
            run_key = f"{clock_id}:{from_tick}:{target_tick}"
            if self.db.execute("SELECT 1 FROM process_runs WHERE branch=? AND process_id=? AND run_key=?", (branch,p["id"],run_key)).fetchone():
                continue
            try:
                c, props, judgment = self._due_process_effect(branch,p,from_tick,target_tick)
                changes.extend(c); properties.extend(props)
                next_tick = (p["next_tick"] + p["interval_value"]) if p.get("interval_value") is not None else None
                if next_tick is not None and p.get("interval_value") and p.get("interval_value") > 0:
                    while next_tick <= target_tick:
                        next_tick += p["interval_value"]
                update = {
                    "op": "update", "id": p["id"],
                    "state": "blocked" if judgment else ("active" if next_tick is not None else "completed"),
                    "last_tick": target_tick, "next_tick": next_tick,
                    "pending_judgment": judgment["reason"] if judgment else None,
                }
                processes.append(update)
                runs.append({"process_id":p["id"],"run_key":run_key,"from_tick":from_tick,"to_tick":target_tick,"outcome":{"changes":c,"judgment":judgment},"status":"blocked" if judgment else "resolved"})
                if judgment:
                    blocked.append({"process_id":p["id"],"reason":judgment["reason"]})
            except Rejected as exc:
                processes.append({"op":"update","id":p["id"],"state":"blocked","pending_judgment":str(exc)})
                runs.append({"process_id":p["id"],"run_key":run_key,"from_tick":from_tick,"to_tick":target_tick,"outcome":{"error":str(exc)},"status":"blocked"})
                blocked.append({"process_id":p["id"],"reason":str(exc)})
        command = {
            "api_version":2,"branch":branch,"expected_revision":expected,"request_id":request_id,"kind":"advance_time","actor":actor,"narrative":narrative,
            "changes":changes,"processes":processes,"properties":properties,"process_runs":runs,"clock_id":clock_id,"tick":target_tick,
        }
        if prepare_only:
            deferred = [p['id'] for p in rows[limit:] if p.get('state') in ('active','due','blocked') and (p.get('next_tick') is None or p['next_tick'] <= target_tick)]
            blocked.extend({'process_id':p['id'],'reason':p.get('pending_judgment') or 'pending judgment'} for p in rows if p['state']=='blocked')
            return {'command':command,'blocked':blocked,'deferred':deferred}
        receipt = self.apply(command)
        receipt["blocked_processes"] = blocked
        receipt["deferred_processes"] = [
            p["id"] for p in rows[limit:]
            if p.get("state") in ("active", "due") and p.get("next_tick") is not None and p["next_tick"] <= target_tick
        ]
        return receipt

    def apply_consequences(self, branch: str, request_id: str, actor: str, narrative: str, expected_revision: int | None = None, limit: int = 50) -> dict:
        meta = self.branch(branch); expected = meta["revision"] if expected_revision is None else expected_revision
        pending = [dict(r) for r in self.db.execute("SELECT * FROM consequences WHERE branch=? AND status='pending' ORDER BY rowid LIMIT ?", (branch,limit))]
        changes: list[dict] = []; properties: list[dict] = []; runs: list[dict] = []; unresolved = []
        for c in pending:
            trigger = json.loads(c["trigger_json"])
            due = trigger.get("kind") in (None, "immediate")
            if "at" in trigger:
                clock_id = trigger.get("clock_id")
                clock = self.get(branch, clock_id) if clock_id else None
                due = bool(clock and clock["domain"] == "clock" and clock["data"].get("tick", 0) >= trigger["at"])
            if trigger.get("requires_judgment"):
                due = False
            if not due:
                continue
            effect = json.loads(c["effect_json"])
            if "changes" in effect:
                changes.extend(effect["changes"])
                runs.append({"consequence_id":c["id"],"run_key":"apply-once","status":"applied","detail":{"changes":len(effect["changes"])}})
            elif "properties" in effect:
                properties.extend(effect["properties"])
                runs.append({"consequence_id":c["id"],"run_key":"apply-once","status":"applied","detail":{"properties":len(effect["properties"])}})
            else:
                unresolved.append({"consequence_id":c["id"],"reason":"effect requires GM judgment or explicit structured changes"})
                runs.append({"consequence_id":c["id"],"run_key":"manual","status":"contested","detail":{"reason":"unsupported free-text effect"}})
        if not changes and not properties and not runs:
            return {"branch":branch,"revision":meta["revision"],"applied":[],"unresolved":unresolved}
        return self.apply({
            "api_version":2,"branch":branch,"expected_revision":expected,"request_id":request_id,"kind":"consequence",
            "actor":actor,"narrative":narrative,"changes":changes,"properties":properties,"consequence_runs":runs,
        }) | {"unresolved":unresolved}

    def rank_relevance(self, branch: str, viewer: str | None, processes: list[dict] | None = None) -> list[dict]:
        processes = processes if processes is not None else self.list_processes(branch, viewer=None)
        current = self.branch(branch)["revision"]
        output = []
        for p in processes:
            factors = p.get("metadata", {}).get("relevance", {})
            score = float(factors.get("causal_connection", 0)) + float(factors.get("urgency", 0)) + float(factors.get("objective_connection", 0)) + float(factors.get("location_proximity", 0)) + float(factors.get("attention", 0))
            if p["state"] in ("due","blocked"):
                score += 100.0
            self.db.execute(
                "INSERT INTO attention_scores VALUES(?,?,?,?,?,?) ON CONFLICT(branch,process_id,viewer_id) DO UPDATE SET score=excluded.score,factors_json=excluded.factors_json,computed_revision=excluded.computed_revision",
                (branch,p["id"],viewer,score,encoded(factors),current),
            )
            pp = dict(p); pp["relevance"] = {"score":score,"factors":factors,"affects_mechanics":False}
            output.append(pp)
        self.db.commit()
        return sorted(output,key=lambda x:(-x["relevance"]["score"],x["id"]))

    def register_snapshot(self, branch: str, snapshot_id: str | None = None) -> dict:
        self.branch(branch)
        state = self._snapshot_payload(branch)
        sid = snapshot_id or f"{branch}:{self.branch(branch)['revision']}:{uuid.uuid4().hex[:8]}"
        self.db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)", (sid,branch,self.branch(branch)["revision"],encoded(state),digest(state)))
        self.db.commit()
        return {"id":sid,"branch":branch,"revision":self.branch(branch)["revision"],"sha256":digest(state)}

    def replay(self, branch: str = "main") -> dict:
        self.branch(branch)
        baseline = self.db.execute("SELECT state_json,revision FROM snapshots WHERE id=?", ("fork:"+branch,)).fetchone()
        records: dict[str,dict] = {}
        aux: dict[str,Any] = {}
        start_revision = 0
        if baseline:
            payload = json.loads(baseline["state_json"])
            if isinstance(payload, list):
                records = {r["id"]:r for r in payload}
            else:
                records = {r["id"]:r for r in payload.get("records",[])}
                kinds = {
                    "properties": "property", "processes": "process", "facets": "facet",
                    "consequences": "consequence", "choices": "choice", "process_runs": "run",
                    "consequence_runs": "consequence_run", "observations": "observation",
                    "profiles": "profile", "links": "link", "classifications": "classification",
                    "will_attempts": "will_attempt",
                }
                for field, kind in kinds.items():
                    for item in payload.get(field, []):
                        aux[self._replay_state_key(kind, item)] = item
                start_revision = int(baseline["revision"])
        for event in self.db.execute("SELECT * FROM events WHERE branch=? AND revision>? ORDER BY revision", (branch,start_revision)):
            for c in self.db.execute("SELECT * FROM changes WHERE event_id=? ORDER BY ordinal", (event["id"],)):
                after = json.loads(c["after_json"]); records[c["record_id"]] = after
            for a in self.db.execute("SELECT * FROM event_aux_changes WHERE event_id=? ORDER BY ordinal", (event["id"],)):
                if a["after_json"] is None: aux.pop(a["state_key"],None)
                else: aux[a["state_key"]] = json.loads(a["after_json"])
        return {"branch":branch,"revision":self.branch(branch)["revision"],"records":sorted(records.values(),key=lambda x:x["id"]),"auxiliary":sorted(aux.items()),"complete":bool(baseline) or not self.db.execute("SELECT 1 FROM property_operations WHERE operation='assign'").fetchone()}

    def causal_history(self, branch: str = "main", event_id: str | None = None, viewer: str | None = None) -> list[dict]:
        rows = {r["id"]: dict(r) for r in self.db.execute("SELECT * FROM events WHERE branch=?", (branch,))}
        if event_id is None:
            selected = set(rows)
        else:
            require(event_id in rows, "event not found")
            selected = set(); stack = [event_id]
            while stack:
                current = stack.pop()
                if current in selected:
                    continue
                selected.add(current)
                stack.extend(json.loads(rows[current]["causes_json"]))
        out = []
        for rid in sorted(selected, key=lambda x: rows[x]["revision"]):
            row = rows[rid]
            if viewer is None:
                out.append(row)
            else:
                out.append({"id": row["id"], "revision": row["revision"], "kind": row["kind"], "actor": row["actor"], "tick": row["tick"]})
        return out

    def verify(self) -> dict:
        require(self.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity check failed")
        require(not self.db.execute("PRAGMA foreign_key_check").fetchall(), "foreign key check failed")
        for source in self.db.execute("SELECT * FROM sources"):
            require(hashlib.sha256(source["content"].encode()).hexdigest() == source["sha256"], "source hash mismatch")
        for snap in self.db.execute("SELECT * FROM snapshots"):
            state = json.loads(snap["state_json"])
            require(digest(state) == snap["sha256"], "snapshot hash mismatch")
        for branch in self.db.execute("SELECT * FROM branches").fetchall():
            self._validate_world(branch["id"])
            baseline = self.db.execute("SELECT state_json,revision FROM snapshots WHERE id=?", ("fork:"+branch["id"],)).fetchone()
            reconstructed: dict[str,dict] = {}
            previous, revision = "", 0
            if baseline:
                payload = json.loads(baseline["state_json"])
                base_records = payload if isinstance(payload,list) else payload.get("records",[])
                reconstructed = {r["id"]:r for r in base_records}; revision = int(baseline["revision"])
            for event in self.db.execute("SELECT * FROM events WHERE branch=? AND revision>? ORDER BY revision", (branch["id"], revision)):
                original = json.loads(event["command_json"])
                require(digest(original) == event["payload_hash"], "command hash mismatch")
                for field in ("branch","request_id","kind","actor","narrative","clock_id","tick"):
                    require(original.get(field) == event[field], "event metadata mismatch")
                require(original.get("causes",[]) == json.loads(event["causes_json"]), "event causes mismatch")
                pending = []
                for change in self.db.execute("SELECT * FROM changes WHERE event_id=? ORDER BY ordinal", (event["id"],)):
                    before = json.loads(change["before_json"]) if change["before_json"] else None
                    after = json.loads(change["after_json"])
                    require(reconstructed.get(change["record_id"]) == before, "history before-image mismatch")
                    reconstructed[change["record_id"]] = after; pending.append((before,after))
                require(event["prev_hash"] == previous or (baseline and revision == event["revision"]-1), "history sequence broken")
                require(digest({"previous":event["prev_hash"],"payload_hash":event["payload_hash"],"changes":pending}) == event["event_hash"], "event hash mismatch")
                receipt = json.loads(event["receipt_json"])
                require(receipt["event_id"] == event["id"] and receipt["event_hash"] == event["event_hash"] and receipt["revision"] == event["revision"] and receipt["branch"] == event["branch"] and receipt["request_id"] == event["request_id"] and receipt["changed"] == [a["id"] for _,a in pending] and receipt["committed"] is True, "receipt mismatch")
                used = [r[0] for r in self.db.execute("SELECT id FROM roll_uses WHERE branch=? AND event_id=? ORDER BY id", (branch["id"], event["id"]))]
                require(used == sorted(original.get("roll_ids",[])), "roll consumption mismatch")
                previous = event["event_hash"]
                revision = event["revision"]
            require(revision == branch["revision"] if not baseline else branch["revision"] == max([r["revision"] for r in self.db.execute("SELECT revision FROM events WHERE branch=?", (branch["id"],))] or [branch["revision"]]), "branch head mismatch")
            require(sorted(reconstructed.values(),key=lambda x:x["id"]) == self.state(branch["id"]), "state differs from event history")
        for row in self.db.execute("SELECT * FROM event_aux_changes"):
            if row["after_json"]:
                require(json.loads(row["after_json"]) is not None, "invalid auxiliary after image")
        for row in self.db.execute("SELECT * FROM will_attempts"):
            require(row["status"] in {"prepared", "blocked", "committed", "cancelled"}, "invalid Will attempt status")
            attempt = json.loads(row["attempt_json"]); compiled = json.loads(row["compiled_json"])
            require(attempt.get("attempt_id") == row["attempt_id"], "Will attempt identity mismatch")
            require(attempt.get("input_snapshot_hash") == row["input_snapshot_hash"], "Will attempt input hash mismatch")
            require(row["status"] != "committed" or (row["event_id"] and self.db.execute("SELECT kind FROM events WHERE id=? AND branch=?", (row["event_id"], row["branch"])).fetchone()[0] == "will_attempt"), "committed Will attempt event mismatch")
        for row in self.db.execute('SELECT * FROM decision_proposals'):
            spec=json.loads(row['spec_json']); compiled=json.loads(row['compiled_json'])
            require(digest(spec)==row['spec_hash'] and spec['id']==row['id'],'decision specification hash mismatch')
            require(compiled['status'] in ('available','blocked'),'invalid decision status')
            require(row['roll'] is None or 1<=row['roll']<=20,'invalid decision roll')
            event=self.db.execute('SELECT er.resolution_json FROM event_resolutions er JOIN events ev ON ev.id=er.event_id WHERE ev.branch=? AND ev.request_id=?',(row['branch'],'decision:'+row['id'])).fetchone()
            if event:
                require(json.loads(event[0]).get('roll_result')==row['roll'],'decision roll differs from event')
        self.validate_registry()
        # v11: composition/knowledge integrity participates in the global verifier.
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='composition_interface'").fetchone():
            for table in ('composition_frames','composition_types','composition_aspects'):
                for row in self.db.execute('SELECT definition_json,source_hash FROM '+table):
                    payload=json.loads(row['definition_json'])
                    require(digest(payload)==row['source_hash'],table+' source hash mismatch')
            for row in self.db.execute('SELECT claims_json,metadata_json,source_type,source_ref,content_hash,captured_at FROM knowledge_ledger'):
                payload={'source_type':row['source_type'],'source_ref':row['source_ref'],'claims':json.loads(row['claims_json']),'metadata':json.loads(row['metadata_json']),'captured_at':row['captured_at']}
                require(hashlib.sha256(encoded(payload).encode()).hexdigest()==row['content_hash'],'knowledge ledger hash mismatch')
            for row in self.db.execute('SELECT status,history_json FROM knowledge_routes'):
                history=json.loads(row['history_json']);require(isinstance(history,list) and history,'knowledge route history missing');require(history[-1].get('status')==row['status'],'knowledge route status/history mismatch')
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v11_operations'").fetchone() or self.db.execute("SELECT 1 FROM engine_versions WHERE component='v11_enforcement'").fetchone():
            from .v11.enforcement import verify_v11
            verify_v11(self)
        from .intelligence.nodes import verify_nodes
        verify_nodes(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='method_interface'").fetchone():
            from .intelligence.methods import verify_methods
            verify_methods(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='learning_interface'").fetchone():
            from .intelligence.learning import verify_learning
            verify_learning(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='contribution_interface'").fetchone():
            from .persistence.contributions import verify_contributions
            verify_contributions(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='encounter_interface'").fetchone():
            from .workspaces.world import verify_encounters
            verify_encounters(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='workspace_interface'").fetchone():
            from .workspaces.registry import verify_workspaces
            verify_workspaces(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='network_interface'").fetchone():
            from .intelligence.network import verify_network
            verify_network(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='pipeline_interface'").fetchone():
            from .workspaces.pipeline import verify_pipelines
            verify_pipelines(self)
        if self.db.execute("SELECT 1 FROM engine_versions WHERE component='operations_interface'").fetchone():
            from .operations import verify_operations
            verify_operations(self)
        return {
            "ok":True,"schema_version":2,"runtime_schema":"4",
            "branches":self.db.execute("SELECT count(*) FROM branches").fetchone()[0],
            "events":self.db.execute("SELECT count(*) FROM events").fetchone()[0],
            "records":self.db.execute("SELECT count(*) FROM records").fetchone()[0],
            "properties":self.db.execute("SELECT count(*) FROM property_values").fetchone()[0],
            "processes":self.db.execute("SELECT count(*) FROM processes").fetchone()[0],
            "will_attempts":self.db.execute("SELECT count(*) FROM will_attempts").fetchone()[0],
        }

    def migration_backup(self, destination: str | Path) -> str:
        """Preserve a predecessor schema without opening/upgrading its copy."""
        require(not self.db.in_transaction, "finish transaction before migration backup")
        destination = Path(destination)
        require(not destination.exists(), "migration backup destination exists")
        out = sqlite3.connect(destination)
        try:
            self.db.backup(out)
            require(out.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "migration backup integrity failed")
        finally:
            out.close()
        return str(destination)

    def backup(self, destination: str | Path) -> str:
        require(not self.db.in_transaction, "finish active transaction before backup")
        destination = Path(destination)
        require(destination.resolve() != Path(self.path).resolve(), "cannot overwrite live database")
        require(not destination.exists(), "backup destination already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        from .checkpoint import checked_backup
        return checked_backup(self, destination)

    @staticmethod
    def restore(source: str | Path, destination: str | Path) -> dict:
        source = Path(source); destination = Path(destination)
        require(source.exists(), "restore source does not exist")
        require(source.resolve() != destination.resolve(), "restore destination must differ from source")
        require(not destination.exists(), "restore destination already exists")
        destination.parent.mkdir(parents=True, exist_ok=True)
        src = sqlite3.connect(source); out = sqlite3.connect(destination)
        try:
            src.backup(out)
        finally:
            out.close(); src.close()
        restored = Engine(destination)
        try:
            return {"source": str(source), "destination": str(destination), "verification": restored.verify()}
        finally:
            restored.close()

    def resolve_character_interaction(self, branch: str, character_id: str, initiator_id: str, proposal: dict | str) -> dict:
        from .characters import resolve_interaction
        return resolve_interaction(self, branch, character_id, initiator_id, proposal)
