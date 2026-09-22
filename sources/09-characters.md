# Characters

## Record contract

Each character record describes identity, capability, condition, relationships, and unresolved state. Do not merge identity, power function, or systemic role into one field.

```yaml
id: character.<stable_id>
name: "Canonical name"
aliases: []
type: person | entity | manifestation | factional_agent | system_entity
origin: ""
identity_status: confirmed | disputed | unresolved | transformed | concealed
role: protagonist | companion | antagonist | neutral | witness | unknown
current_location: location.<stable_id>
current_condition: healthy | injured | exhausted | unconscious | unstable | missing | unknown
capabilities:
  - id: capability.<stable_id>
    name: ""
    function: ""
    limits: []
    costs: []
    status: active | damaged | dormant | evolving | unknown
relationships: []
knowledge: []
goals: []
unresolved_questions: []
provenance: []
status: confirmed | provisional | interpretation
last_updated_event: event.<stable_id>
```

## State rules

- A new name does not automatically replace an old identity.
- A capability is not proof of a character's motive.
- A character's belief is not automatically world truth.
- Injuries, costs, and limits persist until an event changes them.
- Unknowns remain unknown rather than receiving plausible completions.
