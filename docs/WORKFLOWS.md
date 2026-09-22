# Kageyoni Play and Maintain workflows

Release 7: use [PERSONALITY-SYSTEM.md](PERSONALITY-SYSTEM.md) together with
[CONNECTED-PLAY.md](CONNECTED-PLAY.md). Prefer `decision-propose` and
`decision-commit` for coordinated play; `dialogue-propose` compiles into that
same path. Personality context is captured automatically across combat,
travel, discovery, training, social and downtime. Installed skill instructions
were retained; this project guide contains the new workflow contract. The
older raw `workflow`/`apply` paths below remain trusted compatibility APIs and
do not enforce every coordinated dialogue or personality check.

The two installed skills are thin coordination layers over one engine. They do not contain a second database, a hidden campaign save, or independent rules.

## Play

At session opening, call `session` with a branch and optional viewer/scene. Check `compatibility.ok`, revision, visible context, pending consequences, and due or blocked processes. Read a GM context only when the acting role is authorized to see it. The context separates records, properties, entity profiles, observations, and background processes; it does not turn hidden facts into player knowledge.

Before presenting a constrained menu, call `opportunities`. It returns situation-derived routes, hazards, conditions, deadlines, and an explicit open action. Unknown options remain available as free-form intent. Relevance scores affect presentation only and never permission, probability, magnitude, cost, timing, or consequences.

For an action, the skill supplies intent, method, participants, targets, stakes, and a stable request ID. It calls `propose_action` or a focused activity module (`combat`, `travel`, `discovery`, `training`, `social`, or `downtime`). The module selects context and declares dependencies; it does not own a second clock, cost ledger, or random roll. The engine resolves the stages separately:

1. Permission and feasibility.
2. Probability, including one optional d20 uncertainty component.
3. Magnitude.
4. Costs and exposure.
5. Timing.
6. Structured persistent consequences.

Twenty is only the largest face of a d20. It is not a maximum total and is not an automatic success. The engine checks feasibility before rolling, records the random result under a stable attempt ID, and returns the same result on a retry. A changed situation requires a new attempt ID and an explicit explanation.

The skill previews the exact command, supplies bounded GM judgments in `judgment` or `assumptions`, and applies that command unchanged after review. A stale revision is a reread-and-reconsider point. A repeated request with the same payload returns its existing receipt. A different payload under the same request ID is rejected.

### Will operations

Will uses six additive, versioned record domains while retaining the legacy
flat `will` record. `will_definition` is independent of a bearer;
`will_expression` binds a definition to one bearer; techniques, awakenings,
development claims, and persistent effects remain separate records. Every
contract carries `will-contract/0.1`, immutable identity/version, evidence, and
an explicit proposed/accepted design status. Exact record and rule references,
ancestry cycles, target scope, units, costs, and applicability are validated by
the engine.

Use `will-prepare` with the exact expression and technique versions. It checks
the bearer, evaluates typed permission conditions before randomness, pins the
input snapshot and one d20 result when required, and stores a non-fictional
attempt reservation. Use `will-apply` to commit that unchanged reservation as
one `will_attempt` event. The engine owns resolver-derived changes and rejects
stale revisions, altered outcomes, replaced rolls, or caller-injected state
deltas. Proposed mechanics and unresolved freedom, restrained-intelligence,
Haki, and awakening meanings remain judgment-bound.

Use `record_discovery` for witnessed information. The engine distinguishes an event, an observation, a belief, a rumor, and an institutional record. Use `advance_simulation` for explicit fictional time; real-world waiting, reloads, or tool calls do not advance the clock. Apply due structured consequences with `consequences`. Unsupported text effects return a pending judgment instead of an invented state change.

Play may include ordinary competence, quiet scenes, beauty, and dialogue without a roll. NPCs retain their own knowledge, priorities, disagreements, refusals, and actions. Family or collective records do not erase member-level choices.

## Activity modules

Each module is loaded only when its trigger matches the situation. The engine registry contains the verified module IDs and compatible runtime versions.

| Module | Trigger and focus | Typical dependencies | Shared ownership |
| --- | --- | --- | --- |
| `kageyoni.combat` | contested harm, defense, positioning, or surrender | participant context, capabilities, injuries, action rules | one resolution, one roll, one cost set |
| `kageyoni.travel` | movement, routes, navigation, exposure, or deadlines | locations, routes, environment, time | one movement event and one time advance |
| `kageyoni.discovery` | search, observation, investigation, or recognition | visibility, knowledge, environment, discovery rules | one observation or discovery result |
| `kageyoni.training` | practice, learning, demonstrated capability, or recovery | capability, fatigue, progression, costs | one progression judgment and any declared process |
| `kageyoni.social` | negotiation, trust, obligation, refusal, or collective response | directional relationships, knowledge, political conditions | one social resolution; no automatic agency score |
| `kageyoni.downtime` | rest, repair, waiting, recovery, or quiet work | injuries, fatigue, resources, scheduled processes | one explicit interval; no passive repeated rolls |

Mixed situations use one action command with several module dependencies. The engine rejects duplicate contribution IDs, duplicate property assignments, incompatible units, and incompatible module versions.

## Maintain

Maintain operations are engine calls, not fictional events. Use `maintain` or the corresponding Python API for:

- `verify`, `backup`, `snapshot`, and `replay`;
- `validate_registry`, `dependencies`, and `registry_dependency`;
- `define_property`, `revise_property`, and `retire_property`;
- `add_rule` and `register_module`.

Adding a supported property is normally a registry content operation. A storage or constraint change requires an ordered migration with a predecessor, checksum, compatible engine version, backup, transactional application, and post-migration verification. Changed meaning, units, or type requires a new immutable property version. Retiring a property checks rules, derived properties, module manifests, workflows, registry entries, exports, and recorded event usage; historical references remain valid.

## What remains judgment

The skills may interpret intent, establish whether a fictional description is canonically plausible, choose a bounded consequence, or narrate. They cannot turn an unresolved freedom formula, restrained intelligence, Haki teaching mechanism, metaphysical rule, or unsupported prose effect into an enforced numeric rule without a recorded extension. The database never claims to discover arbitrary dependencies hidden in prose or external code.


Writing interface 1: session returns a writing contract; use `writing-brief`, then draft/review and `writing-publish`. Actual dialogue uses decision resolution; `dialogue-receive` records heard interpretation. See [WRITING-HANDOFF.md](WRITING-HANDOFF.md).
