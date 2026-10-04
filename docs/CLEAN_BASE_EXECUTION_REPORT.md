# Clean-base execution report

Date: 2026-10-04 UTC. Source baseline: `c7a6f8dc595b3acada63a9cb4693dbf2b55c7784`.
Review branch: `codex/consolidate-existing-capabilities`. Main is not changed by this work.

**Result: selected consolidation mechanisms implemented and demonstrated; whole-system clean-base acceptance remains incomplete.** Latest completed full comparison with recovered archived inputs: 938 passed, 11 failed, and zero new failing IDs against the matched baseline (898 passed, 30 failed). Five fixture-isolation conflicts in that run are subsequently repaired: the affected 25-check suite passes. Fresh full GitHub verification of this final fixture routing remains pending. The installed wheel also preserves existing rows when upgrading a copy of the authentic historical fixture. These changes establish internal mechanics, not independent cognition, emergence, or an operating rank.

## Original verification checkpoint and scope

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

## Original failure groups (superseded by follow-up)

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


## Verification follow-up

The follow-up repairs portable source-root discovery in the emergence engine and carrier dispatcher, and portable character-root discovery in hydration. Explicit caller-supplied paths remain supported. The canonical `data/SAVE.json` was present in GitHub: its five failing checks were caused by a hard-coded Windows path, not a missing save. That earlier diagnosis is corrected here.

The GitHub verification workflow now installs its test/build dependencies, uses recursive pytest collection (including existing pytest-style tests and nested suites), and retains raw output. Mutation sensitivity, refusal of unsupported R5/R6 self-certification, distribution building and an installed-package behavioral probe are run even if the full suite fails. Uploading evidence is not a qualification verdict. Original failures remain failures; none is hidden with skips or replaced historical state.

The first follow-up local run reports 949 cases: 925 passed, 24 failed, with zero new failing IDs relative to the original baseline. The focused changed-code suite reports 34 passing checks. Paired scenarios still preserve the five recorded behaviors and demonstrate the repaired outer-ledger rollback. The wheel installs outside the checkout and passes migration, dispatch/retry, durable situation and engine verification checks. The mutation probe detects all four injected invalid states, and R5/R6 refuse self-certification.

The first GitHub run failed because its previous workflow omitted pytest and setuptools, used unittest discovery that could not execute the pytest suites, and encountered the recorded unavailable inputs. Its full job output was inspected. The repaired workflow recovered the two authentic historical SQLite files already tracked by GitHub. Both match their original main Git blob SHAs exactly. Additional historical recovery snapshots, private character state, the actual recalled campaign scene, and `ichimonji/engine_core.mjs` have not been recovered; coupling is blocked at that missing carrier, rather than at its repaired SQL path.

Evidence from this follow-up is retained under `evidence/clean_base/verification-followup-*`. Main remains unchanged while whole-system acceptance is incomplete.


### Completed exact-input comparison

| Check | Original code | Updated code |
| --- | --- | --- |
| Full recursive collection with recovered historical fixtures and exact original SQL bytes | 928 cases: 887 passed, 41 failed | 949 cases: 927 passed, 22 failed |
| New failing IDs | — | 0 |
| Resolved original failing IDs | — | 19 |
| Additional boundary/regression cases | — | 21, all pass |
| GitHub full checkout, run 37168713010 | Not rerun remotely | 927 passed, 22 failed; matches local candidate |
| GitHub build, mutation sensitivity, R5/R6 refusal and isolated installed behavior | Not measured | All pass |
| Installed authentic historical upgrade | Not measured | Existing non-version rows/columns retained; engine verification passes |

The downloaded text snapshot had one extra trailing newline on each original SQL file. Once authentic historical databases were recovered, checksum validation correctly refused two local upgrade checks. All 24 original SQL files were restored from the GitHub-produced source distribution only after verifying their Git blob SHAs against main. These are restored original bytes, not rewritten historical migrations. Earlier local runs remain recorded; the exact-input comparison supersedes their migration evidence. Locally generated seed databases created with the altered text snapshot were moved aside, preserving them as diagnostic fixtures. No private or canonical character history was fabricated or overwritten.

The two historical fixture files still have their original SHA-256 digests after the tests. The optional historical input to the installed-package probe is copied into a disposable directory; the original is never opened for mutation. The probe checks the installed migrations through 025, retained original rows/columns, engine integrity, a fresh issued action/retry and durable situation continuation. It does not certify every older database, canonical campaign recovery, independent cognition or external-effect atomicity.

The remaining 22 failures are:

| Required input | Failed cases | Finding |
| --- | ---: | --- |
| Earlier recovery snapshots | 11 | Required `pre-character`, `pre-decisions`, `pre-personality`, `legacy-personality-pending`, `pre-writing`, `pre-v2-methods`, `pre-v3-learning` and `pre-v4-v8` files were not recovered |
| Private character history | 4 | Sciel/Voss/Maki state required by the hydration tests is not in GitHub |
| Actual recalled campaign scene | 5 | `lucretia-voss-recall-scene` is absent from the accessible seed and both recovered historical fixtures |
| Ichimonji carrier | 2 | `engine_core.mjs` is absent; participant-coupling progression remains blocked at round 4 |

Repository tree/history queries for the carrier, character state and representative recovery/campaign paths returned no files/commits; no release assets were available. Available historical workflow artifacts did not contain these inputs. No skips, authored replacement histories, or assumed success results were introduced. Restoring these inputs would require authentic additional project state, not a label change in the tests.

The verified consolidation is on the review branch. Whole-system clean-base acceptance and main integration remain blocked by these explicit failures. Evidence: `verification-exact-comparison.json`, both exact full-run logs, `verification-exact-sql.json`, recovered-input hashes, GitHub run logs and installed-package output in `evidence/clean_base/`.


### Authentic archive recovery and separated test inputs

Read-only Library archives supplied eight original recovery snapshots and the actual 167-event campaign containing `lucretia-voss-recall-scene`. Their archive IDs, member paths and SHA-256 digests are recorded in `verification-library-recovery.json`, `verification-library-v11-recovery.json` and `verification-recovered-fixtures.json`. The archived campaign is a frozen verification input; it is not asserted to be Levi's newest canonical state. No private character database was overwritten or synthesized.

The historical recovery checks pass (62 checks plus 9 subtests, and 33 checks plus 6 subtests). The recovered campaign's composition/CLI suite passes all 10 checks. Matching full comparisons initially report original code 898 passed / 30 failed, updated code 938 passed / 11 failed: 19 original failing IDs resolved and zero new failing IDs. This comparison uses identical archived inputs on both sides.

Five failures exposed test input coupling: the closed-loop and sovereign tests relocated actors from an archived campaign with additional active scene participation, instead of starting from the original seed they assumed. Those two authored scenario modules now seed their own disposable worlds directly. The actual-scene composition and CLI tests explicitly copy `campaign-v11.sqlite`; recovery tests locate their corresponding historical fixture. Assertions and engine invariants are unchanged. All 25 checks across the four affected modules pass after this separation. A fresh full GitHub run is required before claiming the final full count.

The nine recovered databases contain 78,839,808 original bytes. They are retained in Git as 7,981,045 bytes of deterministic lossless gzip, rather than duplicate expanded databases. `tools/prepare_verification_fixtures.py` verifies both compressed and original hashes, restores the exact original bytes, and refuses to replace a different existing fixture. Expanded inputs are ignored by Git. All nine original fixture digests were checked unchanged after use. This is verification packaging, not a new runtime feature or a semantic rewrite of saved state.

The six remaining external-input checks concern four private character hydration/environment checks and two missing `ichimonji/engine_core.mjs` carrier checks. No replacement histories, carrier stubs, weakened assertions or skip markers were supplied. Main remains unchanged until the acceptance boundary is resolved. The branch contains the implemented consolidation and executable verification, not a claim of independent cognition or whole-system qualification.
