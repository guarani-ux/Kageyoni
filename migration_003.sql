BEGIN;
CREATE TABLE IF NOT EXISTS engine_versions(
  component TEXT PRIMARY KEY, version TEXT NOT NULL, checksum TEXT,
  compatible_engine TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS property_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, entity_id TEXT NOT NULL, property_id TEXT NOT NULL,
  definition_version INTEGER NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS property_operations(
  id TEXT PRIMARY KEY, operation TEXT NOT NULL, property_id TEXT NOT NULL,
  definition_version INTEGER, before_json TEXT, after_json TEXT,
  actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS consequence_runs(
  consequence_id TEXT NOT NULL REFERENCES consequences(id), run_key TEXT NOT NULL,
  event_id TEXT NOT NULL REFERENCES events(id), status TEXT NOT NULL,
  detail_json TEXT NOT NULL CHECK(json_valid(detail_json)),
  PRIMARY KEY(consequence_id,run_key)
);
CREATE TABLE IF NOT EXISTS processes(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL,
  process_kind TEXT NOT NULL, state TEXT NOT NULL,
  subjects_json TEXT NOT NULL, scope_json TEXT NOT NULL,
  origin_event TEXT REFERENCES events(id), rule_id TEXT, rule_version INTEGER,
  conditions_json TEXT NOT NULL, subscriptions_json TEXT NOT NULL,
  last_tick REAL, next_tick REAL, interval_value REAL, interval_unit TEXT,
  granularity TEXT NOT NULL DEFAULT 'exact', rng_slot TEXT, pending_judgment TEXT,
  visibility TEXT NOT NULL DEFAULT 'gm', metadata_json TEXT NOT NULL DEFAULT '{}',
  updated_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
);
CREATE TABLE IF NOT EXISTS process_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, process_id TEXT NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS entity_facet_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, entity_id TEXT NOT NULL, facet TEXT NOT NULL,
  before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS process_runs(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, run_key TEXT NOT NULL,
  event_id TEXT, from_tick REAL, to_tick REAL, rng_result_json,
  outcome_json TEXT NOT NULL, status TEXT NOT NULL,
  PRIMARY KEY(branch,process_id,run_key)
);
CREATE TABLE IF NOT EXISTS process_subscriptions(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, event_kind TEXT NOT NULL,
  PRIMARY KEY(branch,process_id,event_kind)
);
CREATE TABLE IF NOT EXISTS attention_scores(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, viewer_id TEXT, score REAL NOT NULL,
  factors_json TEXT NOT NULL, computed_revision INTEGER NOT NULL,
  PRIMARY KEY(branch,process_id,viewer_id)
);
CREATE TABLE IF NOT EXISTS registry_entries(
  kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
  locator TEXT NOT NULL, status TEXT NOT NULL, readers_json TEXT NOT NULL,
  writers_json TEXT NOT NULL, compatibility_json TEXT NOT NULL, source_hash TEXT,
  declared_by TEXT NOT NULL, PRIMARY KEY(kind,stable_id,version)
);
CREATE TABLE IF NOT EXISTS registry_dependencies(
  kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
  depends_kind TEXT NOT NULL, depends_id TEXT NOT NULL, depends_version TEXT,
  relation TEXT NOT NULL,
  PRIMARY KEY(kind,stable_id,version,depends_kind,depends_id,depends_version,relation)
);
CREATE TABLE IF NOT EXISTS module_manifests(
  module_id TEXT PRIMARY KEY, module_version TEXT NOT NULL, entry_skill TEXT NOT NULL,
  triggers_json TEXT NOT NULL, required_context_json TEXT NOT NULL, commands_json TEXT NOT NULL,
  dependencies_json TEXT NOT NULL, compatibility_json TEXT NOT NULL,
  visibility TEXT NOT NULL, source_hash TEXT, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event_aux_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  kind TEXT NOT NULL, state_key TEXT NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS migration_checks(
  version INTEGER PRIMARY KEY, predecessor INTEGER, script_name TEXT NOT NULL,
  checksum TEXT NOT NULL, engine_min TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS event_resolutions(
  event_id TEXT PRIMARY KEY REFERENCES events(id),
  resolution_json TEXT NOT NULL CHECK(json_valid(resolution_json)),
  mechanical INTEGER NOT NULL CHECK(mechanical IN (0,1)),
  judgment_json TEXT NOT NULL CHECK(json_valid(judgment_json))
);
CREATE TABLE IF NOT EXISTS observations(
  id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id),
  event_id TEXT NOT NULL REFERENCES events(id), observer_id TEXT NOT NULL,
  subject_id TEXT NOT NULL, assertion TEXT NOT NULL, certainty TEXT NOT NULL,
  visibility TEXT NOT NULL, audience_json TEXT NOT NULL CHECK(json_valid(audience_json))
);
CREATE TABLE IF NOT EXISTS entity_profiles(
  branch TEXT NOT NULL REFERENCES branches(id), entity_id TEXT NOT NULL,
  identity_label TEXT, nature TEXT NOT NULL, composition_json TEXT NOT NULL,
  agency_mode TEXT NOT NULL, control_mode TEXT NOT NULL, classification_json TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'gm', audience_json TEXT NOT NULL,
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,entity_id)
);
CREATE TABLE IF NOT EXISTS entity_links(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, whole_id TEXT NOT NULL, part_id TEXT NOT NULL,
  relation TEXT NOT NULL, valid_from_event TEXT REFERENCES events(id), valid_until_event TEXT,
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
);
CREATE TABLE IF NOT EXISTS classification_claims(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, subject_id TEXT NOT NULL, claimant_id TEXT NOT NULL,
  classification TEXT NOT NULL, mechanism TEXT, force TEXT NOT NULL, status TEXT NOT NULL,
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
);
CREATE INDEX IF NOT EXISTS processes_due ON processes(branch,state,next_tick);
CREATE INDEX IF NOT EXISTS property_values_entity ON property_values(branch,entity_id);
CREATE INDEX IF NOT EXISTS event_aux_lookup ON event_aux_changes(kind,state_key);
INSERT OR IGNORE INTO engine_versions(component,version) VALUES
 ('runtime_schema','3'),('property_registry','1'),('resolution_rules','1'),('story_state','1'),('workflow_api','2');
COMMIT;
