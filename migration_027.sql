-- Opt-in fenced local work queue. World history and issued jobs are untouched.
CREATE TABLE activity_queue_owners (
 workspace_id TEXT PRIMARY KEY REFERENCES operational_workspaces(workspace_id),
 epoch INTEGER NOT NULL CHECK(epoch>=1),
 last_wall REAL NOT NULL
);
CREATE TABLE activity_queue_roots (
 workspace_id TEXT NOT NULL,
 root_id TEXT NOT NULL,
 starts INTEGER NOT NULL DEFAULT 0 CHECK(starts>=0 AND starts<=4),
 reserved_seconds REAL NOT NULL DEFAULT 0 CHECK(reserved_seconds>=0 AND reserved_seconds<=900),
 last_dispatch INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(workspace_id,root_id),
 FOREIGN KEY(workspace_id,root_id) REFERENCES activity_runs(workspace_id,activity_id)
);
CREATE TABLE activity_queue (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id TEXT NOT NULL UNIQUE REFERENCES activity_jobs(job_id),
 workspace_id TEXT NOT NULL,
 root_id TEXT NOT NULL,
 binding_id TEXT NOT NULL REFERENCES activity_bindings(binding_id),
 authority_epoch INTEGER NOT NULL,
 recipe TEXT NOT NULL,
 parameters_json TEXT NOT NULL CHECK(json_valid(parameters_json)),
 state TEXT NOT NULL CHECK(state IN ('queued','running','paused','reconciling','returned','cancelled','failed')),
 reason TEXT NOT NULL DEFAULT '',
 generation INTEGER NOT NULL DEFAULT 0,
 owner_epoch INTEGER,
 lease_token TEXT,
 lease_until REAL,
 max_seconds REAL NOT NULL CHECK(max_seconds>0 AND max_seconds<=120),
 process_json TEXT CHECK(process_json IS NULL OR json_valid(process_json)),
 output_ref_json TEXT CHECK(output_ref_json IS NULL OR json_valid(output_ref_json)),
 FOREIGN KEY(workspace_id,root_id) REFERENCES activity_queue_roots(workspace_id,root_id)
);
CREATE INDEX activity_queue_ready ON activity_queue(workspace_id,state,sequence);
CREATE INDEX activity_queue_parent ON activity_queue(workspace_id,root_id,state);
INSERT INTO engine_versions(component,version) VALUES('activity_queue_interface','1');
