# Structured command contract

The current workflow API is version `3`, runtime schema is `4`, and the compatible components are checked by `session` and module dependencies.

A normal action command contains:

```json
{
  "api_version": 3,
  "branch": "main",
  "expected_revision": 12,
  "request_id": "scene-12-crossing-attempt-1",
  "kind": "action",
  "actor": "actor-id",
  "narrative": "Bounded GM description of the intent and stakes",
  "changes": [],
  "dependencies": [{"kind": "module", "ref_id": "kageyoni.travel", "version": "1", "usage": "reads"}],
  "roll_ids": [],
  "resolution": {
    "feasible": true,
    "permission": {"allowed": true, "reasons": []},
    "probability": {"difficulty": 15, "modifier": 3, "roll_total": 11, "success": false},
    "magnitude": {"base": 0, "contribution": 1, "success": false},
    "cost": [],
    "timing": {},
    "consequences": []
  },
  "judgment": {},
  "assumptions": []
}
```

Use `properties`, `processes`, `observations`, `profiles`, `entity_links`, `classification_claims`, `choice`, and `consequences` only when their subjects and versions are present. A `choice` records intent, options, selection, knowledge, and agency state; it does not assign an agency number. A discovery uses an observation with an observer, subject, certainty, visibility, and audience.

The engine rejects stale branch revisions, wrong types, incompatible units, invalid applicability, missing references, duplicate contributions, duplicate property assignments, incompatible module versions, reused request IDs with a different payload, and reused random results. Preview is transactional; if it is followed by apply, submit the exact command and expected revision.

For Will play, use the structured operations rather than an improvised SQL
write:

```json
{
  "branch": "main",
  "attempt": {
    "request_id": "will-prepare-1",
    "attempt_id": "will-attempt-1",
    "expected_revision": 12,
    "actor": "character-id",
    "expression": {"id": "expression-id", "version": 1},
    "technique": {"id": "technique-id", "version": 1},
    "intent": "bounded fictional intent",
    "targets": ["target-id"],
    "randomness": {"mode": "d20", "roll_id": "will-roll-1", "difficulty": 15, "modifier": 2},
    "outcome_bindings": [
      {"outcome": "success", "effect_indexes": [0], "cost_ids": []},
      {"outcome": "failure", "effect_indexes": [], "cost_ids": []}
    ],
    "judgments": []
  }
}
```

`will-prepare` records no fictional event. `will-apply` receives the
`attempt_id`, a new event request ID, actor, narrative, and expected revision;
the engine derives allowed changes from the registered resolver and rejects an
altered success flag, roll, input snapshot, or caller-injected delta.

`advance_simulation` accepts an explicit clock and target tick. `consequences` applies only structured effects whose trigger is due. Pending judgments and deferred processes remain in the database and are reported. `history` is GM-only; `context`, `session`, `properties`, `processes`, and observations are viewer-filtered.
