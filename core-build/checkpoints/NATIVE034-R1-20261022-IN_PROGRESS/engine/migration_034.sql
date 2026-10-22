-- Explicit companion custody history, owner-supplied facts; ZERO old-row backfill.
CREATE TABLE activity_worker_registrations (
 job_id TEXT NOT NULL,
 owner_epoch INTEGER NOT NULL CHECK(owner_epoch>=1),
 generation INTEGER NOT NULL CHECK(generation>=1),
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 lease_token TEXT NOT NULL,
 registration_json TEXT NOT NULL CHECK(json_valid(registration_json)),
 registration_digest TEXT NOT NULL CHECK(length(registration_digest)=64),
 registered_at REAL NOT NULL,
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(job_id,owner_epoch,generation),
 UNIQUE(job_id,owner_epoch,generation,workspace_id,lease_token),
 FOREIGN KEY(job_id,owner_epoch,generation) REFERENCES activity_worker_liveness(job_id,owner_epoch,generation)
);
CREATE TABLE activity_worker_absences (
 job_id TEXT NOT NULL,
 owner_epoch INTEGER NOT NULL CHECK(owner_epoch>=1),
 generation INTEGER NOT NULL CHECK(generation>=1),
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 lease_token TEXT NOT NULL,
 observation_json TEXT NOT NULL CHECK(json_valid(observation_json)),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(job_id,owner_epoch,generation),
 FOREIGN KEY(job_id,owner_epoch,generation) REFERENCES activity_worker_liveness(job_id,owner_epoch,generation),
 FOREIGN KEY(job_id,owner_epoch,generation,workspace_id,lease_token) REFERENCES activity_worker_registrations(job_id,owner_epoch,generation,workspace_id,lease_token)
);
CREATE TRIGGER worker_registrations_no_update BEFORE UPDATE ON activity_worker_registrations
 BEGIN SELECT RAISE(ABORT,'worker registration history immutable'); END;
CREATE TRIGGER worker_registrations_no_delete BEFORE DELETE ON activity_worker_registrations
 BEGIN SELECT RAISE(ABORT,'worker registration history immutable'); END;
CREATE TRIGGER worker_absences_no_update BEFORE UPDATE ON activity_worker_absences
 BEGIN SELECT RAISE(ABORT,'worker absence history immutable'); END;
CREATE TRIGGER worker_absences_no_delete BEFORE DELETE ON activity_worker_absences
 BEGIN SELECT RAISE(ABORT,'worker absence history immutable'); END;
CREATE TRIGGER worker_absence_excludes_exit BEFORE INSERT ON activity_worker_absences
 WHEN EXISTS(SELECT 1 FROM activity_worker_exits WHERE job_id=NEW.job_id AND owner_epoch=NEW.owner_epoch AND generation=NEW.generation)
 OR EXISTS(SELECT 1 FROM activity_worker_liveness WHERE job_id=NEW.job_id AND owner_epoch=NEW.owner_epoch AND generation=NEW.generation AND exit_json IS NOT NULL)
 BEGIN SELECT RAISE(ABORT,'known exit and identity absence are distinct terminal facts'); END;
CREATE TRIGGER worker_exit_excludes_absence BEFORE INSERT ON activity_worker_exits
 WHEN EXISTS(SELECT 1 FROM activity_worker_absences WHERE job_id=NEW.job_id AND owner_epoch=NEW.owner_epoch AND generation=NEW.generation)
 BEGIN SELECT RAISE(ABORT,'identity absence and known exit are distinct terminal facts'); END;
CREATE INDEX worker_registration_workspace ON activity_worker_registrations(workspace_id,job_id,owner_epoch,generation);
CREATE INDEX worker_absence_workspace ON activity_worker_absences(workspace_id,job_id,owner_epoch,generation);
INSERT INTO engine_versions(component,version) VALUES('worker_custody_interface','1');
