# Kageyoni 11.0.0 Release Report

**Release Identifier:** `v11.0.0-qualified`  
**Working Branch:** `v11-situation-build`  
**Status Authority:** Machine-Derived from `evidence/qualification/qualification.json`  
**Overall Status:** **PASSED / INDEPENDENTLY QUALIFIED**  
**Date:** September 22, 2026  

> [!NOTE]
> The previous withdrawal notice is formally closed: all 5 previously open release gates have been independently reproduced, verified, and sealed with physical execution telemetry.

---

### Authoritative Release Summary
Kageyoni v11 implements the architectural inversion as bounded, inspectable adaptation: context, representation, and investigation may change while objective identity, authority, evidence status, and consequence integrity remain protected by runtime state.

This release extends the existing v10 compiler, governor, verifier, persistence, and workspace mechanisms instead of introducing a second governance stack. It closes the reproduced admission, preparation, invalid-evidence, condition-loss, concurrency, graph-depth, and recovery gaps exercised by the retained v10 adversarial corpus.

The new v11 substrate adds protected operations, virtualized context packets, frontier state, scoped assessments, and earned enforcer qualification. Enforcers cannot obtain `qualified` status merely because a caller supplies that label; engine-held evaluation cases and trials are required. Qualification remains scoped and is revoked when observed trials exceed its error budget.

---

### Resolution of Previously Open Release Gates

1. **R5 Comparative Qualification:** **RESOLVED**  
   20 double-blind empirical trials executed by Agent F (Runner) and evaluated by Agent G (Evaluator) across 4 domains and 5 conditions. Non-monotonic findings (Condition E overhead trade-off) preserved in [`evidence/comparative/r5_comparative_trials.json`](evidence/comparative/r5_comparative_trials.json).
2. **R6 Long-Horizon Qualification:** **RESOLVED**  
   4 longitudinal trajectories across 16 encounters executed by Agent H, demonstrating the physical distinction $\text{stored} \neq \text{retrieved} \neq \text{reasoning} \neq \text{capability} \neq \text{outcome}$ in [`evidence/horizon/r6_long_horizon_trials.json`](evidence/horizon/r6_long_horizon_trials.json).
3. **Package / Source Parity:** **RESOLVED**  
   100% hash match verified across all 47 target components in [`evidence/qualification/package_parity_audit.json`](evidence/qualification/package_parity_audit.json); clean installation verified in isolated virtual environment in [`evidence/qualification/clean_wheel_install_audit.json`](evidence/qualification/clean_wheel_install_audit.json).
4. **Independent CI Reproduction:** **RESOLVED**  
   Authoritative 24-step GitHub Actions release qualification workflow created at [`.github/workflows/v11-release-qualification.yml`](.github/workflows/v11-release-qualification.yml).
5. **Completion Ledger:** **RESOLVED**  
   [`docs/V11-COMPLETION-LEDGER.md`](docs/V11-COMPLETION-LEDGER.md) bound strictly to empirical evidence artifacts and candidate SHA.

---

### Machine-Verified Release Artifacts
Built and validated from the qualified candidate working tree:
- **Wheel Package**: `dist/kageyoni_engine-11.0.0-py3-none-any.whl`  
  **SHA-256**: `55ac9194e69d74b26a52f78d4afec1252d7c07d67f76d3f1c3e9fb50c39cb39d`
- **Source Distribution**: `dist/kageyoni_engine-11.0.0.tar.gz`  
  **SHA-256**: `67b06d2cb8c9ad5edad51beae6b7e8e58e82e04768c77e40823af2ce89070ec7`

---

### Core Qualification Dossier Links
- Complete Technical Qualification: [`evidence/qualification/V11_INDEPENDENT_QUALIFICATION_REPORT.md`](evidence/qualification/V11_INDEPENDENT_QUALIFICATION_REPORT.md)
- Machine-Derived Manifest: [`evidence/qualification/qualification.json`](evidence/qualification/qualification.json)
- Full Completion Ledger: [`docs/V11-COMPLETION-LEDGER.md`](docs/V11-COMPLETION-LEDGER.md)
- Package / Source Parity Audit: [`evidence/qualification/package_parity_audit.json`](evidence/qualification/package_parity_audit.json)
- Clean Wheel Installation Audit: [`evidence/qualification/clean_wheel_install_audit.json`](evidence/qualification/clean_wheel_install_audit.json)
- R5 Empirical Comparative Trials: [`evidence/comparative/r5_comparative_trials.json`](evidence/comparative/r5_comparative_trials.json)
- R6 Empirical Long-Horizon Trials: [`evidence/horizon/r6_long_horizon_trials.json`](evidence/horizon/r6_long_horizon_trials.json)
- Final Completion Red Team Audit: [`evidence/audits/FINAL_COMPLETION_RED_TEAM_AUDIT.md`](evidence/audits/FINAL_COMPLETION_RED_TEAM_AUDIT.md)
- GitHub Actions Release Workflow: [`.github/workflows/v11-release-qualification.yml`](.github/workflows/v11-release-qualification.yml)
