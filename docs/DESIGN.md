# Engine design and boundaries

The build uses one SQLite database with normalized record projections and versioned auxiliary tables. The legacy domain model remains available for identity, nature, composition, relationships, politics, history, equipment, objectives, environment, and time. The runtime adds:

- `property_definitions`, `property_lifecycle`, `property_values`, `property_changes`, and `property_operations` for typed, versioned assignments;
- `rule_definitions`, `rule_dependencies`, `event_dependencies`, and `registry_*` for executable rule and implementation navigation;
- `event_resolutions`, `observations`, `choices`, and `event_aux_changes` for reproducible event evidence;
- `consequences`, `consequence_runs`, `processes`, `process_runs`, `process_subscriptions`, and `attention_scores` for durable downstream work;
- `entity_profiles`, `entity_links`, and `classification_claims` for composable entities and transformations;
- `will_definition`, `will_expression`, `will_technique`, `will_awakening`,
  `will_development`, `will_effect`, `will_contract_history`, and
  `will_attempts` for versioned Will structure, historical contracts, and
  durable engine-owned attempt reservations;
- `engine_versions` and `migration_checks` for compatibility and ordered upgrades.

Events are append-only and contain the branch revision, request key, command hash, causal IDs, world time, recording order, and before/after record images. Auxiliary state is also written inside the same transaction and has event-linked before/after images. A command can create a record and assign its properties in one atomic operation.

Action resolution has separate permission, probability, magnitude, cost, timing, and consequence stages. The engine does not make bridge capacity comparable to character strength merely because both happen to be numeric. A d20 is an uncertainty component; feasibility comes first, natural 20 has no special success rule, and a stable attempt ID prevents replacement rolls.

The event log is the source of durable causal evidence. Current projections can be rebuilt from a branch snapshot and later event rows. Direct compatibility `set_property` assignments are audited but are deliberately marked as a replay limitation; normal play uses event-mediated `properties` assignments. Revisions of definitions never rewrite old event payloads or random outcomes.

Will preparation is not a fictional event: it records exact contracts, inputs,
judgments, and any reserved roll in `will_attempts`. Only the atomic
`will_attempt` commit appends history and applies resolver-derived changes.

Background processes may be scheduled, event-subscribed, elapsed-time, threshold, aggregate, or judgment-bound. The explicit `advance_simulation` operation evaluates supported rates over an interval, records the run key and outcome, and preserves blocked or deferred work. There is no external scheduler and no simulation tick for each chat message.

Visibility is applied to records, properties, profiles, observations, processes, and session context. The same engine can produce GM or participant context, but free text and a host model still require care when the GM and an actor share a context window. Hidden facts can affect an authorized engine call without being included in an unauthorized view.

Branches copy state at a verified revision. Global auxiliary identifiers are namespaced in the child when the underlying legacy table has a global primary key. Parent records and causal source references remain available; no automatic merge is provided. Temporal corrections and rewinds are new events with explicit retained knowledge and effects.

The engine cannot infer arbitrary prose dependencies, decide canon authenticity, provide a universal physics model, or supply unresolved Kageyoni mechanics. Freedom’s numerical formula, restrained intelligence, detailed Haki mechanics, unknown clock conversions, and unsupported text consequences remain visible judgment boundaries.
