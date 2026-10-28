---
name: subagent-forge
description: Compiler and deterministic qualification gate for autonomous subagents. Compiles user intent into hermetic P-N-S-C execution contracts, injects anti-slop blacklists, enforces pre-tool execution hooks on invoke_subagent, and verifies completion disk sinks.
---

# Subagent Forge: Hermetic P-N-S-C Contract System

> *"An un-forged subagent is an epistemic leak. Without bounded negative space, explicit epistemic invariants, and verified completion sinks, delegated processes default to conversational theater, hallucinated passes, and context pollution."*

---

## 1. Overview & Architecture

The **Subagent Forge** provides mechanical compilation, validation, and enforcement for all autonomous subagent delegations within the Kageyōni estate. It guarantees that any invocation of `invoke_subagent` adheres strictly to the **P-N-S-C (Payload, Negative Bounds, Success Invariant, Completion Sink)** execution kernel.

```
+-----------------------------------------------------------------------------------+
|                                 LEAD ORCHESTRATOR                                 |
+-----------------------------------------------------------------------------------+
                                          |
                      (Intent: Task, Inputs, Bounds, Sinks)
                                          v
+-----------------------------------------------------------------------------------+
|                              tools.subagent forge                                 |
| - Injects Auto Anti-Slop Blacklist                                                |
| - Constructs Hermetic P-N-S-C Execution Kernel                                    |
| - Formats for prompt or JSON invoke_subagent payload                              |
+-----------------------------------------------------------------------------------+
                                          |
                              (invoke_subagent Tool Call)
                                          v
+-----------------------------------------------------------------------------------+
|                         HOOK GATE: tools.subagent hook pre                        |
|                                                                                   |
|  Prompt has [1. PAYLOAD], [2. NEGATIVE BOUNDS],                                   |
|             [3. SUCCESS INVARIANT], [4. COMPLETION SINK]?                         |
|                 /                                     \                           |
|               YES                                      NO                         |
|                v                                        v                         |
|        {"decision": "allow"}                {"decision": "deny",                  |
|                |                             "reason": "FM-FORGE-01..."}          |
+-----------------------------------------------------------------------------------+
                 |
                 v
+-----------------------------------------------------------------------------------+
|                               AUTONOMOUS SUBAGENT                                 |
| - Executes within isolated context                                                |
| - Bounded by Negative Invariants                                                 |
| - Writes output directly to Completion Sink                                       |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                           tools.subagent verify-sink                              |
| - Checks file existence                                                           |
| - Verifies file size >= min_bytes                                                 |
| - Confirms physical termination                                                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. The P-N-S-C Execution Contract

Every subagent prompt must contain four complete, non-empty sections. Omitting any section triggers mechanical denial by the pre-tool guard.

### [1. PAYLOAD]
Defines the execution identity, operational role, primary mission, and input materials.
- **Target Subagent**: Identifies the subagent archetype (`research`, `self`, or custom agent).
- **Operational Role**: High-clarity functional title (e.g., `Reverse Engineering Specialist`).
- **Primary Assignment**: Concrete, actionable task description.
- **Reference Inputs**: Explicit file paths, commit hashes, or memory artifacts to inspect.

### [2. NEGATIVE BOUNDS] (FOREGO)
Establishes the strict negative space of the subagent. Defines what the subagent must **NOT** do.
- **User-Defined Constraints**: Forbidden file paths, off-limit directories, banned packages.
- **Auto-Injected Anti-Slop Blacklist**:
  - `FORBIDDEN: Conversational pleasantries, sycophantic preamble, and unsolicited commentary.`
  - `FORBIDDEN: Narrative plot summaries, encyclopedia filler, and pseudo-intellectual platitudes.`
  - `FORBIDDEN: Mutating unapproved files or modifying global environment configurations.`
  - `FORBIDDEN: Mocking test suites or faking execution passes without verified command outputs.`
  - `FORBIDDEN: Returning hollow stubs (pass/TODO) in place of production-grade implementations.`

### [3. SUCCESS INVARIANT] (EPISTEMIC GATE)
Defines the deterministic, non-negotiable proof criteria for declaring success.
- **Automated Test Gates**: Command lines and expected exit codes (e.g., `pytest tests/test_target.py -v` exits 0).
- **Epistemic Invariants**: No syntax errors, no broken AST boundaries, all assertions executed.
- **Evidence Custody**: Raw subprocess outputs and hash receipts must accompany claims.

### [4. COMPLETION SINK] (PHYSICAL TERMINATION)
Defines where work products physically land and how the process terminates.
- **Disk Sinks**: Explicit paths to created/modified files on disk.
- **Byte Thresholds**: Minimum byte sizes verified by `verify-sink`.
- **Termination Protocol**: Structured IPC message to caller agent via `send_message` followed by immediate session termination.

---

## 3. CLI Command Reference

### 3.1 Forge Contract: `tools.subagent forge`
Compiles parameters into a verified P-N-S-C contract.

```bash
python -m tools.subagent forge \
  --name "researcher" \
  --role "Binary Protocol Auditor" \
  --task "Analyze wire protocol of telemetry daemons in Domain 4." \
  --inputs "kageyoni/network/protocol.py,docs/spec.md" \
  --forego "Modifying network drivers, installing external pip wheels" \
  --success "pytest tests/test_protocol.py exits 0 with 5 passes" \
  --sink "reports/protocol_audit.json" \
  --format prompt
```

#### Supported Options:
- `--name`: Subagent name / `TypeName`
- `--role`: Operational role description
- `--task`: Primary task statement
- `--inputs`: Input files, paths, or dependencies (can be repeated or comma-separated)
- `--forego`: Negative bounds and constraints (can be repeated)
- `--success`: Success invariant statements (can be repeated)
- `--sink`: Output file paths / artifacts (can be repeated)
- `--format`: `prompt` (default) or `json` (suitable for direct API payloads)
- `--out`: Write contract directly to a destination file on disk

---

### 3.2 Validate Contract: `tools.subagent validate`
Validates that an existing contract or prompt satisfies the P-N-S-C specification.

```bash
# Validate string
python -m tools.subagent validate "[SUBAGENT EXECUTION KERNEL: P-N-S-C] 1. PAYLOAD: ... 2. NEGATIVE BOUNDS: ... 3. SUCCESS INVARIANT: ... 4. COMPLETION SINK: ..."

# Validate file
python -m tools.subagent validate --file prompt.txt

# Validate from stdin
cat prompt.txt | python -m tools.subagent validate
```

- **Exit 0**: Contract contains all 4 non-empty P-N-S-C sections.
- **Exit 1**: Contract is missing sections or sections contain empty content. Diagnostic printed to stderr.

---

### 3.3 Hook Gating: `tools.subagent hook pre`
Invoked automatically by the runtime hook runner before any tool execution.
- Reads JSON payload from `stdin`.
- If `toolCall.name == 'invoke_subagent'`:
  - Inspects `args.Prompt`.
  - Runs P-N-S-C validation.
  - Returns `{"decision": "allow", "reason": "P-N-S-C Forge contract verified."}` on pass.
  - Returns `{"decision": "deny", "reason": "FM-FORGE-01 (Un-Forged Subagent Blocked): <diagnostics>"}` on failure.
- If `toolCall.name != 'invoke_subagent'`:
  - Returns `{"decision": "allow"}`.

To install or refresh the hook definition in `.agents/hooks.json`:
```bash
python -m tools.subagent hook install
```

---

### 3.4 Verify Sinks: `tools.subagent verify-sink`
Validates that subagent deliverables actually exist on disk and meet required byte thresholds.

```bash
python -m tools.subagent verify-sink reports/protocol_audit.json --min-bytes 256
```

- Checks existence of all listed sink files.
- Checks `stat().st_size >= min_bytes`.
- Returns exit 0 if all pass; exit 1 if any fail.

---

## 4. Hook Configuration (`.agents/hooks.json`)

The workspace hook registers `tools.subagent hook pre` on all `invoke_subagent` calls:

```json
{
  "subagent_forge": {
    "enabled": true,
    "PreToolUse": [
      {
        "matcher": "invoke_subagent",
        "hooks": [
          {
            "type": "command",
            "command": "python -m tools.subagent hook pre",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

---

## 5. Epistemic Failure Modes Intercepted

| Failure Code | Name | Mechanic Intercepted |
|---|---|---|
| `FM-FORGE-01` | Un-Forged Subagent Blocked | Launching a subagent with unformatted, conversational prompt lacking P-N-S-C sections. |
| `FM-FORGE-02` | Corrupted Hook Payload | Hook received unparseable JSON from runtime tool runner. |
| `FM-FORGE-03` | Empty Section Evasion | Prompt contains P-N-S-C headers but empty or whitespace-only bodies. |
| `FM-FORGE-04` | Phantom Completion Sink | Subagent reports completion but declared sink files are missing or empty on disk. |
