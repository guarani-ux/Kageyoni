---
name: zero-trust-architect
description: Architectural patterns and procedural guidance for high-assurance software engineering tasks. Covers candidate isolation, deterministic evidence-bound verification, bounded repair iteration, and procedural separation of duties.
---

# ZERO-TRUST ARCHITECTURE PATTERNS (SOFTWARE 3.0)

This skill provides procedural patterns for high-assurance software development tasks requiring structured isolation, deterministic verification receipts, and bounded iteration. It is an optional high-assurance method, not a universal mandate for routine software edits.

---

## 1. Architectural Guidance & Enforcement Realism

1. **Procedural Separation of Roles (Coordination Pattern, Not OS Security):**
   - Main conversation thread coordinates state and tracks invariants.
   - Code generation may be scoped to a candidate proposal step.
   - Verification may be assigned to a dedicated evaluation step.
   - *Epistemic note:* Delegating verification to a separate model subagent persona does **not** constitute independent validation. A subagent shares model biases and lacks verification authority unless bound to **external, deterministic contact** (e.g., test suite exit codes, linters, compiler checks, or human review).

2. **Isolated Candidate Staging:**
   - Candidate modifications should be isolated from protected branches or deployment targets (e.g., in a scratch directory, staging path, or ephemeral Git worktree).
   - Candidate changes are evaluated within their staging boundary before promotion.
   - Worktree isolation requires a functioning local Git repository and explicit branch management; it is a repository workspace pattern, not a virtualization container.

3. **Mechanical Guardrails Depend on Verified Host Infrastructure:**
   - Procedural guidelines cannot mechanically intercept tool calls on their own.
   - True mechanical prevention requires an installed, active, and verified host enforcement adapter (e.g., `PreToolUse` hook returning `deny` or `force_ask`, or operating system ACLs).
   - In the absence of a qualified mechanical guard, procedural rules rely on voluntary agent compliance, which must not be misrepresented as a tamper-resistant security boundary.

4. **Bounded Iteration (3-Strike Governor):**
   - Limit repair attempts to a maximum of 3 failed iterations on the same structural defect.
   - If Strike 3 is reached, halt iteration and trigger a Root Cause Architecture Assessment rather than churning through cosmetic variations.

5. **Receipt-Based Evidence Binding:**
   - A promotion claim must be backed by a concrete operational receipt: candidate identity (e.g., SHA-256 digest), exact test command executed, exit code, and captured output.
   - A digest binds bytes to a run; it does not certify correctness by itself.

---

## 2. Structured Workflow Pattern (When High Assurance Is Required)

```mermaid
sequenceDiagram
    autonumber
    participant User as Architect / User
    participant Coord as Coordinator (Active State)
    participant Staging as Staging Envelope
    participant Runner as External Verifier (Test/Linter)
    participant Target as Protected Target

    User->>Coord: High-Assurance Task Authorized
    Coord->>Staging: Propose Candidate into Staging
    Coord->>Runner: Execute Deterministic Check on Staging
    Runner-->>Coord: Deterministic Receipt {exit_code, trace, digest}
    alt Exit Code == 0 (Valid Evidence)
        Coord->>Target: Promote Candidate to Target (with authority)
        Coord-->>User: Report Verified Advancement + Receipt
    else Exit Code != 0 (Strike < 3)
        Coord->>Coord: Record Failure Trace; Attempt Diagnosis
    else Exit Code != 0 (Strike == 3)
        Coord->>Staging: Abandon Staging; Halt
        Coord-->>User: Escalate to Root Cause Assessment
    end
```

---

## 3. Minimal Receipt Contract (JSON Schema Example)

When capturing deterministic verification evidence, record factual operational observations rather than model self-assertions:

```json
{
  "task_id": "string",
  "candidate_digest": "sha256-hex",
  "test_command": "string",
  "exit_code": 0,
  "stdout_summary": "string",
  "duration_seconds": 0.00,
  "verified_at": "ISO-8601-timestamp"
}
```

---

## 4. Software Principles

1. **Gall's Law (Simplicity):** Working complex systems evolve from working simple systems. Avoid introducing unprompted abstraction layers, subagent swarms, or daemons.
2. **Atomic Modification:** File mutations must be atomic to prevent partially written or corrupt state.
3. **Receipt vs Claim:** An assertion of success requires inspectable, reproducible output from the execution environment.
