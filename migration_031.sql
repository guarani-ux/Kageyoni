-- Explicit opt-in operational capacity profiles. No fictional events or old SQL changes.
CREATE TABLE activity_resource_profile_receipts (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 request_id TEXT NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 payload_hash TEXT NOT NULL CHECK(length(payload_hash)=64),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 UNIQUE(workspace_id,request_id)
);
CREATE TRIGGER activity_resource_receipts_no_update
 BEFORE UPDATE ON activity_resource_profile_receipts
 BEGIN SELECT RAISE(ABORT,'resource profile receipts are immutable'); END;
CREATE TRIGGER activity_resource_receipts_no_delete
 BEFORE DELETE ON activity_resource_profile_receipts
 BEGIN SELECT RAISE(ABORT,'resource profile receipts are immutable'); END;
CREATE TABLE activity_resource_profiles (
 workspace_id TEXT PRIMARY KEY REFERENCES operational_workspaces(workspace_id),
 profile_json TEXT NOT NULL CHECK(json_valid(profile_json)),
 profile_digest TEXT NOT NULL CHECK(length(profile_digest)=64),
 selected_request_id TEXT NOT NULL,
 FOREIGN KEY(workspace_id,selected_request_id)
  REFERENCES activity_resource_profile_receipts(workspace_id,request_id)
);
ALTER TABLE activity_queue ADD COLUMN profile_digest TEXT NOT NULL
 DEFAULT '15d0de5ddb8735e040ee1e71ad18aedb04d452ebb52e2168876aba62ee19800c'
 CHECK(length(profile_digest)=64);
INSERT INTO engine_versions(component,version) VALUES('resource_profile_interface','1');
