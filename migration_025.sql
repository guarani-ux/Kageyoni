-- Opt-in issued encounter requests and exact execution continuation.
CREATE TABLE shinobi_action_requests (
 branch TEXT NOT NULL REFERENCES branches(id),
 request_id TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 reply_digest TEXT,
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 PRIMARY KEY(branch,request_id)
);
CREATE TRIGGER shinobi_action_requests_fixed BEFORE UPDATE OF branch,request_id,request_hash,request_json ON shinobi_action_requests
BEGIN SELECT RAISE(ABORT,'issued action requests are immutable'); END;
CREATE TRIGGER shinobi_action_requests_terminal BEFORE UPDATE ON shinobi_action_requests WHEN OLD.result_json IS NOT NULL
BEGIN SELECT RAISE(ABORT,'completed action requests are immutable'); END;
CREATE TRIGGER shinobi_action_requests_no_delete BEFORE DELETE ON shinobi_action_requests
BEGIN SELECT RAISE(ABORT,'action request history is immutable'); END;
INSERT INTO engine_versions(component,version) VALUES('action_dispatch_interface','1');
