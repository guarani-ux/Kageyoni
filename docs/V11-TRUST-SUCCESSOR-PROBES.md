# V11 trust successor probes

The frozen enforcement crucible remains unchanged.

Focused replay against the repaired r2 lineage showed that Q08, O08 and F07 no longer reach their original target because the candidate rejects their unsafe setup earlier. The old harness therefore reports PRODUCT_ERROR rather than PASS. These are not counted as frozen-probe passes.

Direct successor probes were executed against disposable copies of the same repaired source and preserved campaign:

- Q08 successor: one-sided supported-only reference cases cannot qualify an enforcer — PASS.
- O08 successor: a caller cannot inject a fake assessment id to move PREPARED -> ASSESSED — PASS.
- F07 successor: a frontier cannot jump directly from open -> resolved — PASS.
- N01 original focused crucible case: concurrent acknowledged operation history is retained or rejected — PASS.

The successor probes preserve the original invariant while testing the stricter boundary now enforced by the repaired implementation. The frozen original observations remain evidence of probe incompatibility and are not rewritten as passes.
