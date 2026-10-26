-- Persistent node interface 1; predecessor 008; runtime schema remains 4.
CREATE TABLE network_nodes(
 node_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('character','engine')),
 identity_revision INTEGER NOT NULL CHECK(identity_revision>0), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE network_workspaces(
 workspace_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='world'),
 branch TEXT NOT NULL UNIQUE REFERENCES branches(id), adapter_version TEXT NOT NULL
);
CREATE TABLE node_bindings(
 node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id),
 branch TEXT NOT NULL REFERENCES branches(id), character_id TEXT NOT NULL,
 profile_revision INTEGER NOT NULL CHECK(profile_revision>0), source_json TEXT NOT NULL,
 PRIMARY KEY(node_id,workspace_id), UNIQUE(branch,character_id),
 FOREIGN KEY(branch,character_id) REFERENCES character(branch,id)
);
CREATE TABLE network_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE,
 payload_hash TEXT NOT NULL, node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 branch TEXT NOT NULL REFERENCES branches(id), kind TEXT NOT NULL,
 profile_revision INTEGER NOT NULL, payload_json TEXT NOT NULL, receipt_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('node_interface','1','4');
