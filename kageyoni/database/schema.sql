PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. CHARACTER GENESIS (DETERMINISTIC 64-BIT SEED & 6-AXIS TENSOR)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_genesis (
    character_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    genesis_seed TEXT NOT NULL UNIQUE,
    province_origin TEXT NOT NULL,
    affinity_agency REAL NOT NULL CHECK(affinity_agency BETWEEN 0.0 AND 1.0),
    affinity_substance REAL NOT NULL CHECK(affinity_substance BETWEEN 0.0 AND 1.0),
    affinity_information REAL NOT NULL CHECK(affinity_information BETWEEN 0.0 AND 1.0),
    affinity_space REAL NOT NULL CHECK(affinity_space BETWEEN 0.0 AND 1.0),
    affinity_time REAL NOT NULL CHECK(affinity_time BETWEEN 0.0 AND 1.0),
    affinity_value REAL NOT NULL CHECK(affinity_value BETWEEN 0.0 AND 1.0),
    current_will INTEGER NOT NULL CHECK(current_will >= 0),
    max_will INTEGER NOT NULL CHECK(max_will > 0),
    erosion_level REAL NOT NULL DEFAULT 0.00 CHECK(erosion_level BETWEEN 0.00 AND 1.00),
    is_dissolved INTEGER NOT NULL DEFAULT 0 CHECK(is_dissolved IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 2. CHARACTER INTERIORITY & QUAD-VECTORS
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_interiority (
    character_id TEXT PRIMARY KEY REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    moral_anchor TEXT NOT NULL,
    relational_gravity TEXT NOT NULL,
    intimate_stakes TEXT NOT NULL,
    blind_spot TEXT NOT NULL,
    drive_statement TEXT NOT NULL,
    boundary_statement TEXT NOT NULL,
    conflict_statement TEXT NOT NULL
);

-- ============================================================================
-- 3. CHARACTER SOMATICS & SARTORIAL PHENOTYPE
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_somatics (
    character_id TEXT PRIMARY KEY REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    life_stage TEXT NOT NULL CHECK(life_stage IN ('adolescent', 'young_adult', 'mature_veteran', 'weathered_elder')),
    approx_age INTEGER NOT NULL CHECK(approx_age > 0),
    silhouette TEXT NOT NULL CHECK(silhouette IN ('chubby_brawny', 'curvy_voluptuous', 'slim_lanky', 'stocky_barrel', 'dense_muscle_cut')),
    height_cm INTEGER NOT NULL,
    weight_kg INTEGER NOT NULL,
    jaw_shape TEXT NOT NULL,
    nose_cartilage TEXT NOT NULL,
    eye_shape TEXT NOT NULL,
    hair_style TEXT NOT NULL,
    dress_code TEXT NOT NULL CHECK(dress_code IN ('provocative_carnal', 'modest_guarded', 'casual_slovenly', 'flamboyant_ostentatious', 'austere_functional')),
    garments_description TEXT NOT NULL
);

-- ============================================================================
-- 4. ACID CONTACT LEDGER
-- ============================================================================
CREATE TABLE IF NOT EXISTS contact_ledger (
    strike_id INTEGER PRIMARY KEY AUTOINCREMENT,
    encounter_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    attacker_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    anatomical_target TEXT NOT NULL,
    damage_type TEXT NOT NULL,
    force_magnitude REAL NOT NULL,
    is_critical INTEGER NOT NULL DEFAULT 0 CHECK(is_critical IN (0, 1)),
    permanent_trauma_flag INTEGER NOT NULL DEFAULT 0 CHECK(permanent_trauma_flag IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 5. SUBLIMATED 3-SLOT ZENKAI SCARS
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_scars (
    scar_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    origin_strike_id INTEGER REFERENCES contact_ledger(strike_id),
    slot_index INTEGER CHECK(slot_index BETWEEN 1 AND 3),
    is_calcified INTEGER NOT NULL DEFAULT 0 CHECK(is_calcified IN (0, 1)),
    scar_name TEXT NOT NULL,
    anatomical_site TEXT NOT NULL,
    tactical_penalty TEXT NOT NULL,
    compensatory_art TEXT NOT NULL,
    calcified_armor_trait TEXT,
    acquired_turn INTEGER NOT NULL,
    calcified_turn INTEGER
);

-- ============================================================================
-- 6. RELATIONAL LEDGER (3-LAYER RELATIONAL VECTOR)
-- ============================================================================
CREATE TABLE IF NOT EXISTS relational_ledger (
    source_character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    target_character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    trust_dial INTEGER NOT NULL DEFAULT 0 CHECK(trust_dial BETWEEN -100 AND 100),
    lust_dial INTEGER NOT NULL DEFAULT 0 CHECK(lust_dial BETWEEN 0 AND 100),
    contempt_dial INTEGER NOT NULL DEFAULT 0 CHECK(contempt_dial BETWEEN 0 AND 100),
    last_interaction_turn INTEGER DEFAULT 0,
    pa_interaction_count INTEGER DEFAULT 0,
    is_in_grief_berserk INTEGER NOT NULL DEFAULT 0 CHECK(is_in_grief_berserk IN (0, 1)),
    PRIMARY KEY(source_character_id, target_character_id),
    CHECK(source_character_id <> target_character_id)
);

-- ============================================================================
-- 7. CHARACTER TECHNIQUES (MODULAR MARTIAL GRAMMAR)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_techniques (
    technique_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    stance_id TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    infusion_id TEXT NOT NULL,
    intent_id TEXT NOT NULL,
    practice_status TEXT NOT NULL CHECK (practice_status IN ('proposed', 'experimental', 'demonstrated', 'retained', 'unavailable')),
    mastery_discount REAL NOT NULL DEFAULT 0.0 CHECK (mastery_discount BETWEEN 0.0 AND 0.35),
    stamina_cost REAL NOT NULL,
    erosion_ticks REAL NOT NULL,
    backlash_damage REAL NOT NULL,
    recovery_frames INTEGER NOT NULL,
    times_executed INTEGER NOT NULL DEFAULT 0,
    times_hit INTEGER NOT NULL DEFAULT 0,
    discovery_engine TEXT NOT NULL CHECK (discovery_engine IN ('forge', 'satori', 'camp_sparring', 'quarried')),
    lineage_donor_id TEXT,
    created_turn INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 8. MARTIAL KATA DECKS (ATTUNED 4-SLOT LOADOUT)
-- ============================================================================
CREATE TABLE IF NOT EXISTS martial_kata_decks (
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    slot_index INTEGER NOT NULL CHECK (slot_index BETWEEN 1 AND 4),
    technique_id TEXT NOT NULL REFERENCES character_techniques(technique_id),
    is_active INTEGER NOT NULL DEFAULT 1,
    equipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (character_id, slot_index)
);

-- ============================================================================
-- 9. CHARACTER TALENTS (STAR OCEAN FAILURE-DRIVEN AWAKENING)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_talents (
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    talent_id TEXT NOT NULL,
    friction_accumulated REAL NOT NULL DEFAULT 0.0,
    is_awakened INTEGER NOT NULL DEFAULT 0 CHECK (is_awakened IN (0, 1)),
    awakened_turn INTEGER,
    breakthrough_attempts INTEGER NOT NULL DEFAULT 0,
    last_practice_outcome TEXT,
    PRIMARY KEY (character_id, talent_id)
);

-- ============================================================================
-- 10. QUARRIED SHARDS (OPERATION ROOM JUTSU AST EXTRACTIONS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS quarried_shards (
    shard_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    source_boss TEXT NOT NULL,
    slot_type TEXT NOT NULL CHECK (slot_type IN ('stance', 'vector', 'infusion', 'intent')),
    primitive_id TEXT NOT NULL,
    raw_ast_json TEXT NOT NULL,
    is_sanitized INTEGER NOT NULL DEFAULT 0 CHECK (is_sanitized IN (0, 1)),
    is_deadlock_free INTEGER NOT NULL DEFAULT 0 CHECK (is_deadlock_free IN (0, 1)),
    is_tainted INTEGER NOT NULL DEFAULT 0 CHECK (is_tainted IN (0, 1)),
    quarried_turn INTEGER NOT NULL,
    quarried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 11. SATORI EPIPHANIES (IN-COMBAT MUTATION AUDIT)
-- ============================================================================
CREATE TABLE IF NOT EXISTS satori_epiphanies (
    epiphany_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    dilemma_index REAL NOT NULL,
    mutated_slot TEXT NOT NULL CHECK (mutated_slot IN ('stance', 'vector', 'infusion', 'intent')),
    original_primitive TEXT NOT NULL,
    mutated_primitive TEXT NOT NULL,
    clash_success INTEGER NOT NULL CHECK (clash_success IN (0, 1)),
    receipt_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 12. WORLD TILES (10,000 CONTINUOUS GRID TILES)
-- ============================================================================
CREATE TABLE IF NOT EXISTS world_tiles (
    tile_index INTEGER PRIMARY KEY,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    zone_id INTEGER NOT NULL,
    province_id INTEGER NOT NULL,
    terrain_type TEXT NOT NULL,
    elevation INTEGER NOT NULL,
    canopy_height INTEGER NOT NULL DEFAULT 0,
    is_passable_ground BOOLEAN NOT NULL,
    is_glassed_ruin BOOLEAN NOT NULL DEFAULT 0,
    controlling_faction TEXT DEFAULT NULL,
    influence_score REAL NOT NULL DEFAULT 0.0,
    CONSTRAINT check_coords CHECK (x >= 0 AND x < 100 AND y >= 0 AND y < 100),
    CONSTRAINT uq_world_tiles_xy UNIQUE(x, y)
);

-- ============================================================================
-- 13. STRATEGIC NODES (MACRO FORTRESSES, PASSES, OUTPOSTS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategic_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    province_id INTEGER NOT NULL,
    zone_id INTEGER NOT NULL,
    controlling_faction TEXT NOT NULL,
    is_root_supply_generator BOOLEAN NOT NULL DEFAULT 0,
    current_garrison_hp INTEGER NOT NULL DEFAULT 10000,
    max_garrison_hp INTEGER NOT NULL DEFAULT 10000,
    garrison_commander_id TEXT DEFAULT NULL REFERENCES character_genesis(character_id),
    FOREIGN KEY(x, y) REFERENCES world_tiles(x, y)
);

-- ============================================================================
-- 14. STRATEGIC EDGES (HIGHWAYS & VALLEY CORRIDORS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS strategic_edges (
    edge_id TEXT PRIMARY KEY,
    origin_node_id TEXT NOT NULL REFERENCES strategic_nodes(node_id),
    destination_node_id TEXT NOT NULL REFERENCES strategic_nodes(node_id),
    march_turn_cost INTEGER NOT NULL,
    ration_cost INTEGER NOT NULL,
    highway_type TEXT NOT NULL,
    is_paved BOOLEAN NOT NULL DEFAULT 1
);

-- ============================================================================
-- 15. PASS FORTRESSES (CONCENTRIC GATING STATE MACHINE)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pass_fortresses (
    pass_id TEXT PRIMARY KEY,
    pass_level INTEGER NOT NULL,
    state TEXT NOT NULL,
    pass_policy TEXT NOT NULL DEFAULT 'ALLIANCE_ONLY',
    owner_faction TEXT DEFAULT NULL,
    current_hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    footprint_x_min INTEGER NOT NULL,
    footprint_x_max INTEGER NOT NULL,
    footprint_y_min INTEGER NOT NULL,
    footprint_y_max INTEGER NOT NULL,
    toll_fee_gold INTEGER NOT NULL DEFAULT 50,
    chronicle_unseal_step INTEGER NOT NULL DEFAULT 0
);

-- ============================================================================
-- 16. CORRIDOR SUPPLY ROUTES (SUPPLY LINE INTEGRITY)
-- ============================================================================
CREATE TABLE IF NOT EXISTS corridor_supply_routes (
    route_id TEXT PRIMARY KEY,
    root_node_id TEXT NOT NULL REFERENCES strategic_nodes(node_id),
    target_node_id TEXT NOT NULL REFERENCES strategic_nodes(node_id),
    faction TEXT NOT NULL,
    integrity_percentage REAL NOT NULL DEFAULT 1.00,
    status TEXT NOT NULL DEFAULT 'HEALTHY',
    turns_under_contestation INTEGER NOT NULL DEFAULT 0,
    path_tiles_json TEXT NOT NULL
);

-- ============================================================================
-- 17. REGIONAL SUBSTRATE (ENTON RUPTURE & GLASSING HYSTERESIS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS regional_substrate (
    chunk_coord TEXT PRIMARY KEY,
    stability_index REAL NOT NULL DEFAULT 1.0,
    glassing_turns_remaining INTEGER NOT NULL DEFAULT 0,
    cumulative_ruptures_in_act INTEGER NOT NULL DEFAULT 0,
    is_void_ruin INTEGER NOT NULL DEFAULT 0
);

-- ============================================================================
-- 18. CHRONICLE KALPA LEDGER (BOARD-CLEARING & MOLT CYCLES)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chronicle_kalpa_ledger (
    kalpa_cycle_number INTEGER PRIMARY KEY,
    started_at_timestamp TEXT NOT NULL,
    completed_at_timestamp TEXT DEFAULT NULL,
    tiles_total INTEGER NOT NULL DEFAULT 10000,
    tiles_conquered_by_regime INTEGER NOT NULL DEFAULT 0,
    conquest_saturation_percentage REAL NOT NULL DEFAULT 0.0,
    was_molt_triggered BOOLEAN NOT NULL DEFAULT 0,
    subterranean_scars_persisted INTEGER NOT NULL DEFAULT 0,
    reality_law_state TEXT NOT NULL DEFAULT 'NOMINAL'
);

-- ============================================================================
-- 19. COMBAT ENCOUNTERS (TACTICAL SKIRMISH ARENAS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_encounters (
    encounter_id TEXT PRIMARY KEY,
    world_node_id TEXT NOT NULL REFERENCES strategic_nodes(node_id),
    grid_x INTEGER NOT NULL,
    grid_y INTEGER NOT NULL,
    terrain_type TEXT NOT NULL,
    weather_state TEXT NOT NULL,
    atmospheric_density REAL NOT NULL DEFAULT 1.0,
    elevation_level INTEGER NOT NULL DEFAULT 0,
    turn_counter INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'VICTORY', 'DEFEAT', 'RETREAT', 'FLED')),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- ============================================================================
-- 20. COMBAT COMMANDER SQUADS (RISE OF KINGDOMS DUAL-COMMANDERS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_commander_squads (
    squad_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id) ON DELETE CASCADE,
    faction TEXT NOT NULL,
    primary_commander_id TEXT NOT NULL REFERENCES character_genesis(character_id),
    secondary_commander_id TEXT REFERENCES character_genesis(character_id),
    troop_count INTEGER NOT NULL DEFAULT 1,
    current_rage INTEGER NOT NULL DEFAULT 0 CHECK(current_rage >= 0 AND current_rage <= 1200),
    turn_t_skill_queued TEXT,
    turn_t1_skill_queued TEXT,
    effective_affection REAL NOT NULL DEFAULT 50.0,
    discord_flag INTEGER NOT NULL DEFAULT 0
);

-- ============================================================================
-- 21. COMBAT DMW POOLS (CRISIS CORE RESONANCE TOKENS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_dmw_pools (
    pool_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id) ON DELETE CASCADE,
    squad_id TEXT NOT NULL REFERENCES combat_commander_squads(squad_id) ON DELETE CASCADE,
    focus_tokens INTEGER NOT NULL DEFAULT 0 CHECK(focus_tokens >= 0),
    echo_tokens INTEGER NOT NULL DEFAULT 0 CHECK(echo_tokens >= 0),
    surge_tokens INTEGER NOT NULL DEFAULT 0 CHECK(surge_tokens >= 0),
    catharsis_tokens INTEGER NOT NULL DEFAULT 0 CHECK(catharsis_tokens >= 0),
    total_tokens INTEGER GENERATED ALWAYS AS (focus_tokens + echo_tokens + surge_tokens + catharsis_tokens) VIRTUAL,
    primed_companion_id TEXT REFERENCES character_genesis(character_id),
    primed_probability REAL DEFAULT 0.0
);

-- ============================================================================
-- 22. COMBAT WEAPON DURABILITY (SOMATIC CONTACT WEAR)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_weapon_durability (
    item_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    current_durability INTEGER NOT NULL,
    max_durability INTEGER NOT NULL,
    is_chipped INTEGER NOT NULL DEFAULT 0,
    wear_resistance REAL NOT NULL DEFAULT 1.0,
    updated_at REAL NOT NULL
);

-- ============================================================================
-- 23. COMBAT ACTION LEDGER (CRYPTOGRAPHIC 2RN ACTION TRAIL)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_action_ledger (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT UNIQUE NOT NULL,
    encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id) ON DELETE CASCADE,
    turn_number INTEGER NOT NULL,
    attacker_id TEXT NOT NULL REFERENCES character_genesis(character_id),
    defender_id TEXT NOT NULL REFERENCES character_genesis(character_id),
    technique_compound_hash TEXT NOT NULL,
    is_somatic_contact INTEGER NOT NULL,
    display_hit INTEGER NOT NULL,
    roll_1 INTEGER NOT NULL,
    roll_2 INTEGER NOT NULL,
    true_hit_roll INTEGER NOT NULL,
    is_hit INTEGER NOT NULL,
    is_crit INTEGER NOT NULL,
    gambit_declared TEXT CHECK(gambit_declared IN ('NONE', 'VAJRA_READ', 'ROLL_AND_COUNTER', 'BRACE_SHIELD')),
    gambit_vector_guess TEXT,
    gambit_success INTEGER NOT NULL DEFAULT 0,
    damage_inflicted REAL NOT NULL,
    recoil_damage REAL NOT NULL DEFAULT 0.0,
    durability_loss INTEGER NOT NULL DEFAULT 0,
    rage_generated INTEGER NOT NULL DEFAULT 0,
    tokens_generated_json TEXT,
    prev_hash TEXT NOT NULL,
    action_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

-- ============================================================================
-- 24. COMBAT CASUALTY LEDGER (3-TIER CASUALTY ECONOMICS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS combat_casualty_ledger (
    casualty_id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id),
    battalion_id TEXT NOT NULL,
    total_engaged INTEGER NOT NULL,
    slight_wounded INTEGER NOT NULL,
    severe_wounded INTEGER NOT NULL,
    killed_in_action INTEGER NOT NULL,
    stagnant_convalescent INTEGER NOT NULL DEFAULT 0,
    hospital_capacity_at_resolution INTEGER NOT NULL,
    created_at REAL NOT NULL
);

-- ============================================================================
-- 25. STAGNANT CONVALESCENCE ROSTER (ANTI-OVERFLOW TRIAGE)
-- ============================================================================
CREATE TABLE IF NOT EXISTS stagnant_convalescence_roster (
    convalescent_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    origin_encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id),
    current_hp INTEGER NOT NULL DEFAULT 1,
    daily_ration_upkeep REAL NOT NULL DEFAULT 2.0,
    days_in_stagnation INTEGER NOT NULL DEFAULT 0,
    lockout_status TEXT NOT NULL DEFAULT 'LOCKED' CHECK(lockout_status IN ('LOCKED', 'ADMITTED', 'RECOVERED', 'STARVED')),
    admitted_hospital_node_id TEXT REFERENCES strategic_nodes(node_id),
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- ============================================================================
-- 26. MEMORIAL KIA LEDGER (PERMANENT KIA INSCRIPTION & EULOGY)
-- ============================================================================
CREATE TABLE IF NOT EXISTS memorial_kia_ledger (
    inscription_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES character_genesis(character_id),
    character_name TEXT NOT NULL,
    encounter_id TEXT NOT NULL REFERENCES combat_encounters(encounter_id),
    slain_by_entity_id TEXT NOT NULL,
    fatal_technique_hash TEXT NOT NULL,
    grief_berserk_triggered INTEGER NOT NULL DEFAULT 0,
    bereaved_companions_json TEXT NOT NULL,
    sha256_eulogy_seal TEXT NOT NULL,
    recorded_at REAL NOT NULL
);

-- ============================================================================
-- 27. PRIVATE ACTION QUEUE (STAR OCEAN CAMPFIRE AGENDAS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS private_action_queue (
    pa_id TEXT PRIMARY KEY,
    originating_contact_event_id TEXT NOT NULL,
    source_character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    target_character_id TEXT NOT NULL REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    pa_title TEXT NOT NULL,
    tactical_agenda_source TEXT NOT NULL,
    tactical_agenda_target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued', 'active', 'resolved', 'dismissed')),
    priority_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 28. DIALOGUE SCENES (SCENE CONTEXT & RUPTURE PRESSURE)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dialogue_scenes (
    scene_id TEXT PRIMARY KEY,
    location_id TEXT NOT NULL,
    current_beat_index INTEGER NOT NULL DEFAULT 0,
    active_ambiguity INTEGER NOT NULL CHECK(active_ambiguity BETWEEN 0 AND 4),
    active_pressure INTEGER NOT NULL CHECK(active_pressure BETWEEN 0 AND 4),
    is_glassed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 29. DIALOGUE NODES (NARRATION BEATS & PHYSICAL ANCHORS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dialogue_nodes (
    node_id TEXT PRIMARY KEY,
    scene_id TEXT NOT NULL REFERENCES dialogue_scenes(scene_id) ON DELETE CASCADE,
    speaker_id TEXT NOT NULL REFERENCES character_genesis(character_id),
    narration_pre_beat TEXT NOT NULL,
    spoken_dialogue TEXT NOT NULL,
    physical_anchor_1 TEXT NOT NULL,
    physical_anchor_2 TEXT NOT NULL
);

-- ============================================================================
-- 30. DIALOGUE OPTIONS (CAPABILITY AFFORDANCE FILTER & DC CHECKS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dialogue_options (
    option_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL REFERENCES dialogue_nodes(node_id) ON DELETE CASCADE,
    display_order INTEGER NOT NULL,
    affordance_tag TEXT NOT NULL,
    declared_text TEXT NOT NULL,
    required_stat TEXT,
    min_stat_value INTEGER,
    required_scar_id TEXT,
    required_role TEXT,
    stat_check_key TEXT,
    skill_check_key TEXT,
    base_dc INTEGER,
    physical_anchor TEXT NOT NULL,
    requires_state TEXT NOT NULL,
    grounds_state TEXT NOT NULL,
    next_node_id TEXT
);

-- ============================================================================
-- 31. DIALOGUE CONSEQUENCES (CAUSAL CONSEQUENCE GRAPH MUTATIONS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dialogue_consequences (
    consequence_id TEXT PRIMARY KEY,
    option_id TEXT NOT NULL REFERENCES dialogue_options(option_id) ON DELETE CASCADE,
    on_branch TEXT NOT NULL CHECK(on_branch IN ('success', 'complication', 'critical_failure')),
    approval_deltas TEXT NOT NULL DEFAULT '{}',
    faction_disposition_deltas TEXT NOT NULL DEFAULT '{}',
    grid_displacement TEXT NOT NULL DEFAULT '{}',
    inflicted_pressure INTEGER NOT NULL DEFAULT 0,
    spawn_echo_id TEXT
);

-- ============================================================================
-- 32. CHARACTER VISUAL PROFILES (PROCEDURAL ANTI-SAME-FACE SEEDS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS character_visual_profiles (
    character_id TEXT PRIMARY KEY REFERENCES character_genesis(character_id) ON DELETE CASCADE,
    visual_seed INTEGER NOT NULL,
    age_years INTEGER NOT NULL,
    silhouette_id TEXT NOT NULL,
    mandibular_id TEXT NOT NULL,
    nasal_id TEXT NOT NULL,
    zygomatic_id TEXT NOT NULL,
    ocular_id TEXT NOT NULL,
    sartorial_code_id TEXT NOT NULL,
    ansi_fg_color INTEGER NOT NULL DEFAULT 254,
    ansi_bg_color INTEGER NOT NULL DEFAULT 236
);

-- ============================================================================
-- PERFORMANCE & INTEGRITY INDICES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_scars_char ON character_scars(character_id);
CREATE INDEX IF NOT EXISTS idx_relational_target ON relational_ledger(target_character_id);
CREATE INDEX IF NOT EXISTS idx_char_techniques_char ON character_techniques(character_id);
CREATE INDEX IF NOT EXISTS idx_kata_decks_char ON martial_kata_decks(character_id);
CREATE INDEX IF NOT EXISTS idx_char_talents_char ON character_talents(character_id);
CREATE INDEX IF NOT EXISTS idx_quarried_shards_owner ON quarried_shards(owner_id);
CREATE INDEX IF NOT EXISTS idx_satori_char ON satori_epiphanies(character_id);
CREATE INDEX IF NOT EXISTS idx_tiles_coords ON world_tiles(x, y);
CREATE INDEX IF NOT EXISTS idx_tiles_chunk ON world_tiles(chunk_id);
CREATE INDEX IF NOT EXISTS idx_tiles_faction ON world_tiles(controlling_faction);
CREATE INDEX IF NOT EXISTS idx_nodes_coords ON strategic_nodes(x, y);
CREATE INDEX IF NOT EXISTS idx_edges_origin ON strategic_edges(origin_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_dest ON strategic_edges(destination_node_id);
CREATE INDEX IF NOT EXISTS idx_supply_root ON corridor_supply_routes(root_node_id);
CREATE INDEX IF NOT EXISTS idx_supply_target ON corridor_supply_routes(target_node_id);
CREATE INDEX IF NOT EXISTS idx_encounters_node ON combat_encounters(world_node_id);
CREATE INDEX IF NOT EXISTS idx_squad_encounter ON combat_commander_squads(encounter_id);
CREATE INDEX IF NOT EXISTS idx_dmw_squad ON combat_dmw_pools(squad_id);
CREATE INDEX IF NOT EXISTS idx_weapon_durability_char ON combat_weapon_durability(character_id);
CREATE INDEX IF NOT EXISTS idx_combat_ledger_enc ON combat_action_ledger(encounter_id);
CREATE INDEX IF NOT EXISTS idx_combat_ledger_turn ON combat_action_ledger(turn_number);
CREATE INDEX IF NOT EXISTS idx_casualty_enc ON combat_casualty_ledger(encounter_id);
CREATE INDEX IF NOT EXISTS idx_stagnant_status ON stagnant_convalescence_roster(lockout_status);
CREATE INDEX IF NOT EXISTS idx_memorial_char ON memorial_kia_ledger(character_id);
CREATE INDEX IF NOT EXISTS idx_pa_queue_source ON private_action_queue(source_character_id);
CREATE INDEX IF NOT EXISTS idx_pa_queue_target ON private_action_queue(target_character_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_nodes_scene ON dialogue_nodes(scene_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_options_node ON dialogue_options(node_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_consequences_opt ON dialogue_consequences(option_id);
