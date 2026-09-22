# Dynamics

Dynamics describe changing relationships and pressures between characters, factions, locations, objectives, powers, and rules.

## Record contract

```yaml
id: dynamic.<stable_id>
kind: relationship | approval | rivalry | trust | fear | romance | obligation | faction_pressure | world_rule | conflict
from: entity.<stable_id>
to: entity.<stable_id>
state: ""
value: null
direction: positive | negative | mixed | unstable | unknown
visibility: public | private | hidden | contested
trigger_conditions: []
decay_or_change_conditions: []
last_changed_event: event.<stable_id>
provenance: []
status: confirmed | provisional | interpretation
```

## State rules

- Relationships are not reducible to approval scores.
- A dynamic may be asymmetric: one character can trust another who distrusts them.
- Companion reactions can alter objectives, access, tactics, and future events.
- World rules must be distinguished from a character's belief about a world rule.
