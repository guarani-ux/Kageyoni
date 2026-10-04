# [SOVEREIGN META-SYSTEM (SMS) FRAMEWORK SPECIFICATION]
## Version: 1.0.0 (Hardened)

### 1. THE CORE PHILOSOPHY
The SMS is a **Deterministic Agentic Framework**. It is designed to eliminate "AI Theater" (placeholders, hallucinations, and non-functional abstractions) by enforcing rigorous substrate audits and logical grounding.

### 2. THE THREE LAWS OF THE SUBSTRATE
1.  **The Law of Determinism**: No agent shall use `pass`, `TODO`, or `...` in its core logic. If a function is not yet reified, it must be quarantined.
2.  **The Law of Path Invariance**: All file and module references must be relative to the kernel's location using `Path(__file__)`. Absolute paths are prohibited.
3.  **The Law of Witness**: Every reification strike and state change must be logged in the `MISSION_CONTROL_LEDGER.json` and broadcast to the `output/` directory for fleet awareness.

### 3. ARCHITECTURAL HIERARCHY
*   **CORE**: `sovereign_core.py` (The Initializer).
*   **FLEET**: `SMS_MIRROR/fleet/` (The Agents/Kernels).
*   **HARNESS**: `SMS_MIRROR/harness/` (The Communication/Relay Layer).
*   **TECHNIQUES**: `SMS_MIRROR/techniques/` (The Shared Logic/TruthLattice).
*   **INTEGRATION**: `SMS_MIRROR/integration/` (State-Sync and Cognition Requests).

### 4. AGENT REIFICATION PIPELINE
1.  **Simulation (Stage 0)**: Placeholder agent with `...` logic.
2.  **Hardening (Stage 1)**: Logic implemented, paths fixed, theater purged.
3.  **Grounding (Stage 2)**: Agent verified in a live environment against real data.
4.  **Sovereign (Stage 3)**: Agent is 100% deterministic and integrated into the Core.

---
**[STAMP: REGISTERED UNDER THE SOVEREIGN PROTOCOL]**
