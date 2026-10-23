"""Explicit domain definitions; single source for DDL, validation and documentation.
Field kinds: text, number, integer, json, enum:a|b, ref:domain[|domain].
References are branch-local and validated by the engine in addition to SQL FKs.
"""
DOMAINS = {
'character': dict(name='text', entity_kind='enum:person|entity|manifestation|unknown', aliases='json', personality='text', voice='text', motives='text', condition='text', location='ref:location', identity='text'),
'faction': dict(name='text', purpose='text', institution='text', leadership='text', resources='text'),
'location': dict(name='text', kind='enum:world|island|region|room|ship|route|layer|unknown', parent='ref:location', geography='text', ecology='text', infrastructure='text'),
'relationship': dict(subject='ref:character|faction', object='ref:character|faction', kind='text', feeling='text', obligation='text', tension='text', shared_history='text'),
'ability': dict(name='text', function='text', conditions='text', limits='text', costs='text', mechanical_rule='text'),
'capability': dict(character='ref:character', ability='ref:ability', mastery='text', condition='text', demonstrated_use='text'),
# The legacy flat ``will`` record remains for backward compatibility.  The
# versioned Will system is additive: a definition can exist independently of
# any bearer, an expression binds it to a bearer, and techniques/awakenings/
# development/effects remain separate records so identity and history survive
# revision and transformation.
'will': dict(name='text', bearer='ref:character|location|faction', principles='text', expression='text', limits='text', erosion='text'),
'will_definition': dict(name='text', classification='enum:primordial|derivative|independent|false|unknown', contract='json'),
'will_expression': dict(definition='ref:will_definition', bearer='ref:character|location|faction', legacy_will='ref:will', contract='json'),
'will_technique': dict(expression='ref:will_expression', ability='ref:ability', name='text', contract='json'),
'will_awakening': dict(expression='ref:will_expression', contract='json'),
'will_development': dict(expression='ref:will_expression', progression='ref:progression', contract='json'),
'will_effect': dict(expression='ref:will_expression', technique='ref:will_technique', contract='json'),
'item': dict(name='text', kind='text', condition='text', effects='text', costs='text', origin='text'),
'loadout': dict(item='ref:item', holder='ref:character|location|faction', slot='text', equipped='integer', bond='text'),
'loot': dict(item='ref:item', location='ref:location', discovery='enum:hidden|discoverable|discovered|claimed|destroyed|inaccessible|unknown', claimant='ref:character|faction', requirements='text', risks='text'),
'environment': dict(location='ref:location', feature='text', kind='enum:terrain|ecology|hazard|infrastructure|metaphysical|weather|interactable', rule='text', duration='text', ending_condition='text'),
'route': dict(origin='ref:location', destination='ref:location', access='enum:open|blocked|conditional|unknown', conditions='text', duration='text'),
'scene': dict(name='text', location='ref:location', clock='ref:clock', phase='enum:open|active|closed', round='integer', context='text', hazards='text'),
'participation': dict(scene='ref:scene', character='ref:character', position='text', initiative='number', actions_remaining='integer', active_effects='text'),
'objective': dict(title='text', holder='ref:character|faction', phase='enum:unknown|available|active|blocked|completed|failed|abandoned|transformed', stakes='text', success='text', failure='text', progress='number'),
'dependency': dict(objective='ref:objective', prerequisite='ref:objective', relation='enum:requires|conflicts|supports'),
'decision': dict(actor='ref:character|faction', objective='ref:objective', choice='text', alternatives='json', rationale='text', commitment='text'),
'arc': dict(name='text', phase='enum:proposed|active|resolved|abandoned', conflict='text', stakes='text', outcome='text'),
'thread': dict(arc='ref:arc', question='text', phase='enum:open|investigating|answered|abandoned', answer='text'),
'progression': dict(character='ref:character', ability='ref:ability', experience='text', practice='text', discovery='text', setback='text', cost='text', demonstrated='text', phase='enum:proposed|attempted|demonstrated|retained|discarded'),
'political_claim': dict(claimant='ref:character|faction', territory='ref:location', authority='text', legitimacy='text', recognition='text', enforcement='text', phase='enum:asserted|contested|recognized|withdrawn|unknown'),
'affiliation': dict(character='ref:character', faction='ref:faction', role='text', allegiance='enum:member|independent|estranged|defected|unknown', consent='text'),
'law': dict(issuer='ref:character|faction', jurisdiction='ref:location', name='text', provision='text', enforcement='text', phase='enum:proposed|active|suspended|repealed'),
'accord': dict(party_a='ref:character|faction', party_b='ref:character|faction', kind='enum:alliance|truce|war|trade|obligation|other', terms='text', phase='enum:proposed|active|broken|ended|unknown'),
'office': dict(faction='ref:faction', holder='ref:character', title='text', jurisdiction='ref:location', succession='text', phase='enum:occupied|vacant|disputed'),
'resource': dict(holder='ref:character|faction|location', name='text', quantity='number', unit='text', availability='text'),
'knowledge': dict(holder='ref:character|faction', subject='text', assertion='text', attitude='enum:knows|believes|suspects|denies|unknown', basis='text'),
'historical_account': dict(author='ref:character|faction', event_reference='text', assertion='text', interpretation='text', audience='text'),
'clock': dict(name='text', location='ref:location', tick='number', unit='text', calendar='text', relation_to_others='text'),
'experience': dict(character='ref:character', clock='ref:clock', elapsed='number', unit='text', remembered='text', survives_rewind='integer'),
'schedule': dict(clock='ref:clock', due='number', trigger='text', proposed_effect='text', phase='enum:pending|due|resolved|cancelled'),
'world_rule': dict(name='text', scope='ref:location', statement='text', exceptions='text', resolution='enum:mechanical|gm_judgment|unknown'),
'consequence': dict(subject='text', effect='text', duration='text', ending_condition='text', reversibility='enum:reversible|conditional|irreversible|unknown'),
}
REQUIRED = {
'character':['name','entity_kind'], 'faction':['name'], 'location':['name','kind'],
'relationship':['subject','object','kind'], 'ability':['name','function'], 'capability':['character','ability'],
'will':['name','bearer'],
'will_definition':['name','classification','contract'],
'will_expression':['definition','bearer','contract'],
'will_technique':['expression','name','contract'],
'will_awakening':['expression','contract'],
'will_development':['expression','contract'],
'will_effect':['expression','technique','contract'],
'item':['name','condition'], 'loadout':['item','holder','slot','equipped'],
'loot':['item','location','discovery'], 'environment':['location','feature','kind'], 'route':['origin','destination','access'],
'scene':['name','location','phase','round'], 'participation':['scene','character'], 'objective':['title','phase'],
'dependency':['objective','prerequisite','relation'], 'decision':['actor','choice'], 'arc':['name','phase'],
'thread':['question','phase'], 'progression':['character','experience','phase'],
'political_claim':['claimant','territory','authority','phase'], 'affiliation':['character','faction','allegiance'],
'law':['issuer','jurisdiction','name','provision','phase'], 'accord':['party_a','party_b','kind','phase'],
'office':['faction','title','phase'], 'resource':['holder','name','quantity','unit'],
'knowledge':['holder','assertion','attitude'], 'historical_account':['assertion'], 'clock':['name','tick','unit'],
'experience':['character','clock','unit','survives_rewind'], 'schedule':['clock','due','trigger','phase'],
'world_rule':['name','scope','statement','resolution'], 'consequence':['subject','effect','reversibility']}
STATUSES = ('confirmed','reported','inferred','contested','unknown','proposed')
from .characters import DOMAINS as CHARACTER_DOMAINS, REQUIRED as CHARACTER_REQUIRED
DOMAINS.update(CHARACTER_DOMAINS)
REQUIRED.update(CHARACTER_REQUIRED)
from .writing import DOMAINS as WRITING_DOMAINS, REQUIRED as WRITING_REQUIRED
DOMAINS.update(WRITING_DOMAINS)
REQUIRED.update(WRITING_REQUIRED)

from .contests import DOMAINS as CONTEST_DOMAINS, REQUIRED as CONTEST_REQUIRED
DOMAINS.update(CONTEST_DOMAINS)
REQUIRED.update(CONTEST_REQUIRED)

# Optional source authority is installed explicitly; never default DDL.
from .workspaces.source_authority_installation import DOMAINS as SOURCE_AUTHORITY_DOMAINS, REQUIRED as SOURCE_AUTHORITY_REQUIRED
DOMAINS.update(SOURCE_AUTHORITY_DOMAINS)
REQUIRED.update(SOURCE_AUTHORITY_REQUIRED)

def schema():
    sql = '''PRAGMA foreign_keys=ON;
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
'''
    for domain, fields in DOMAINS.items():
        if domain == 'source_authority':
            continue
        cols=['branch TEXT NOT NULL','id TEXT NOT NULL']
        refs=[]
        for field, kind in fields.items():
            typ='REAL' if kind=='number' else 'INTEGER' if kind=='integer' else 'TEXT'
            col=f'"{field}" {typ}' + (' NOT NULL' if field in REQUIRED[domain] else '')
            if kind.startswith('enum:'):
                vals=','.join("'"+v+"'" for v in kind[5:].split('|'))
                col+=f' CHECK("{field}" IN ({vals}))'
            if kind=='json': col+=f' CHECK("{field}" IS NULL OR json_valid("{field}"))'
            cols.append(col)
            if kind.startswith('ref:'): refs.append(f'FOREIGN KEY(branch,"{field}") REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED')
        cols+=['PRIMARY KEY(branch,id)','FOREIGN KEY(branch,id) REFERENCES records(branch,id) DEFERRABLE INITIALLY DEFERRED']+refs
        sql+=f'CREATE TABLE "{domain}"('+','.join(cols)+');\n'
    sql+='CREATE UNIQUE INDEX one_item_holder ON loadout(branch,item);\n'
    sql+="CREATE UNIQUE INDEX one_equipped_slot ON loadout(branch,holder,slot) WHERE equipped=1;\n"
    sql+='CREATE UNIQUE INDEX one_participation ON participation(branch,scene,character);\n'
    sql+='CREATE UNIQUE INDEX one_capability ON capability(branch,character,ability);\n'
    sql+='CREATE INDEX records_domain ON records(branch,domain);\nCREATE INDEX changes_record ON changes(record_id);\n'
    for table in ('events','changes','sources','excerpts','rolls','roll_uses'):
        for operation in ('UPDATE','DELETE'):
            sql+=f"CREATE TRIGGER immutable_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'append-only {table}'); END;\n"
    sql += '''
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
'''
    return sql
