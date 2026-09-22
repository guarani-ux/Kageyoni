CREATE TABLE IF NOT EXISTS v11_enforcer_cases(
 case_id TEXT PRIMARY KEY, scope TEXT NOT NULL, protected_requirement TEXT NOT NULL,
 expected_disposition TEXT NOT NULL CHECK(expected_disposition IN ('supported','contradicted','unresolved')),
 basis_json TEXT NOT NULL, source_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_enforcer_trials(
 trial_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES v11_enforcer_cases(case_id),
 enforcer_id TEXT NOT NULL, enforcer_version TEXT NOT NULL, observed_disposition TEXT NOT NULL CHECK(observed_disposition IN ('supported','contradicted','unresolved')),
 correct INTEGER NOT NULL CHECK(correct IN (0,1)), result_json TEXT NOT NULL, source_hash TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(case_id,enforcer_id,enforcer_version)
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at) VALUES('v11_enforcer_eval','1',NULL,'4',CURRENT_TIMESTAMP);
