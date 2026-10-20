-- Opt-in actual owner-supplied worker liveness; no old attempt backfill.
CREATE TABLE activity_worker_liveness (
 job_id TEXT NOT NULL REFERENCES activity_queue(job_id),
 owner_epoch INTEGER NOT NULL CHECK(owner_epoch>=1),
 generation INTEGER NOT NULL CHECK(generation>=1),
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 lease_token TEXT NOT NULL,
 policy_json TEXT NOT NULL CHECK(json_valid(policy_json)),
 policy_digest TEXT NOT NULL CHECK(length(policy_digest)=64),
 claimed_at REAL NOT NULL,
 execution_until REAL NOT NULL,
 lease_until REAL NOT NULL,
 last_sequence INTEGER NOT NULL DEFAULT 0 CHECK(last_sequence>=0),
 last_heartbeat REAL,
 process_json TEXT CHECK(process_json IS NULL OR json_valid(process_json)),
 stop_requested_at REAL,
 stop_deadline REAL,
 stop_disposition TEXT,
 stop_request_id TEXT,
 exit_json TEXT CHECK(exit_json IS NULL OR json_valid(exit_json)),
 PRIMARY KEY(job_id,owner_epoch,generation)
);
CREATE TRIGGER worker_liveness_identity_immutable BEFORE UPDATE OF job_id,owner_epoch,generation,workspace_id,lease_token,policy_json,policy_digest,claimed_at,execution_until ON activity_worker_liveness
 BEGIN SELECT RAISE(ABORT,'worker liveness identity is immutable'); END;
CREATE TRIGGER worker_liveness_no_delete BEFORE DELETE ON activity_worker_liveness
 BEGIN SELECT RAISE(ABORT,'worker liveness history is immutable'); END;
CREATE TABLE activity_worker_heartbeats (
 job_id TEXT NOT NULL, owner_epoch INTEGER NOT NULL, generation INTEGER NOT NULL,
 sequence INTEGER NOT NULL CHECK(sequence>0),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(job_id,owner_epoch,generation,sequence),
 FOREIGN KEY(job_id,owner_epoch,generation) REFERENCES activity_worker_liveness(job_id,owner_epoch,generation)
);
CREATE TABLE activity_worker_stops (
 ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
 job_id TEXT NOT NULL, owner_epoch INTEGER NOT NULL, generation INTEGER NOT NULL,
 request_id TEXT NOT NULL, disposition TEXT NOT NULL,
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 UNIQUE(job_id,owner_epoch,generation,request_id),
 FOREIGN KEY(job_id,owner_epoch,generation) REFERENCES activity_worker_liveness(job_id,owner_epoch,generation)
);
CREATE TABLE activity_worker_exits (
 job_id TEXT NOT NULL, owner_epoch INTEGER NOT NULL, generation INTEGER NOT NULL,
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(job_id,owner_epoch,generation),
 FOREIGN KEY(job_id,owner_epoch,generation) REFERENCES activity_worker_liveness(job_id,owner_epoch,generation)
);
CREATE TRIGGER worker_heartbeats_no_update BEFORE UPDATE ON activity_worker_heartbeats BEGIN SELECT RAISE(ABORT,'heartbeat receipts immutable'); END;
CREATE TRIGGER worker_heartbeats_no_delete BEFORE DELETE ON activity_worker_heartbeats BEGIN SELECT RAISE(ABORT,'heartbeat receipts immutable'); END;
CREATE TRIGGER worker_stops_no_update BEFORE UPDATE ON activity_worker_stops BEGIN SELECT RAISE(ABORT,'stop receipts immutable'); END;
CREATE TRIGGER worker_stops_no_delete BEFORE DELETE ON activity_worker_stops BEGIN SELECT RAISE(ABORT,'stop receipts immutable'); END;
CREATE TRIGGER worker_exits_no_update BEFORE UPDATE ON activity_worker_exits BEGIN SELECT RAISE(ABORT,'exit receipts immutable'); END;
CREATE TRIGGER worker_exits_no_delete BEFORE DELETE ON activity_worker_exits BEGIN SELECT RAISE(ABORT,'exit receipts immutable'); END;
CREATE INDEX worker_liveness_workspace ON activity_worker_liveness(workspace_id,job_id,owner_epoch,generation);
INSERT INTO engine_versions(component,version) VALUES('worker_liveness_interface','1');
