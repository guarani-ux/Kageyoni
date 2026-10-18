-- Opt-in property selection/change lifecycles. Base definitions/values, native
-- rules, resources and history remain in their existing engine tables.
CREATE TABLE property_selections (
 snapshot_id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 principal_id TEXT NOT NULL,
 authority_epoch INTEGER NOT NULL,
 branch TEXT NOT NULL REFERENCES branches(id),
 revision INTEGER NOT NULL,
 expires REAL NOT NULL,
 frozen_json TEXT NOT NULL CHECK(json_valid(frozen_json)),
 frozen_digest TEXT NOT NULL CHECK(length(frozen_digest)=64)
);
CREATE TABLE property_selection_cursors (
 cursor_id TEXT PRIMARY KEY,
 snapshot_id TEXT NOT NULL REFERENCES property_selections(snapshot_id),
 offset INTEGER NOT NULL CHECK(offset>=0)
);
CREATE TABLE property_change_sets (
 change_id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 snapshot_id TEXT NOT NULL REFERENCES property_selections(snapshot_id),
 principal_id TEXT NOT NULL,
 authority_epoch INTEGER NOT NULL,
 proposal_json TEXT NOT NULL CHECK(json_valid(proposal_json)),
 proposal_digest TEXT NOT NULL CHECK(length(proposal_digest)=64),
 status TEXT NOT NULL CHECK(status IN ('prepared','active','withdrawn','waiting')),
 diff_ref_json TEXT NOT NULL CHECK(json_valid(diff_ref_json)),
 applied_event TEXT REFERENCES events(id),
 ended_event TEXT REFERENCES events(id)
);
CREATE TABLE property_effects (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 effect_id TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>=1),
 entity_id TEXT NOT NULL,
 change_id TEXT NOT NULL REFERENCES property_change_sets(change_id),
 property_id TEXT NOT NULL,
 definition_version INTEGER NOT NULL,
 override_json TEXT NOT NULL CHECK(json_valid(override_json)),
 override_digest TEXT NOT NULL CHECK(length(override_digest)=64),
 state TEXT NOT NULL CHECK(state IN ('active','ended')),
 ended_event TEXT REFERENCES events(id),
 PRIMARY KEY(workspace_id,effect_id,version,entity_id),
 FOREIGN KEY(property_id,definition_version) REFERENCES property_definitions(property_id,definition_version)
);
CREATE INDEX property_effects_resolve ON property_effects(workspace_id,entity_id,property_id,definition_version,state);
CREATE TABLE property_support_bindings (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 support_id TEXT NOT NULL,
 branch TEXT NOT NULL,
 entity_id TEXT NOT NULL,
 resource_id TEXT NOT NULL,
 dependency_json TEXT NOT NULL CHECK(json_valid(dependency_json)),
 trace_ref_json TEXT NOT NULL CHECK(json_valid(trace_ref_json)),
 active INTEGER NOT NULL CHECK(active IN (0,1)),
 PRIMARY KEY(workspace_id,support_id),
 FOREIGN KEY(branch,resource_id) REFERENCES records(branch,id)
);
CREATE TABLE property_read_grants (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 principal_id TEXT NOT NULL,
 authority_epoch INTEGER NOT NULL,
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 scope_json TEXT NOT NULL CHECK(json_valid(scope_json)),
 PRIMARY KEY(workspace_id,principal_id,artifact_id)
);
INSERT INTO engine_versions(component,version) VALUES('property_change_interface','1');
