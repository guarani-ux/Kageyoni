CREATE TABLE IF NOT EXISTS v11_operations(
  operation_id TEXT PRIMARY KEY,
  objective TEXT NOT NULL,
  requirement_version TEXT NOT NULL,
  scope TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('DECLARED','PREPARED','ASSESSED','AUTHORIZED','EXECUTED','OBSERVED','VERIFIED','COMPLETED','BLOCKED','UNCERTAIN')),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_context_packets(
  context_id TEXT PRIMARY KEY,
  operation_id TEXT REFERENCES v11_operations(operation_id),
  scope TEXT NOT NULL,
  basis_json TEXT NOT NULL CHECK(json_valid(basis_json)),
  included_json TEXT NOT NULL CHECK(json_valid(included_json)),
  unresolved_json TEXT NOT NULL CHECK(json_valid(unresolved_json)),
  excluded_json TEXT NOT NULL CHECK(json_valid(excluded_json)),
  source_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at)
VALUES('v11_runtime','1',NULL,'4',CURRENT_TIMESTAMP);
