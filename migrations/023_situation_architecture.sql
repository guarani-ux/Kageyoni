-- Kageyoni v11 Situation Architecture
-- Operational storage only; canonical world/event tables remain authoritative.
CREATE TABLE IF NOT EXISTS situation_records (
  kind TEXT NOT NULL,
  record_key TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (kind, record_key)
);
