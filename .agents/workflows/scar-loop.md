# Workflow: Scar Saturation Loop

## Purpose
Systematically attack, reproduce, repair, and permanently close adversarial failure classes across Kageyoni v11 boundaries.

## Stages
1. **Adversarial Probe Formulation:** Formulate a failing attack probe targeting a specific trust, lifecycle, or boundary gap.
2. **Deterministic Reproduction:** Run probe to produce a reproducible physical exception or state corruption.
3. **Root Cause Classification:** Trace the failure to its structural root cause in runtime invariants.
4. **Upstream Source Repair:** Modify physical engine source at the root cause.
5. **Targeted Falsification & Positive Controls:** Run the failing probe (must now pass) and neighboring positive tests (must remain green).
6. **Mutation Sensitivity Testing:** Mutate the repair logic to confirm the test fails immediately (100% kill rate).
7. **Wider Regression Run:** Run full regression suite to prove no collateral breakages.
8. **Permanent Scar Preservation:** Commit probe into the permanent Scar regression test suite.
