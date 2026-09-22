CREATE TABLE IF NOT EXISTS composition_frames(
  frame_id TEXT NOT NULL,
  version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft','active','deprecated','retired')),
  definition_json TEXT NOT NULL CHECK(json_valid(definition_json)),
  source_hash TEXT NOT NULL,
  PRIMARY KEY(frame_id,version)
);
CREATE TABLE IF NOT EXISTS composition_types(
  type_id TEXT PRIMARY KEY,
  family TEXT NOT NULL,
  purpose_type TEXT NOT NULL,
  short_description TEXT NOT NULL,
  definition_json TEXT NOT NULL CHECK(json_valid(definition_json)),
  source_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft','active','deprecated','retired'))
);
CREATE TABLE IF NOT EXISTS composition_aspects(
  aspect_id TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version>0),
  family TEXT NOT NULL,
  type_id TEXT NOT NULL REFERENCES composition_types(type_id),
  purpose_type TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft','active','deprecated','retired')),
  definition_json TEXT NOT NULL CHECK(json_valid(definition_json)),
  source_hash TEXT NOT NULL,
  declared_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(aspect_id,version)
);
CREATE TABLE IF NOT EXISTS composition_receipts(
  receipt_id TEXT PRIMARY KEY,
  branch TEXT NOT NULL REFERENCES branches(id),
  frame_id TEXT NOT NULL,
  branch_revision INTEGER NOT NULL,
  bindings_json TEXT NOT NULL CHECK(json_valid(bindings_json)),
  result_json TEXT NOT NULL CHECK(json_valid(result_json)),
  basis_hash TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('compiled','invalidated')),
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_ledger(
  entry_id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  claims_json TEXT NOT NULL CHECK(json_valid(claims_json)),
  evidence_status TEXT NOT NULL CHECK(evidence_status IN ('unassessed','source_verified','contested','retracted')),
  metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
  captured_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS knowledge_routes(
  route_id TEXT PRIMARY KEY,
  entry_id TEXT NOT NULL REFERENCES knowledge_ledger(entry_id),
  target_ref TEXT NOT NULL,
  reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('AVAILABLE','ROUTED','ENCOUNTERED','INTERPRETED','TESTED','INTEGRATED','REJECTED','UNRESOLVED','TRANSFERRED')),
  history_json TEXT NOT NULL CHECK(json_valid(history_json)),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR REPLACE INTO engine_versions(component,version,checksum,compatible_engine,updated_at)
VALUES('composition_interface','1',NULL,'4',CURRENT_TIMESTAMP);
