---
name: agent-genesis
description: Protocols, architectural invariants, and generation tools to construct, customize, and qualify situated, history-bearing developmental agents for Kageyōni (Directives #22 - #45). Hardened against counterfeit capability.
---

# AGENT GENESIS SKILL (HARDENED PROTOCOL)

## PURPOSE
Construct situated, history-bearing agents whose future capabilities change strictly through consequential encounters inside Kageyōni.

**Never construct a super-agent by aggregating existing skills.**
Initial capability must always be **intentionally incomplete**.
Remove every path by which configuration, generated tests, or the harness could counterfeit developmental capability.

---

## 1. THE 13 HARDENING LAWS

### 1. Separate Qualification Levels
Never report an agent as "qualified" merely because its generated genesis tests pass.
- `VALID_GENESIS`: Structural invariants, initial incomplete loadout, and A0 snapshot validity verified.
- `DEVELOPMENT_OBSERVED`: Structural delta observed between Agent(t) and Agent(t+1).
- `CAPABILITY_DEMONSTRATED`: Capability exercised on an encounter.
- `CAPABILITY_QUALIFIED`: Capability survives independent qualification trials and holdout encounter.
- `RELATIONAL_CAPABILITY_QUALIFIED`: Relational capability $C_{AB}$ survives the 5-way relational probe.

### 2. Prevent Self-Qualification
The Forge must not generate both the developmental behavior being claimed and the only verifier that declares it successful. Generated tests establish ONLY `VALID_GENESIS`. Developmental claims require independent capability-forcing probes whose success conditions are defined *before* history occurs.

### 3. Immutable Genesis Snapshots (A0 Manifest)
Every forged agent emits an immutable `a0_snapshot.json` containing:
- `snapshot_id`, `genesis_mode`, `objective`
- `initial_horizon`, `initial_techniques`, `initial_salience`
- `authority_tier`, `code_config_digest` (SHA-256)
All future development is measured against this exact A0.

### 4. Configured vs. Developed Difference
- `SPECIALIZED_GENESIS`: Configured parameter differences allowed. (Never use as proof of history-induced differentiation).
- `IDENTICAL_GENESIS`: $A_0$ and $B_0$ must be structurally equivalent except identity/seed fields.

### 5. Twin Forging
`forge_twins(objective, n)` generates genesis-equivalent agents ($A_0 \approx B_0$) for controlled ablation experiments.

### 6. History Ablation
To prove a capability is history-dependent, compare:
$$A_n \text{ (with history)} \quad \text{vs} \quad A_0 \text{ (restored)} \quad \text{vs} \quad A_n \text{ (causal encounter ablated)}$$
The capability is verified only if the delta disappears when the causal encounter is ablated.

### 7. No Harness-Supplied Learning
The harness must NOT grant techniques, insert expected capabilities, or tell the agent what lesson to extract. The environment supplies raw physical consequences; the agent must supply the candidate interpretation.

### 8. Novel Holdout Encounters
Development must be evaluated on an encounter NOT used to create or qualify the candidate capability:
$$\text{History} \longrightarrow \text{Candidate} \longrightarrow \text{Qualification} \longrightarrow \text{Later Discovery} \longrightarrow \text{Novel Holdout Use} \longrightarrow \Delta \text{Capability}$$

### 9. Hardened Relational Capability ($C_{AB}$)
Requires the 5-way probe:
1. $A$ alone $\rightarrow$ absent
2. $B$ alone $\rightarrow$ absent
3. $A \times B$ cold $\rightarrow$ absent
4. $A \times B$ with relevant history $\rightarrow$ present
5. $A \times B$ with relationship history ablated $\rightarrow$ absent
Bind $C_{AB}$ to $R_{AB}$ only after this survives.

### 10. Auditable Salience
All initial salience weights are recorded in A0. When claiming history-induced differentiation, demonstrate that initial salience does not explain the delta.

### 11. Negative Development
Agents must be capable of negative development:
- Suspending capabilities (`demote_technique`)
- Invalidating techniques (`invalidate_technique`)
- Severing relational capabilities (`sever_relational_capability`)
- Retaining unexplained residue without forced theories

### 12. 6-Part Provenance on Every Delta
Every `DevelopmentalDelta` must answer:
- WHAT changed?
- FROM what state?
- BECAUSE OF which encounter?
- WHO interpreted? (agent vs. harness)
- WHAT verifier supports attribution?
- WHAT future behavior changed?
If attribution is unresolved, preserve `RESIDUE` instead of claiming `DEVELOPMENT`.

### 13. Honest Reporting
Report statuses separately: `FORGE_VERIFIED`, `GENESIS_VALID`, `DEVELOPMENT_OBSERVED`, `CAPABILITY_QUALIFIED`, `RELATIONAL_CAPABILITY_QUALIFIED`.

---

## 2. CLI COMMANDS

### Forge Single Agent
```powershell
python -m kageyoni.developmental.forge --name "perimeter_scout" --objective "Survey sector boundary"
```

### Forge Identical Twins
```powershell
python -m kageyoni.developmental.forge --name "twin" --objective "Contain reactor breach" --twins 2
```

### Run Genesis Validity Test
```powershell
python -m unittest tests/test_<name>_genesis_validity.py
```

### Run Adversarial Developmental Acceptance Test
```powershell
python -m unittest tests/test_adversarial_developmental_acceptance.py
```
