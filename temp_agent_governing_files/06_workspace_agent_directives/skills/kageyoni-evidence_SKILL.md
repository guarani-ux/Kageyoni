---
name: kageyoni-evidence
description: Permanent evidence laws, custody requirements, and anti-theater standards for Kageyoni v11 qualification.
---

# Kageyoni Permanent Evidence Laws

No claim is qualified without satisfying these physical evidence laws.

## 1. The Ten Evidence Laws
1. **Artifact name is not evidence.** (A file named `success.json` does not prove success.)
2. **Test name is not evidence.** (A test named `test_package_parity` does not prove parity unless it falsifies non-parity.)
3. **Model statement is not evidence.** (Self-assertion of correctness is untrusted candidate hypothesis.)
4. **Generated JSON is not evidence unless its fields derive from observed execution.** (Mocked, static, or synthetic dictionaries are rejected.)
5. **A `.patch` is not an applied repair.** (Required fixes must be verified in physical target source code.)
6. **A Git commit is not a passing test.** (Commits only establish lineage, not behavioral validity.)
7. **A passing test does not prove that the test measures its named claim.** (Must prove causal sensitivity via mutation or negative controls.)
8. **A local pass is not a clean-install pass.** (Clean virtual environment installation and parity checks are mandatory.)
9. **Kageyoni cannot independently prove its own semantic superiority.** (Empirical comparison requires frozen rubrics, blind execution, and external ground truth.)
10. **Every release claim requires provenance.** (Must identify exact commit SHA, raw telemetry, falsifier, and runtime environment.)

## 2. Release Gate Audit Protocol
Every qualified release gate must explicitly emit:
- **CLAIM:** Exact statement being established.
- **FALSIFIER:** Precise adversarial condition that would invalidate the claim.
- **MEASUREMENT:** Objective measurement technique used.
- **RAW EVIDENCE:** Path or reference to unmodified execution telemetry.
- **PROVENANCE:** Git SHA, execution timestamp, environment details.
- **WHAT THIS ESTABLISHES:** Narrow boundary of demonstrated fact.
- **WHAT THIS DOES NOT ESTABLISH:** Explicit boundaries, non-transferred domains, and remaining unknowns.
- **STATUS:** `PASS` / `FAIL` / `UNQUALIFIED`.
