# Objectives

Objectives define what someone is trying to accomplish and what changes if they succeed, fail, abandon, or reinterpret the goal.

## Record contract

```yaml
id: objective.<stable_id>
title: ""
description: ""
holder: character.<stable_id> | faction.<stable_id> | system
type: main | companion | hidden | reactive | exploration | survival | meta
status: unknown | available | active | blocked | completed | failed | abandoned | transformed
priority: low | normal | high | critical
stakes: []
requirements: []
dependencies: []
conflicts: []
progress: 0
success_conditions: []
failure_conditions: []
known_to: []
hidden_information: []
related_events: []
provenance: []
```

## State rules

- Objectives may conflict without one being invalid.
- A character may pursue an objective for reasons unknown to the party.
- Completion requires an event or explicit GM resolution.
- A completed objective can still create downstream consequences.
