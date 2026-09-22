# History

History is append-only. It records what happened, what changed, and how confidently the event is established.

## Event contract

```yaml
id: event.<stable_id>
sequence: 0
timestamp: null
scene: scene.<stable_id>
type: discovery | decision | dialogue | movement | attack | damage | ability_change | relationship_change | objective_change | world_change | artifact_created
actors: []
targets: []
action: ""
result: ""
cause: []
effects: []
costs: []
evidence: []
epistemic_status: confirmed | reported | inferred | contested | unknown
reversibility: reversible | conditionally_reversible | irreversible | unknown
durability: temporary | scene | persistent | world_defining
consequence_links: []
supersedes: []
```

## State rules

- Never delete a consequential event to repair continuity.
- Corrections create a new correction event with provenance.
- A failed action is still a historical event.
- Facts discovered by a character are distinct from facts established for the world.
- Every major scene should leave at least one durable state change.
