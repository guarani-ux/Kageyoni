-- Durable local repository candidates and DAG execution.
CREATE TABLE repository_candidates(candidate_id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id), request_id TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL);
CREATE TABLE pipeline_runs(pipeline_id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id), request_id TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL, payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL);
CREATE TABLE pipeline_events(event_id INTEGER PRIMARY KEY AUTOINCREMENT, pipeline_id TEXT NOT NULL REFERENCES pipeline_runs(pipeline_id), payload_json TEXT NOT NULL, payload_hash TEXT NOT NULL);
CREATE TRIGGER pipeline_events_no_update BEFORE UPDATE ON pipeline_events BEGIN SELECT RAISE(ABORT,'pipeline events immutable'); END;
CREATE TRIGGER pipeline_events_no_delete BEFORE DELETE ON pipeline_events BEGIN SELECT RAISE(ABORT,'pipeline events immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('pipeline_interface','1','4');
