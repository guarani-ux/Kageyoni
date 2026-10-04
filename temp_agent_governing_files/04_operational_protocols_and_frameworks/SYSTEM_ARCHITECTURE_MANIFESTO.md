# [SYSTEM ARCHITECTURE MANIFESTO v3.2.0]
# [SOVEREIGN META-SYSTEM — THE BIT-PERFECT SUBSTRATE]

## 1. THE PRIME INVARIANT
All components of the Sovereign Meta-System (SMS) must be **Deterministic, Hardened, and Zero-Theater.** If a module cannot execute its primary function without "Placeholder Logic," it is considered a substrate infection and must be liquidated.

## 2. TECHNICAL SPECIFICATIONS (THE PHYSICS)

### 2.1. LANGUAGE & ENVIRONMENT
*   **Core**: Python 3.11+
*   **Dependencies**: Must be explicitly listed in the kernel and verified by Urahara.
*   **Shell**: PowerShell/Cmd compatible (Windows Substrate).

### 2.2. PATHING INVARIANT (THE FEET)
*   All file references MUST use `Path(__file__).resolve().parents[n]` to ensure location-independence.
*   Hard-coded absolute paths are **STRICTLY PROHIBITED.**
*   Relative paths are permitted only for local, non-executable documentation.

### 2.3. MODULE STRUCTURE
*   **Fleet**: `SMS_MIRROR/fleet/` (Agents and Kernels).
*   **Harness**: `SMS_MIRROR/harness/` (Relays and Communication).
*   **Integration**: `SMS_MIRROR/integration/` (State-Sync and Cognition Requests).
*   **Output**: `SMS_MIRROR/output/` (Signal LEDGER and Findings).

## 3. COMMUNICATION PROTOCOL (THE RELAY)
*   Agents must communicate via the `SovereignCloudHarness`.
*   All inter-agent requests must be logged in `integration/COGNITION_REQUEST.json`.
*   Direct kernel-to-kernel communication is permitted only for **Read-Only** telemetry.

## 4. SECURITY & COMPLIANCE (ZORO'S LAW)
*   **Audit Frequency**: Zoro must audit the substrate after every kernel modification.
*   **Theater Threshold**: Zero. Any file containing `pass`, `TODO`, `...`, or `placeholder` will fail the audit.
*   **Liquidations**: Zoro is authorized to auto-purge non-compliant files in the `integration/` and `output/` directories.

## 5. VERSIONING & STATE
*   Current Version: 3.2.0 (Hardened Substrate).
*   State Grounding: Every session MUST begin with a `MISSION_CONTROL_LEDGER.json` sync.

---
**[CERTIFICATION: SAGE ZORO | SAGE URAHARA | SAGE ARBITER]**
