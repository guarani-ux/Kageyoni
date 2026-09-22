# V7 — bounded local repository and pipeline execution

After `install_pipelines(engine)`, `Application(engine).repository` and `.pipelines` expose
owner-only local execution. No model API, API key, external publishing or push
is involved. Test programs run with the operator's operating-system permissions;
this runner is not a security sandbox for untrusted repositories.

## Repository loop

`Repository.prepare(branch, request_id, source_dir, workspace_dir, patches,
test_argv, qualification_id)` creates a separate candidate from a bounded source
tree. Each patch has `path`, `before_sha256`, and complete UTF-8 `content`.
Existing tests cannot be patched through this interface. `test_argv` supports
`['python','-m','unittest','discover']`. A V5 repository transfer candidate is
required; preparation and checking constitute a trial, not demonstrated competence.

`check(branch,candidate_id,timeout_seconds=30)` actually runs unittest discovery,
requires at least one test and exit zero, and binds before/after tree digests.
The mapped registered method actually executes over recorded test metrics
(`tests`, passed `checks`, `failures`). Retained unknown guards or unsupported
metric mappings remain unresolved and cannot qualify or promote. The resulting
operation, guards, inputs and method effect are bound into the trial receipt.
Failed and interrupted attempts remain recorded. A changed candidate fails closed.
`promote(branch,candidate_id,destination)` requires a qualified destination transfer,
passed checks, identical candidate bytes and a new destination. `trial_artifact`
creates exact executed-check evidence; V5 calls `validate_trial` against the
persisted test attempt and current tree, so caller-supplied passed flags cannot
qualify a repository transfer. Promotion also binds that exact trial artifact. Promotion checks
copied bytes again. `reconcile` resolves completed copies by digest; a partial
preparation retains its intent and asks for an inspected new-destination retry.
A running test interrupted before its receipt becomes failed, never passed.

## Pipeline loop

`create(branch,request_id,tasks)` accepts a bounded acyclic graph. Each task has
`id`, `kind`, `config`, optional `dependencies: [{task_id,type}]`. Every declared
`DEPENDS_ON`, `REQUIRES`, `AFTER`, and `USES` dependency blocks until completed.
Unknown edge kinds are rejected. Task kinds:

- `repository_check`: config `{candidate_id}`; real check must pass.
- `write_file`: config `{root,path,content,expected_sha256,max_bytes?}`; create-new
  UTF-8 file with exact hash. Instead of `content`, `content_from` can name a
  declared blocking dependency whose actual string result supplies the bytes;
  the expected hash still must match. Active V8 artifact policy applies when installed.
- `artifact_read`: config `{artifact_id,expected_sha256,composition_id?}` reads
  immutable UTF-8 artifact bytes into a downstream result. When a collective
  composition is named, the engine verifies its body ancestry and exact artifact
  identity before consumption.
- `manual`: waits for an attributed owner observation. `resume_manual` requires
  `{disposition:'completed'|'waiting'|'failed',value,...}` and rationale; a pending
  or failed answer does not release dependent work.

`run(branch,pipeline_id,max_steps=10,timeout_seconds=30)` retains each real attempt
and returns an honest completed, waiting, failed, or reconcile_required state.
It pins component versions across suspension. Re-running failed code actually
invokes the checker again. Exhausted step budget preserves work for resume.

Writes persist intent before O_EXCL creation, fsync bytes before recording receipt,
and never blindly repeat after interruption. `reconcile` checks exact current
bytes: matching effect completes without another write, absent effect permits an
explicit retry, conflicting bytes wait for owner recovery. Preexisting identical
files are not claimed as effects from this workflow. Symlink roots/paths and path
traversal are rejected. Pipelines never overwrite an existing file.

## Evidence and limits

`tests/test_v7_pipeline.py` includes an actual child-process exit after fsync and
before receipt, exact-candidate mutation rejection, real retries, dependency
controls and bounded execution. Isolated repository tests mock V5 qualification
only to test local repository mechanics; the integrated demo exercises V5 itself.
Passing tests establishes behavior for these cases, not arbitrary repository
correctness or trustworthiness of test programs. Human semantic judgments remain
attributed. World/campaign records are not changed by repository/pipeline actions.

## Relocated recovery

Each candidate and pipeline pins its originating database path. Reads remain
available after export/import or restore, but mutation/execution is blocked until
an owner explicitly rebinds local paths. `Pipelines.rebind(branch,pipeline_id,roots)`
requires an old-root → new-root mapping for every write task. Pending destinations
must be absent; completed/uncertain effects must be present with exact bytes before
reconciliation or retry. Referenced repository candidates must be rebound first.
`Repository.rebind(branch,candidate_id,source_dir,workspace_dir,destination=None)`
checks saved source, candidate and promoted digests. Both retain historical attempts
and append old/new path provenance; rebind does not rewrite test evidence. External
repository trees and outputs must be carried separately from the database bundle.
