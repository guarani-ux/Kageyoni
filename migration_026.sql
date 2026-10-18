-- Opt-in durable application activities. Domain events remain Engine-owned.
CREATE TABLE activity_runs (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 activity_id TEXT NOT NULL,
 branch TEXT NOT NULL REFERENCES branches(id),
 parent_id TEXT,
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
 spec_digest TEXT NOT NULL CHECK(length(spec_digest)=64),
 version INTEGER NOT NULL CHECK(version>=1),
 state TEXT NOT NULL CHECK(state IN ('ready','preparing','running','waiting','committing','reconciling','paused','finished','failed','cancelled')),
 outcome TEXT NOT NULL CHECK(outcome IN ('achieved','partial','not_achieved','unresolved','not_applicable')),
 checkpoint_json TEXT NOT NULL CHECK(json_valid(checkpoint_json)),
 native_json TEXT NOT NULL CHECK(json_valid(native_json)),
 PRIMARY KEY(workspace_id,activity_id),
 FOREIGN KEY(workspace_id,parent_id) REFERENCES activity_runs(workspace_id,activity_id)
);
CREATE INDEX activity_runs_ready ON activity_runs(workspace_id,state,activity_id);
CREATE INDEX activity_runs_parent ON activity_runs(workspace_id,parent_id);
CREATE TABLE activity_jobs (
 job_id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL,
 activity_id TEXT NOT NULL,
 generation INTEGER NOT NULL CHECK(generation>=1),
 version INTEGER NOT NULL CHECK(version>=1),
 state TEXT NOT NULL,
 actor_id TEXT NOT NULL,
 prepared_json TEXT NOT NULL CHECK(json_valid(prepared_json)),
 prepared_digest TEXT NOT NULL CHECK(length(prepared_digest)=64),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 returned_by TEXT CHECK(returned_by IS NULL OR returned_by IN ('operator','player','worker')),
 FOREIGN KEY(workspace_id,activity_id) REFERENCES activity_runs(workspace_id,activity_id)
);
CREATE INDEX activity_jobs_pending ON activity_jobs(workspace_id,activity_id,state);
CREATE TABLE activity_bindings (
 binding_id TEXT PRIMARY KEY,
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 principal_id TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('operator','player','worker')),
 character_id TEXT,
 authority_epoch INTEGER NOT NULL CHECK(authority_epoch>=0),
 active INTEGER NOT NULL CHECK(active IN (0,1)),
 grants_json TEXT NOT NULL CHECK(json_valid(grants_json)),
 activity_id TEXT
);
CREATE TABLE activity_messages (
 workspace_id TEXT NOT NULL,
 principal_id TEXT NOT NULL,
 request_id TEXT NOT NULL,
 binding_id TEXT NOT NULL REFERENCES activity_bindings(binding_id),
 request_digest TEXT NOT NULL CHECK(length(request_digest)=64),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(workspace_id,principal_id,request_id)
);
CREATE TRIGGER activity_messages_no_update BEFORE UPDATE ON activity_messages
BEGIN SELECT RAISE(ABORT,'activity receipts are immutable'); END;
CREATE TRIGGER activity_messages_no_delete BEFORE DELETE ON activity_messages
BEGIN SELECT RAISE(ABORT,'activity receipts are immutable'); END;
CREATE TABLE activity_artifact_grants (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 principal_id TEXT NOT NULL,
 artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
 digest TEXT NOT NULL CHECK(length(digest)=64),
 activity_id TEXT,
 PRIMARY KEY(workspace_id,principal_id,artifact_id)
);
CREATE TABLE activity_staging (
 staging_ref TEXT PRIMARY KEY,
 binding_id TEXT NOT NULL REFERENCES activity_bindings(binding_id),
 job_id TEXT NOT NULL REFERENCES activity_jobs(job_id),
 generation INTEGER NOT NULL,
 digest TEXT NOT NULL CHECK(length(digest)=64),
 size INTEGER NOT NULL CHECK(size>=0 AND size<=10000000),
 media_type TEXT NOT NULL,
 content BLOB NOT NULL,
 consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1))
);
CREATE TABLE activity_outbox (
 workspace_id TEXT NOT NULL,
 parent_id TEXT NOT NULL,
 child_id TEXT NOT NULL,
 child_version INTEGER NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 status TEXT NOT NULL CHECK(status IN ('pending','delivered')),
 PRIMARY KEY(workspace_id,parent_id,child_id,child_version),
 FOREIGN KEY(workspace_id,parent_id) REFERENCES activity_runs(workspace_id,activity_id),
 FOREIGN KEY(workspace_id,child_id) REFERENCES activity_runs(workspace_id,activity_id)
);
INSERT INTO engine_versions(component,version) VALUES('activity_interface','1');
