ALTER TABLE v11_preparations ADD COLUMN payload_hash TEXT;
CREATE TABLE IF NOT EXISTS v11_execution_receipts(
  receipt_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES v11_operations(operation_id),
  evidence_type TEXT NOT NULL, evidence_ref TEXT NOT NULL, payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  source_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_observations(
  observation_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES v11_operations(operation_id),
  receipt_id TEXT NOT NULL REFERENCES v11_execution_receipts(receipt_id), payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  source_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_verifications(
  verification_id TEXT PRIMARY KEY, operation_id TEXT NOT NULL REFERENCES v11_operations(operation_id),
  observation_id TEXT NOT NULL REFERENCES v11_observations(observation_id), disposition TEXT NOT NULL CHECK(disposition IN ('passed','failed','unresolved')),
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), source_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS v11_frontier_observations(
  observation_id TEXT PRIMARY KEY, frontier_id TEXT NOT NULL REFERENCES v11_frontiers(frontier_id),
  refs_json TEXT NOT NULL CHECK(json_valid(refs_json)), payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  source_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at)
VALUES('v11_trust','1',NULL,'4',CURRENT_TIMESTAMP);
