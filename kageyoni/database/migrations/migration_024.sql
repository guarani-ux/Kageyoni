-- Kageyoni-Shinobi participant protocol storage. Predecessor 023.
-- Identity remains a Kageyoni character + node binding; these tables hold the
-- split-phase host protocol (request/reply), saved cognitive configuration,
-- and human-adjudicated Returns. Installed only by install_shinobi().
CREATE TABLE shinobi_identity(
 slot TEXT PRIMARY KEY CHECK(slot='self'),
 participant_id TEXT NOT NULL UNIQUE,
 branch TEXT NOT NULL REFERENCES branches(id),
 character_id TEXT NOT NULL,
 name TEXT NOT NULL,
 configuration_json TEXT NOT NULL CHECK(json_valid(configuration_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(branch,character_id) REFERENCES character(branch,id)
);
CREATE TABLE shinobi_encounters(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 encounter_id TEXT NOT NULL UNIQUE,
 topic TEXT NOT NULL,
 request_json TEXT NOT NULL CHECK(json_valid(request_json)),
 request_hash TEXT NOT NULL,
 response_json TEXT CHECK(response_json IS NULL OR json_valid(response_json)),
 status TEXT NOT NULL CHECK(status IN ('awaiting_host','executing','completed','failed','interrupted')),
 outcome_json TEXT CHECK(outcome_json IS NULL OR json_valid(outcome_json)),
 dialogue_event_id TEXT,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX shinobi_encounters_topic ON shinobi_encounters(topic,status);
CREATE TABLE shinobi_returns(
 sequence INTEGER PRIMARY KEY AUTOINCREMENT,
 return_id TEXT NOT NULL UNIQUE,
 candidate_delta_json TEXT NOT NULL CHECK(json_valid(candidate_delta_json)),
 provenance TEXT NOT NULL CHECK(length(trim(provenance))>0),
 supporting_encounter_refs_json TEXT NOT NULL CHECK(json_valid(supporting_encounter_refs_json)),
 demonstrated_scope TEXT NOT NULL CHECK(length(trim(demonstrated_scope))>0),
 reversal_conditions TEXT NOT NULL CHECK(length(trim(reversal_conditions))>0),
 proposed_target_json TEXT NOT NULL CHECK(json_valid(proposed_target_json)),
 lesson_id TEXT,
 lesson_revision INTEGER,
 status TEXT NOT NULL CHECK(status IN ('CANDIDATE','ACCEPTED','REJECTED','RESIDUE')),
 adjudication_json TEXT CHECK(adjudication_json IS NULL OR json_valid(adjudication_json)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TRIGGER shinobi_encounters_no_delete BEFORE DELETE ON shinobi_encounters BEGIN SELECT RAISE(ABORT,'shinobi encounter history is immutable'); END;
CREATE TRIGGER shinobi_encounters_request_fixed BEFORE UPDATE OF encounter_id,topic,request_json,request_hash ON shinobi_encounters BEGIN SELECT RAISE(ABORT,'shinobi encounter requests are immutable'); END;
CREATE TRIGGER shinobi_encounters_terminal BEFORE UPDATE ON shinobi_encounters WHEN OLD.status IN ('completed','failed','interrupted') BEGIN SELECT RAISE(ABORT,'terminal shinobi encounters are immutable'); END;
CREATE TRIGGER shinobi_returns_no_delete BEFORE DELETE ON shinobi_returns BEGIN SELECT RAISE(ABORT,'shinobi returns are immutable'); END;
CREATE TRIGGER shinobi_returns_adjudicated BEFORE UPDATE ON shinobi_returns WHEN OLD.status<>'CANDIDATE' BEGIN SELECT RAISE(ABORT,'adjudicated shinobi returns are immutable'); END;
CREATE TRIGGER shinobi_identity_no_delete BEFORE DELETE ON shinobi_identity BEGIN SELECT RAISE(ABORT,'shinobi identity is immutable'); END;
CREATE TRIGGER shinobi_identity_fixed BEFORE UPDATE OF participant_id,branch,character_id ON shinobi_identity BEGIN SELECT RAISE(ABORT,'shinobi identity binding is immutable'); END;
INSERT INTO engine_versions(component,version,compatible_engine) VALUES('shinobi_interface','1','4');
