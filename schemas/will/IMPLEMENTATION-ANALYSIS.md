# Kageyoni Will system: schema and implementation analysis

Status: proposed contract 0.1; schemas delivered, engine integration not performed.
Inspected project: /workspace/scratch/05f434ae971b/kageyoni-local-dev

## Observed baseline

A SQLite online backup was taken using a read-only source connection. Engine.verify ran on that isolated copy because Engine construction opens WAL and runs schema/version initialization; invoking the CLI on the source would not be a strictly read-only inspection.

Observed: integrity OK; legacy schema 2, runtime schema 3, workflow API 2, property registry 1, resolution rules 1, story state 1. Main revision 1, one event, 165 records, zero property assignments, zero background processes. The only seeded Will is booder-will, borne by Alexandra, with descriptive principles and unresolved limits. This is a conservative seed, not evidence that current conversations or all eight Wills are installed. Existing regression suite: 90 tests passed. This is baseline evidence, not acceptance of the new design.

## Implementation findings

- model.py DOMAINS/REQUIRED are the source of generated SQL, domain validation and record serialization. Existing will combines bearer and nature; ability/capability/progression already represent practices. Preserve them and link them, rather than replacing campaign data.
- records/changes/events provide branch-scoped identity, epistemic status, visibility, revision and before/after history. New Will records should use this path, so forks and state reconstruction can reuse domain handling.
- property_definitions/property_values already support exact units, definition versions and unknown states. Use those for measured capacity/control/etc. Do not create competing stat columns or assign guessed numbers. Potency, capacity, control, stability and mastery remain proposed dimensions; map existing measures first.
- evaluate_rule supports threshold, sum, contextual and judgment paths. resolve_action collects rule_results but does not map a false threshold result into failed permission. Permission defaults to allowed. A stored rule is not an enforced Will constraint.
- resolve_action returns magnitude/cost/timing/consequence descriptions. It does not compile these into state mutations. apply accepts separately supplied changes. A Will compiler must derive and validate the committed changes against the resolved outcome; otherwise success/failure and state changes can diverge.
- Contribution IDs reject exact duplicates, not two differently named contributions from the same cause. Require causal-source IDs and a stage-specific stacking policy.
- resolve_action truncates the modifier to int when calling roll while calculating its total with the original number. Require integer probability modifiers in this contract until a versioned numeric policy resolves the discrepancy. Physical magnitude can remain real-valued with units.
- Activity preparation can accept a pre-supplied resolution when feasible is present. A new governed Will entrypoint must reject unverified caller success/permission and bind resolution receipts to exact input revisions. This is an engine-interface safeguard, not isolation from a host able to edit the database directly.
- roll is persisted during resolution before apply/preview. Retries need a stable attempt with input fingerprint; a preview must not generate a fresh roll. Admission/roll reservation and story-event commit are distinct lifecycle stages. A stale scene requires explicit reconsideration, not fishing for another result.
- replay reconstructs recorded after-images. It is not independent recalculation of historical mechanics. Preserve definitions, rolls and judgments so both reconstruction and optional historical validation are possible.
- Workflows.open_session hardcodes runtime_schema=3 and workflow_api=2. A later migration requires an explicit compatibility update. The proposed DDL deliberately does not claim a migration number or advance versions.

## Delivered schemas

All seven JSON schemas use the Draft 2020-12 vocabulary. Six describe domain payloads; will_attempt describes a new proposed workflow request, NOT a command accepted by the current CLI.

1. will_definition: nature, ancestry with evidence, classification, generative boundary, invariants, inherent limits. No bearer required. Primordial classification grants no automatic success or universal access.
2. will_expression: definition and bearer, interpretation, channels, stat bindings, learned techniques, condition, separate awakening access and mastery. Legacy will link preserves earlier records.
3. will_technique: derivation, practice status, activation, access medium, preconditions, effects, costs, resistance, resolution-policy version and termination.
4. will_awakening: qualitative change, substrates, eligibility, activation, transformed techniques, upkeep, interruption, others' agency, residue and recovery. Awakening need not create a domain. No universal eight-box threshold.
5. will_development: one evidenced developmental claim, dimension, stage, limitations, supporting events and mechanical unlocks. The eight dimensions are a proposed fictional framework, not Buddhist doctrine or eight numeric attributes. No automatic score or power reward for personal beliefs.
6. will_effect: active occurrence, source event, targets, anchors, clock, termination, process/consequence links and persistent residue. Distinguishes an effect ending from its consequences being undone.
7. will_attempt: actor intent, exact versions/revision, targets, contest, input snapshot, permission checks, random declaration, outcome bindings and bounded judgments. Same technique can serve different intentions.

Common record envelope stays in existing records: branch, ID, version, status, visibility, audience, evidence and updated_event. JSON payload identity/version must match that envelope. design_status is separate from epistemic status: accepting a design does not prove an in-world claim. Do not expose hidden ancestry or awakening eligibility through player errors or context.

## Storage strategy

proposed-will-tables.sql creates six additive domain projections with composite branch/ID FKs to records. domain-additions.json gives matching DOMAINS/REQUIRED entries. These are storage candidates, not an install script for the unchanged engine. Loading the DDL without extending model.py would leave unknown domains and incomplete runtime validation.

The contract JSON keeps evolving mechanics together; branch/domain/ref/version validation must be performed by the application. SQL json_valid only proves parseable JSON. It does not enforce JSON Schema or reference semantics. Add a pinned local schema validator or implement the emitted subset in the engine, without any network/model API requirement. The package's test helper is only a structural test utility.

Definition and technique revisions are immutable historical contracts: an edit creates a new version; old event versions remain retrievable from changes. Current projection is latest state. The adapter must implement get_contract(branch,id,version), never silently resolving an old reference to the latest definition. Forked records preserve inherited history; validate historical references against the fork lineage. Add a version lookup index if needed, not a second mutable history.

Polymorphic bearers intentionally match existing will support: character/location/faction. Other substrates can be targets. Adding items as actual bearers is an explicit ontology decision and migration, not an assumed extension.

## Required semantic constraints beyond JSON shape

- Resolve each contract reference in the correct branch/ancestor lineage and expected domain at its exact version; reject dangling, future, cross-branch and incompatible references.
- Definition ancestry must be acyclic. Expression bearers and technique owners must agree. Ability/capability links cannot silently grant a technique to another bearer.
- Rule mode requires a real rule; judgment mode requires a scoped recorded decision when used. Null rules and unknown scope never imply permission. Mechanical authority requires a supported resolver and all required inputs.
- Scope quantities must be nonnegative with compatible units; null means unresolved, not unlimited. Validate target kinds, distance/area/duration and channel availability before random resolution.
- Each stat binding has source, exact definition version, applicability and stacking identity. Missing/unknown/disputed/absent/not_applicable are distinct and cannot silently become zero.
- Costs are nonnegative debits with matching resource units. Attempt costs apply on failure when specified. Sustained costs use one clock and one process; insufficient resources block or interrupt unless an explicit overdraw rule exists.
- D20 requires non-null roll ID and integer difficulty; mode none requires both null and no fabricated roll. No-roll outcome is determined by a versioned rule or recorded judgment.
- Outcome effect indexes and cost IDs must exist. Outcome branches must cover every permitted result. Partial success is permitted only when the policy defines it; the current binary resolver does not supply it automatically.
- Resolve coexistence/opposition/interruption at a named target/change. Unknown interaction requests judgment. No global 'strongest Will wins' fallback.
- Condition failure on sustained effects changes active state; ending an effect does not delete previously realized damage, knowledge or environmental residue.
- Development unlocks and awakening access require linked evidence/authorized canon decision. A critical roll alone cannot grant them. Primordial status is not a roll modifier.

## Implementation sequence

1. Freeze contract and numeric policies. Keep the four user-selected Will identities separate from proposed mechanical definitions. Reconcile contemporary canon with this older seed before importing any roster/bearer claims. Do not invent bearers.
2. Back up and record versions/revision; generate a migration from the actual current predecessor. Update model.py, REQUIRED, generated schema.sql, migration code and compatibility manifest together. Preserve legacy records. No fictional awakening events during migration.
3. Implement validated historical contract access and domain payload/ref validation. Register schema/rule/module readers and writers with exact locators.
4. Implement Will admission: derive allowed effect, load inputs, evaluate preconditions/channels/scope, resolve bounded judgments. Bind approved admission to state and contracts before reserving randomness.
5. Implement resolution-policy compiler: convert recorded outcome into property assignments, domain changes, observations, costs and processes. Integrate with the existing atomic apply transaction. Reject caller-edited receipts/deltas and double charging.
6. Route combat/travel/discovery/training/social/downtime through one Will coordinator when applicable. Reuse one random attempt, shared resources and clock. Keep ordinary non-Will actions available.
7. Implement awakening/development state transitions and event subscriptions for interrupted channels, ended anchors and upkeep. Reuse processes/consequences. No real-time advancement or background daemon implied.
8. Run acceptance cases on isolated fixtures; only then offer campaign migration and persisted release. Preserve earlier saves and newer events throughout.

## Acceptance cases for the integrated release

A. Two bearers of one Will have distinct techniques; one cannot borrow the other's mastery.
B. A false mechanical precondition blocks before randomness and costs not due on rejection.
C. Impossible Witness inference stays unavailable after the highest d20 face.
D. Same attempt returns same roll; changed inputs under same attempt are rejected; stale revision never commits.
E. Failure charges only declared failure/attempt costs, with no success effect; duplicate commit does not charge twice.
F. Equal contributions with different labels but same causal origin cannot double-count.
G. Invalid scope units, negative costs, missing values and wrong target domains are rejected.
H. Coexisting effects remain; a specifically countered channel interrupts only dependent effects.
I. Awakening accessible but unstable differs from mastered; no automatic awakening from a high roll or eight dimensions filled.
J. Upkeep exhaustion, anchor destruction and voluntary release terminate correctly while retaining residue.
K. Training evidence can unlock a novel application without granting the whole domain or changing personality.
L. Unknown ancestry remains hidden; public session/diagnostic output does not leak secret conditions or process reasons.
M. Fresh schema, real-predecessor upgrade, branch isolation, historical versions, interruption rollback, backup/restore and recorded replay retain exact state without rerolling.
N. An altered success flag or caller-injected state delta is rejected at apply, not merely by the UI.

## Validation performed for this delivery

Existing 90-test regression suite passed. Baseline copy verified. Proposed DDL executed successfully on a copy with record count preserved and integrity/FKs clean. Local subset validator checked a noncanonical Witness example and rejected unknown fields, invalid classification, missing nature and invalid version. Full JSON Schema metaschema validation was unavailable in the installed runtimes; no conformance certification is claimed. Acceptance A–N remain implementation requirements, not tests already passed.

No live project code, canonical source, campaign state or GitHub repository was modified by this task.
