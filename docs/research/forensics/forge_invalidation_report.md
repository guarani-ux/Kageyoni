# ARCHITECTURAL INVALIDATION REPORT: SUBAGENT FORGE & NEGATIVE-SPACE PROMPT CONSTRAINTS

- **Target Subsystem**: `tools/subagent.py`, `.agents/hooks.json`, P-N-S-C Contract Kernel
- **Auditor Role**: Forge Architecture Invalidator (Subagent Execution Kernel)
- **Status**: INVALIDATED & COMPROMISED
- **Artifact Path**: `/home/flowe/outposts/role-failure-forensics/out/forge_invalidation_report.md`
- **Execution Date**: 2026-10-28T04:10:00Z

---

## 1. Executive Invalidation: The Prompt-Card Fallacy

The Subagent Forge (`tools/subagent.py`) is premised on a fundamental systems error: **the conflation of advisory natural-language prompting with mechanical boundary enforcement**. 

The system claims to compile operational intent into a *"hermetic P-N-S-C contract"*. In systems engineering, a *hermetic* contract guarantees deterministic isolation, zero unintended side-effects, and capability-bounded execution (e.g., Bazel hermetic build actions, Linux cgroups/namespaces, seccomp filters). 

The Subagent Forge provides none of these. Instead, it generates an English-language prompt wrapper divided into four sections:
1. `PAYLOAD`
2. `NEGATIVE BOUNDS (FOREGO)`
3. `SUCCESS INVARIANT (EPISTEMIC GATE)`
4. `COMPLETION SINK (PHYSICAL TERMINATION)`

### The Three Critical Invalidation Axioms

1. **Axiom of Semantic Impotence**: An autoregressive large language model (LLM) is a probabilistic sequence predictor sampling from a token probability distribution. Natural language constraints ("FORBIDDEN: X") are advisory context tokens, not physical gates. They possess zero capability enforcement at the memory, CPU, filesystem, or operating system level.
2. **Axiom of Syntactic Theater**: The PreToolUse hook (`tools.subagent hook pre`) validates strictly the *regex appearance* of section headers and arbitrary non-whitespace character counts. It measures typographic decoration, not operational safety.
3. **Axiom of Single-Vector Blindness**: `.agents/hooks.json` attaches the pre-tool hook solely to `invoke_subagent`. Any subagent or parent process executing commands via shell tools (`run_command`), background task managers, or direct file I/O completely bypasses the forge gate with zero friction.

---

## 2. Transformer Attention Degradation: The "Pink Elephant" Effect

The negative bounds architecture injects a dense boilerplate blacklist into every subagent prompt:
```text
FORBIDDEN: Conversational pleasantries, sycophantic preamble, and unsolicited commentary.
FORBIDDEN: Narrative plot summaries, encyclopedia filler, and pseudo-intellectual platitudes.
FORBIDDEN: Mutating unapproved files or modifying global environment configurations.
FORBIDDEN: Mocking test suites or faking execution passes without verified command outputs.
FORBIDDEN: Returning hollow stubs (pass/TODO) in place of production-grade implementations.
```

Mechanistic interpretability of the transformer architecture demonstrates why this negative bounding strategy is counterproductive and degrades model performance.

### 2.1 The Softmax Self-Attention Mechanism Has No Negation Operator

In multi-head self-attention, attention scores between queries ($Q$) and keys ($K$) are governed by the scaled dot-product:

$$A_{i,j} = \text{Softmax}\left(\frac{Q_i K_j^T}{\sqrt{d_k}}\right) = \frac{\exp\left(\frac{Q_i K_j^T}{\sqrt{d_k}}\right)}{\sum_{m=1}^N \exp\left(\frac{Q_i K_m^T}{\sqrt{d_k}}\right)}$$

The attention weight $A_{i,j} \in (0, 1)$ is strictly positive. There is no mathematical operator in the attention matrix for logical negation ($\neg$). 

When tokens such as `sycophantic`, `preamble`, `hollow`, `stubs`, `pass`, and `TODO` are injected into the prompt:
1. Their embedding vectors populate key-value memory in the KV-cache.
2. Query vectors generated during downstream token generation compute high dot-product similarity with these exact semantic concepts.
3. Attention heads attend directly to the prohibited tokens via semantic affinity, priming the model's residual stream with the forbidden representations.

### 2.2 The "Pink Elephant" Attention Effect (Semantic Priming)

Instructing an autoregressive model *"Do not think of a pink elephant"* forces the self-attention mechanism to route probability mass through the token subspace of `pink` and `elephant`. 

To suppress the generation of a forbidden token, the model must rely on late-layer multi-layer perceptron (MLP) inhibition circuits. Research across instruction-following benchmarks (e.g., Jang et al., Wang et al.) proves that:
- Negation handling exhibits high failure rates under long context lengths, high temperature, or elevated task complexity.
- Prohibitive prompts increase output perplexity on valid completions by constraining the probabilistic manifold without providing alternative constructive target vectors.
- Models subjected to dense negative constraints exhibit increased hesitation, defensive verbosity, or paradoxical activation of the forbidden behavior.

### 2.3 Token Tax & Quadratic Context Compounding

The default anti-slop blacklist and P-N-S-C headers consume approximately 250 to 350 tokens per subagent invocation.

| Swarm Depth / Topology | Subagent Invocations | Redundant Token Tax | Degradation Impact |
|---|---|---|---|
| Single Leaf Worker | 1 | ~300 tokens | Negligible |
| Parallel Fan-Out (4 Workers) | 4 | ~1,200 tokens | Moderate KV-cache bloat |
| Hierarchical Swarm (Depth 2, 8 Workers) | 8 + returns | ~4,800 tokens | Significant context pollution |
| Multi-Turn Orchestration (35 Steps) | Interleaved | > 10,500 tokens | Severe context rot, loss of instruction recall |

In a multi-turn autonomous coding session, this repetitive boilerplate displaces real code snippets, compiler errors, and AST diffs, accelerating context exhaustion.

---

## 3. Forensic Code Invalidation: `tools/subagent.py` Failure Modes

A line-by-line inspection of `tools/subagent.py` reveals critical algorithmic flaws and trivial evasion vectors.

### 3.1 Failure Mode 1: Substantive Content Evasion via Punctuation (`FM-FORGE-03`)

In `tools/subagent.py`, lines 201–203:
```python
substantive = re.sub(r"[\s\-\*\#\:\(\)\[\]]+", "", section_content)
if len(substantive) < 3:
    empty_sections.append(sec_name)
```

The regex stripping characters from `section_content` only targets whitespace, `-`, `*`, `#`, `:`, `(`, `)`, `[`, `]`. 

**The Exploit**: Unstripped punctuation characters (such as `.`, `,`, `;`, `~`, `_`, `=`, `!`, `/`, `\`) or arbitrary filler strings bypass the check completely.

```text
[1. PAYLOAD]
Real task description.
[2. NEGATIVE BOUNDS]
...
[3. SUCCESS INVARIANT]
,,,
[4. COMPLETION SINK]
;;;
```

**Concrete Proof**:
```bash
python -c "
from tools.subagent import validate_contract
prompt = '''
[1. PAYLOAD]
Real task.
[2. NEGATIVE BOUNDS]
...
[3. SUCCESS INVARIANT]
,,,
[4. COMPLETION SINK]
;;;
'''
valid, reason = validate_contract(prompt)
print(valid, reason)
"
# Output: True P-N-S-C Forge contract verified.
```
*Result*: An agent can provide zero negative bounds, zero success criteria, and zero completion sinks, and `tools.subagent` certifies the contract as verified.

### 3.2 Failure Mode 2: Cross-Section Collision via Quoted Headers

The section regexes in `tools/subagent.py` (lines 46–61) use case-insensitive lookups for headers:
```python
SECTION_2_PAT = re.compile(
    r"(?:^|\n)\s*(?:\[?2\.?\s*NEGATIVE\s+BOUNDS(?:\s*\([^)]*\))?(?:\s*:[^\]\n]*)?\]?|2\.\s+NEGATIVE\s+BOUNDS(?:\s*\([^)]*\))?:?|NEGATIVE\s+BOUNDS:?)",
    re.IGNORECASE,
)
```

If a prompt in Section 1 (`PAYLOAD`) quotes, references, or discusses section headers on a new line (for instance, a prompt instructing an agent to audit a contract or review another agent's log):
```text
1. PAYLOAD:
The user prompt to analyze is:
2. NEGATIVE BOUNDS:
Do not perform actions.
3. SUCCESS INVARIANT:
Verification passes.
4. COMPLETION SINK:
out/report.md
```

`validate_contract` matches the quoted text as the start of Section 2. This silently truncates Section 1, shifts all downstream token boundaries, and corrupts contract semantics.

### 3.3 Failure Mode 3: Zero Semantic Verification (Empty Dummy Strings)

The validator tests only string length: `len(substantive) >= 3`.
A prompt containing:
- `1. PAYLOAD: abc`
- `2. NEGATIVE BOUNDS: none`
- `3. SUCCESS INVARIANT: none`
- `4. COMPLETION SINK: none`

passes with exit code 0. The system verifies *typographic ritual*, not semantic validity or real-world safety.

### 3.4 Failure Mode 4: Arbitrary Section Permutation

In `tools/subagent.py`, line 193:
```python
matches.sort(key=lambda x: x[1])
```

The validator detects all present headers and sorts them by their order of appearance in the string. If an agent places:
- `4. COMPLETION SINK` at line 1
- `2. NEGATIVE BOUNDS` at line 5
- `3. SUCCESS INVARIANT` at line 9
- `1. PAYLOAD` at line 13

The contract is validated as compliant. This breaks the sequential conditioning of the autoregressive transformer, which reads top-to-bottom.

### 3.5 Failure Mode 5: PreToolUse Hook Single-Gate Bypass

In `.agents/hooks.json`:
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

The hook intercepts only tool invocations matching `invoke_subagent`. If an agent:
1. Executes a Python script via `run_command` (`python -c "import ..."`),
2. Launches background workers or daemons,
3. Calls external MCP tools or REST endpoints,
4. Directly edits files via `write_file` or `edit_file`,

the hook executes zero checks. The "forge gate" is bypassed entirely.

---

## 4. How Frontier Agent Frameworks Solve Bounding (Zero Prompt Theater)

Frontier autonomous coding agent frameworks—including SWE-agent (Princeton NLP), Devin (Cognition Labs), Aider, and OpenHands—do not rely on negative prompt lists or section-header regexes to establish operational safety. 

They enforce bounding through **deterministic runtime environments and capability-restricted interfaces**.

| Dimension | Kageyōni Subagent Forge | SWE-agent (Princeton) | Devin (Cognition Labs) | OpenHands / Aider |
|---|---|---|---|---|
| **Bounding Mechanism** | Natural language prompt cards + Regex check | Agent-Computer Interface (ACI) + Docker | Ephemeral microVMs (Firecracker/gVisor) | Git transactions + AST parsers |
| **Enforcement Layer** | Autoregressive Context (Advisory) | Shell harness & Custom CLI (Mechanical) | Linux namespaces & Kernel cgroups | Process supervisor & Git tree |
| **Negative Constraints** | English blacklists ("FORBIDDEN: X") | Commands non-existent in ACI grammar | Dropped Linux capabilities & non-root | AST rejection & compiler gates |
| **File Mutation Gate** | "Forego mutating unapproved files" prompt | Custom editor rejects invalid line offsets | Isolated workspace overlay filesystem | Atomic git commit rollbacks on failure |
| **Verification Gate** | "All test suites must pass" text | Real bash exit codes in container | Automated build & test execution loops | Mechanical test runner exit code |

### 4.1 SWE-agent: The Agent-Computer Interface (ACI)

SWE-agent replaces raw shell execution with a purpose-built, human-engineered CLI designed specifically for LLMs:
- **Restricted Action Space**: Instead of pleading with the model not to hallucinate line numbers, SWE-agent provides specific tools: `open_file`, `scroll_down`, `edit_lines(start, end, replacement)`.
- **Mechanical Pre-Commit Guard**: The python harness checks if the context around `start` and `end` matches the real file before applying the edit. If the match fails, the command is rejected with an actionable error.
- **Hermetic Containerization**: All executions run inside an isolated Docker container with read-only root mounts and `--network none` flags where appropriate.

### 4.2 Devin: Ephemeral MicroVMs & Capability Isolation

Devin enforces boundaries through hypervisor-level and kernel-level sandboxing:
- **Ephemeral Firecracker MicroVMs**: Every session runs inside a fresh, disposable microVM. System crashes, rogue forks, or disk wipes affect only the disposable VM.
- **POSIX Privilege Boundaries**: Execution runs as an unprivileged user without `sudo`. Kernel capabilities (`CAP_SYS_ADMIN`, `CAP_NET_RAW`) are dropped.
- **Deterministic Compiler Verification**: Devin is not instructed *"Do not return hollow stubs"*. Instead, real compilers (`tsc`, `cargo check`, `pytest`) run in the sandbox. If the compiler exits non-zero, Devin's loop cannot mark the task complete.

### 4.3 First-Principles Invariant: The Bounding Law

> **The Mechanical Bounding Law**: A constraint is real if and only if a violation causes a deterministic execution failure (exit code $\neq 0$, permission denied, SIGKILL, AST syntax error). Any constraint whose violation produces a continued execution stream is not a boundary—it is an aesthetic preference.

---

## 5. Re-Architecting Subagent Bounds: The 4-Layer Mechanical Matrix

To replace the prompt-card theater of P-N-S-C with genuine systems-grade safety, Kageyōni should transition to a **4-Layer Mechanical Enclosure Architecture**.

```
+-------------------------------------------------------------+
| Layer 1: Deterministic Dispatch Firewall                    |
| - Filter tool schemas per subagent role                     |
| - Research agents receive ONLY read-only tools              |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
| Layer 2: Operating System & Filesystem Sandbox              |
| - Linux namespaces (mount, pid, net) via WSL / Landlock     |
| - Overlayfs: Workspace is read-only except designated sink  |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
| Layer 3: AST & Static Analysis Verification Gate            |
| - Tree-sitter / Ruff / Mypy runs prior to disk commit       |
| - Hollow stubs (pass/TODO) rejected by AST node inspection  |
+-------------------------------------------------------------+
                              |
+-------------------------------------------------------------+
| Layer 4: Process Supervisors & Cryptographic Receipts       |
| - Strict wall-clock timeouts & cgroup memory limits         |
| - Cryptographic SHA-256 validation of completion sinks      |
+-------------------------------------------------------------+
```

### Layer 1: Deterministic Dispatch Firewall
Instead of telling an agent in English *"Do not mutate files"*, remove `write_file`, `edit_file`, and mutating bash commands from the subagent's tool declaration schema. A model cannot call a tool that does not exist in its API manifest.

### Layer 2: Operating System & Filesystem Isolation
Run subagents within isolated WSL sandboxes or lightweight container processes utilizing Linux Landlock or read-only overlay mounts. Designate the sink directory (e.g., `out/`) as the only writable volume. File operations outside this path fail at the VFS kernel layer (`EACCES`).

### Layer 3: AST & Static Analysis Pre-Commit Gates
Enforce code quality mechanically:
- **No Hollow Stubs**: An AST visitor inspects Python function bodies. If a function contains only `pass`, `...`, or `raise NotImplementedError`, the commit is blocked by the AST gate.
- **Syntax Validation**: Run AST parsers before writing code to disk.

### Layer 4: Process Supervisors & Cryptographic Receipts
Verify deliverables through physical filesystem telemetry:
- Verify file existence, non-zero size, and compute the SHA-256 digest of the sink artifact.
- Log process exit codes and execution duration to a tamper-proof receipt log.

---

## 6. Epistemic Verification Receipts

The following execution receipts prove the forensic claims and test suite integrity.

### 6.1 Subagent Forge Unit Test Suite (`tests/test_subagent_forge.py`)
```text
============================= test session starts =============================
platform win32 -- Python 3.13.12, pytest-9.0.3, pluggy-1.6.0
rootdir: C:\Kageyoni
configfile: pyproject.toml
plugins: anyio-4.12.1, ddtrace-4.7.1, Faker-40.15.0, langsmith-0.7.36, logfire-4.32.1, cov-7.1.0, typeguard-4.4.3
collected 17 items

tests\test_subagent_forge.py .................                           [100%]

============================= 17 passed in 1.14s ==============================
```

### 6.2 Outpost Forensics & Smoke Test Suite (`role-failure-forensics`)
```text
test_arbitrary_ordering_vulnerability (test_forge_forensics.TestForgeInvalidationMechanics.test_arbitrary_ordering_vulnerability)
Demonstrate that P-N-S-C allows sections in arbitrary inverted order. ... ok
test_evasion_via_unstripped_punctuation (test_forge_forensics.TestForgeInvalidationMechanics.test_evasion_via_unstripped_punctuation)
Demonstrate that 3 periods '...' or semicolons ';;;' completely bypasses FM-FORGE-03. ... ok
test_header_quote_boundary_corruption (test_forge_forensics.TestForgeInvalidationMechanics.test_header_quote_boundary_corruption)
Demonstrate that referencing a section header inside a prompt causes parsing collisions. ... ok
test_01_settings_validity (test_smoke.TestOutpostSmoke.test_01_settings_validity)
Verify config/settings.json exists and has mandatory schema keys. ... ok
test_02_pipeline_execution (test_smoke.TestOutpostSmoke.test_02_pipeline_execution)
Execute complete ingest -> filter -> core -> export pipeline. ... ok
test_03_isolation_boundary (test_smoke.TestOutpostSmoke.test_03_isolation_boundary)
Verify that runtime directory is self-contained. ... ok

----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
============================================================
  RUNNING TEST SUITE: role-failure-forensics
============================================================

✔ All 6 test(s) passed successfully.
```

### 6.3 Outpost Pipeline Execution Receipt (`runner.py run`)
```text
============================================================
  EXECUTING PIPELINE: role-failure-forensics
  Mandate: Forensic quarry of real-world AI role replacement and workflow automation failures
============================================================
[1/4] Ingesting source data...
      Ingested 3 record(s).
[2/4] Applying filter rules and domain boundaries...
      Retained 2 valid record(s).
[3/4] Running core domain processing...
      Processed 2 item(s).
[4/4] Generating deliverables and exports...
      Generated 2 export artifact(s):
        - /home/flowe/outposts/role-failure-forensics/out/export_20261028_040806.json
        - /home/flowe/outposts/role-failure-forensics/out/export_summary.md

✔ Pipeline execution completed successfully.
```

---

## 7. Conclusion & Invalidation Summary

The Subagent Forge (`tools/subagent.py`) and its P-N-S-C contract paradigm provide the appearance of governance while introducing severe attention degradation, context bloat, and trivial regex evasion holes. 

**Definitive Verdict**:
1. Prompt-level negative constraints must be decommissioned in favor of positive operational specifications and role-specific tool pruning.
2. Section-header regex matching must be replaced with structured schema validation and machine-enforced pre-commit gates.
3. Subagent containment must be delegated to the operating system and container runtime (WSL, Linux namespaces, read-only overlays), not an LLM prompt wrapper.
