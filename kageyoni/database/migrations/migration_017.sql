-- Daily operation history is operational; it never advances story state.
CREATE TABLE operation_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL, scope TEXT NOT NULL, payload_json TEXT NOT NULL CHECK(json_valid(payload_json)), digest TEXT NOT NULL);
CREATE TRIGGER operation_events_no_update BEFORE UPDATE ON operation_events BEGIN SELECT RAISE(ABORT,'immutable operation history'); END;
CREATE TRIGGER operation_events_no_delete BEFORE DELETE ON operation_events BEGIN SELECT RAISE(ABORT,'immutable operation history'); END;
INSERT INTO engine_versions(component,version) VALUES('operations_interface','1');
