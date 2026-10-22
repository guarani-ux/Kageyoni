# Installed product27 affected regression — stopped on first failure

Exact installed runtime: `56e54d9f91bf266d61e5364fd014a3c46bd290681609c607888014939b00cb30`; product `0.5.3.dev27`, native `11.1.0.dev16`. Same-process before/after proof matched all 238 source/wheel/installed payloads. All 32 original test source files remained unchanged.

The serial `pytest --import-mode=importlib -q -x` mandatory stage stopped after **1 passed, 1 failed in 1.74 seconds**. No retry occurred. Eighteen remaining mandatory predicates and all seven conditional predicates were not run.

| Exact original predicate | Result |
| --- | --- |
| `test_bounded_runner.py::QueueTests::test_exact_admission_retry_no_duplicate_and_clock_rollback` | PASS |
| `test_bounded_runner.py::QueueTests::test_failed_process_registration_stops_unfed_child_and_retains_reconciliation` | FAIL |

The failure is at unchanged source line 126: after the original test injects `RuntimeError('injected registration failure')` into `queue.process` and calls `runner.tick()`, its actual owned child still returns `None` from `processes[0].poll()`. The exact original `assertIsNotNone` failed. No fixture, assertion, source, installed payload, resource allowance, or product 1 GiB disk guard was changed to obtain a different result. This observation establishes failure on this candidate/run; it does not establish whether the same timing failure would occur on the predecessor, which was not run here.

Original test teardown completed and every tracked in-process Owner closed. No Client session had been started before `-x` stopped. There were no unresolved wire exchanges. The retained-world initializer detached TemporaryDirectory finalizers immediately, including before any possible setUp failure. Both temporary worlds remain intact:

- `/dev/shm/p27aff-r1/t/samsara-queue-2_mnocdt/world` — failed registration predicate.
- `/dev/shm/p27aff-r1/t/samsara-queue-ddo_ta6r/world` — passed exact admission/replay/clock rollback predicate.

Read-only inspection acquired each closed-world owner lock separately and ran integrity_check, FK, Engine.verify, validate_registry, native liveness/custody verification, and exact artifact byte/digest checks. Both worlds were valid, each connection recorded total_changes=0, and all world file hashes matched before and after inspection. Both queue rows remain reconciling with NULL process, zero custody registrations, zero absences, and zero known-exit receipts. The failed registration attempt retains a genuine `protocol_error` stop; the other world's shutdown stop came from its original teardown. No journal was deleted and no repair or extra native disposition was performed.

The failed predicate directly observed poll=None. Although teardown completed and Owner.close returned, the harness did not record a final independent child poll/reap observation. That child’s final reaping status is therefore not claimed. No later unknown PID was probed or signalled. Root should retain this evidence limit when deciding the next bounded diagnosis.

RAM/cgroup capacity was checked before every fixture and Owner/TemporaryDirectory initialization. The original 1 GiB product guard remained intact. Own retained growth at completion was 88,378,139 bytes, tmpfs free was 4,913,758,208 bytes, and conservative headroom including inactive reclaimable file cache exceeded 5.5 GB. No new OOM event occurred.

Evidence: `evidence/raw.jsonl` contains 67 actual issued/reply/lifecycle/capacity/test events, including 19 original-source frame events. `evidence/mandatory.xml` and `run-stdout.log` preserve JUnit and exact failure. `evidence/test-results.json`, four installed-proof files, `readonly-postconditions.json`, and `summary.json` retain outcomes and correspondence. The original candidate/native journal-recovery failure remains unresolved; these two valid new fixtures do not erase it.

The serial lane is released. Next action belongs to root: assess the failed immediate child-exit predicate and the final-reap evidence gap before authorizing any diagnosis, change, or additional run. This return claims neither the full affected suite nor release/general-host/sandbox/human qualification.
