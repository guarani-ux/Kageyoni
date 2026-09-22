CREATE TABLE IF NOT EXISTS v11_preparations(
  proposal_id TEXT PRIMARY KEY,
  branch TEXT NOT NULL REFERENCES branches(id),
  expected_revision INTEGER NOT NULL,
  command_hash TEXT NOT NULL,
  compilation_hash TEXT NOT NULL,
  basis_hash TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  status TEXT NOT NULL CHECK(status IN ('prepared','consumed','invalidated')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  consumed_at TEXT
);
CREATE TABLE IF NOT EXISTS v11_enforcer_qualifications(
  qualification_id TEXT PRIMARY KEY,
  enforcer_id TEXT NOT NULL,
  version TEXT NOT NULL,
  scope TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('candidate','shadow','qualified','restricted','suspended')),
  evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)),
  metrics_json TEXT NOT NULL CHECK(json_valid(metrics_json)),
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_assessments(
  assessment_id TEXT PRIMARY KEY,
  enforcer_id TEXT NOT NULL,
  qualification_id TEXT REFERENCES v11_enforcer_qualifications(qualification_id),
  protected_requirement TEXT NOT NULL,
  basis_json TEXT NOT NULL CHECK(json_valid(basis_json)),
  disposition TEXT NOT NULL CHECK(disposition IN ('supported','contradicted','unresolved')),
  result_json TEXT NOT NULL CHECK(json_valid(result_json)),
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_frontiers(
  frontier_id TEXT PRIMARY KEY,
  parent_ref TEXT,
  objective TEXT NOT NULL,
  kind TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('open','investigating','resolved','blocked','abandoned')),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at)
VALUES('v11_enforcement','1',NULL,'4',CURRENT_TIMESTAMP);
