# Failed-registration diagnosis and separate successor28 source review

## Finding

The exact original immediate-exit predicate failed on installed27 because `tick()` can return after closing the unfed worker's stdin but before the operating system has completed and reaped that worker's natural exit. The source provides no exit-observation barrier between those actions. This is a real failed acceptance predicate on27; the source comparison does **not** establish that27 removed an immediate-exit guarantee previously implemented in26. The same scheduling gap already exists in26.

This diagnosis reads only existing source and logs. It does not rerun the test, inspect a process, open a DB, change source/assertions, or repair evidence. The already executed original test is the retained red signal. No repeated/deterministic reproduction or differential predecessor execution is claimed. The diagnosing-bugs workflow's new reproduction/minimization steps were intentionally not performed under the root's read-only commission.

## Actual observations and their limits

The unchanged original `current26/extracted/samsara_core/product/tests/test_bounded_runner.py` lines117–129 captures the actual Popen, injects a failure into `queue.process`, invokes `runner.tick()` at125, then requires `processes[0].poll()` to be non-None at126 without another runner service call or a wait. That assertion failed. It must remain unchanged.

Existing `product27-affected-r1/evidence/raw.jsonl` records:

| Sequence | Observation | Wall time |
| --- | --- | --- |
|54|Original test reaches `runner.tick()` line125|1792693874.2907794|
|55|Original test leaves the patch block after tick|1792693874.320392|
|56–57|Line126 followed by `AssertionError('unexpectedly None')`|1792693874.3204389–1792693874.3204854|
|59|Original teardown calls Owner.close|1792693874.320686|
|60|Owner.close returns|1792693874.3251202|

The earlier read-only `product27-affected-r1/readonly-postconditions.json` records the failed world's queue reason as `unregistered child exited; no native exit identity invented`. It also records NULL native process and exit_json, no custody registration, no absence, no known-exit receipt, a genuine protocol_error stop at1792693874.3192194 and fixed deadline1792693879.3192194. Teardown's later shutdown receipt preserves that same first time/deadline and selected protocol_error disposition.

The queue reason adds useful **source-backed** teardown evidence: its only current writer is `_observe_terminal`, gated behind a real Popen returncode, reached by `_service_live` after actual `Popen.poll`. It supports an inference that teardown subsequently observed/accounted for the unfed child exit. It is not a separately captured final numeric Popen returncode, PID, or independent reap probe. Natural EXIT21 is the worker's source-defined expected EOF outcome, not a numeric status logged by this run.

The test does not assert that the mocked `queue.process` was reached, and the raw trace does not record the swallowed `_launch` exception class or provider call result. A provider failure before that injected call is therefore not ruled out. Both pre-registration failures take the same EOF-close/asynchronous-exit path, so that uncertainty does not change the demonstrated missing barrier.

## Causal source path and predecessor comparison

All new27 references here are to `product27-build/package/samsara/runner.py`; old26 references are to `current26/extracted/samsara_core/product/samsara/runner.py`.

1. **Worker is still a running process when the parent receives identity.** The byte-identical `local_worker.py` prints/flushed the identity at296–300, sets limits/nonblocking descriptors at301–307, then calls `read_task` at308. `read_task` detects actual stdin EOF and raises `WorkerExit(EXIT_DETACHED)` at75–89. That exception returns21 at319–320 and `SystemExit(main())` exits the interpreter at328–329. Receiving identity or closing the parent's pipe does not wait for those subsequent instructions or kernel exit/reaping.
2. **New registration ordering is stronger before work, not a failure-exit barrier.** New27 `_launch` lines567–579 adds actual positive provider registration and one outer UoW for native033process/native034register; the local registered flag and first task pump follow the outer commit. Old26 lines413–420 had handshake, nativeprocess, flag, task pump. If queue.process raises, native `UnitOfWork.__exit__` rolls back before the new27 outer exception branch; no task pump is reached. Provider failure likewise cannot reach task bytes.
3. **The failure branch is unchanged.** New27 `_launch` lines580–590 and old26 lines421–431 have identical exception-handler ASTs: mark channel_error, close stdin while unregistered, then persist/request protocol_error stop. Neither waits, polls, or services the child before returning.
4. **Tick services before launching, not after this failed launch.** New27 lines899–915 and old26 lines740–756 are AST-identical. `_service()` executes at the beginning. After `_launch`, any local unregistered record breaks the admission loop. No second `_service()` or actual Popen wait occurs before `tick()` returns. The guard correctly prevents additional admission while this child remains unobserved; it does not satisfy the immediate-exit assertion.
5. **Later service owns real observation.** New27 `_service_live` lines814–841 obtains actual `process.poll()`. None retains the child/charge and permits guarded escalation only at the first stop deadline. A real code is copied into `live['returncode']` and then reaches `_observe_terminal`. That method lines709–744 refuses missing actual returncode; the native-unregistered branch changes queue reason/state without inventing a native identity or exit receipt. These methods are unchanged from26.
6. **Close supplies the later service window.** New27 lines917–949 and old26 lines758–790 are AST-identical: one shared existing five-second drain, then existing guarded escalation/observation; no per-child fresh five-second wait. Owner.close calls runner.close before closing the engine (`owner.py` lines180–195). The retained reason and roughly4.4ms teardown interval are consistent with natural EOF exit being observed there, after the failed assertion.

Static comparisons also found `_cache_stop`, `_pump_input`, `_service`, `_service_live`, `_observe_terminal`, `tick`, and `close` unchanged26→27, and local_worker byte-identical. The new provider/outer transaction and absence guards can change scheduling opportunities and timing. This single run does not establish their direction or their causal effect on a previously passing execution. A correct classification is **an inherited synchronization gap exposed by a real27 predicate failure**, with predecessor runtime behavior untested.

Competing explanations retained: a provider failure earlier than the mock is possible but reaches the same gap; a failure of native stop persistence is contradicted by genuine retained stop receipts; a five-second grace expiration cannot explain the immediate assertion because its fixed deadline was still almost five seconds away. No permanent leak or before-grace signal is demonstrated by these records.

## One smallest proposed repair

After the genuine protocol_error stop has completed, add one narrowly gated helper for this fresh unfed local child:

- Require an actual local live record, `registered == False`, `task_offset == 0`, and already-closed stdin.
- Assert outside-UoW operation.
- Call that owned Popen's `wait(timeout=0.1)` once. This is real exit/reap synchronization, not a guessed EXIT21, a fixed sleep, or a signal.
- On `subprocess.TimeoutExpired`, return without deleting the live record, changing process/queue custody, manufacturing an exit, or releasing capacity. Existing later service/close retains its original first-stop semantics.
- Only after wait succeeds, pass a freshly reread queue row and the same live record to existing `_service_live`; its actual poll and native-unregistered settlement path perform the existing accounting/handle cleanup.

This adds at most the configured100ms wait to one failed launch, plus existing bookkeeping. Tick already stops after an unregistered failed launch, so this does not create a five-second-per-child stall. The helper has no new wait on registered/running work and no task/stop write. It does not call Owner.close or drain unrelated jobs.

The first-stop receipt/deadline stays immutable: native `WorkerLiveness.request_stop` lines169–170 preserves the original requested time/deadline, and existing `_cache_stop` lines598–615 preserves the original monotonic candidate/minimum. The helper needs no new stop request, grace reset, or early kill. After successful wait, `_service_live` sees a real cached terminal returncode, so its code-is-None escalation branch is not taken. The native-unregistered route still produces no fake native exit receipt.

A100ms timeout is deliberately not an unconditional scheduling theorem. A severely delayed child can remain unobserved at timeout, in which case safety requires retaining it and the original immediate-poll predicate may still fail. The original assertion remains the rejection-capable acceptance test. No pass for the proposed repair is inferred here.

## Separate read-only review of root successor28

Root supplied `product28-build/package/samsara/runner.py` after the diagnosis. Its SHA-256 is `20cb96dda98daa42b0949f3bb6b7eda47eba20d24a2b80a179209dc272d55832`. The preserved27 runner is `bc7facde3ea38912124840edf49bb394bcb23a452fd9701d0f618e1402eb13eb`.

**No actionable introduced flaw found in the exact helper/call source.** The only changed existing runner method is `_launch`; `_drain_unfed_exit` is the only added method.

- Line590 retains the genuine `_request_stop` before the helper call at591. If stop persistence raises, the helper is not entered.
- Lines593–597 enforce outside-UoW and exactly the local/unregistered/unfed/closed-stdin scope. Normal committed registration and any partial/full task delivery bypass the wait.
- Lines601–604 use actual owned `Popen.wait(timeout=0.1)` and preserve the child/live record on timeout. No signal, receipt, queue transition, or first-stop mutation is performed in the helper.
- Line605 invokes the existing `_service_live` with a fresh queue row only after wait success. Existing actual-poll/terminal guards remain responsible for accounting. A terminal Popen cache makes its code-is-None kill branch inapplicable on this success path.
- Before-task provider/outer-native-commit/registered-flag/task ordering at567–579 is unchanged27→28. `_request_stop`, `_cache_stop`, `_service_live`, `_observe_terminal`, `tick`, and `close` have identical ASTs to27. There is no broadened registered-worker wait, admission exception, early signal, fresh five-second grace, synthetic numeric exit, or native absence shortcut in this source change.

Source inspection cannot verify100ms behavior under actual scheduling or the original assertion's pass. Root's proposed actual original-test and pure timeout/admission checks remain the next evidence. The27 failure and all earlier raw evidence remain intact; no rerun or DB/process action was performed in this commission. The separate original native journal-recovery limitation remains unresolved.
