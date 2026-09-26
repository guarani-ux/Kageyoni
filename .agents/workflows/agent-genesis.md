# Workflow: Hardened Developmental Agent Genesis

## Purpose
Construct, customize, and mechanically verify situated developmental agents adhering strictly to Directives #22 – #45, completely hardened against counterfeit capability and self-qualification.

---

## Stages

### 1. Invariant Anchoring & Genesis Mode Selection
* Define `agent_name` and the immutable sovereign `objective`.
* Select `GenesisMode`:
  - `IDENTICAL_GENESIS`: For controlled experiments where twins must share an identical A0 digest.
  - `SPECIALIZED_GENESIS`: For dedicated operational agents with customized initial parameters.
* Assign a sovereign delegation key for Tier 0 authority protection.

### 2. Salience & Incomplete Horizon Setup
* Establish baseline `SalienceVector` weights.
* Ensure initial reachability is strictly incomplete: `{"inspect", "orient"}`. Zero pre-loaded active techniques.

### 3. Programmatic Manifest, Snapshot & Test Generation
* Execute the hardened forge CLI:
  ```powershell
  python -m kageyoni.developmental.forge --name "<agent_name>" --objective "<objective>" --mode "<mode>"
  ```
* Outputs generated:
  1. `.agents/agents/<agent_name>/a0_snapshot.json`: Immutable A0 manifest with SHA-256 digest.
  2. `.agents/agents/<agent_name>/agent.md`: The Antigravity host subagent manifest.
  3. `tests/test_<agent_name>_genesis_validity.py`: Test establishing ONLY `VALID_GENESIS`.

### 4. Genesis Validity Gate (Level: VALID_GENESIS)
* Run the generated genesis test in the Tier 0 autonomous loop:
  ```powershell
  python -m unittest tests/test_<agent_name>_genesis_validity.py
  ```
* Confirms:
  - 0 active techniques, incomplete loadout.
  - Snapshot digest integrity.
  - Objective immutability.
  - Authority invariance.
* **Invariant**: This gate establishes ONLY `VALID_GENESIS`. It does NOT report the agent as "qualified."

### 5. Independent Capability-Forcing & Holdout Gate
To advance qualification levels:
* **DEVELOPMENT_OBSERVED**: The agent must undergo an encounter yielding a non-empty `DevelopmentalDelta` with 6-part provenance.
* **CAPABILITY_QUALIFIED**: Candidate technique must pass independent qualification trials (2+ classes, 0 error) and be successfully executed on an unseen holdout encounter.
* **RELATIONAL_CAPABILITY_QUALIFIED**: Must survive the 5-way relational probe ($A$ alone fails, $B$ alone fails, $A \times B$ cold fails, $A \times B$ ablated fails, $A \times B$ with history succeeds).

### 6. Full Adversarial Acceptance Gate
* Verify complete pipeline via the acceptance suite:
  ```powershell
  python -m unittest tests/test_adversarial_developmental_acceptance.py
  ```
