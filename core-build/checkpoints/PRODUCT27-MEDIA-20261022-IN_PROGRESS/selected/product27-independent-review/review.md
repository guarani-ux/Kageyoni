# Independent product27 source review

Reviewed frozen patch SHA-256 `1c294476ca5e0f446f2078b7a933a6a451adb6b291d4771d50703ed29d19ba2e` against exact `current26/extracted/samsara_core/product`, root-adopted `D15b-product-root-seam.md`, preserved native034 absence-only contract, and actual `native034-r1/engine` APIs. The earlier independent media-participant encounter remains closed and supplied no input to this separate source-review decision.

## Spec and trust boundary

No actionable runtime defect found in this bounded source review.

- **Before-task atomicity:** `samsara/runner.py` lines 567–579 obtain the handshake and actual provider registration before the outer `UnitOfWork`. `JobQueue.process` and `WorkerCustody.register` run inside that one outer boundary using the same fence, identity, and wall reading. Actual native `UnitOfWork` owns the outer commit and uses nested savepoints; native register's nested boundary does not commit the product outer transaction. Only afterward does the runner set `live['registered']` and pump task bytes. The exception path at lines 580–590 closes stdin when registration has not completed and retains the actual-Popen observation path. No synthetic native registration or guessed exit is added.
- **Both dispositions and replay:** `samsara/application.py` lines 895–905 prepare every new `job.reconcile` outside the command UoW, with exact workspace/grant/revision handling preserved. Stored request replay bypasses preparation and still checks the immutable request digest. Independent execution of the actual extracted `handle` method with inert dictionary collaborators confirmed this for both discard and recover. Recover replay retains the existing protected artifact-integrity read; no new provider call or worker-output-file read occurs.
- **Private, pinned preparation:** `runner.py` lines 377–401 bind workspace, activity/version, exact queue fence, worker binding/authority/process/state, full binding row, registration digest, operator binding record, and prepared job-row digest. Lines 415–461 authorize before observing; owned unsettled Popen is BUSY; actual provider observation is normalized against the genuine stored registration; recover uses unchanged strict `_output`; the pin is checked again after observations. Lines 467–497 reauthorize, re-read, and compare pin and full registration before native mutation. The exact private carrier type is required; it is not part of the participant contract.
- **Absence/known-exit/no-registration:** Existing validated absence avoids fresh provider observation and stop mutation. A new normalized absence crosses into the command UoW at lines 498–508 only after a genuine native stop intent exists. Lines 509–513 avoid cancel dominance after terminal absence. Native APIs distinguish an absence with unknown returncode from an integer exit. Missing old034 companion cannot be backfilled by this path: `WorkerCustody.row` fails before the provider is used. Known exits and truthful no-registration reconciliation retain their existing routes.
- **Recovery and integrity:** Recovery adds the exact preflight bytes as an unaccepted component with prepared input lineage and an explicit continuation requirement at lines 515–525. Discard does not add a recovered component. `_output`, generic protected artifact readers, process settlement, historical suppression of signals, and existing stop/supervision bodies are AST-identical to product26. Queue disposition remains explicit cancellation without refund or automatic retry.
- **Native coupling:** Direct native033 verification invokes native034 verification. Native034's verifier calls only per-attempt liveness reads and bounded correspondence helpers, not the global033 verifier, so the inspected coupling introduces no global-verifier recursion. Terminal absence validates the real companion/receipt, current fence, token, historical process and stop correspondence rather than inferring absence from NULL process/exit fields. Native transition guards allow the explicit terminal disposition without revising the first absence receipt. Owner readonly preflight requires034; explicit synthetic initialization installs034; the product runtime fingerprint includes exact provider bytes.

The source observations above concern provider/process and worker-output observation placement. They are not a proof that every inherited filesystem operation is absent from a UoW: native migration checksum resources and the existing artifact integrity/materialization path still perform their established resource/file access. The patch preserves those integrity paths as requested.

## Repository standards

No documented-standard violation or sufficiently useful smell finding identified. Standards inspected: `AGENTS.md`, repository `README.md`, `workflows/council.md`, and the full Law review profile. No `CODING_STANDARDS` or `CONTRIBUTING` file was present in the examined checkout. Existing direct-work and evidence-scope rules were followed; no extra reviewers were fabricated or spawned. Shared versions and engine locks remain intentionally unbumped pending root build, as commissioned, and are not a finding.

## Executed evidence

`source_countercases.py` ran once with the installed current26 Python executable. It imports no product/native runtime and opens no database, worker, provider, or world. Actual source methods are extracted by AST and run only against inert Python dictionaries for the replay/pin/data-carrier checks.

Eight checks passed:

1. Exact frozen patch reconstructs every changed successor file from exact product26 in memory.
2. All 32 existing Python test files remain byte-identical.
3. Protected output/artifact/process methods retain their exact ASTs.
4. Adopted provider bytes are exact: SHA-256 `0e3a51bb8c63e30dd4ab55242528052177c58afa4320f7f3ae1bc32f80387340`.
5. Actual discard receipt replay bypasses new observation/preparation.
6. Actual recover receipt replay bypasses new observation/preparation and preserves protected-result integrity checking.
7. Twelve distinct prepared-input/binding/authority/registration/activity/fence/process/state mutations change the actual private pin.
8. Eight malformed time/payload/carrier cases are rejected by the actual private carrier.

Detailed observations are in `source-countercase-results.json`. The test script itself is retained. The frozen patch digest was checked before and after these checks.

## Remaining qualification and continuation

This review executed no native transaction, process, signal, DB recovery, build, installation, participant session, current-world operation, or source mutation. Before-task failure cleanup and real native savepoint/commit semantics were source-inspected, not runtime-qualified here. The existing native journal-recovery failure remains an adoption/qualification limit; a healthy RAM fixture does not erase it.

Root can use this return as a bounded source-review input to the next adopted build/qualification decision. Installed dual-commit interruption, real owner loss, retained-output recovery/discard, old-save compatibility, backup/restore/relocation, and the unresolved journal behavior still require their separately authorized evidence. No human/full-release claim is supported by this review.
