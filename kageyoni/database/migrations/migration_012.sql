-- V3 outcomes, bounded lesson revisions and attributed qualification.
CREATE TABLE learning_outcomes(
 outcome_id TEXT PRIMARY KEY, contribution_id TEXT NOT NULL REFERENCES contributions(contribution_id),
 branch TEXT NOT NULL REFERENCES branches(id), node_id TEXT NOT NULL REFERENCES network_nodes(node_id),
 workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id), world_revision INTEGER NOT NULL,
 contribution_digest TEXT NOT NULL, observation_json TEXT NOT NULL CHECK(json_valid(observation_json)),
 source_refs_json TEXT NOT NULL CHECK(json_valid(source_refs_json)), snapshots_json TEXT NOT NULL CHECK(json_valid(snapshots_json)),
 origin_event_ids_json TEXT NOT NULL CHECK(json_valid(origin_event_ids_json)), digest TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE
);
CREATE TABLE lesson_revisions(
 lesson_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
 node_id TEXT NOT NULL REFERENCES network_nodes(node_id), branch TEXT NOT NULL REFERENCES branches(id),
 workspace_id TEXT NOT NULL REFERENCES network_workspaces(workspace_id), world_revision INTEGER NOT NULL,
 definition_json TEXT NOT NULL CHECK(json_valid(definition_json)), method_digest TEXT NOT NULL,
 outcome_ids_json TEXT NOT NULL CHECK(json_valid(outcome_ids_json)), counter_outcome_ids_json TEXT NOT NULL CHECK(json_valid(counter_outcome_ids_json)),
 evidence_digest TEXT NOT NULL, prior_digest TEXT, digest TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
 PRIMARY KEY(lesson_id,revision), FOREIGN KEY(node_id,workspace_id) REFERENCES node_bindings(node_id,workspace_id)
);
CREATE TABLE lesson_reviews(
 lesson_id TEXT NOT NULL, lesson_revision INTEGER NOT NULL, review_revision INTEGER NOT NULL CHECK(review_revision>0),
 status TEXT NOT NULL CHECK(status IN ('qualified','contested','retired')), rationale TEXT NOT NULL,
 world_revision INTEGER NOT NULL, lesson_digest TEXT NOT NULL,
 method_assignment_revision INTEGER NOT NULL, method_assignment_digest TEXT,
 counter_outcome_ids_json TEXT NOT NULL CHECK(json_valid(counter_outcome_ids_json)),
 evidence_digest TEXT NOT NULL, prior_digest TEXT, digest TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
 PRIMARY KEY(lesson_id,lesson_revision,review_revision),
 FOREIGN KEY(lesson_id,lesson_revision) REFERENCES lesson_revisions(lesson_id,revision)
);
CREATE TABLE learning_events(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL CHECK(kind IN ('outcome','proposed','revised','reviewed')),
 object_id TEXT NOT NULL, branch TEXT NOT NULL REFERENCES branches(id),
 payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL CHECK(json_valid(payload_json)),
 receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX learning_outcome_scope ON learning_outcomes(branch,node_id,workspace_id);
CREATE INDEX lesson_scope ON lesson_revisions(branch,node_id,workspace_id,lesson_id,revision);
CREATE TRIGGER learning_outcomes_no_update BEFORE UPDATE ON learning_outcomes BEGIN SELECT RAISE(ABORT,'outcomes are immutable'); END;
CREATE TRIGGER learning_outcomes_no_delete BEFORE DELETE ON learning_outcomes BEGIN SELECT RAISE(ABORT,'outcomes are immutable'); END;
CREATE TRIGGER lesson_revisions_no_update BEFORE UPDATE ON lesson_revisions BEGIN SELECT RAISE(ABORT,'lessons are immutable'); END;
CREATE TRIGGER lesson_revisions_no_delete BEFORE DELETE ON lesson_revisions BEGIN SELECT RAISE(ABORT,'lessons are immutable'); END;
CREATE TRIGGER lesson_reviews_no_update BEFORE UPDATE ON lesson_reviews BEGIN SELECT RAISE(ABORT,'reviews are immutable'); END;
CREATE TRIGGER lesson_reviews_no_delete BEFORE DELETE ON lesson_reviews BEGIN SELECT RAISE(ABORT,'reviews are immutable'); END;
CREATE TRIGGER learning_events_no_update BEFORE UPDATE ON learning_events BEGIN SELECT RAISE(ABORT,'learning events are immutable'); END;
CREATE TRIGGER learning_events_no_delete BEFORE DELETE ON learning_events BEGIN SELECT RAISE(ABORT,'learning events are immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('learning_interface','1','4');
