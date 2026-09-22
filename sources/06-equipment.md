# Equipment

Equipment is an owned, carried, worn, wielded, installed, or bonded object with operational effects.

## Record contract

```yaml
id: equipment.<stable_id>
item_name: "Canonical name"
category: weapon | armor | tool | artifact | consumable | focus | companion_item
holder: character.<stable_id> | location.<stable_id> | null
slot: main_hand | off_hand | body | accessory | carried | installed | none
condition: pristine | functional | damaged | unstable | broken | transformed | unknown
effects: []
limits: []
costs: []
charges: null
bond: null
origin_event: event.<stable_id>
condition_events: []
visibility: public | known_to_party | concealed | unknown
provenance: []
```

## State rules

- Equipment effects are separate from the user's intention.
- Damage must be recorded as an event, not silently normalized away.
- A transformed item keeps its prior identity and history unless canon explicitly replaces it.
- An item may be powerful, dangerous, misunderstood, or unusable independently.
