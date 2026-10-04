# Workflow: Portable Playable World Turn

## Purpose
Execute one complete, honest turn of the Portable Play Kernel (`playable-world/0.1`), preserving continuity, free-form action, and the boundary between fictional consequences and real external mutations across any AI host.

## Stages

### 1. Boot & Host Discovery
* Load current `SAVE.json`.
* Discover host-local capabilities (`available_actions`, storage tools, write permissions).
* Verify base revision matches current world revision. If `base_revision != current_revision`, reject handoff to prevent silent state divergence.

### 2. Turn Execution (7-Phase Cycle)
1. **Receive**: Parse incoming intent (action, observation, artifact, question, correction).
2. **Situate**: Recover active scene, copresent entities, active claims, and relevant methods from save.
3. **Make Playable**: Ground the input as an encounter with observable details, character agency, and consequences.
4. **Offer**: Provide 2–4 meaningful options plus explicitly permit free-form actions.
5. **Respond**: Adjudicate through the appropriate boundary:
   - Fictional narrative adjudication (delegated narrator authority).
   - Real-world bridge (drafting text, reasoning, staging).
   - Tool execution (strictly within actual host permissions; never invent tool receipts).
6. **Reconcile**: Update entities, relationships, beliefs, and monotonic revision counter (`revision += 1`).
7. **Continue**: Present the changed scene and halt at the next meaningful player decision.

### 3. State Handoff & Persistence
* Construct the updated `SAVE.json` payload with incremented revision, event digest, and preserved residue.
* If storage tool is available: persist save and verify readback.
* If storage tool is unavailable: output complete JSON export for the player/adapter.

### 4. Acceptance Encounter Qualification
* Verify that:
  - Fictional outcomes do not self-certify real external progress.
  - Missing host tools leave actions in `pending_actions` rather than faking execution.
  - Stale saves fail closed before mutating state.
