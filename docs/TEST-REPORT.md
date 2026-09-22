# Verification report

Executed in the isolated `kageyoni-local-dev` project on 2026-09-19 with Python 3.12 and the standard-library SQLite driver.

| Check | Observed result |
| --- | --- |
| Existing and integrated unit/integration suite | **98 tests passed** (`python3 -m unittest discover -s tests -v`) |
| Python compilation | `python3 -m py_compile kageyoni/*.py tests/*.py` passed |
| Fresh schema and source seed | 165 source-grounded records, 9 source files, 92 excerpts, 1 import event; `verify` passed |
| Runtime compatibility | runtime schema 4, property registry 1, resolution rules 1, story state 1, workflow API 3; `session.compatibility.ok` true |
| Actual archive v1 upgrade | `build/recovery/archive-local-build.sqlite` upgraded in a copy; schema marker 1 → 2, runtime migrations 3 and 4 recorded, 165 records retained, pre-v2/pre-v4 backups created, `verify` passed |
| Prior working v2 database | copied to `build/recovery/original-build-v2.sqlite`, opened and verified without modifying the source project |
| Prior v2 archive diagnosis | `Kageyoni-Integrated-World-State-v2.zip` contains no SQLite file; the omission is recorded in `build/recovery/migration-report.json` and the archive inventory |
| Property review package | The candidate SQL/catalog/checks were inspected and preserved as proposed material; they were not mistaken for an integrated property system or activated without engine validation |
| Backup and restore | fresh backup and restored copy have matching SHA-256; restored database `verify` passed |
| Branch continuity | branches copy properties, processes, consequences, choices, observations, profiles, links, classifications, rolls, and process runs; globally keyed rows are namespaced in the child; `verify` passed |
| Randomness | stable roll IDs are reused on retries and roll use is one-to-one with an event; natural 20 has no automatic-success path |
| Background processing | explicit elapsed-time processing records run keys, outcomes, blocked work, and deferred work; one-hour-plus-two-hour and one three-hour fixture results agree |
| Visibility | participant context omits GM/restricted facts and observations outside the audience; authorized resolution can still use hidden input |
| Will contract/attempt fixtures | Six additive Will domains, exact contract references, durable `will_attempts`, historical `will_contract_history`, stable d20 reservation, resolver-derived commit, scope/unit checks, hidden-context redaction, and caller-delta rejection passed focused tests |
| Will design provenance | The uploaded `Kageyoni-Will-System-Schemas.zip` is retained in `build/recovery/` and unpacked under `schemas/will/`; the engine uses its contract version and structural requirements without activating unresolved mechanics |
| Skill validation | `kageyoni-play` and `kageyoni-maintain` passed the available skill validation; both document the workflow API 3 Will operations and remain separate from live campaign state |
| Handoff archive | refreshed Will-integrated archive reopened in a temporary directory; all 98 tests, database verification, migration metadata, source provenance, and both bundled skill source trees passed |

The detailed named acceptance mapping is in `REQUIREMENT-CHECKLIST.md`. The fixtures are temporary and noncanonical. The supplied campaign database contains only the source-preserving seed; the integrated crossing, family, patrol, fatigue, water, faction, deadline, and branch journey is exercised in `tests/test_world_engine.py` and is not inserted into canonical history.

## Meaningful failure coverage

The suite checks wrong property types, incompatible units, invalid entity applicability, missing references, duplicate contributions and assignments, dependency cycles, stale branch revisions, request-key reuse with changed payloads, duplicate process requests, incompatible module versions, invalid atomic batches, append-only history, branch isolation, hidden context, deferred/judgment processes, and save/reload. These checks inspect state and receipts after rejection; they are not row-count assertions.

## Recovery instructions

1. Copy the database to a new path and run `python3 -m kageyoni --db <copy> verify`.
2. Before an upgrade, run `backup` to a new destination. Keep the original and backup.
3. Open the copy with the engine. A v1 database is backed up as `<copy>.pre-v2.bak` before migration 002; runtime migration 003 then migration 004 (Will) record checksums and predecessors in `migration_checks`, with `<copy>.pre-v4.bak` created before the Will upgrade.
4. Run `verify`, inspect `session`, `replay`, pending consequences, and process state, and only then use the copy for play.
5. To restore a backup without overwriting an existing save, pass a JSON object with distinct `source` and `destination` paths to the `restore` operation. Verify the restored copy before resuming.

A maintenance operation does not create a fictional event. Recovery after new story events must preserve or explicitly reconcile those events. Do not delete the original recovery candidates in `build/recovery/` until a separate retention decision is made.

## Remaining boundaries

The engine does not claim complete simulation of reality or autonomous judgment. Freedom’s numerical formula, restrained intelligence, detailed Haki mechanics, awakening semantics beyond declared contracts, unknown calendar conversions, unsupported free-text effects, arbitrary external dependencies, and an external always-running scheduler remain unresolved. Direct administrative `set_property` writes are retained for compatibility but are reported as incomplete for auxiliary replay; ordinary play uses event-mediated assignments.
