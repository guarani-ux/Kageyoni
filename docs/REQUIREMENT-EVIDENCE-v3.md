# Integrated Kageyoni requirement-to-evidence report

## Baseline and delivery

The implementation was built in `kageyoni-local-dev`. The original `kageyoni-local` project and working database were preserved. The earlier v1 database from `Kageyoni-Local-Database-and-Workflows.zip`, the prior working v2 database, all prior delivery archives, and the property-review candidate were copied to `build/recovery/`. The review package remains proposed material; its catalog and narrow checks were not treated as an integrated property system. The v2 archive was confirmed to omit its SQLite file. The fresh delivered database is source-preserving and contains no noncanonical fixture events.

## Enforced behavior

- Records, properties, rules, processes, consequences, observations, choices, profiles, relationships, classifications, branches, snapshots, and event history use one transactional engine interface.
- Event-mediated auxiliary writes carry property/process/observation/profile/link/classification/resolution/Will-attempt before/after images and are included in receipts and replay support.
- The refined Will system adds six contract domains plus `will_contract_history` and `will_attempts`. Definitions are independent of bearers; expressions bind one bearer; techniques are expression-owned; awakenings, development claims, and effects remain separate. Exact versions, design status, evidence, rule dependencies, scope units, costs, ancestry cycles, source events, clocks, and residue links are validated.
- Will preparation evaluates typed feasibility before randomness, reserves one stable d20 result, records the input snapshot, and keeps preparation non-fictional. Only unchanged resolver-derived preparation can commit a `will_attempt` event; stale input, altered outcomes, replaced rolls, and caller-injected deltas are rejected. Proposed freedom/Will/Haki meanings remain unresolved judgments.
- Typed property definitions are immutable by version, with lifecycle, applicability, units, constraints, epistemic states, visibility, source-event references, and dependency inspection. Unknown, zero, absent, and not-applicable remain distinct.
- Entity identity, nature, composition, agency, control, and classification are separate. Membership, component changes, splits, merges, and succession have explicit link rows. A classification claim records its claimant and any mechanism giving it force.
- Action resolution separates permission, probability, magnitude, cost, timing, and consequences. Feasibility precedes randomness. A d20 result is persisted once per stable attempt and has no natural-20 auto-success rule.
- Consequences can execute structured record/property changes when due; unsupported or judgment-bound effects remain pending/contested. Process subscriptions mark matching work due in the same event, while scheduled advancement remains explicit, elapsed-time based, idempotent, bounded, and records blocked/deferred work. Relevance scoring is presentation-only.
- Context and observations are viewer-filtered. NPC knowledge and collective member choices remain independent. Choices preserve intent, options, selection, knowledge, and agency state without inventing a numerical agency score.
- Module manifests and registry dependencies connect stable concepts to readers, writers, locators, versions, compatibility, workflows, and tests. Mismatched module versions are rejected before event insertion.
- Migration 002 upgrades legacy schema v1 to v2 with a recovery copy. Migration 003 installs runtime schema 3; migration 004 adds the Will contracts/history/attempt tables and workflow API 3, each with checksum and predecessor. Backup, restore, branch, snapshot, replay, and verification are exercised.
- Installed `Kageyoni Play` and `Kageyoni Maintain` skills route to the structured engine. Live campaign state remains in the database and skill source is kept separately.

## Acceptance evidence

The full mapping is maintained in `REQUIREMENT-CHECKLIST.md`. The 98-test run covers the original regression suite, A–J, activity-module routing, open opportunities, rule use, branch auxiliary collision handling, spent-roll copying, compatibility mismatch, atomic rollback, elapsed-time and event-trigger processing, hidden facts, collective disagreement, property evolution, replay, the integrated bridge/water/family/fatigue/patrol/faction journey, and the focused Will contract/attempt cases. `TEST-REPORT.md` records the commands and observed upgrade/recovery results.

## Confirmed canon, proposed mechanics, and judgment

The seed records supplied continuity with source excerpts and preserves unresolved questions. The engine machinery for freedom, Will capacity/mastery, learned mastery, power, practical agency, Haki, restrained intelligence, and Gaia balancing is available as typed properties/rules and judgment fields. Their unresolved numerical or metaphysical meanings were not invented. The engine also does not infer universal effects from rank, obedience, victory, or raw combat strength.

A GM/agent remains responsible for interpreting intent, choosing whether an unsupported fictional effect is plausible, supplying bounded judgments, and narrating. The system does not provide an external scheduler, autonomous omniscience, universal physics, complete dependency discovery, or a GUI. Those are explicit limitations rather than claims of completion.
