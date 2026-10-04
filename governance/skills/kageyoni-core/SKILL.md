---
name: kageyoni-core
description: Unified architectural invariants, permanent evidence laws, adversarial scar saturation protocol, and release qualification standards for Kageyōni.
---

# Kageyōni Core Systems Protocol

This skill consolidates Kageyōni's foundational architecture invariants, evidence laws, scar lifecycle, and release qualification gates.

---

## 1. Architectural Invariants

- **ONE Shared Engine**: All situations, characters, research, and campaigns share the authoritative Kageyōni engine and SQLite event store (`kageyoni.engine`). No private parallel engines.
- **Structural Separation of Concerns**:
  - `Workspace`: Domain filesystem and runtime boundary.
  - `Situation Template`: Class-level schema, prerequisites, and invariants (contains no instantiated work).
  - `Situation`: Instantiated working world with objective, state, participants, constraints, and provenance.
  - `Workflow`: Directed process execution graph with stages, gates, and recovery rules.
  - `Frame`: Structural perspective/view over situation state.
  - `Method`: Learned or adaptable participant technique.
  - `Domain Projection`: Reorganization of attention, constraints, and possibilities derived from participant history.
- **Epistemic Integrity**:
  - Unknowns remain unknown. Never invent placeholder facts to satisfy schema completeness. Contradictions must be preserved.
  - Cross-domain transfer requires destination-appropriate evidence. Story competence cannot grant repo repair competence.
  - Preserve core experiential qualities: Play, surprise, attachment, character agency, unresolved mystery.

---

## 2. Permanent Evidence Laws

1. **Artifact name is not evidence**: A file named `success.json` does not prove success.
2. **Test name is not evidence**: `test_package_parity` does not prove parity unless it actively falsifies non-parity.
3. **Model statement is not evidence**: Self-assertion of completion or correctness is an untrusted candidate hypothesis.
4. **Generated JSON is not evidence**: Synthetic or mocked dictionaries are rejected; fields must derive from observed physical execution.
5. **A patch/diff is not an applied repair**: Fixes must be verified in the physical target codebase.
6. **A Git commit is not a passing test**: Commits establish lineage, not behavioral correctness.
7. **Passing test without sensitivity proof is invalid**: Must demonstrate causal sensitivity via mutation (100% kill rate on repair mutation) or negative controls.
8. **Clean-room parity**: Clean installation in an isolated virtual environment is mandatory before release qualification.
9. **No self-proclaimed semantic superiority**: Comparison requires frozen rubrics, blind execution, and external ground truth.
10. **Immutable Provenance**: Every claim requires Git SHA, execution timestamp, raw execution telemetry, and verified falsifier.

---

## 3. Adversarial Scar Saturation Protocol

Failures are not bugs to be quietly patched; they are physical reality boundaries to be preserved as permanent regression barriers.

### The Scar Lifecycle
$$\text{PROBE} \longrightarrow \text{REPRODUCE} \longrightarrow \text{CLASSIFY} \longrightarrow \text{ROOT CAUSE} \longrightarrow \text{UPSTREAM REPAIR} \longrightarrow \text{TARGETED TEST} \longrightarrow \text{POSITIVE NEIGHBOR} \longrightarrow \text{MUTATION TEST} \longrightarrow \text{WIDER REGRESSION} \longrightarrow \text{PRESERVE SCAR}$$

### Scar Closure Gate
A Scar is closed **ONLY** when:
1. An explicit upstream repair reference is linked in the physical codebase.
2. The failing probe passes without synthetic skips.
3. Positive neighboring functionality remains demonstrably intact.
4. Mutation testing proves the repair is causally necessary (mutating the repair kills the test).
5. The probe is committed to the permanent regression test suite.

---

## 4. Release Qualification Gate

Every release claim must emit a cryptographically bound receipt:
- **CLAIM**: Exact statement established.
- **FALSIFIER**: Specific adversarial condition that would invalidate the claim.
- **MEASUREMENT**: Objective measurement technique used.
- **RAW EVIDENCE**: Unmodified execution telemetry and exit codes.
- **PROVENANCE**: Git SHA, timestamp, and environment.
- **ESTABLISHED vs. UNKNOWN**: Narrow boundary of demonstrated fact vs. explicit residue and non-transferred domains.
