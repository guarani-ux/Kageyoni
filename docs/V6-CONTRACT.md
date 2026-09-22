# V6 collective contribution contract

`Network.run(branch, request_id, participants, viewer=None, workspace_id=None)`
executes configured persistent character nodes over the **same task**. Participants
are `{character_id, task}` objects; only `method_ids` may differ between tasks.
The world route uses V2/V3 Contributions and inherits source visibility,
qualification, stale-evidence checks and scoped lesson application.

Each successful node supplies its actual operation body. The engine coordination
identity `engine:kageyoni` receives bodies, compares rankings, preserves conflicting
rank orders and calculates an equal-weight rank-sum result over shared candidates.
A lexical tie break is explicit. This is a registered calculation, not semantic
prose synthesis or independent expert judgment. Unsupported/no eligible output
returns `blocked` with an action reason. Waiting node contributions remain visible
in the collective ancestry; they cannot silently vote.

Identical checked calculation outputs count once, even with different method
provenance or character identities. This conservative rule can collapse coincident
outputs. Source snapshots are deduplicated separately and **never described as
independent corroboration**. Bodies, receptions, disagreements, calculated output
and task/contribution ancestry are persisted atomically. Retrying an exact request
returns its original run; changed payloads are rejected. Owner-only contributions
cannot be exposed to character viewers through a collective result.

`Network.compose(branch, request_id, workspace_id, draft_ids, synthesis=None,
viewer=None)` handles V5 document contributions. It requires at least two distinct
persistent nodes with qualified destination transfers and actual method effects.
It retains the actual text, source references, unknowns, obligations and method
differences of all drafts. Without synthesis it returns a durable `waiting` packet.
An operator supplies `{text, uses:[{draft_id, quote}], rationale}`. Every draft
must have an exact excerpt of at least 32 characters (or its entire shorter body)
that occurs in both its source and the output.
The resulting artifact is stored by V5 Artifacts. This verifies body consumption;
it does **not** prove that the authored interpretation is insightful or true.
Disagreements and missing evidence remain attached to the result.

`read`, `list`, `read_composition` expose durable authorized history. `compare`
requires an exact single-node participant/task retained in the multi-node trial.
Its explicit acceptable-candidate criterion records measured candidate acceptance
and actual contribution/calculation counts. It does not infer real-world quality,
elapsed time or cognitive superiority. `record_coordination_lesson` stores an
operator-reviewed, scoped observation under the separate engine identity.
Qualification requires a positive difference on the supplied criterion; rejected
or proposed observations can preserve unsuccessful trials. Lessons do not silently
activate a routing policy; controlled policy evolution belongs to V8.

## Reproducible evaluation

Run `python -m examples.v6_demo --output /new/directory`. The isolated fixture uses
speed, check-coverage, copied-speed and unconfigured nodes. A single speed method
selects the fast option. Combining conflicting preferences ties their rank sums;
the declared lexical rule selects the careful option. The fixture records positive,
negative and no-help acceptance criteria, rather than assuming the network is
better. The changed output is a mechanism demonstration, not proof of creative
advantage. The database and JSON include actual bodies and receipts, so the
comparison is inspectable after restart or restore.
