---
name: developmental-genesis
description: Protocols, architectural invariants, and verification engines to construct, qualify, and ablate situated, history-bearing developmental agents for Kageyōni. Hardened against counterfeit capability.
---

# Developmental Agent Genesis Protocol

## Purpose
Construct situated, history-bearing agents whose future capabilities develop strictly through consequential encounters inside Kageyōni.

**Core Invariant**: Initial capability must always be **intentionally incomplete**. Never construct a super-agent by aggregating existing skills.

---

## 1. The Hardening Laws

1. **Qualification Hierarchy**:
   - `VALID_GENESIS`: Structural invariants, incomplete initial loadout, and A0 snapshot validity verified.
   - `DEVELOPMENT_OBSERVED`: Structural delta observed between $\text{Agent}(t)$ and $\text{Agent}(t+1)$.
   - `CAPABILITY_DEMONSTRATED`: Capability exercised on an encounter.
   - `CAPABILITY_QUALIFIED`: Capability survives independent qualification trials and holdout encounter.
   - `RELATIONAL_CAPABILITY_QUALIFIED`: Joint capability $C_{AB}$ survives the 5-way relational probe.
2. **Prevent Self-Qualification**: The Forge must not generate both the developmental behavior and the only verifier that declares it successful. Success conditions must be defined *before* history occurs.
3. **Immutable Genesis Snapshots (A0 Manifest)**:
   Every forged agent emits an immutable `a0_snapshot.json` with `snapshot_id`, `genesis_mode`, `objective`, `initial_horizon`, and SHA-256 `code_config_digest`. All future development is measured against this exact A0.
4. **Controlled Twin Forging**:
   `forge_twins(objective, n)` generates structurally identical agents ($A_0 \approx B_0$) for controlled ablation experiments.
5. **History Ablation**:
   To prove a capability is history-dependent, compare:
   $$A_n \text{ (with history)} \quad \text{vs} \quad A_0 \text{ (restored)} \quad \text{vs} \quad A_n \text{ (causal encounter ablated)}$$
   The capability is verified only if the delta disappears when the causal encounter is ablated.
6. **No Harness-Supplied Learning**: The harness supplies raw physical consequences; the agent must supply candidate interpretations.
7. **Holdout Encounters**: Development must be evaluated on an encounter NOT used to create or qualify the candidate capability.
8. **5-Way Relational Probe ($C_{AB}$)**:
   A relational capability $C_{AB}$ is qualified if and only if:
   1. $A$ alone $\longrightarrow$ absent
   2. $B$ alone $\longrightarrow$ absent
   3. $A \times B$ cold $\longrightarrow$ absent
   4. $A \times B$ after shared history $\longrightarrow$ demonstrated
   5. $A \times B$ with relational encounter ablated $\longrightarrow$ absent

---

## 2. Innate Agent Verbs & 7-Way Metabolism

Every developmental agent begins with ONLY five innate verbs:
1. `SITUATE`: Ingest local state through the gateway viewer filter without omniscience.
2. `ENCOUNTER`: Execute bounded actions strictly within $H_t^{\text{believed}} \cap H_t^{\text{actual}}$.
3. `METABOLIZE`: Classify outcomes across 7 independent categories:
   - `ORDINARY_HISTORY`: Expected progression, logs event.
   - `SCAR_CANDIDATE`: Hard invariant rejection; forges leased defeasible constraint.
   - `DEFICIT`: Identifiable missing prerequisite.
   - `RESIDUE`: Unexplained anomaly; preserved without forced narrative.
   - `CAPABILITY_CANDIDATE`: Unqualified extracted pattern.
   - `RELATIONSHIP_DELTA`: Consequential modification to relational bond.
   - `NOTHING_REUSABLE`: Ephemeral turn; discarded.
4. `REGROUND`: Synchronize private hypotheses with physical Ground (`tx-receipt:`).
5. `CAPABILITY_MEMBRANE`: Enforce capability ownership boundaries and lifecycle transitions.
