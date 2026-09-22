PRAGMA foreign_keys=ON;
CREATE TABLE schema_version(version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES(2);
CREATE TABLE branches(id TEXT PRIMARY KEY,parent TEXT REFERENCES branches(id),fork_revision INTEGER,revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0));
INSERT INTO branches(id) VALUES('main');
CREATE TABLE sources(id TEXT PRIMARY KEY,path TEXT NOT NULL,sha256 TEXT NOT NULL,content TEXT NOT NULL);
CREATE TABLE excerpts(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(id),start_line INTEGER NOT NULL CHECK(start_line>0),end_line INTEGER NOT NULL CHECK(end_line>=start_line),heading TEXT NOT NULL,text TEXT NOT NULL);
CREATE TABLE events(id TEXT PRIMARY KEY,branch TEXT NOT NULL REFERENCES branches(id),revision INTEGER NOT NULL,request_id TEXT NOT NULL,payload_hash TEXT NOT NULL,command_json TEXT NOT NULL CHECK(json_valid(command_json)),kind TEXT NOT NULL,actor TEXT NOT NULL,narrative TEXT NOT NULL,clock_id TEXT,tick REAL,causes_json TEXT NOT NULL CHECK(json_valid(causes_json)),prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL,receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(branch,revision),UNIQUE(branch,request_id));
CREATE TABLE records(branch TEXT NOT NULL REFERENCES branches(id),id TEXT NOT NULL,domain TEXT NOT NULL,version INTEGER NOT NULL CHECK(version>0),status TEXT NOT NULL CHECK(status IN ('confirmed','reported','inferred','contested','unknown','proposed')),visibility TEXT NOT NULL CHECK(visibility IN ('public','restricted','gm')),audience_json TEXT NOT NULL CHECK(json_valid(audience_json)),evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)),updated_event TEXT NOT NULL REFERENCES events(id),PRIMARY KEY(branch,id));
CREATE TABLE changes(event_id TEXT NOT NULL REFERENCES events(id),ordinal INTEGER NOT NULL,record_id TEXT NOT NULL,before_json TEXT,after_json TEXT NOT NULL CHECK(json_valid(after_json)),PRIMARY KEY(event_id,ordinal));
CREATE TABLE rolls(branch TEXT NOT NULL REFERENCES branches(id),id TEXT NOT NULL,sides INTEGER NOT NULL CHECK(sides>=2),target INTEGER NOT NULL,modifier INTEGER NOT NULL,result INTEGER NOT NULL,reason TEXT NOT NULL,PRIMARY KEY(branch,id));
CREATE TABLE roll_uses(branch TEXT NOT NULL,id TEXT NOT NULL,event_id TEXT NOT NULL REFERENCES events(id),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES rolls(branch,id));
CREATE TABLE snapshots(id TEXT PRIMARY KEY,branch TEXT NOT NULL REFERENCES branches(id),revision INTEGER NOT NULL,state_json TEXT NOT NULL CHECK(json_valid(state_json)),sha256 TEXT NOT NULL);
CREATE TABLE "character"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"entity_kind" TEXT NOT NULL CHECK("entity_kind" IN ('person','entity','manifestation','unknown')),"aliases" TEXT CHECK("aliases" IS NULL OR json_valid("aliases")),"personality" TEXT,"voice" TEXT,"motives" TEXT,"condition" TEXT,"location" TEXT,"identity" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "faction"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"purpose" TEXT,"institution" TEXT,"leadership" TEXT,"resources" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "location"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"kind" TEXT NOT NULL CHECK("kind" IN ('world','island','region','room','ship','route','layer','unknown')),"parent" TEXT,"geography" TEXT,"ecology" TEXT,"infrastructure" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"parent") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "relationship"(branch TEXT NOT NULL,id TEXT NOT NULL,"subject" TEXT NOT NULL,"object" TEXT NOT NULL,"kind" TEXT NOT NULL,"feeling" TEXT,"obligation" TEXT,"tension" TEXT,"shared_history" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"subject") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"object") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "ability"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"function" TEXT NOT NULL,"conditions" TEXT,"limits" TEXT,"costs" TEXT,"mechanical_rule" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "capability"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"ability" TEXT NOT NULL,"mastery" TEXT,"condition" TEXT,"demonstrated_use" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"ability") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"bearer" TEXT NOT NULL,"principles" TEXT,"expression" TEXT,"limits" TEXT,"erosion" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"bearer") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_definition"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"classification" TEXT NOT NULL CHECK("classification" IN ('primordial','derivative','independent','false','unknown')),"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_expression"(branch TEXT NOT NULL,id TEXT NOT NULL,"definition" TEXT NOT NULL,"bearer" TEXT NOT NULL,"legacy_will" TEXT,"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"definition") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"bearer") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"legacy_will") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_technique"(branch TEXT NOT NULL,id TEXT NOT NULL,"expression" TEXT NOT NULL,"ability" TEXT,"name" TEXT NOT NULL,"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"ability") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_awakening"(branch TEXT NOT NULL,id TEXT NOT NULL,"expression" TEXT NOT NULL,"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_development"(branch TEXT NOT NULL,id TEXT NOT NULL,"expression" TEXT NOT NULL,"progression" TEXT,"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"progression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "will_effect"(branch TEXT NOT NULL,id TEXT NOT NULL,"expression" TEXT NOT NULL,"technique" TEXT NOT NULL,"contract" TEXT NOT NULL CHECK("contract" IS NULL OR json_valid("contract")),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"expression") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"technique") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "item"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"kind" TEXT,"condition" TEXT NOT NULL,"effects" TEXT,"costs" TEXT,"origin" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "loadout"(branch TEXT NOT NULL,id TEXT NOT NULL,"item" TEXT NOT NULL,"holder" TEXT NOT NULL,"slot" TEXT NOT NULL,"equipped" INTEGER NOT NULL,"bond" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"item") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"holder") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "loot"(branch TEXT NOT NULL,id TEXT NOT NULL,"item" TEXT NOT NULL,"location" TEXT NOT NULL,"discovery" TEXT NOT NULL CHECK("discovery" IN ('hidden','discoverable','discovered','claimed','destroyed','inaccessible','unknown')),"claimant" TEXT,"requirements" TEXT,"risks" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"item") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"claimant") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "environment"(branch TEXT NOT NULL,id TEXT NOT NULL,"location" TEXT NOT NULL,"feature" TEXT NOT NULL,"kind" TEXT NOT NULL CHECK("kind" IN ('terrain','ecology','hazard','infrastructure','metaphysical','weather','interactable')),"rule" TEXT,"duration" TEXT,"ending_condition" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "route"(branch TEXT NOT NULL,id TEXT NOT NULL,"origin" TEXT NOT NULL,"destination" TEXT NOT NULL,"access" TEXT NOT NULL CHECK("access" IN ('open','blocked','conditional','unknown')),"conditions" TEXT,"duration" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"origin") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"destination") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "scene"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"location" TEXT NOT NULL,"clock" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('open','active','closed')),"round" INTEGER NOT NULL,"context" TEXT,"hazards" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"clock") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "participation"(branch TEXT NOT NULL,id TEXT NOT NULL,"scene" TEXT NOT NULL,"character" TEXT NOT NULL,"position" TEXT,"initiative" REAL,"actions_remaining" INTEGER,"active_effects" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"scene") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "objective"(branch TEXT NOT NULL,id TEXT NOT NULL,"title" TEXT NOT NULL,"holder" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('unknown','available','active','blocked','completed','failed','abandoned','transformed')),"stakes" TEXT,"success" TEXT,"failure" TEXT,"progress" REAL,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"holder") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "dependency"(branch TEXT NOT NULL,id TEXT NOT NULL,"objective" TEXT NOT NULL,"prerequisite" TEXT NOT NULL,"relation" TEXT NOT NULL CHECK("relation" IN ('requires','conflicts','supports')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"objective") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"prerequisite") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "decision"(branch TEXT NOT NULL,id TEXT NOT NULL,"actor" TEXT NOT NULL,"objective" TEXT,"choice" TEXT NOT NULL,"alternatives" TEXT CHECK("alternatives" IS NULL OR json_valid("alternatives")),"rationale" TEXT,"commitment" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"actor") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"objective") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "arc"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"phase" TEXT NOT NULL CHECK("phase" IN ('proposed','active','resolved','abandoned')),"conflict" TEXT,"stakes" TEXT,"outcome" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "thread"(branch TEXT NOT NULL,id TEXT NOT NULL,"arc" TEXT,"question" TEXT NOT NULL,"phase" TEXT NOT NULL CHECK("phase" IN ('open','investigating','answered','abandoned')),"answer" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"arc") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "progression"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"ability" TEXT,"experience" TEXT NOT NULL,"practice" TEXT,"discovery" TEXT,"setback" TEXT,"cost" TEXT,"demonstrated" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('proposed','attempted','demonstrated','retained','discarded')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"ability") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "political_claim"(branch TEXT NOT NULL,id TEXT NOT NULL,"claimant" TEXT NOT NULL,"territory" TEXT NOT NULL,"authority" TEXT NOT NULL,"legitimacy" TEXT,"recognition" TEXT,"enforcement" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('asserted','contested','recognized','withdrawn','unknown')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"claimant") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"territory") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "affiliation"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"faction" TEXT NOT NULL,"role" TEXT,"allegiance" TEXT NOT NULL CHECK("allegiance" IN ('member','independent','estranged','defected','unknown')),"consent" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"faction") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "law"(branch TEXT NOT NULL,id TEXT NOT NULL,"issuer" TEXT NOT NULL,"jurisdiction" TEXT NOT NULL,"name" TEXT NOT NULL,"provision" TEXT NOT NULL,"enforcement" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('proposed','active','suspended','repealed')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"issuer") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"jurisdiction") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "accord"(branch TEXT NOT NULL,id TEXT NOT NULL,"party_a" TEXT NOT NULL,"party_b" TEXT NOT NULL,"kind" TEXT NOT NULL CHECK("kind" IN ('alliance','truce','war','trade','obligation','other')),"terms" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('proposed','active','broken','ended','unknown')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"party_a") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"party_b") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "office"(branch TEXT NOT NULL,id TEXT NOT NULL,"faction" TEXT NOT NULL,"holder" TEXT,"title" TEXT NOT NULL,"jurisdiction" TEXT,"succession" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('occupied','vacant','disputed')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"faction") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"holder") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"jurisdiction") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "resource"(branch TEXT NOT NULL,id TEXT NOT NULL,"holder" TEXT NOT NULL,"name" TEXT NOT NULL,"quantity" REAL NOT NULL,"unit" TEXT NOT NULL,"availability" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"holder") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "knowledge"(branch TEXT NOT NULL,id TEXT NOT NULL,"holder" TEXT NOT NULL,"subject" TEXT,"assertion" TEXT NOT NULL,"attitude" TEXT NOT NULL CHECK("attitude" IN ('knows','believes','suspects','denies','unknown')),"basis" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"holder") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "historical_account"(branch TEXT NOT NULL,id TEXT NOT NULL,"author" TEXT,"event_reference" TEXT,"assertion" TEXT NOT NULL,"interpretation" TEXT,"audience" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"author") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "clock"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"location" TEXT,"tick" REAL NOT NULL,"unit" TEXT NOT NULL,"calendar" TEXT,"relation_to_others" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "experience"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"clock" TEXT NOT NULL,"elapsed" REAL,"unit" TEXT NOT NULL,"remembered" TEXT,"survives_rewind" INTEGER NOT NULL,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"clock") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "schedule"(branch TEXT NOT NULL,id TEXT NOT NULL,"clock" TEXT NOT NULL,"due" REAL NOT NULL,"trigger" TEXT NOT NULL,"proposed_effect" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('pending','due','resolved','cancelled')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"clock") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "world_rule"(branch TEXT NOT NULL,id TEXT NOT NULL,"name" TEXT NOT NULL,"scope" TEXT NOT NULL,"statement" TEXT NOT NULL,"exceptions" TEXT,"resolution" TEXT NOT NULL CHECK("resolution" IN ('mechanical','gm_judgment','unknown')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"scope") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "consequence"(branch TEXT NOT NULL,id TEXT NOT NULL,"subject" TEXT NOT NULL,"effect" TEXT NOT NULL,"duration" TEXT,"ending_condition" TEXT,"reversibility" TEXT NOT NULL CHECK("reversibility" IN ('reversible','conditional','irreversible','unknown')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "character_identity"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"existence" TEXT NOT NULL CHECK("existence" IN ('established','provisional','alleged')),"canonical_name" TEXT,"name_status" TEXT NOT NULL CHECK("name_status" IN ('known','unknown','absent','not_applicable')),"continuity" TEXT NOT NULL CHECK("continuity" IN ('established','disputed','unresolved','transformed')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "character_aspect"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"section" TEXT NOT NULL CHECK("section" IN ('nature','interiority','portrayal','condition','perspective','development')),"kind" TEXT NOT NULL CHECK("kind" IN ('facet','embodiment','constituent','principle','drive','commitment','preference','boundary','conflict','description','voice','mannerism','habit','pleasure','attachment','injury','fatigue','memory_disruption','recognition_disruption','intention_impairment','agency_constraint','communication','memory','question','appraisal','arousal','attention_style','comfort','emotion','expression_state','humor','regulation','self_concept','thinking_style','thought','verbal_style')),"value_status" TEXT NOT NULL CHECK("value_status" IN ('known','unknown','absent','not_applicable')),"statement" TEXT,"related_character" TEXT,"related_item" TEXT,"clock" TEXT,"valid_from" REAL,"valid_until" REAL,"ending_condition" TEXT,"phase" TEXT NOT NULL CHECK("phase" IN ('active','ended')),"change_basis" TEXT NOT NULL CHECK("change_basis" IN ('established','voluntary','compelled','deceived','disrupted','recovered','unknown')),"supersedes" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"related_character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"related_item") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"clock") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"supersedes") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "character_presence"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"location" TEXT NOT NULL,"embodiment" TEXT,"mode" TEXT NOT NULL CHECK("mode" IN ('physical','projected','distributed','unknown')),"phase" TEXT NOT NULL CHECK("phase" IN ('present','departed','uncertain')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"location") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"embodiment") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "character_lineage"(branch TEXT NOT NULL,id TEXT NOT NULL,"predecessor" TEXT NOT NULL,"successor" TEXT NOT NULL,"relation" TEXT NOT NULL CHECK("relation" IN ('origin','split','merge','succession','copy','fragment','disputed')),"explanation" TEXT NOT NULL,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"predecessor") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"successor") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "personality_profile"(branch TEXT NOT NULL,id TEXT NOT NULL,"character" TEXT NOT NULL,"framework" TEXT NOT NULL CHECK("framework" IN ('mbti-inspired')),"type_code" TEXT,"interpretation" TEXT NOT NULL CHECK("interpretation" IN ('proposed','accepted','unknown')),"note" TEXT NOT NULL,"policy_id" TEXT,"policy_version" INTEGER,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"character") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "dialogue_turn"(branch TEXT NOT NULL,id TEXT NOT NULL,"speaker" TEXT NOT NULL,"listeners" TEXT NOT NULL CHECK("listeners" IS NULL OR json_valid("listeners")),"scene" TEXT,"reply_to" TEXT,"act" TEXT NOT NULL,"text" TEXT NOT NULL,"mode" TEXT NOT NULL CHECK("mode" IN ('spoken','gesture','silence')),PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"speaker") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"scene") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"reply_to") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "writing_delivery"(branch TEXT NOT NULL,id TEXT NOT NULL,"audience" TEXT NOT NULL,"form" TEXT NOT NULL CHECK("form" IN ('narration','dialogue','situation','scenario','event','history','discovery','reflection','recap','description')),"text" TEXT NOT NULL,"scene" TEXT,"supersedes" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"audience") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"scene") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"supersedes") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE TABLE "dialogue_reception"(branch TEXT NOT NULL,id TEXT NOT NULL,"listener" TEXT NOT NULL,"turn" TEXT NOT NULL,"interpretation" TEXT NOT NULL,"certainty" TEXT NOT NULL CHECK("certainty" IN ('tentative','confident','unknown')),"response" TEXT,"supersedes" TEXT,PRIMARY KEY(branch,id),FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"listener") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"turn") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED,FOREIGN KEY(branch,"supersedes") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED);
CREATE UNIQUE INDEX one_item_holder ON loadout(branch,item);
CREATE UNIQUE INDEX one_equipped_slot ON loadout(branch,holder,slot) WHERE equipped=1;
CREATE UNIQUE INDEX one_participation ON participation(branch,scene,character);
CREATE UNIQUE INDEX one_capability ON capability(branch,character,ability);
CREATE INDEX records_domain ON records(branch,domain);
CREATE INDEX changes_record ON changes(record_id);
CREATE TRIGGER immutable_events_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
CREATE TRIGGER immutable_events_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
CREATE TRIGGER immutable_changes_update BEFORE UPDATE ON changes BEGIN SELECT RAISE(ABORT,'append-only changes'); END;
CREATE TRIGGER immutable_changes_delete BEFORE DELETE ON changes BEGIN SELECT RAISE(ABORT,'append-only changes'); END;
CREATE TRIGGER immutable_sources_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'append-only sources'); END;
CREATE TRIGGER immutable_sources_delete BEFORE DELETE ON sources BEGIN SELECT RAISE(ABORT,'append-only sources'); END;
CREATE TRIGGER immutable_excerpts_update BEFORE UPDATE ON excerpts BEGIN SELECT RAISE(ABORT,'append-only excerpts'); END;
CREATE TRIGGER immutable_excerpts_delete BEFORE DELETE ON excerpts BEGIN SELECT RAISE(ABORT,'append-only excerpts'); END;
CREATE TRIGGER immutable_rolls_update BEFORE UPDATE ON rolls BEGIN SELECT RAISE(ABORT,'append-only rolls'); END;
CREATE TRIGGER immutable_rolls_delete BEFORE DELETE ON rolls BEGIN SELECT RAISE(ABORT,'append-only rolls'); END;
CREATE TRIGGER immutable_roll_uses_update BEFORE UPDATE ON roll_uses BEGIN SELECT RAISE(ABORT,'append-only roll_uses'); END;
CREATE TRIGGER immutable_roll_uses_delete BEFORE DELETE ON roll_uses BEGIN SELECT RAISE(ABORT,'append-only roll_uses'); END;

CREATE TABLE property_definitions(property_id TEXT NOT NULL,definition_version INTEGER NOT NULL CHECK(definition_version>0),label TEXT NOT NULL,meaning TEXT NOT NULL,value_type TEXT NOT NULL CHECK(value_type IN ('number','integer','text','boolean','reference','structured')),unit TEXT,applicability_json TEXT NOT NULL CHECK(json_valid(applicability_json)),constraints_json TEXT NOT NULL CHECK(json_valid(constraints_json)),origin TEXT NOT NULL DEFAULT 'design',PRIMARY KEY(property_id,definition_version));
CREATE TABLE entity_facets(branch TEXT NOT NULL REFERENCES branches(id),entity_id TEXT NOT NULL,facet TEXT NOT NULL,source_event TEXT,PRIMARY KEY(branch,entity_id,facet));
CREATE TABLE property_values(branch TEXT NOT NULL REFERENCES branches(id),entity_id TEXT NOT NULL,property_id TEXT NOT NULL,definition_version INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('known','unknown','absent','not_applicable','disputed')),number_value REAL,text_value TEXT,json_value TEXT CHECK(json_value IS NULL OR json_valid(json_value)),unit TEXT,context_json TEXT NOT NULL CHECK(json_valid(context_json)),valid_from_event TEXT,valid_until_event TEXT,epistemic_status TEXT NOT NULL,visibility TEXT NOT NULL DEFAULT 'gm' CHECK(visibility IN ('public','restricted','gm')),PRIMARY KEY(branch,entity_id,property_id,definition_version),FOREIGN KEY(property_id,definition_version) REFERENCES property_definitions(property_id,definition_version));
CREATE TABLE property_lifecycle(sequence INTEGER PRIMARY KEY AUTOINCREMENT,property_id TEXT NOT NULL,definition_version INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('proposed','active','deprecated','retired')),reason TEXT NOT NULL,recorded_event TEXT,FOREIGN KEY(property_id,definition_version) REFERENCES property_definitions(property_id,definition_version));
CREATE TABLE rule_definitions(rule_id TEXT NOT NULL,rule_version INTEGER NOT NULL,name TEXT NOT NULL,inputs_json TEXT NOT NULL CHECK(json_valid(inputs_json)),outputs_json TEXT NOT NULL CHECK(json_valid(outputs_json)),mechanical INTEGER NOT NULL CHECK(mechanical IN (0,1)),definition_json TEXT NOT NULL CHECK(json_valid(definition_json)),PRIMARY KEY(rule_id,rule_version));
CREATE TABLE rule_dependencies(rule_id TEXT NOT NULL,rule_version INTEGER NOT NULL,property_id TEXT NOT NULL,property_version INTEGER,usage TEXT NOT NULL CHECK(usage IN ('reads','writes','derives')),PRIMARY KEY(rule_id,rule_version,property_id,property_version,usage),FOREIGN KEY(rule_id,rule_version) REFERENCES rule_definitions(rule_id,rule_version));
CREATE TABLE event_dependencies(event_id TEXT NOT NULL REFERENCES events(id),kind TEXT NOT NULL,ref_id TEXT NOT NULL,version TEXT,usage TEXT NOT NULL,PRIMARY KEY(event_id,kind,ref_id,usage));
CREATE TABLE consequences(id TEXT PRIMARY KEY,branch TEXT NOT NULL REFERENCES branches(id),source_event TEXT NOT NULL REFERENCES events(id),subject_id TEXT NOT NULL,effect_json TEXT NOT NULL CHECK(json_valid(effect_json)),trigger_json TEXT NOT NULL CHECK(json_valid(trigger_json)),status TEXT NOT NULL CHECK(status IN ('pending','applied','cancelled','contested')),apply_once INTEGER NOT NULL DEFAULT 1 CHECK(apply_once IN (0,1)),applied_event TEXT);
CREATE TABLE choices(id TEXT PRIMARY KEY,branch TEXT NOT NULL REFERENCES branches(id),event_id TEXT NOT NULL REFERENCES events(id),actor_id TEXT NOT NULL,intent TEXT NOT NULL,method TEXT,agency_state TEXT NOT NULL,options_json TEXT NOT NULL CHECK(json_valid(options_json)),selected_json TEXT NOT NULL CHECK(json_valid(selected_json)),knowledge_json TEXT NOT NULL CHECK(json_valid(knowledge_json)));
CREATE TABLE migrations(version INTEGER PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX property_values_entity ON property_values(branch,entity_id);
CREATE INDEX event_dependencies_ref ON event_dependencies(kind,ref_id);
-- Runtime metadata keeps schema compatibility separate from the legacy v2 marker.
CREATE TABLE IF NOT EXISTS engine_versions(
  component TEXT PRIMARY KEY,
  version TEXT NOT NULL,
  checksum TEXT,
  compatible_engine TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO engine_versions(component,version) VALUES
 ('runtime_schema','4'),('property_registry','1'),('resolution_rules','1'),('story_state','1'),('workflow_api','3');
CREATE TABLE IF NOT EXISTS property_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, entity_id TEXT NOT NULL, property_id TEXT NOT NULL,
  definition_version INTEGER NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal),
  FOREIGN KEY(property_id,definition_version) REFERENCES property_definitions(property_id,definition_version)
);
CREATE INDEX IF NOT EXISTS property_changes_lookup ON property_changes(branch,entity_id,property_id);
CREATE TABLE IF NOT EXISTS property_operations(
  id TEXT PRIMARY KEY, operation TEXT NOT NULL, property_id TEXT NOT NULL,
  definition_version INTEGER, before_json TEXT, after_json TEXT,
  actor TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS entity_facet_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, entity_id TEXT NOT NULL, facet TEXT NOT NULL,
  before_json TEXT, after_json TEXT, PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS consequence_runs(
  consequence_id TEXT NOT NULL REFERENCES consequences(id), run_key TEXT NOT NULL,
  event_id TEXT NOT NULL REFERENCES events(id), status TEXT NOT NULL,
  detail_json TEXT NOT NULL CHECK(json_valid(detail_json)),
  PRIMARY KEY(consequence_id,run_key)
);
CREATE TABLE IF NOT EXISTS processes(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL,
  process_kind TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('active','paused','due','blocked','completed','cancelled')),
  subjects_json TEXT NOT NULL CHECK(json_valid(subjects_json)), scope_json TEXT NOT NULL CHECK(json_valid(scope_json)),
  origin_event TEXT REFERENCES events(id), rule_id TEXT, rule_version INTEGER,
  conditions_json TEXT NOT NULL CHECK(json_valid(conditions_json)), subscriptions_json TEXT NOT NULL CHECK(json_valid(subscriptions_json)),
  last_tick REAL, next_tick REAL, interval_value REAL, interval_unit TEXT,
  granularity TEXT NOT NULL DEFAULT 'exact' CHECK(granularity IN ('exact','threshold','aggregate','judgment')),
  rng_slot TEXT, pending_judgment TEXT, visibility TEXT NOT NULL DEFAULT 'gm' CHECK(visibility IN ('public','restricted','gm')),
  metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)), updated_event TEXT REFERENCES events(id),
  PRIMARY KEY(branch,id)
);
CREATE INDEX IF NOT EXISTS processes_due ON processes(branch,state,next_tick);
CREATE TABLE IF NOT EXISTS process_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL,
  branch TEXT NOT NULL, process_id TEXT NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE TABLE IF NOT EXISTS process_runs(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, run_key TEXT NOT NULL,
  event_id TEXT, from_tick REAL, to_tick REAL, rng_result_json TEXT,
  outcome_json TEXT NOT NULL CHECK(json_valid(outcome_json)), status TEXT NOT NULL,
  PRIMARY KEY(branch,process_id,run_key)
);
CREATE TABLE IF NOT EXISTS process_subscriptions(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, event_kind TEXT NOT NULL,
  PRIMARY KEY(branch,process_id,event_kind), FOREIGN KEY(branch,process_id) REFERENCES processes(branch,id)
);
CREATE TABLE IF NOT EXISTS attention_scores(
  branch TEXT NOT NULL, process_id TEXT NOT NULL, viewer_id TEXT, score REAL NOT NULL,
  factors_json TEXT NOT NULL CHECK(json_valid(factors_json)), computed_revision INTEGER NOT NULL,
  PRIMARY KEY(branch,process_id,viewer_id)
);
CREATE TABLE IF NOT EXISTS registry_entries(
  kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
  locator TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('declared','verified','uncertain','retired')),
  readers_json TEXT NOT NULL CHECK(json_valid(readers_json)), writers_json TEXT NOT NULL CHECK(json_valid(writers_json)),
  compatibility_json TEXT NOT NULL CHECK(json_valid(compatibility_json)), source_hash TEXT,
  declared_by TEXT NOT NULL, PRIMARY KEY(kind,stable_id,version)
);
CREATE TABLE IF NOT EXISTS registry_dependencies(
  kind TEXT NOT NULL, stable_id TEXT NOT NULL, version TEXT NOT NULL,
  depends_kind TEXT NOT NULL, depends_id TEXT NOT NULL, depends_version TEXT,
  relation TEXT NOT NULL, PRIMARY KEY(kind,stable_id,version,depends_kind,depends_id,depends_version,relation),
  FOREIGN KEY(kind,stable_id,version) REFERENCES registry_entries(kind,stable_id,version)
);
CREATE TABLE IF NOT EXISTS module_manifests(
  module_id TEXT PRIMARY KEY, module_version TEXT NOT NULL, entry_skill TEXT NOT NULL,
  triggers_json TEXT NOT NULL CHECK(json_valid(triggers_json)), required_context_json TEXT NOT NULL CHECK(json_valid(required_context_json)),
  commands_json TEXT NOT NULL CHECK(json_valid(commands_json)), dependencies_json TEXT NOT NULL CHECK(json_valid(dependencies_json)),
  compatibility_json TEXT NOT NULL CHECK(json_valid(compatibility_json)), visibility TEXT NOT NULL,
  source_hash TEXT, status TEXT NOT NULL CHECK(status IN ('active','proposed','deprecated','retired'))
);
CREATE TABLE IF NOT EXISTS event_aux_changes(
  event_id TEXT NOT NULL REFERENCES events(id), ordinal INTEGER NOT NULL, kind TEXT NOT NULL,
  state_key TEXT NOT NULL, before_json TEXT, after_json TEXT,
  PRIMARY KEY(event_id,ordinal)
);
CREATE INDEX IF NOT EXISTS event_aux_lookup ON event_aux_changes(kind,state_key);
CREATE TABLE IF NOT EXISTS migration_checks(
  version INTEGER PRIMARY KEY, predecessor INTEGER, script_name TEXT NOT NULL,
  checksum TEXT NOT NULL, engine_min TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS event_resolutions(
  event_id TEXT PRIMARY KEY REFERENCES events(id),
  resolution_json TEXT NOT NULL CHECK(json_valid(resolution_json)),
  mechanical INTEGER NOT NULL CHECK(mechanical IN (0,1)),
  judgment_json TEXT NOT NULL CHECK(json_valid(judgment_json))
);
CREATE TABLE IF NOT EXISTS observations(
  id TEXT PRIMARY KEY, branch TEXT NOT NULL REFERENCES branches(id),
  event_id TEXT NOT NULL REFERENCES events(id), observer_id TEXT NOT NULL,
  subject_id TEXT NOT NULL, assertion TEXT NOT NULL, certainty TEXT NOT NULL,
  visibility TEXT NOT NULL, audience_json TEXT NOT NULL CHECK(json_valid(audience_json))
);
CREATE TABLE IF NOT EXISTS entity_profiles(
  branch TEXT NOT NULL REFERENCES branches(id), entity_id TEXT NOT NULL,
  identity_label TEXT, nature TEXT NOT NULL, composition_json TEXT NOT NULL CHECK(json_valid(composition_json)),
  agency_mode TEXT NOT NULL, control_mode TEXT NOT NULL, classification_json TEXT NOT NULL CHECK(json_valid(classification_json)),
  visibility TEXT NOT NULL DEFAULT 'gm', audience_json TEXT NOT NULL CHECK(json_valid(audience_json)),
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,entity_id)
);
CREATE TABLE IF NOT EXISTS entity_links(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, whole_id TEXT NOT NULL, part_id TEXT NOT NULL,
  relation TEXT NOT NULL, valid_from_event TEXT REFERENCES events(id), valid_until_event TEXT,
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
);
CREATE TABLE IF NOT EXISTS classification_claims(
  branch TEXT NOT NULL REFERENCES branches(id), id TEXT NOT NULL, subject_id TEXT NOT NULL, claimant_id TEXT NOT NULL,
  classification TEXT NOT NULL, mechanism TEXT, force TEXT NOT NULL, status TEXT NOT NULL,
  source_event TEXT REFERENCES events(id), PRIMARY KEY(branch,id)
);
-- Versioned Will attempt reservations are execution metadata, not fictional
-- events.  They pin exact contracts, inputs and randomness before a commit so
-- retries cannot reroll or accept caller-edited state deltas.
CREATE TABLE IF NOT EXISTS will_attempts(
  branch TEXT NOT NULL REFERENCES branches(id),
  attempt_id TEXT NOT NULL,
  prepare_request_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  expression_id TEXT NOT NULL,
  expression_version INTEGER NOT NULL,
  technique_id TEXT NOT NULL,
  technique_version INTEGER NOT NULL,
  expected_revision INTEGER NOT NULL,
  input_snapshot_hash TEXT NOT NULL,
  attempt_json TEXT NOT NULL CHECK(json_valid(attempt_json)),
  compiled_json TEXT NOT NULL CHECK(json_valid(compiled_json)),
  status TEXT NOT NULL CHECK(status IN ('prepared','blocked','committed','cancelled')),
  roll_id TEXT,
  event_id TEXT REFERENCES events(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(branch,attempt_id),
  UNIQUE(branch,prepare_request_id)
);
CREATE INDEX IF NOT EXISTS will_attempts_actor ON will_attempts(branch,actor,status);
CREATE INDEX IF NOT EXISTS will_attempts_expression ON will_attempts(branch,expression_id,technique_id);
CREATE TABLE IF NOT EXISTS will_contract_history(
  branch TEXT NOT NULL REFERENCES branches(id),
  record_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version>0),
  record_json TEXT NOT NULL CHECK(json_valid(record_json)),
  source_event TEXT REFERENCES events(id),
  PRIMARY KEY(branch,record_id,version)
);
CREATE INDEX IF NOT EXISTS will_contract_history_lookup ON will_contract_history(branch,record_id,version);
