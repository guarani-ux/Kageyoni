# Kageyoni v11.0.0 handoff

Status: implemented v11 foundation with adaptive enforcement substrate. This release does not claim autonomous semantic judgment or independent multi-agent verification.

## What changed

- Canonical admission: only admitted, scoped aspects can affect resolution; collisions, counterfeit identities, malformed candidate shapes and inactive supplied inputs fail closed or remain explicitly unresolved.
- Conditions survive expression. Unsupported or unevaluated effect conditions cannot silently become unconditional pressures.
- Generic resolution binds to explicit/current context rather than dropping branch/revision scope.
- Canonical claims require admitted evidence from runnable compilations.
- Engine-custodied preparation binds proposal identity, command, compilation, basis and revision. Caller-created preparation cannot authorize commit.
- Post-commit verification faults return an explicit committed-but-unverified recovery receipt and compatibility marker; they do not imply that no effect occurred.
- Composition/knowledge/v11 structures participate in global verification. Knowledge-route transitions are atomic under concurrent use.
- Explanation traversal is iterative and bounded rather than Python-recursion-limited.
- Pipeline destination waits can resume after their blocker is actually remedied.
- Protected-operation state machine separates declared, prepared, assessed, authorized, executed, observed, verified, uncertain, blocked and completed states. Objective and requirement identity cannot silently change during adaptation.
- Context packets preserve included, unresolved and excluded material. Blocking unknowns prevent a commit-sufficiency claim; omission is not represented as absence.
- Frontier records support bounded investigation, capability and representation pivots while preserving the parent objective.
- Enforcer competence is now earned rather than self-labelled: qualification requires engine-held evaluation cases and recorded trials within scope. Wrong trials exceed the default error budget and block qualification. Qualified assessments remain scoped and evidence-bearing.

## Migrations

- 019: preparations, enforcer qualification/assessment records, frontiers.
- 020: protected operations and virtualized context packets.
- 021: engine-held enforcer evaluation cases and trials.

All are additive. `v11_enforcer_eval` is operational metadata and is excluded from world-resolution fingerprints, so installing it does not invalidate pending world decisions merely because the enforcement substrate advanced.

## Executed qualification

- V11 enforcement tests after earned-qualification hardening: **18 passed**.
- Adaptive-loop acceptance tests: **4 passed**: unresolved story dependency remains blocked; artifact dependency can resolve and resume; technical reality-contact evidence returns to the original contract; frontier adaptation cannot rewrite the parent objective.
- Current critical regression set (v11 + adaptive-loop tests + all v10 tests + release integration + composition/pipeline/operations): **97 passed, 6 subtests passed**.
- Updated release-integration witness: **4 passed, 6 subtests passed**. The original v10 copy of that test is retained under `evidence/v11/`; its hard-coded max-migration=18 assertion is superseded by the additive v11 migrations, while state/fingerprint preservation remains tested.
- Replayed v10 adversarial lanes against this v11 source:
  - governance: **16 PASS**, 1 retained capability-gap note, 0 FAIL/ERROR;
  - evidence: **12 PASS**, 4 retained semantic limitations, 0 FAIL/ERROR;
  - stress: **14 PASS**, 4 benchmarks, 0 FAIL/ERROR.
- Broader inherited-suite attempts were also run, but combined invocations exceeded the execution window before completion. They are not represented as a full-suite pass. Earlier per-file runs found one version-pinning assertion, which is the release-integration assertion explicitly updated and preserved above.

## What the evidence does not establish

The deterministic runtime still cannot prove arbitrary source-to-claim entailment, narrative quality, professional competence or that every consequential context item has been discovered. Semantic assessment remains a host/model/human responsibility whose results can be recorded and gated only after scoped qualification.

Engine-held evaluation cases make competence claims auditable and prevent direct self-promotion, but the quality of the reference cases still depends on whoever authoritatively establishes those cases. This is not independent certification.

No external paid API, autonomous worker swarm, universal ontology or automatic external-action authority is introduced. A host route that bypasses Kageyoni is outside Kageyoni's enforcement guarantee.

## Start

Use `kageyoni.persistence.migrations.install_v11(engine)` on an exact v10 lineage copy, then run `engine.verify()`. Preserve the source database until the migrated copy and campaign-specific checks are accepted.
