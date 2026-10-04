---
name: kageyoni-release
description: Release qualification, clean-room reproduction, package-source parity, and anti-premature reporting governance.
---

# Kageyoni Release Qualification Governance

A release is not a declaration; it is a reproducible, clean-room artifact proven by independent reproduction.

## 1. Release Invariants
- **No Self-Certification:** The builder cannot declare its own build complete. Evaluation, evidence audit, and reproduction must execute under separate roles.
- **Package / Source Parity:**
  - Build wheel (`.whl`) and sdist (`.tar.gz`) from clean commit.
  - Unpack wheel in an isolated scratch space.
  - Verify 100% file list parity against qualified source (migrations, schemas, modules).
  - Verify module importability in fresh virtual environment without build dependencies.
- **No Premature Reporting:** A passing slice or unit test is never reported as complete release qualification until all 10 release gates pass and the Final Adversarial Review reveals zero open material findings.
