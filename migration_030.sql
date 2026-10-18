-- Explicit installed-content lifecycle, in the authoritative engine database.
CREATE TABLE extension_assets (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 asset_id TEXT NOT NULL,
 digest TEXT NOT NULL CHECK(length(digest)=64),
 content_json TEXT NOT NULL CHECK(json_valid(content_json)),
 available INTEGER NOT NULL CHECK(available IN (0,1)),
 PRIMARY KEY(workspace_id,asset_id,digest)
);
CREATE TABLE extension_versions (
 workspace_id TEXT NOT NULL REFERENCES operational_workspaces(workspace_id),
 extension_id TEXT NOT NULL,
 version INTEGER NOT NULL CHECK(version>=1),
 state TEXT NOT NULL CHECK(state IN ('prepared','active','disabled','retired')),
 prepared_revision INTEGER NOT NULL,
 manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json)),
 manifest_digest TEXT NOT NULL CHECK(length(manifest_digest)=64),
 capsule_ref_json TEXT NOT NULL CHECK(json_valid(capsule_ref_json)),
 preview_ref_json TEXT NOT NULL CHECK(json_valid(preview_ref_json)),
 last_event TEXT REFERENCES events(id),
 ending_trace_ref_json TEXT CHECK(ending_trace_ref_json IS NULL OR json_valid(ending_trace_ref_json)),
 PRIMARY KEY(workspace_id,extension_id,version)
);
CREATE UNIQUE INDEX extension_one_active ON extension_versions(workspace_id,extension_id) WHERE state='active';
CREATE TABLE extension_pins (
 workspace_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('change','support')),
 reference_id TEXT NOT NULL,
 extension_id TEXT NOT NULL,
 version INTEGER NOT NULL,
 PRIMARY KEY(workspace_id,kind,reference_id),
 FOREIGN KEY(workspace_id,extension_id,version) REFERENCES extension_versions(workspace_id,extension_id,version)
);
INSERT INTO engine_versions(component,version) VALUES('extension_lifecycle_interface','1');
