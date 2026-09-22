-- Decision interface 1, predecessor 005. Engine owns transaction/checksum.
CREATE TABLE decision_proposals (
 branch TEXT NOT NULL REFERENCES branches(id),
 id TEXT NOT NULL,
 spec_hash TEXT NOT NULL,
 state_hash TEXT NOT NULL,
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json)),
 compiled_json TEXT NOT NULL CHECK(json_valid(compiled_json)),
 roll INTEGER,
 PRIMARY KEY(branch,id)
);
INSERT INTO engine_versions(component,version) VALUES('decision_interface','1');
