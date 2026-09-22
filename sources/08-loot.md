# Loot

Loot is discoverable or claimable value. It is not automatically equipment, and discovery is not ownership.

## Record contract

```yaml
id: loot.<stable_id>
name: "Canonical name"
category: item | currency | knowledge | key | relic | component | evidence | quest_reward
location: location.<stable_id>
container: ""
status: hidden | discoverable | discovered | claimed | destroyed | inaccessible | unknown
owner: null
revealed_properties: []
hidden_properties: []
requirements: []
risks: []
related_objectives: []
provenance: []
discovery_event: event.<stable_id>
claim_event: null
```

## State rules

- Hidden properties cannot be used unless discovered in play.
- Claimed loot must create an ownership or custody event.
- Evidence can be loot without being useful, true, or complete.
- Destruction does not erase the item's history.
