# Schema and property evolution

The project keeps separate versions for `schema_version`, runtime schema, property registry, resolution rules, workflow API, skills, and story state. A content-only property addition should use the property registry. A new storage behavior or constraint needs a numbered SQL migration.

A migration should:

1. Declare its predecessor and compatible engine range.
2. Use a stable script checksum recorded in `migration_checks`.
3. Run after a verified backup and within a transaction when the engine supports it.
4. Preserve existing event, property, process, snapshot, branch, and source rows.
5. Perform post-migration integrity, foreign-key, registry, replay, and version checks.
6. Leave an explicit recovery candidate if it fails.

Definition changes create a new immutable version. Assignments name the definition version, subject, context, validity, source event, epistemic status, and visibility. Retired definitions remain readable for old events. Dependency inspection covers rules, derived properties, registry entries, module manifests, workflows, exports, views, and recorded event usage; declared or uncertain dependencies are labeled accordingly.

Never use schema maintenance to create a story event. Never discard a newer event because an older save is easier to migrate. If the event history contains a direct compatibility write, report that replay is complete only for event-mediated auxiliary state.
