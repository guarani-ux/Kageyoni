# Proposed genuine-worker fixture counterparts — NOT EXECUTED

This is bounded authoring only. `new_actual_queue_tests.py` has not been imported
or executed. No current28/source/original test, prior failure, DB or process was
changed. The original fairness test remains a historical FAIL on installed28;
these counterparts do not turn that run into a clean original20 suite.

## What changed in these two explicit counterparts

Only the two original methods that directly transition an unregistered claimed
job to returned are represented. Their original `self.assert*` expressions and
control structure around those assertions are copied unchanged. The synthetic
returned-transition fixture steps are replaced as follows:

- Fairness/shared budget: retain the original two explicit queue claims, launch
  both actual claimed rows before any service, then call only runner._service
  until both actually return. Each of the next three original explicit claims
  is launched and serviced individually.
- Parent pause/independent root: retain the original claim and every original
  assertion, then actually launch/service that chosen independent job.

The helper retains each actual Popen/live reference before _service can remove
it. It requires committed local registration, polls the actual retained Popen
for zero, checks genuine native033/034 per-attempt process correspondence and
immutable registration, and requires the real output artifact, digest, native
job result and returned checkpoint reference. It does not invent a process,
write native setup SQL, patch rows, bypass admission, call tick/auto-claim,
reprepare stale work, or write a result on behalf of a worker. A refusal,
non-running/non-returned state or bounded eight-second service timeout fails
with its actual queue/channel/settlement information.

Original setUp/tearDown/call/start/enqueue function objects are reused by direct
reference from the unchanged QueueTests class. The new class does not inherit
original test methods, preventing duplicate inherited collection. Root should
still select only the two explicit new node IDs below.

Every original test-body assertion is intended to retain its exact AST. No test
or source-validation code has been executed in this authoring commission. Root
can statically compare the original assertion nodes before giving execution GO.

## Proposed explicit next selection: 18 unchanged + 2 counterparts + conditional 7

This is a proposed new bounded run, not an execution request already performed.
The 18 unchanged predicates below mean the original20 minus the two direct
synthetic-return cases; they include two predicates that already passed in the
stopped28 run. They are not eighteen previously unrun predicates. The new
counterparts must be reported separately from original tests. Preserve the
original fairness FAIL and original parent-pause NOT RUN status.

For these node IDs, `ORIGINAL` means the absolute directory
`/workspace/scratch/5c7ed9200168/recovery-20261022/current26/extracted/samsara_core/product/tests`.
`NEW` means
`/workspace/scratch/5c7ed9200168/recovery-20261022/product28-actual-queue-fixture`.

The 18 unchanged original predicates:

1. `ORIGINAL/test_bounded_runner.py::QueueTests::test_old_epoch_expiry_and_wrong_token_never_accept`
2. `ORIGINAL/test_bounded_runner.py::QueueTests::test_exact_admission_retry_no_duplicate_and_clock_rollback`
3. `ORIGINAL/test_bounded_runner.py::QueueTests::test_revoke_queued_authority_and_worker_cannot_request_diagnostic`
4. `ORIGINAL/test_bounded_runner.py::QueueTests::test_finished_output_survives_owner_loss_without_accepting_stale_lease`
5. `ORIGINAL/test_bounded_runner.py::QueueTests::test_failed_process_registration_stops_unfed_child_and_retains_reconciliation`
6. `ORIGINAL/test_bounded_runner.py::QueueTests::test_one_cpu_lane_still_admits_independent_io`
7. `ORIGINAL/test_bounded_runner.py::QueueTests::test_managed_and_manual_returns_charge_shared_parent_once`
8. `ORIGINAL/test_bounded_runner.py::ProcessRunnerTests::test_two_actual_jobs_overlap_and_pause_cancel_keep_owner_responsive`
9. `ORIGINAL/test_bounded_runner.py::ProcessRunnerTests::test_actual_output_fresh_recipient_and_explicit_parent_continuation`
10. `ORIGINAL/test_bounded_runner.py::ProcessRunnerTests::test_owner_kill_requires_observed_reconciliation_and_new_generation`
11. `ORIGINAL/test_bounded_runner.py::ProcessRunnerTests::test_strict_stale_result_preserves_bytes_without_rebase`
12. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_revoke_before_exact_retry`
13. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_live_operation_grant_is_enforced_on_retry`
14. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_atomic_world_and_operational_commit_failure`
15. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_hidden_source_and_wrong_workspace_cannot_start`
16. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_expired_chunk_token_refuses_even_exact_retry`
17. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_worker_is_not_operator_and_frame_bool_revision_rejects`
18. `ORIGINAL/test_application_integrity.py::ApplicationIntegrityTests::test_staging_admission_is_bounded_and_inspection_remains_callable`

The two explicit genuine-worker counterparts:

19. `NEW/new_actual_queue_tests.py::ActualQueueFixtureTests::test_fair_parent_selection_capacity_and_shared_budget`
20. `NEW/new_actual_queue_tests.py::ActualQueueFixtureTests::test_parent_pause_and_cancellation_block_descendants_not_other_roots`

Only if all first20 pass, the seven previously selected original conditional
predicates, retaining their own authentic fixture data/assertions:

21. `ORIGINAL/test_private_sourcework.py::test_private_native_inquiry_scaffold_and_exact_retry_reopen`
22. `ORIGINAL/test_private_sourcework.py::test_c2_only_source_becomes_private_native_and_withdraws_all_derived_reads`
23. `ORIGINAL/test_private_sourcework.py::test_private_source_withdrawal_after_prepare_prevents_native_commit`
24. `ORIGINAL/test_private_sourcework.py::test_private_source_with_future_keeper_parent_refuses_before_native_ingest`
25. `ORIGINAL/test_artifact_audience.py::test_immutable_audience_survives_accidental_grant_and_transitive_copy`
26. `ORIGINAL/test_artifact_audience.py::test_restricted_intake_dedup_keeps_raw_extracted_and_manifest_audiences`
27. `ORIGINAL/test_artifact_audience.py::test_borrowed_output_and_tool_refs_cannot_relay_private_or_undelivered_bytes`

Any future run still requires root GO, installed28 proof, import-mode importlib,
serial ownership, -x, fresh capacity guards, unchanged 1 GiB product guard,
immediate temporary-world retention, actual owned-child observation, and
read-only closed-world postconditions. No failure should be repaired or retried
inside that run. No release or general-host qualification is proposed.
