-- Bounded collective coordination, immutable runs and reviewed observations.
CREATE TABLE coordination_nodes(node_id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind='engine'), roles_json TEXT NOT NULL);
INSERT INTO coordination_nodes VALUES('engine:kageyoni','engine','["receive","challenge","synthesize","observe"]');
CREATE TRIGGER coordination_nodes_no_update BEFORE UPDATE ON coordination_nodes BEGIN SELECT RAISE(ABORT,'coordination identity immutable'); END;
CREATE TRIGGER coordination_nodes_no_delete BEFORE DELETE ON coordination_nodes BEGIN SELECT RAISE(ABORT,'coordination identity immutable'); END;
CREATE TABLE collective_runs(
 run_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
 branch TEXT NOT NULL REFERENCES branches(id), viewer TEXT,
 request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
 result_json TEXT NOT NULL, result_hash TEXT NOT NULL
);
CREATE TABLE coordination_lessons(
 lesson_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
 branch TEXT NOT NULL REFERENCES branches(id),
 payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL,
 result_json TEXT NOT NULL, result_hash TEXT NOT NULL
);
CREATE TRIGGER collective_runs_no_update BEFORE UPDATE ON collective_runs BEGIN SELECT RAISE(ABORT,'collective runs immutable'); END;
CREATE TRIGGER collective_runs_no_delete BEFORE DELETE ON collective_runs BEGIN SELECT RAISE(ABORT,'collective runs immutable'); END;
CREATE TRIGGER coordination_lessons_no_update BEFORE UPDATE ON coordination_lessons BEGIN SELECT RAISE(ABORT,'coordination lessons immutable'); END;
CREATE TRIGGER coordination_lessons_no_delete BEFORE DELETE ON coordination_lessons BEGIN SELECT RAISE(ABORT,'coordination lessons immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('network_interface','1','4');
CREATE TABLE collective_compositions(
 composition_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
 branch TEXT NOT NULL REFERENCES branches(id), viewer TEXT,
 request_json TEXT NOT NULL, request_hash TEXT NOT NULL,
 result_json TEXT NOT NULL, result_hash TEXT NOT NULL
);
CREATE TRIGGER collective_compositions_no_update BEFORE UPDATE ON collective_compositions BEGIN SELECT RAISE(ABORT,'compositions immutable'); END;
CREATE TRIGGER collective_compositions_no_delete BEFORE DELETE ON collective_compositions BEGIN SELECT RAISE(ABORT,'compositions immutable'); END;
