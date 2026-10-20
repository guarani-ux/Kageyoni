-- Native membership projection from actual immutable activity specifications.
CREATE TABLE activity_participants (
 workspace_id TEXT NOT NULL,
 character_id TEXT NOT NULL CHECK(length(character_id)>0),
 activity_id TEXT NOT NULL,
 PRIMARY KEY(workspace_id,character_id,activity_id),
 FOREIGN KEY(workspace_id,activity_id) REFERENCES activity_runs(workspace_id,activity_id)
);
CREATE INDEX activity_participants_activity ON activity_participants(workspace_id,activity_id,character_id);
INSERT INTO activity_participants(workspace_id,character_id,activity_id)
 SELECT DISTINCT a.workspace_id,p.value,a.activity_id
 FROM activity_runs a,json_each(a.spec_json,'$.participants') p
 WHERE p.type='text';
INSERT INTO engine_versions(component,version) VALUES('resource_admission_interface','1');
