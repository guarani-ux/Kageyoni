---
name: kageyoni-maintain
description: Safely verify, back up, evolve, migrate, replay, branch, and recover the Kageyoni engine and campaign without creating fictional events or losing newer state.
---

# Kageyoni Maintain

Use this skill when the user asks to inspect or change Kageyoni’s engine, SQL schema, property/rule registry, workflows, installed skills, campaign save, branches, snapshots, migrations, replay, backup, or recovery.

## Establish the baseline

Locate the isolated development project and its authoritative campaign database. Preserve the original project and database. Inventory source files, archives, migration scripts, runtime versions, branch revisions, snapshots, pending consequences, processes, property assignments, and registry entries. Compare candidate databases by schema version, event revision, source hashes, and verification results; never assume an older archive is the latest canon.

Run `verify` before making changes. Create a backup to a new path before migration or recovery. Keep the backup and the original recovery candidate. A backup or archive is a recovery artifact, not a fictional event.

Read [references/maintenance-contract.md](references/maintenance-contract.md) for operation routing and [references/schema-evolution.md](references/schema-evolution.md) when changing definitions or SQL.

## Use the engine interface

Use structured CLI operations or the engine Python API. Do not ask an ordinary play workflow to improvise SQL. Maintenance operations include:

- `verify`, `backup`, `restore`, `snapshot`, `replay`, and `fork`;
- `registry`, `dependencies`, and `maintain validate_registry`;
- `maintain define_property`, `revise_property`, and `retire_property`;
- `maintain add_rule`, `register_module`, and `registry_dependency`.
- `will-contract`, `will-prepare`, and `will-apply` for exact-version Will
  definitions, durable attempt reservations, and atomic event commits. A
  prepared attempt is execution metadata; it becomes fictional history only
  when `will-apply` commits the unchanged engine-owned result.

Check compatibility among schema, property, rule, workflow, skill, and story-state versions before writing. Register readers, writers, locators, compatibility, and verified/declared/uncertain status for engine-mediated dependencies. Do not claim arbitrary prose or external code dependencies can be discovered perfectly.

## Evolve properties and rules

Treat a supported new property as content when existing storage and constraints already support it. Give every definition a stable ID, immutable version, exact type and unit, applicability, constraints, lifecycle, change mechanism, mechanical uses, and provenance. Assign `known`, `unknown`, `absent`, `not_applicable`, or `disputed` deliberately; never add an arbitrary default. Preserve directional and relational facts as relationships.

When meaning, unit, or type changes, create a new definition version and an explicit replacement or split/merge mapping. Before retirement, inspect rule, derived-property, workflow, module, export, view, and recorded-event dependencies. Keep old definitions available for historical replay. Use event-mediated assignments for play; the compatibility `set_property` path is administrative and is marked as a replay limitation.

Rules must state inputs, outputs, units, preconditions, effects, costs, duration, dependencies, version, and whether the engine or GM supplies the result. Reject missing inputs, incompatible units, invalid applicability, duplicate contributions, and dependency cycles.

Will contracts are versioned records (`will_definition`, `will_expression`,
`will_technique`, `will_awakening`, `will_development`, and `will_effect`).
Keep legacy flat `will` records for compatibility. Definitions remain
independent of bearers; an expression binds a bearer; a technique is usable
only through its owning expression. Unknown freedom, Will, Haki, and
awakening meanings remain proposed or judgment-bound rather than becoming an
invented score. Historical contract versions are retained through branches
and replay.

## Migrate and recover

Every SQL migration is ordered and checked by predecessor, checksum, compatible engine version, backup, transaction where supported, and post-migration verification. Test fresh creation and upgrade from the actual earlier database. The runtime preserves the legacy schema marker for compatibility while recording component versions separately.

A failure before new story writes must restore the prior consistent state. Recovery after new events must preserve or explicitly reconcile those events. Replay uses recorded property/rule versions, inputs, judgments, random results, and causal/recording order; it never rerolls a historical attempt. Temporal corrections are new events with explicit retained knowledge and effects.

If a migration or restore candidate fails, stop mutation, preserve the failing copy and error, and report the recovery path. Never overwrite the only database.

## Validate delivery

Run existing regression tests plus focused acceptance fixtures. Exercise meaningful failures: stale revisions, duplicate request IDs, wrong types and units, missing references, dependency cycles, incompatible skill versions, concurrent writes, interrupted atomic batches, deferred processes, hidden context, branch isolation, save/reload, backup/restore, and replay. Inspect actual state and receipts, not only test counts.

Package the engine, migrations, definitions, source provenance, installed skill source, campaign database, pending work, version manifest, checksums, tests, and recovery instructions together. Maintenance and skill changes must not automatically create fictional events. Report enforced behavior, proposed mechanics, confirmed canon, fixtures, and remaining GM judgment separately.
