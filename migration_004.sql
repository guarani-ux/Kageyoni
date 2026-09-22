-- Additive Will-system migration.  This migration does not alter existing
-- records or create fictional events; it only creates versioned projections
-- and execution metadata used by the engine.
BEGIN;

CREATE TABLE IF NOT EXISTS "will_definition"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  name TEXT NOT NULL,
  classification TEXT NOT NULL CHECK(classification IN ('primordial','derivative','independent','false','unknown')),
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "will_expression"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  definition TEXT NOT NULL,
  bearer TEXT NOT NULL,
  legacy_will TEXT,
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,definition) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,bearer) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,legacy_will) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "will_technique"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  expression TEXT NOT NULL,
  ability TEXT,
  name TEXT NOT NULL,
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,expression) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,ability) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "will_awakening"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  expression TEXT NOT NULL,
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,expression) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "will_development"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  expression TEXT NOT NULL,
  progression TEXT,
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,expression) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,progression) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE IF NOT EXISTS "will_effect"(
  branch TEXT NOT NULL,
  id TEXT NOT NULL,
  expression TEXT NOT NULL,
  technique TEXT NOT NULL,
  contract TEXT NOT NULL CHECK(json_valid(contract)),
  PRIMARY KEY(branch,id),
  FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,expression) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,
  FOREIGN KEY(branch,technique) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED
);
CREATE INDEX IF NOT EXISTS will_expression_bearer ON will_expression(branch,bearer);
CREATE INDEX IF NOT EXISTS will_technique_expression ON will_technique(branch,expression);

CREATE TABLE IF NOT EXISTS will_attempts(
  branch TEXT NOT NULL REFERENCES branches(id),
  attempt_id TEXT NOT NULL,
  prepare_request_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  expression_id TEXT NOT NULL,
  expression_version INTEGER NOT NULL,
  technique_id TEXT NOT NULL,
  technique_version INTEGER NOT NULL,
  expected_revision INTEGER NOT NULL,
  input_snapshot_hash TEXT NOT NULL,
  attempt_json TEXT NOT NULL CHECK(json_valid(attempt_json)),
  compiled_json TEXT NOT NULL CHECK(json_valid(compiled_json)),
  status TEXT NOT NULL CHECK(status IN ('prepared','blocked','committed','cancelled')),
  roll_id TEXT,
  event_id TEXT REFERENCES events(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(branch,attempt_id),
  UNIQUE(branch,prepare_request_id)
);
CREATE INDEX IF NOT EXISTS will_attempts_actor ON will_attempts(branch,actor,status);
CREATE INDEX IF NOT EXISTS will_attempts_expression ON will_attempts(branch,expression_id,technique_id);
CREATE TABLE IF NOT EXISTS will_contract_history(
  branch TEXT NOT NULL REFERENCES branches(id),
  record_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version>0),
  record_json TEXT NOT NULL CHECK(json_valid(record_json)),
  source_event TEXT REFERENCES events(id),
  PRIMARY KEY(branch,record_id,version)
);
CREATE INDEX IF NOT EXISTS will_contract_history_lookup ON will_contract_history(branch,record_id,version);

INSERT OR IGNORE INTO engine_versions(component,version,compatible_engine)
  VALUES('runtime_schema','4','4');
INSERT OR IGNORE INTO engine_versions(component,version,compatible_engine)
  VALUES('workflow_api','3','4');
UPDATE engine_versions SET version='4',compatible_engine='4',updated_at=CURRENT_TIMESTAMP
  WHERE component='runtime_schema' AND CAST(version AS INTEGER) < 4;
UPDATE engine_versions SET version='3',compatible_engine='4',updated_at=CURRENT_TIMESTAMP
  WHERE component='workflow_api' AND CAST(version AS INTEGER) < 3;
COMMIT;
