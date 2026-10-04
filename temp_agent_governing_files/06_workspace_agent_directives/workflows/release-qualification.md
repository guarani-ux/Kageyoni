# Workflow: Final Release Qualification & Verification

## Purpose
Govern the clean-room verification, package/source parity audit, and final adversarial review for Kageyoni v11 release.

## Separation of Powers
- **Agent I (Release Reproducer):** Checks out exact Git SHA, executes clean-room reproduction, builds distribution packages, executes fresh installation, verifies file and checksum parity. Cannot repair code during reproduction.
- **Agent J (Release Reporter):** Compiles the authoritative release report from verified qualification receipts. Cannot independently assign `PASS`.

## Stages
1. **Clean-Room Checkout:** Inspect working tree, record exact qualified SHA.
2. **Ten Release Gates:**
   - Full inherited regression suite
   - Full v11 trust suite
   - Full Situation lifecycle suite
   - Scar saturation probes
   - Mutation sensitivity suite
   - Migration 002–023 checksum checks
   - Historical restore/reopen tests
   - Fresh installation in isolated venv
   - Canonical-world preservation checks
   - Package/source parity audit
3. **Adversarial Red-Team Completion Review:** Execute the 7-point adversarial audit probing what could make the build appear complete while requirements remain unsatisfied.
4. **Publication:** Generate release evidence dossier and archive packages.
