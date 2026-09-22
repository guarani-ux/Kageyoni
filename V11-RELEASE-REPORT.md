# Kageyoni v11 Release Status

**Working branch:** `v11-situation-build`
**Status:** **RELEASE CANDIDATE — QUALIFICATION OPEN**

The previous Mid-Yonko completion claim is withdrawn pending independent reproduction.

## Mechanically demonstrated candidate areas
- inherited Kageyoni engine is present in Git;
- v11 ProtectedOperations and Situation Architecture are implemented;
- Situation integration, trust, Scar and mutation test suites exist;
- pipeline trust mediation is mandatory in production source as of the post-audit repair.

## Open release gates
1. **R5 comparative qualification:** previous evidence used predetermined metric profiles. Those profiles were removed. R5 now requires observed task executions and evidence-backed scoring with no expected winner.
2. **R6 long-horizon qualification:** previous evidence injected a qualified capability and changed outcome. That path was removed. R6 now requires observed repeated encounters and evidence-backed capability/outcome changes.
3. **Package/source parity:** must be reproduced from an exact Git SHA by building and installing the package in a clean environment, then comparing installed contents/hashes to qualified source.
4. **Independent CI reproduction:** the release candidate must pass the complete qualification workflow on GitHub Actions.
5. **Completion ledger:** may be closed only from reproduced evidence, not by copying prior release claims.

Historical evidence and reports remain in the repository for auditability; they are not current qualification authority.

No v11 release tag or promotion to `main` should occur until these gates pass.
