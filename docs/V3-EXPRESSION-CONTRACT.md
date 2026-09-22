# V3: recorded experience changes a later operation

V3 adds a bounded development loop to V2: record a contribution, observe later evidence about its outcome, propose a scoped lesson, explicitly qualify it, and apply it to a later matching task. A qualified lesson changes the parameters of the existing registered operation. This produces an observable difference in calculation or checking, without replacing the character's base method or inventing competence.

For example, a fixed method initially ranks hypothetical editing plans by recorded time cost. Later feedback motivates an operator-reviewed lesson for the exact context `{"priority":"detail"}`: rank those same candidate inputs by recorded check count instead. With the task, base method, method assignment and world revision held constant, qualifying the lesson changes the chosen candidate. Renaming a lesson or appending a reflection alone does not constitute demonstrated development.

## Task context and scope

Tasks may supply `context`, a map of at most 32 named scalar values. Nested objects, arrays, nonfinite numbers and oversized strings are rejected. Existing V2 tasks may omit it; when no lesson applies, their calculation and output structure remain unchanged.

Lesson scope matches the exact task domain, bound character node, branch, workspace, method revision, current assignment and evidenced context. Context is a full-map match in V3, rather than a prediction about unseen combinations: extra or missing keys do not match, a missing key does not equal explicit null, and booleans do not equal numbers. Broadening a lesson's scope requires a new supported declaration and review.

## Application boundary

```python
from kageyoni.intelligence.development import Development

selection = Development(engine).apply(
    branch, character_id, task_domain, context, methods,
    viewer=viewer, workspace_id=workspace_id,
)
```

`Learning.applicable` supplies only current, qualified, visible lessons with fresh outcome evidence. `Development` checks the application scope again, validates the replacement parameters using the operation registry, and produces explicit effective operations. `Expression.prepare` runs this inside the same transaction snapshot as source visibility, current method assignments and candidate inputs.

The lesson replaces the operation's complete `params` object. It cannot change the operation kind, remove the base method's preconditions, change checking obligations, grant a world ability, or rewrite the stored method revision. The original method remains available in the prepared packet with its original digest; effective operations are separate.

If multiple qualified lessons request different parameters for the same method, preparation is blocked with the conflicting lesson IDs and no completed artifact. Matching parameter substitutions apply once and retain all provenance. Their count is not treated as independent corroboration or additional authority.

## Evidence and revision binding

Each selected lesson contributes an exact binding containing its stable ID, revision, content digest, review revision and review digest, target method revision, evidence digest and retained counterevidence digest. Its current supporting source references join the task and method dependency references. Historical contrary references have a separate binding: they retain their observed versions and require continuing visibility, rather than silently becoming current supporting facts. The prepared packet also records the base and effective operations.

Qualifying, contesting, retiring or revising a lesson changes what is eligible. A previously prepared packet cannot silently execute under a different set of lessons or review decisions. A changed supporting source, revoked method assignment, new incompatible method revision, hidden evidence or unmatched context prevents reuse. A method that is revoked and later requalified requires a fresh lesson review before the old lesson applies again.

The evidence history remains durable. A contrary observation can contest a lesson; its intervention then stops affecting later matching tasks. Revising an interpretation preserves the old revision and its supporting and contrary evidence. The application layer never infers that a logged success automatically teaches the node.

## Meaning of the result

The artifact includes the calculated result and the explicit development trace when a lesson applies. The outcome of the registered calculation can be complete while the user's broader task objective remains unresolved. Outcome interpretation, causal attribution, context meanings and lesson qualification remain attributed operator judgments. Mechanical checks establish exact recorded inputs, scope, current evidence and the actual operational change; they do not independently prove a theory of the world or a character's mastery.

Focused development tests exercise the complete recorded-outcome/review/application path, a fixed-method causal control, proposal without qualification, irrelevant contexts, conflicting lessons, suspended and retired lessons, method revision pins, hidden lessons, corrected feedback, stale preparation, and reopening. All observations and characters in these tests are synthetic disposable fixtures; no campaign events are advanced by the test suite.
