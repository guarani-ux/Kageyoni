-- V4 provisional genesis and authored encounters. Predecessor 012.
CREATE TABLE genesis_profiles(
 branch TEXT NOT NULL REFERENCES branches(id), character_id TEXT NOT NULL,
 node_id TEXT NOT NULL REFERENCES network_nodes(node_id), request_id TEXT NOT NULL UNIQUE,
 profile_json TEXT NOT NULL CHECK(json_valid(profile_json)), payload_hash TEXT NOT NULL,
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 PRIMARY KEY(branch,character_id), FOREIGN KEY(branch,character_id) REFERENCES character(branch,id)
);
CREATE TABLE encounter_definitions(
 definition_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version>0),
 spec_json TEXT NOT NULL CHECK(json_valid(spec_json)), digest TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE, PRIMARY KEY(definition_id,version)
);
CREATE TABLE encounter_instances(
 branch TEXT NOT NULL REFERENCES branches(id), encounter_id TEXT NOT NULL,
 definition_id TEXT NOT NULL, definition_version INTEGER NOT NULL,
 participants_json TEXT NOT NULL CHECK(json_valid(participants_json)),
 revision INTEGER NOT NULL, state_json TEXT NOT NULL CHECK(json_valid(state_json)),
 PRIMARY KEY(branch,encounter_id),
 FOREIGN KEY(definition_id,definition_version) REFERENCES encounter_definitions(definition_id,version)
);
CREATE TABLE encounter_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, branch TEXT NOT NULL, encounter_id TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE, revision INTEGER NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), payload_hash TEXT NOT NULL,
 before_json TEXT, after_json TEXT NOT NULL CHECK(json_valid(after_json)),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),
 FOREIGN KEY(branch,encounter_id) REFERENCES encounter_instances(branch,encounter_id),
 UNIQUE(branch,encounter_id,revision)
);
CREATE TRIGGER genesis_no_update BEFORE UPDATE ON genesis_profiles BEGIN SELECT RAISE(ABORT,'genesis profiles are immutable'); END;
CREATE TRIGGER genesis_no_delete BEFORE DELETE ON genesis_profiles BEGIN SELECT RAISE(ABORT,'genesis profiles are immutable'); END;
CREATE TRIGGER encounter_definitions_no_update BEFORE UPDATE ON encounter_definitions BEGIN SELECT RAISE(ABORT,'encounter definitions are immutable'); END;
CREATE TRIGGER encounter_definitions_no_delete BEFORE DELETE ON encounter_definitions BEGIN SELECT RAISE(ABORT,'encounter definitions are immutable'); END;
CREATE TRIGGER encounter_events_no_update BEFORE UPDATE ON encounter_events BEGIN SELECT RAISE(ABORT,'encounter history is immutable'); END;
CREATE TRIGGER encounter_events_no_delete BEFORE DELETE ON encounter_events BEGIN SELECT RAISE(ABORT,'encounter history is immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('encounter_interface','1','4');
