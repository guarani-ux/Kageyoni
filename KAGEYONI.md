# Kageyoni v10 candidate entrypoint

This tree is **v11.0.0**, promoted after Foundry adversarial qualification. See `PROMOTION.md` for the exact boundary of what promotion establishes.

## One front door

```sh
python -m kageyoni --db /path/to/world.sqlite engine-init
python -m kageyoni --db /path/to/world.sqlite verify
python -m kageyoni --db /path/to/world.sqlite operate --input command.json
```

`engine-init` installs additive interfaces through migration 018. Existing campaign events and records are not rewritten.

## Ask the engine what it knows

```json
{"service":"simulation","action":"capabilities","arguments":{}}
```

```json
{"service":"simulation","action":"graph","arguments":{}}
```

The graph exposes installed Frames, Slots, 108 initial slottable Aspect types, accepted-slot edges, dependencies, and cross-family reactions.

## Compile and resolve

Existing Kageyoni scene:

```json
{"service":"simulation","action":"resolve_scene","arguments":{"scene_id":"lucretia-voss-recall-scene","participant_ids":["sciel"]}}
```

Arbitrary Frame/Aspect configuration:

```json
{"service":"simulation","action":"resolve","arguments":{"frame_id":"content_development.v1","aspects":[],"bindings":{}}}
```

Compilation is fail-closed for missing required causal state, incompatible types, cardinality violations, disallowed authority, failed dependencies, and unknown verification gates. Ontology gaps remain visible as `UNPLACED`.

The qualitative Effect Resolver preserves opposing pressures rather than averaging them away. The resulting Expression Contract constrains canonical truth while leaving language/performance to the host.

## Knowledge Ledger

External information enters as evidence, not truth:

```json
{"service":"knowledge","action":"ingest","arguments":{"source_type":"report","source_ref":"...","claims":[]}}
```

It can then be explicitly routed and advanced through encounter/interpretation/testing states. Ingestion does not alter character belief or world truth.

## Mutating world state

World mutations remain two-stage and reuse the existing causal engine:

1. `simulation.prepare_event` compiles and previews the exact `Engine.apply` command.
2. `simulation.commit_event` rebinds the exact supporting records, rejects stale/tampered inputs, requires `authorize=true`, commits through `Engine.apply`, then verifies the database.

The composition layer has no second canonical mutation path.

## Authority order

1. Current verified database state and event history.
2. Installed Frame/Slot contracts and registered engine contracts.
3. Provenance-bearing evidence/owner inputs allowed by the Frame.
4. Derived state permitted by the Frame.
5. Attributed host judgment only where the Frame explicitly permits it.

## Qualification

```sh
python scripts/v10/preflight.py --db /path/to/migrated-copy.sqlite
python scripts/v10/check_fast.py
python scripts/v10/check_full.py
```

See `V10-HANDOFF.md` and `evidence/v10/` for boundaries and evidence.
