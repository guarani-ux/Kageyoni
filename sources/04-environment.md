# Environment

Environment contains locations and the active physical, metaphysical, social, and interactive conditions of a scene.

## Record contract

```yaml
id: location.<stable_id>
name: "Canonical name"
parent_location: null
type: room | region | island | world_layer | route | battlefield | ship | domain
coordinates: null
description: ""
current_state: []
features: []
hazards: []
interactables: []
entrances: []
exits: []
occupants: []
active_rules: []
visibility: normal | obscured | altered | hostile | unknown
related_objectives: []
provenance: []
```

## Scene state

```yaml
scene_id: scene.<stable_id>
location: location.<stable_id>
round: 0
initiative: []
active_effects: []
open_routes: []
blocked_routes: []
interactable_changes: []
current_objectives: []
```

## State rules

- Environment is an active participant in play, not a backdrop.
- Terrain, distance, visibility, routes, hazards, and objects can be used by any side.
- A temporary battlefield change must identify its duration or ending condition.
- Environmental state can survive a battle and affect future scenes.
