# Workflow: R5 Real Comparative Qualification

## Purpose
Execute empirical, non-monotonic comparative trials across 4 task domains and 5 execution conditions without synthetic scaffolding or predetermined outcomes.

## Separation of Powers
- **Agent F (Experiment Runner):** Freezes tasks, generates SHA-256 fixture hashes, executes trials, captures raw output, telemetry, tool traces, overhead, and failures. Agent F writes ZERO scores.
- **Agent G (Evaluator):** Reads frozen raw outputs and applies immutable evaluation rubrics. Valid findings explicitly include ties, regressions, overhead penalties, and Condition A beating Condition E.

## Stages
1. **Fixture & Rubric Freezing:** Define 4 immutable domain fixtures (Creative/Production, Research/Planning, Repository/Technical, Living World) and rubrics. Compute SHA-256 hashes.
2. **Blind Execution (Agent F):** Execute Condition A, B, C, D, and E across all 4 fixtures. Dump raw outputs to `experiments/r5/outputs/`.
3. **Objective Evaluation (Agent G):** Evaluate raw outputs against frozen rubrics. Compute metrics:
   - Requirement satisfaction
   - Source fidelity
   - Continuity
   - Useful novelty
   - Correction burden
   - Reconstruction burden
   - Execution overhead
   - Recovery
4. **Evidence Preservation:** Store comprehensive evidence dossier in `evidence/comparative/r5_comparative_trials.json`.
