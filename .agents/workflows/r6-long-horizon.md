# Workflow: R6 Real Long-Horizon Development

## Purpose
Execute repeated multi-turn trajectories across 4 domains to demonstrate genuine developmental progression while strictly enforcing the epistemic boundary:

$$\text{stored history} \neq \text{retrieved history} \neq \text{changed reasoning} \neq \text{changed capability} \neq \text{changed outcome}$$

## Operational Rules
- Never manually insert synthetic tokens: `qualified_technique`, `changed_capability`, `verified_changed_outcome`.
- All developmental claims must be derived purely from observed execution.
- Agent H runs trajectories and captures raw encounter traces without self-assigning scores.

## Trajectory Stages
- **Encounter 1 (Baseline):** Execute task with zero prior memory. Record baseline result and consequences.
- **Encounter 2 (Reasoning Adaptation):** Permit retrieval of prior encounter state. Execute again. Differentiate changed reasoning from capability growth.
- **Encounter 3+ (Method Qualification):** Allow Kageyoni learning mechanisms to propose a Method *only* if warranted by observed friction. The method must undergo real engine qualification before execution.
- **Control Trials:** Include controls (history stored but not retrieved; history retrieved but no method learned; method proposed but rejected; qualified method irrelevant).
- **Post-Hoc Derivation:** Audit encounter data and emit findings to `evidence/horizon/r6_long_horizon_trials.json`.
