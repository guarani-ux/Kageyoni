# Workflow: Repository Repair & Baseline Integration

## Purpose
Govern the complete reconciliation, baseline repair, and invariant enforcement of Kageyoni v11 through an engine-held Repository Repair Situation.

## Stages
1. **Freeze Baseline:** Record exact Git SHA, working tree cleanliness, and active environment.
2. **Audit & Lineage Mapping:** Map inherited Foundation against Git branch. Reconcile all differences.
3. **Patch Elimination:** Audit every file in `patches/`. Classify as `APPLIED`, `PARTIALLY_APPLIED`, `SUPERSEDED`, or `UNAPPLIED`. Migrate all required fixes into physical source.
4. **Mechanical Baseline Gate:** Run regression test matrix. Cluster all failures by shared upstream cause.
5. **Upstream Repair:** Apply minimal, mathematically pure repairs without parallel production bypasses.
6. **Frontier & Ledger Check:** Update Kageyoni Frontiers and completion ledger.
