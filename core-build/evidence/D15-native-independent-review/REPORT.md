# D15 repaired native liveness: independent source review

**Final verdict: ACCEPT_SOURCE_ONLY for exact RAM V3 worker `a6ca48206fb5bd5cbbd1c5fbd78e93520268017b220bf14265becb8c8645d8d6` and queue `e27ee95f81c3c772b96909dafaaea0b20020b13f6ef4907f8f51b5b5a760e39c`. No repaired runtime result is claimed.** This commission ran no native code, tests, databases, owner processes or heavy jobs, opened no worlds, and changed no leaf/root source, contract, wheel, environment, version, lock or remote. Only this review directory contains reviewer writes.

## Exact inspected material

The owning agent supplied immutable repaired-static-freeze (V1) and repaired-static-freeze-v2 (V2). Every manifest file was read and SHA-matched. `inspection-identities.json` records exact source, test, report, contract and raw failure identities. All32 actual antecedent SQL files (schema.sql and migrations002–032) remain byte-identical to current D14. New033 and the appended installer remain byte-identical to their initial accepted leaf editions; no backfill or rewriting of old attempt metadata was introduced.

| File | V1 | V2 |
| --- | --- | --- |
| worker_liveness.py | 31eb602eb724c964ede81faa0598e6887d634e831b7ba844b249cd37784abb3f | 2fe335a44981a97f6ae513712b60a158971e024e03f4bf0737dfd258495bf4ab |
| job_queue.py | 2a90c1bf470db085c4616253139b2fc385e1424a470987aa0e160b6d9f895244 | e27ee95f81c3c772b96909dafaaea0b20020b13f6ef4907f8f51b5b5a760e39c |
| migration033 | ae7c588d694dbd2aa67a3b862277ab5badd483b7bf02a224070034a0a3dd67f0 | unchanged |
| migrations.py | ceab5ba005ff78d494f6b909363cf05ac4f880bc02a75ec87eec5ab94bb19747 | unchanged |

The preserved prerepair stdout/XML records **three actual failures in3.95s**, matching the initial independent review's concrete paths. That is root/leaf execution evidence, not execution by this reviewer. The original22PASS antecedent stays in freeze-for-checkpoint. V2 has34 and final V3 has37 authored native cases, all static only; none may inherit that earlier pass count.

## Targeted source repairs

### Stopped attempts cannot become successful output

Transition no longer enters its protection only when the mutable queue process is present. It now finds the exact033 attempt by job/owner epoch/generation on every transition. Stopped returned transitions are refused even before a process was registered. A never-registered stopped attempt may settle only reconciling, paused for pause, or cancelled for cancel; it cannot revive queued/running/returned or claim success. A later process registration still goes through assert_lease, whose running-state gate refuses the stopped/reconciling row.

The direct verifier independently rejects a stopped returned/running shape and the inappropriate no-registration terminal states. A registered identity retained in the attempt requires observed exit before queue process/slot cleanup. Illicitly clearing queue.process_json no longer removes that guard: the attempt's retained identity, not the mutable queue column's presence, selects it. Ordinary registered stopped cleanup keeps native process capacity until trusted exit observation; no stop acknowledgement clears the process and no charged start/ceiling is refunded.

### Durable cross-attempt owner floor

New stop and exit observations now update activity_queue_owners.last_wall with max(previous, now). Receipts retain owner_wall_before/after, and backward time sets clock_rollback/time_status=uncertain without lowering the floor. The first stop still fixes its requested time and +5 deadline; later requests, including pause→cancel, do not reset grace. Direct verification checks the exact field shapes, finite times, max arithmetic, rollback classification and final owner high-water correspondence.

JobQueue.boot preserves max(old floor, new boot time) when033 is present, rather than replacing the earlier floor with an older reboot wall time. Old persisted fences remain usable for stop/exit cleanup while the current-owner heartbeat/acceptance path is fenced after restart. Stop/exit replay looks up its immutable receipt before any state/clock update and returns it unchanged; an exact historical replay is not a new timestamp observation. Actual root supervision still needs a monotonic first-five-second drain clock, independently of these wall-time metadata assertions.

### Known heartbeat receipt replay after current gates

Known-sequence lookup now occurs after current queue running/no-stop/no-exit, exact attempt/fence/current owner, monotone owner time, current unexpired lease and execution ceiling, queue lease correspondence, binding authority, profile, waiting job, and every ancestor gate. An eligible known sequence returns its exact immutable stored receipt with no update, lease renewal or sequence/clock advancement. New sequences remain contiguous+1; unknown older rows and gaps reject. Rollback is still a refusal/reconciliation path, not eligible replay or authority renewal. Root must not wrap that rejecting heartbeat in a surrounding rollback if its reconciliation must persist.

A historical acknowledgement carries its historical lease_until. Root's transport must continue reading current authoritative queue/attempt state rather than replacing a newer lease with this old receipt. Framing, bounded producer delivery and incrementing only after a complete send remain actual supervisor responsibilities; no native metadata proves worker10-second heartbeat production.

## New finding in V1 and its adopted V2 correction

The initial repair still defined normal_return from running/no-stop/returned/clear_process alone. A registered no-stop running attempt whose queue-only process identity had been illicitly cleared or mutated could therefore use that exemption to erase the mismatch. It also allowed a never-registered running attempt to use successful return. These are source-level countercases, not executed DB reproductions in this review.

Root adopted requiring a non-null registered attempt identity exactly equal to the current queue identity. V2 implements that requirement while preserving the genuine same-identity no-stop running→returned/clear_process path without forcing an observe_exit before acceptance. Root's real Popen.poll plus fenced acceptance remains a separate indispensable observation. The V2 verifier independently requires the final normal-return shape to have registered identity, no stop, no exit receipt and a cleared queue process.

Four new static cases preserve cleared/mutated/never-registered refusals and a legitimate same-identity success. This is not a claim that those cases ran. Old never-claimed/historical rows without a033 attempt retain their prior queue semantics; no synthetic process evidence is backfilled.

## V2 diagnostic-order mismatch: corrected in V3

V2's new `if q.state == returned` verifier check precedes its existing first-stop check. The retained authored `test_never_registered_stop_settles_without_invented_exit` deliberately damages a stopped row to returned and expects the specific refusal “returned or revived.” V2 instead reaches “invalid unobserved normal worker return” first. The refusal itself remains correct, but the authored test will not match that diagnostic. This was found through source inspection, not a test failure claim.

Moving the new normal-return shape check after the existing first-stop block preserves both source guards and the earlier specific negative assertion. That recommendation was sent to the owning agent and is implemented in frozen V3: the stopped-returned guard now executes before generic normal-shape validation. The retained specific assertions remain exact. Neither the34 V2 cases nor the37 V3 cases has executed against repaired code.

## Final V3 correspondence and explicit cancel policy

The final frozen source is `/dev/shm/d15-repair-current/freeze-v3`. Its complete manifest was freshly read and SHA-matched; V1/V2 immutable copies remain exact. The worker is `a6ca48206fb5bd5cbbd1c5fbd78e93520268017b220bf14265becb8c8645d8d6`; queue remains the V2 `e27ee95f…e39c`. New033 and installer remain unchanged. Full identities are in inspection-identities.json.

The additional read-only finding was a missing reverse correspondence rule: a current033 attempt with no retained registration could nevertheless have a queue-only process identity and pass the direct verifier. That is not a shape the atomic valid JobQueue.process producer creates. Root adopted requiring NULL queue.process_json whenever the current attempt has no registered identity. V3 adds that rule while preserving valid pre-registration NULL/NULL and historical queue rows with no033 attempt. A new damaged-specimen assertion is authored; it was not executed by this reviewer or the leaf owner in this freeze.

Inspection of the actual D14 Runner.reconcile consumer also exposed a missing adopted policy: it always requests cancelled settlement, while a never-registered shutdown/protocol_error stop could only remain reconciling. The original native stop reducer allowed only pause→cancel; simply sending an explicit cancel after shutdown did not work. Root explicitly adopted a NEW cancel request dominating ANY prior stop disposition, preserving first requested_at/deadline, immutable earlier receipts, charged budgets and no acceptance/revival. Other new dispositions do not override the existing selected disposition. V3 changes the API reducer and direct verifier identically. Two new static native countercases cover shutdown/protocol_error→explicit cancel, unchanged115 deadline, no fabricated process/exit, exact old receipt replay without writes, noncancel inability to downgrade cancel, and budget/late-registration/false-return refusal.

An older immutable stop receipt still returns its historical disposition on replay. It must not replace the current attempt's authoritative stop_disposition, just as an older heartbeat receipt must not replace a newer authoritative lease. The product supervisor/reconcile consumer must implement and qualify that distinction; the old D14 consumer is not silently assumed compatible.

The RAM freeze's contract is9809B/SHA256 `441d115b45388d4c75e1a2fcdf0c0fdf1faef68d7cc8ed1aa025dd50c6a9d7d8`. It differs from the overlay root contract9035B/SHA256 `4f5b230463751a4dc65675774f19aefdac1d81fa5ab3f71beedf36db4516852c` only by the explicit RAM addendum carrying these latest root-adopted messages. Root must preserve/adopt the actual new contract in the final authoritative checkpoint; this review did not overwrite it.

Overlay free space reached0. The initial draft and observation bytes remain untouched on overlay; this final report/receipt uses small private RAM files under `/dev/shm/d15-repair-independent-review-current`. These final RAM artifacts are not claimed durable. Root must persist them and the exact accepted variant when capacity allows. No unique work was deleted.

## Remaining root qualification

After a final static freeze, root must run the current repaired native suite and affected legacy/migration/backup/restore/authority/replay/clock/refusal cases serially, with exact source/runtime correspondence. Root also owns the global Engine.verify hook on033 table OR component OR migration evidence. The leaf direct verifier is conditional and the installer invokes it; this review does not add or test the global hook.

Actual bound-worker framed checkpoints past30 seconds, immutable execution ceiling, cooperative stop plus actual exit, wedged-worker silence, guarded five-second escalation, shared owner-close drain, pidfd/procfs identity, interruption/reconciliation, retained unaccepted bytes, recipient retrieval and later continuation remain execution evidence requirements. Synthetic PID observations in native tests are explicitly not those operations. No unknown/model-worker admission, full resource calibration, human test or whole F1–F5 completion follows from this source review.

The read-only identity collector initially assumed migration_001.sql; that file does not exist, so it stopped before writing a report. It was corrected to the actual schema.sql+002–032 enumeration. No native import, DB or source mutation occurred in either collector attempt.
