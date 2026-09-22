# Character contract acceptance (frozen before implementation)

- Minimal identity: create an unnamed character with explicit existence, provenance and visibility; no invented statistics.
- Typed connected records: nature, origin, embodiment, agency constraints, interiority, portrayal, conditions and lineage have validated references and independent visibility. Reuse capabilities, relationships, objectives, knowledge, resources and Will domains.
- Reject invalid categories, missing subjects, self-lineage, contradictory known/unknown values and invalid validity intervals atomically.
- Structured character creation, reading and readiness commands require no SQL. Readiness distinguishes existence, scene context and explicitly supplied action requirements; never claims universal mechanical readiness.
- Hidden character details and references are omitted from participant views. Rumored existence is not treated as established scene presence.
- Renaming preserves identity and history; state changes require events, expected revisions and evidence. Duplicate requests recover receipts; stale writes fail.
- Fresh creation and upgrading the actual prior campaign preserve its records and event revision. Migration is checksummed, transactional and backed up; maintenance creates no fictional events.
- New records survive fork, snapshot, replay, reopen and archive resume. Run all existing regressions and meaningful new failure tests.
- Deliver runnable project and campaign, schema mapping, examples, recovery instructions, test evidence and explicit judgment boundaries. Preserve original sources and database hashes.

## Observed evidence

All 15 tests in `tests/test_characters.py` pass, alongside the 98 baseline tests.
Minimal create/retry, hidden details and nonexistent-vs-hidden errors, rumor
status, scene/action input checks, invalid assignments with complete rollback,
name-status/duplicate identity rejection, voluntary replacement history,
competing connections, branch/snapshot/replay/reload, actual campaign upgrade,
interrupted migration/retry, CLI operations, supersession cycles, temporal expiry
and hidden clocks, and checksum rejection each have explicit assertions.

The migrated supplied campaign still has 165 records and one event; original
project database and all original source hashes match the pre-change inventory.
No claims are made that arbitrary prose ending conditions execute, character
readiness proves action feasibility, or participant projections authenticate a
local user. See CHARACTER-SCHEMA.md for those boundaries and the GM-only treatment
of existing classification claims. Installed skills were not changed.
