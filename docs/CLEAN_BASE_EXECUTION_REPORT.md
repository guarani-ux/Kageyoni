# Clean-base execution report

Date: 2026-10-04 UTC. Source baseline: `c7a6f8dc595b3acada63a9cb4693dbf2b55c7784`.
Review branch: `codex/consolidate-existing-capabilities`. Main is not changed by this work.

**Result: selected consolidation mechanisms implemented and demonstrated; whole-system clean-base acceptance remains incomplete.** Thirty pre-existing checks still fail in this environment. These changes establish internal mechanics, not independent cognition, emergence, or an operating rank.

## Evidence and scope

| Check | Baseline | Candidate |
| --- | --- | --- |
| Recursive `python -m pytest -q` | 928 cases: 885 passed, 43 failed | 949 cases: 919 passed, 30 failed |
| New failing test IDs relative to baseline | — | 0 |
| New regression/boundary tests | — | 21, all pass in the full run |
| Focused affected suite | — | 158 passed, 1 failed: unavailable historical learning fixture |
| Paired synthetic scenarios | Recorded independently against baseline source copy | Five preserved outcomes; outer ledger rollback repaired |
| Isolated wheel install outside checkout | Not measured in this run | Passed selected migrations, dispatch/retry, situation continuation and engine verification |

Both full runs report three collection warnings and 70 passing subtests; subtests are separate from the case counts. No checks were marked skipped to hide failures. Thirteen resolved baseline failures were caused by the qualification tests' hard-coded Windows repository root; only their path discovery was corrected. This does not qualify the claims in those tests' names or docstrings.

Raw output and structured comparisons are in `evidence/clean_base/`. The intermediate run found three new regressions; they were corrected before the final run. Its log is retained. The intermediate process also printed `fatal library error, lookup self` after its pytest summary; the final process exited with pytest's ordinary failing-test status and no such message. The cause of that one shutdown diagnostic is unresolved.

The source checkout was reconstructed through authenticated GitHub text access. Root SQL, sources, tests, entry scripts, governance, and text fixtures were included. Binary historical databases and Levi's Windows character databases were not accessible. Archived agent configuration was excluded. The baseline manifest identifies downloaded source files; it does not certify a complete binary checkout or original Git history.

## Changes and ownership

| Surface | Owner after this change | Removed duplication / repaired behavior |
| --- | --- | --- |
| Shared graph | `CausalDAG` | Prevalidate updates before changing metadata/edges; rehash changed payloads; reject malformed restoration |
| Research claim lineage | Checked DAG edges with sequence views | Remove independent parent/child backing lists; indexing, iteration, mutation and serialization agree |
| Research invalidation | Shared DAG traversal, followed by research-specific effects | Remove duplicate recursive traversal; preserve project/package/section invalidation |
| Production dependency state | DAG-backed bound node properties | Remove independently writable topology/status copies; reject approval of a stale node |
| Participant encounter execution | `PersistentParticipant` delegates to Application's existing encounter service | Observation uses bound branch; accepted replies reach the engine without a separate mutation script |
| Celestial helper | Compatibility facade borrowing participant identity/connection | Delegate bound observation; preserve owned-versus-borrowed connection lifetime |
| Action trace | Issued request plus authoritative encounter receipt | Reject fabricated or altered requests, wrong bindings, stale revisions, ambiguous field aliases and conflicting retries |
| Internal commit | Existing `UnitOfWork` | Remove premature helper commits; effect, required dispatch record and supplementary ledger append share the transaction |
| Situation continuity | Existing SQLite adapter/store | Replace four service and three runtime dictionaries with store-backed mappings; remove duplicated cache/store writes |
| Operational access | Existing Application and console allowlist | Expose encounter request/dispatch and durable situation operations through the shared boundary |
| Legacy export | Read-only source snapshot and supplementary ledger | Preserve original row/time data; deterministic ordering, identical-snapshot deduplication and atomic target writes |

No entire source module or class was deleted. Existing domain imports remain compatibility entry points and delegate topology/traversal to their shared owner. Unique research provenance, production approvals, Learning/Methods, Shinobi host-turn behavior, and the separate `shinobi_agent` protocol are retained. Generic gates retain legacy Python comparison semantics; typed world preconditions and authority checks remain separate. Static scouting does not confer executable availability.

Low-level direct Python/SQLite access remains trusted. Closing domain view bypasses is not operating-system isolation, and a supplied model label is not evidence of a host invocation.

## Behavior demonstrated

The new tests exercise rejected graph updates without prior-state damage; checked lineage edits; stale snapshot recovery; malformed saved topology; issued-request forgery; actor/encounter/branch mismatch; stale observations without revision rebasing; dialogue-only proposals; conflicting `payload`/`fields`; failure during required receipt recording; concurrent identical retries; distinct legitimate turns; non-main participant actions; borrowed connection lifetime; and fresh-process continuation.

Failure injection covers both ordinary event effects and Will preparation/effects. A failed required ledger write leaves the world revision, encounter state, dispatch history and operation result unchanged; the issued request remains pending and can be retried. Exact completed retries return the recorded result without another effect or ledger append. Rejection diagnostics may legitimately persist without prohibited world changes.

Paired baseline/candidate scenarios preserve the authored narrative outcome and continuation, research descendants/unrelated claims, production approval revocation, participant identity/dialogue, and waiting situation continuation. The sixth comparison exposes a baseline premature commit: an interrupted outer ledger operation left one record. The repaired operation leaves zero. These are declared synthetic scenarios, not character experiences or evidence of model cognition.

## Public compatibility changes

1. Bound production adjacency is read-only. Supported topology edits go through graph methods. Claim sequence mutations reject cycles and unknown nodes rather than bypassing checks; order is canonical, not caller insertion order.
2. Dispatcher clients must call `prepare(branch, encounter_id, participant_id, request_id)` and echo the returned hash/encounter binding in the reply. Arbitrary client-created authority packets are refused. There is no fallback to the latest revision. Existing legacy audit rows remain readable and are not deleted or silently deduplicated.
3. `action.payload` remains accepted as a compatibility alias for `action.fields`; providing both is rejected. `action:none` records its outcome without world mutation. A missing response remains an issued, uncompleted request; no response is generated on behalf of a model.
4. Situation records returned by a store mapping are snapshots. Persist changes by assignment or service methods. Default installation is restart-safe for identical stored definitions and refuses conflicting definitions. The recovery test now reads authoritative runtime state instead of assuming an old supplied Python object updates itself.
5. `DatabaseMigrator` remains the compatibility class name, but its operation is explicitly snapshot export. Payloads retain source rows, schema, identity and original timestamps. Unknown or timezone-ambiguous historical times remain unknown. Re-exporting an identical snapshot adds zero records; a changed source is a different snapshot. This does not preserve application permissions or replay semantics as a domain migration would.

Example of the trusted-runtime proposal path, with an explicit fixture/human choice:

```python
request = participant.prepare_action(encounter_id)
reply = {
    "encounter_id": encounter_id,
    "request_hash": request["request_hash"],
    "action": {"kind": "propose_action", "action_id": selected_action},
}
result = participant.dispatch_reply(encounter_id, request, reply)
```

This does not invoke an AI host. The caller supplies the actual response.

## Migration and recovery

`migration_025.sql` is opt-in through `install_action_dispatch`, after the existing Shinobi migration 024. First construction of the dispatcher installs it using the existing migration machinery. It verifies the baseline, creates a uniquely named pre-v25 backup, records the script checksum/predecessor/engine minimum, and checks integrity, foreign keys and engine verification. Prior SQL migrations are unchanged. Existing world events and dispatch audit rows are retained; the new table binds issued requests by `(branch, request_id)`.

Instantiate/install services before entering an outer unit of work. Schema installation is not supported inside that transaction. The packaged-install probe verifies migrations 002–025 are present and that a reopened engine returns the committed dispatch result.

For rollback before any candidate state is used, return to the baseline code and its existing database. Once schema 025 has been installed or candidate operations performed, retain that database and evidence; do not overwrite newer state with an older backup. Inspect the pre-v25 backup as a separate recovery candidate. Any reverse migration or replay of newer state requires its own verified procedure; none is asserted here.

Atomicity demonstrated here is same-database SQLite atomicity. External messages, files or tools are not made transactional by these repairs. Their existing pending/uncertain semantics are not replaced with a false rollback guarantee.

## Remaining failure groups

All 30 IDs also failed before changes; the structured test comparison lists each one.

| Group | Cases | Current evidence |
| --- | ---: | --- |
| Historical upgrade/recovery fixtures | 13 | Required historical SQLite files unavailable; original bytes were not substituted |
| Character hydration/environment tests | 4 | Windows character state absent; hydrated intent/identity claims cannot be established |
| Playable-world canonical save | 5 | Expected canonical `SAVE.json` unavailable |
| Actual-campaign scene compilation | 5 | Required scene unavailable in accessible campaign state |
| Emergence/participant-coupling checks | 3 | Baseline execution is blocked; exact missing carrier/context causes remain unresolved |

B0 is incomplete for binary/canonical inputs. B1/B2 are demonstrated within tested graph scope. B3/B4 are demonstrated for the issued internal encounter path; no host-cognition claim follows. B5 is demonstrated for store-backed situations and existing participant continuity. B6/B7 are completed only for the selected services and proven internal redundancies. B8 has a comparison/report and installed-package evidence, but whole-system acceptance remains blocked by the failures above and unverified external-effect/host paths.

The next work is to recover authentic required inputs and diagnose the three blocked coupling checks, then rerun the same recorded suite and remaining B8 boundaries. Do not manufacture fixtures, reinterpret a blocked result as success, or assign a rank from the passing component tests.
