-- Kageyoni v11 Situation Architecture operational storage.
-- Canonical world/event tables remain authoritative.
CREATE TABLE IF NOT EXISTS situation_records (
  kind TEXT NOT NULL,
  record_key TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (kind, record_key)
);
