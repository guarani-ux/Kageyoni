-- Kageyoni v11 Situation Architecture operational storage.
-- Canonical world/event tables remain authoritative.
CREATE TABLE IF NOT EXISTS situation_records (
  kind TEXT NOT NULL,
  record_key TEXT NOT NULL,
  payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
  PRIMARY KEY (kind, record_key)
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at)
VALUES('situation_architecture','1',NULL,'4',CURRENT_TIMESTAMP);
