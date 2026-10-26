-- V2 contribution receipts; predecessor 010. No fictional events.
CREATE TABLE contributions(
 contribution_id TEXT PRIMARY KEY,
 request_id TEXT NOT NULL UNIQUE,
 branch TEXT NOT NULL REFERENCES branches(id),
 node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id),
 viewer TEXT,
 request_json TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 result_json TEXT NOT NULL,
 result_hash TEXT NOT NULL,
 receipt_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER contributions_no_update BEFORE UPDATE ON contributions BEGIN
 SELECT RAISE(ABORT, 'contributions are immutable');
END;
CREATE TRIGGER contributions_no_delete BEFORE DELETE ON contributions BEGIN
 SELECT RAISE(ABORT, 'contributions are immutable');
END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('contribution_interface','1','4');
