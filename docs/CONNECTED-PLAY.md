# Connected play interface 1

Use this path for new coordinated scenes. Engine runtime 4 / API 3 and character
schema 1 remain supported; migration 006 adds `decision_interface=1` and durable
proposal reservations. No canonical events or character facts are invented by
the upgrade. The supplied campaign is a snapshot, not a claim to contain all
later story conversations.

## Session workflow

1. Open `session`, select branch, read character/context for the actor. Player
   and NPC context must use their own viewer. GM-only raw data is separate.
2. Interpret intent and propose a method. Populate a decision specification from
   established records and rule versions; include a recorded GM adjudication
   explaining the semantic connection between method and outcome. Free-form
   intent is supported; unimplemented mechanics require explicit extension or
   bounded judgment, not invented numbers.
3. `decision-propose` validates prerequisites, capabilities, custody, independent
   responses, Will ownership/learned technique, rules, costs and both outcomes.
   It records a reservation without a roll, story event, time or resource charge.
4. Present known stakes, costs and time to the player. Participant `decision-read`
   deliberately withholds GM assessment details. GM narration must be grounded in
   viewer context and never copy the raw assessment.
5. `decision-commit` requires actor and `accept:true`. It resolves one d20 (or no
   roll), applies the stored success/failure outcome and charges shared costs once.
   Applicable background effects/time are compiled into the same transaction.
6. `decision-settle` applies due supported consequences in bounded order. It stops
   at an unresolved effect and preserves it. Inspect pending processes before the
   next action; due consequences and unresolved background judgments block new
   coordinated progress.
7. Save/close. Reopen the same database and branch; retry by proposal ID recovers
   the result. State changes require a new assessment. Forks preserve proposal
   evidence/rolls as inherited metadata but invalidate their parent state binding:
   explicitly reassess with a new ID in the child branch.

## Executable commands

From the extracted project root:

```sh
python -m kageyoni --db build/kageyoni.sqlite session
python -m kageyoni --db build/decision-fixture.sqlite decision-read --input examples/decision-read.json
python -m kageyoni --db build/decision-fixture.sqlite decision-commit --input examples/decision-commit.json
python -m kageyoni --db build/decision-fixture.sqlite decision-settle
python -m unittest discover -s tests -v
```

The fixture database already contains the pending example proposal. To author a
proposal use `decision-propose --input examples/decision-propose.json` on its
matching initial state. Identical proposal retries recover the stored proposal.
Structured Python methods are `Workflows.decision_propose`, `decision_read`,
`decision_commit`, and `decision_settle`. Ordinary play does not require SQL.

## Mechanisms and boundaries

| Stage | Implemented connection |
| --- | --- |
| Permission | Exact record predicates, owned capabilities/custody, versioned boolean rules, Will definition invariants/trigger/channel access/effect preconditions, declared independent responses |
| Probability | Active typed property inputs through declared rule dependencies; integral `bonus` units; one d20 against explicit difficulty; no natural-20 override |
| Magnitude | Separate `effect`-unit rule result; explicit `{"decision_value":"magnitude"}` binding in outcome patch fields |
| Cost | Actor-owned resource rows with units, plus supported attempt/success/failure Will property costs; duplicate/conflicting writes rejected |
| Timing | Explicit clock and duration; process clock/unit declarations; supported elapsed effects; stops before intermediate scheduled/consequence deadlines or unresolved work |
| History | Atomic event, choices, exact inputs, specification, GM rationale, rule/property references, roll, state changes, and persistent/pending consequences |

The schema does not assign a freedom score or new Haki rules. Numeric advantages
never automatically control NPCs. NPC responses are supplied by the GM with
visible basis records; unknown knowledge references are rejected. Visibility of
a record is not proof the NPC would interpret it correctly. Motivation and
consent remain semantic judgments, not independently verified psychology.

Will support is intentionally bounded: mechanical admission conditions and
supported costs execute. The GM explicitly assesses targets, narrative scope,
resistance, channel breaks, postconditions and intended effects. Upkeep/release
cost lifecycles and target-paid costs require extensions. The earlier Will-only
resolution path remains legacy; this release does not claim to repair every
gap in it. Both outcome bundles must be authored and justified; the engine does
not derive every narrative consequence from a technique description.

Combat/travel/discovery/training/social/downtime labels coordinate through one
proposal; labels do not grant separate rolls, costs or modifiers. Individual
gameplay mechanics still need supported rules. Quiet scenes use uncertainty
`none`. This interface is trusted local GM tooling, not an authenticated service.
The old raw `apply` and legacy workflow paths remain available for maintenance
and compatibility; use this coordinated path for its additional guarantees.

Randomness persists before story application, so an interrupted apply cannot
reroll. A concurrent change invalidates the proposal and preserves its reserved
result. A changed-world attempt is explicitly a new ID; the trusted GM remains
responsible for authorizing that genuine new attempt. Proposal exploration is
read-only with respect to story state, although execution metadata is saved.

Background simulation is conservative. Cross-clock/unspecified processes,
unknown effects and conflicting simultaneous writes stop for judgment. Supported
process changes occur over a declared interval, with no invented intermediate
history. Reaction subscriptions mark further work due; there is no external
scheduler. A bounded settle operation can commit an initial portion of a chain;
its response reports the exact remaining work. Free-text triggers are not executable.

## Preservation and recovery

Before upgrade: `build/recovery/pre-decisions-v1.sqlite`. Automatic backup:
`build/kageyoni.sqlite.pre-v6.bak`. Migration 006 validates predecessor and checksum
and commits DDL/version/receipt together. Tests interrupt it and successfully
retry. Reopen with this engine to finish/retry an upgrade. Restore only to a NEW
path; never discard newer events by overwriting with a pre-upgrade backup.
After new writes, retain the newer ledger and reconcile explicitly; no automatic
downgrade is provided. Original source files and original project database remain
unchanged. Package contains the actual campaign, fixture, backups, code and tests.

## Evidence and remaining scope

`tests/test_decisions.py` has 15 focused tests; the whole suite has 128 tests.
Mixed travel/social/Will and water processing, downstream route difference,
independent refusal, hidden context, duplicate/units/ownership rejection,
interrupted commit, no natural-20 override, stale revisions/admin stat writes,
competing connections, deadlines, consequence processing, replay/snapshot/fork,
actual-save upgrade and failed migration recovery are exercised.

See `build/decision-test-results.txt` and `build/decision-delivery-verification.json`.
Only the local Python/SQLite execution environment is tested. Installed platform
skills have not been updated; the usable project workflow and this handoff are
the entry point. Latest-story reconciliation and fully autonomous NPC reasoning
remain outside the demonstrated build. These limits preserve the original larger
requirements as outstanding; passing this suite does not mark every earlier
world-simulation acceptance requirement complete.
