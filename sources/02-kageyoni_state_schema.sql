PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'provisional',
  current_location_id TEXT,
  current_condition TEXT,
  data_json TEXT NOT NULL DEFAULT '{}',
  created_event_id TEXT,
  updated_event_id TEXT
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  location_type TEXT NOT NULL,
  parent_location_id TEXT,
  state_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'provisional'
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  item_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'provisional',
  data_json TEXT NOT NULL DEFAULT '{}',
  created_event_id TEXT
);

CREATE TABLE IF NOT EXISTS objectives (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  holder_id TEXT,
  objective_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'unknown',
  progress REAL NOT NULL DEFAULT 0,
  data_json TEXT NOT NULL DEFAULT '{}',
  created_event_id TEXT,
  updated_event_id TEXT
);

CREATE TABLE IF NOT EXISTS dynamics (
  id TEXT PRIMARY KEY,
  dynamic_type TEXT NOT NULL,
  from_entity_id TEXT NOT NULL,
  to_entity_id TEXT NOT NULL,
  state_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'provisional',
  updated_event_id TEXT
);

CREATE TABLE IF NOT EXISTS equipment (
  id TEXT PRIMARY KEY,
  item_id TEXT NOT NULL,
  holder_id TEXT,
  slot TEXT NOT NULL DEFAULT 'none',
  condition TEXT NOT NULL DEFAULT 'functional',
  state_json TEXT NOT NULL DEFAULT '{}',
  updated_event_id TEXT
);

CREATE TABLE IF NOT EXISTS scenes (
  id TEXT PRIMARY KEY,
  location_id TEXT NOT NULL,
  round INTEGER NOT NULL DEFAULT 0,
  state_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  sequence INTEGER NOT NULL UNIQUE,
  scene_id TEXT,
  event_type TEXT NOT NULL,
  action TEXT NOT NULL,
  result TEXT NOT NULL,
  epistemic_status TEXT NOT NULL DEFAULT 'confirmed',
  reversibility TEXT NOT NULL DEFAULT 'unknown',
  durability TEXT NOT NULL DEFAULT 'persistent',
  data_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS event_entities (
  event_id TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  role TEXT NOT NULL,
  PRIMARY KEY (event_id, entity_id, role)
);

CREATE TABLE IF NOT EXISTS provenance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_type TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'confirmed',
  note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS state_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,
  last_event_sequence INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_scene ON events(scene_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_provenance_subject ON provenance(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_dynamics_from_to ON dynamics(from_entity_id, to_entity_id);
