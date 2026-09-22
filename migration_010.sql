-- Method interface 1: immutable definitions, scoped assignments and request history.
CREATE TABLE method_revisions(
 method_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 branch TEXT NOT NULL REFERENCES branches(id),
 workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id),
 world_revision INTEGER NOT NULL CHECK(world_revision>=0),
 definition_json TEXT NOT NULL CHECK(json_valid(definition_json)),
 source_refs_json TEXT NOT NULL CHECK(json_valid(source_refs_json)),
 snapshots_json TEXT NOT NULL CHECK(json_valid(snapshots_json)),
 source_digest TEXT NOT NULL, prior_digest TEXT, digest TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE,
 PRIMARY KEY(method_id,revision),
 FOREIGN KEY(node_id,workspace_id) REFERENCES node_bindings(node_id,workspace_id)
);
CREATE TABLE node_method_assignments(
 node_id TEXT NOT NULL, method_id TEXT NOT NULL, method_revision INTEGER NOT NULL,
 branch TEXT NOT NULL REFERENCES branches(id), workspace_id TEXT NOT NULL,
 assignment_revision INTEGER NOT NULL CHECK(assignment_revision>0),
 qualification TEXT NOT NULL CHECK(qualification IN ('proposed','experimental','revoked')),
 rationale TEXT NOT NULL, world_revision INTEGER NOT NULL CHECK(world_revision>=0),
 method_digest TEXT NOT NULL, prior_digest TEXT, digest TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE,
 PRIMARY KEY(node_id,method_id,workspace_id,assignment_revision),
 FOREIGN KEY(method_id,method_revision) REFERENCES method_revisions(method_id,revision),
 FOREIGN KEY(node_id,workspace_id) REFERENCES node_bindings(node_id,workspace_id)
);
CREATE TABLE method_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL CHECK(kind IN ('created','revised','assigned')),
 method_id TEXT NOT NULL, node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 branch TEXT NOT NULL REFERENCES branches(id), workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id),
 payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX method_scope ON method_revisions(branch,workspace_id,node_id,method_id,revision);
CREATE INDEX method_assignment_scope ON node_method_assignments(branch,workspace_id,node_id,method_id,assignment_revision);
CREATE TRIGGER method_revisions_no_update BEFORE UPDATE ON method_revisions BEGIN SELECT RAISE(ABORT,'method revisions are immutable'); END;
CREATE TRIGGER method_revisions_no_delete BEFORE DELETE ON method_revisions BEGIN SELECT RAISE(ABORT,'method revisions are immutable'); END;
CREATE TRIGGER method_assignments_no_update BEFORE UPDATE ON node_method_assignments BEGIN SELECT RAISE(ABORT,'method assignments are immutable'); END;
CREATE TRIGGER method_assignments_no_delete BEFORE DELETE ON node_method_assignments BEGIN SELECT RAISE(ABORT,'method assignments are immutable'); END;
CREATE TRIGGER method_events_no_update BEFORE UPDATE ON method_events BEGIN SELECT RAISE(ABORT,'method events are immutable'); END;
CREATE TRIGGER method_events_no_delete BEFORE DELETE ON method_events BEGIN SELECT RAISE(ABORT,'method events are immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('method_interface','1','4');
