# Installed product28 affected regression — stopped on first failure

Installed runtime `1289b896d6de9194f286a0e9860e20ff65337b78a3efb536bae981cd90ebc858`, product 0.5.3.dev28 / native 11.1.0.dev16. Same-process before/after proof preserved all 238 exact source/wheel/installed payloads; all 32 original test files remained unchanged.

Serial original `pytest --import-mode=importlib -q -x` stopped after **2 PASS, 1 FAIL in 3.75 s**. Seventeen remaining mandatory predicates and all seven conditional predicates were not run. No retry, assertion/source change, guard relaxation or substituted fixture occurred.

| Exact original QueueTests predicate | Result |
| --- | --- |
|`test_exact_admission_retry_no_duplicate_and_clock_rollback`|PASS|
|`test_failed_process_registration_stops_unfed_child_and_retains_reconciliation`|PASS|
|`test_fair_parent_selection_capacity_and_shared_budget`|FAIL|

The failed-registration predicate's actual owned child was captured without changing its behavior. Raw event 59 issued actual Popen.wait(timeout=0.1); event 60 returned actual 21 about 1.2 ms later; event 61's service poll, event 64's original assertion poll, and final event 161 poll all returned 21. The final observation reaped/confirmed the actual Popen status rather than inferring a code from native state. No signal was added. Its retained native history still contains no custody registration, absence or known-exit receipt.

The new failing original predicate claims two queue jobs without registering an actual process, then calls `queue.transition(first['job_id'],'returned',clear_process=True)` at unchanged `test_bounded_runner.py:53`. Installed native `kageyoni/workspaces/job_queue.py:205` rejects this with **`Rejected: stopped worker cannot return`**, because the strict normal-return predicate requires a registered process identity. The unchanged original assertions were not bypassed. The run establishes this candidate/predicate failure; no predecessor differential was executed. Root must assess the queue-only fixture/strict native-return contract before authorizing further work. This stopped run does not authorize weakening the actual-process guard or editing the original predicate.

All three tracked in-process Owners closed; no Client session was reached. The sole actual Popen Python reference ended with 21, so no captured active/uncertain process or unknown wire exchange remains. Observation wrappers recorded original Popen construction/poll/wait calls; they neither invented process references nor instrumented separate owners' children. All generated TemporaryDirectory worlds were retained immediately:

- `/dev/shm/p28aff-r1/t/samsara-queue-aowcwiam/world` — exact-admission predicate.
- `/dev/shm/p28aff-r1/t/samsara-queue-wljd16p4/world` — failed-registration predicate, now passed.
- `/dev/shm/p28aff-r1/t/samsara-queue-i904icyd/world` — failed fairness predicate.

After all Owners closed, each world independently obtained the closed-owner lock and passed read-only integrity_check, FK, Engine.verify, validate_registry, liveness/custody verification and exact artifact integrity checks. Every connection had total_changes=0, and complete before/after file manifests matched. The fairness world retains two reconciling and five queued rows; teardown preserved real shutdown intent for its two claimed/unregistered attempts. No world was repaired and no journal was removed.

Own retained growth was 132,681,735 bytes; tmpfs free 4,780,974,080 bytes. Every fixture/Owner/temp initialization passed the fresh capacity guard, the original product 1 GiB guard remained intact, and no new OOM event occurred.

Evidence: `evidence/raw.jsonl` has 164 actual events including 50 original-source frame events; `evidence/mandatory.xml` and `run-stdout.log` preserve the exact failure. `summary.json`, `evidence/test-results.json`, installed proof pairs and `readonly-postconditions.json` contain exact outcomes, Popen status and world manifests. The earlier 27 failure/evidence remains unchanged.

Serial DB/process lane released. Root owns the next contract/fixture diagnosis. The full affected suite remains incomplete; original native journal-recovery failure remains unresolved. No release/general-host/sandbox/human qualification follows from these results.
