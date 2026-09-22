# V4: character introduction and authored encounters

This release supplies provisional character creation and playable authored interaction policies. Characters retain stable IDs, known/unknown/proposed declarations and separate Named Will interpretation and Primordial definition references. No personality label creates a stat, mastery score, innate mechanic or accepted Will technique.

`Genesis(engine).introduce(branch, request_id, expected_revision, profile, viewer=None)` calls the existing character API, commits permitted supplied details through `Engine.apply`, and binds a persistent node in the same unit of work. `read(branch, character_id, viewer=None)` returns the permitted profile and normal character view. Introduction creates fictional events only when explicitly called. Installing the migration creates none.

The smallest profile is `{"label":"Unnamed traveler"}`. Optional fields are `character_id`, `canonical_name`, `entity_kind`, `existence`, `visibility`, `audience`, `basis`, `motivation`, `communication`, `innate_will`, `stats`, `abilities`, `named_will` and `primordial_will`. Motivation, communication and innate Will use `{status, statement}`; absent values stay `{status:"unknown", statement:null}`. Existence defaults to provisional. A label is not automatically a canonical name.

- Stats use `{property_id, definition_version, status, value, unit, basis}` and existing registered definitions. Known authored values and explicit unknowns enter the existing property store. Proposed values remain declarations and cannot fund an ability. Wrong types, units or applicability reject the transaction.
- Abilities use `{ability_id, status, basis}` referencing an existing ability. A supplied known capability preserves unknown mastery; proposed/unknown capabilities grant nothing.
- Named Will uses `{status, name, interpretation}` and is the bearer's interpretation. Primordial Will separately uses `{status, definition_ref:{id,version}|null, basis}`. A reference must resolve to an existing exact primordial definition. Contradictory interpretation does not rewrite that definition, and introduction does not create an accepted mechanical expression.

## Encounter API

`Encounters` lives in `kageyoni.workspaces.world` (`WorldWorkspace` is an alias).

| Operation | Arguments after the engine constructor | Result |
|---|---|---|
| `define` | `definition_id, version, spec, request_id, viewer=None` | Immutable authored version and digest |
| `start` | `branch, definition_id, definition_version, encounter_id, request_id, expected_revision, participants, viewer=None, continuation_of=None, evidence_refs=None` | Pinned instance and initial state receipt |
| `inspect` | `branch, encounter_id, viewer=None` | Current phase, objective outcome, loops, pending actor/choice and typed available actions |
| `act` | `branch, encounter_id, action_id, request_id, expected_revision, fields=None, viewer=None, expected_encounter_revision=None` | Exactly-once transition and any actual world receipt |

`expected_revision` is the world branch revision. `expected_encounter_revision` additionally pins an operational state, including a suspended judgment that has not advanced the world. IDs refer to characters, not their display names; Unicode names and later renaming do not transfer speaker authority.

Definitions contain `title`, `roles`, `initial_state`, `states`, `loops`, `actions`, plus optional `visibility`, `scene_id` and `max_steps`. A state has `{phase,outcome,actions}`. Every definition starts active, with an unresolved objective; terminal states expose no old choices. A loop has `{id,kind,required,depends_on,continuable}` and optional `parent,cancellable`. Required child obligations cannot disappear when their parent resolves. A continuable loop detaches only with an explicit existing world-record link. Containment and dependency cycles are checked separately.

Each action has `{label,actor_role,kind,payload,resolve_loops}`, a `next_state` or outcome-to-state mapping, and optional requirements, detachments and reasoned cancellations. Payload placeholders are exact JSON objects `{"$role":"traveler"}` and `{"$encounter":"record-suffix"}`; ordinary prose is never string-substituted or evaluated as code.

Requirements compare exact permitted world fields with typed values: false is distinct from zero, and a hidden reference projected as null does not become evidence of a known null. The immutable start event pins participant IDs and definition version; changed current projections fail validation rather than transferring a speaker's authority.

- `dialogue` uses `{text,act,mode,listener_roles}`. The existing writing brief supplies scope, the world engine validates a normal dialogue turn, and listeners receive hearing observations. Hearing does not establish agreement, trust or listener belief.
- `will` supplies an ordinary exact-version Will attempt without caller-owned execution IDs. The existing Will engine checks ownership, conditions, targets, costs, effects and durable rolls. Caller-injected deltas are rejected.
- `event` supplies existing changes, properties, consequences, observations or processes. Existing world validation applies. Actor-visible actions cannot target hidden record references.
- `judgment` supplies `{question,choices:[{id,label,next_state}],unknowns}`. Its first call saves a waiting packet. A later request with `{choice_id,rationale}` records an explicit choice. Invalid responses, stale revisions and mismatched actors do not advance the world.

An unknown action creates a bounded waiting inquiry without inventing effects. Existing authored choices remain available. A finite step budget blocks cyclic/repetitive policies while retaining their unresolved objectives. New episodes may link to concluded encounters only with exact evidence created after the earlier closure; the old outcome is retained.

## Transactions and recovery

Will preparation is an existing standalone transaction and can leave a reserved roll or prepared attempt after interruption. The encounter calls preparation before its final unit of work, then rechecks both revisions. Applying the prepared world effect and advancing the encounter share one transaction. A late failure rolls back both; retry reuses the saved preparation and roll. `act` therefore requires no caller transaction to be open. Other actions use the same final atomic boundary.

Encounters keep immutable definition and transition history plus a checked current projection. Duplicate requests return their prior receipt and never replay costs, dialogue or consequences. A new request with an already-settled action is rejected. Reading does not re-run old judgments or rewrite the state under newer definitions.

## Executable demonstration

Run `python -m examples.v4_demo --output NEW_DIRECTORY`. The separate synthetic world offers a bridge/ferry route, safe-withdrawal dialogue during an unresolved defense, a real registered Will technique with resource cost, a saved interruption, a response and consequential departure. Its promise remains open through an explicit continuation link. The alternative counteroffer path requests bounded human judgment. No AI API is used.

`examples.v4_demo.setup(engine)` exposes the fixture on an existing disposable engine for integrated demonstrations. It must not be used on a campaign database. `tests/test_v4_world.py` exercises real SQLite state, rollback after Will application, replay, stale/invalid responses, nested closure, cycle budget, actor identity, unknown stats and divergent methods under the same Primordial Will.

The demonstrated intelligence is authored routing and preserved experience. Open-ended prose quality, motives, practical judgment, trust and new game mechanics still require explicit human or authorized host interpretation; successful execution does not infer them.
