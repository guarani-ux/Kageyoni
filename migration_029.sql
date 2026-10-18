-- Operational delivery of native process/event work. Engine events, processes,
-- process subscriptions and runs remain the authoritative fictional history.
CREATE TABLE causal_roots (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 root_id TEXT NOT NULL,
 source_event TEXT NOT NULL REFERENCES events(id),
 source_record TEXT NOT NULL,
 source_digest TEXT NOT NULL CHECK(length(source_digest)=64),
 PRIMARY KEY(workspace_id,root_id)
);
CREATE TABLE causal_deliveries (
 workspace_id TEXT NOT NULL,
 root_id TEXT NOT NULL,
 source_event TEXT NOT NULL REFERENCES events(id),
 process_id TEXT NOT NULL,
 process_version INTEGER NOT NULL CHECK(process_version>=1),
 parent_id TEXT,
 depth INTEGER NOT NULL CHECK(depth>=0),
 state TEXT NOT NULL CHECK(state IN ('queued','delivered','blocked','parked')),
 reason TEXT NOT NULL,
 result_event TEXT REFERENCES events(id),
 trace_ref_json TEXT CHECK(trace_ref_json IS NULL OR json_valid(trace_ref_json)),
 PRIMARY KEY(workspace_id,process_id,process_version,source_event),
 FOREIGN KEY(workspace_id,root_id) REFERENCES causal_roots(workspace_id,root_id)
);
CREATE INDEX causal_ready ON causal_deliveries(workspace_id,state,root_id,depth);
CREATE TABLE causal_read_grants (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 scope_json TEXT NOT NULL CHECK(json_valid(scope_json)),
 PRIMARY KEY(workspace_id,artifact_id)
);
INSERT INTO engine_versions(component,version) VALUES('causal_delivery_interface','1');
