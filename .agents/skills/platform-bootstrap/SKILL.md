---
name: platform-bootstrap
description: Automatically detects the host platform (macOS/Darwin vs Windows), provisions local directories and outpost sandboxes, and verifies runtime health for Kageyoni.
---

# Kageyōni Platform Bootstrap & Runtime Detection

The **Platform Bootstrap Engine** (`tools/bootstrap.py`) establishes automated, deterministic detection, provisioning, and health qualification for Kageyōni across dual-homed environments: **macOS / Darwin** (Apple Silicon & Intel) and **Windows** (WSL2 Ubuntu).

By mechanically verifying system prerequisites, establishing local runtime directories, mounting outpost sandboxes, and executing zero-trust domain audits, bootstrap ensures that the entire system estate is verified before any causal or agentic workflows execute.

---

## 1. Platform Detection Architecture

The bootstrap engine probes host system primitives using pure Python standard library:

| Platform Component | Probed Attribute | Supported Targets | Normalization Rule |
| :--- | :--- | :--- | :--- |
| **Operating System** | `sys.platform` | `darwin`, `win32`, `linux` | `darwin` $\rightarrow$ `macOS / Darwin`<br/>`win32` $\rightarrow$ `Windows`<br/>`linux` $\rightarrow$ `Linux` |
| **CPU Architecture** | `platform.machine()` | `arm64`, `aarch64`, `x86_64`, `AMD64` | `arm64`/`aarch64` on Darwin $\rightarrow$ `arm64 (Apple Silicon)`<br/>`x86_64`/`AMD64` $\rightarrow$ `x86_64 (Intel/AMD)` |
| **Python Runtime** | `sys.version_info` | Python $\ge$ 3.10 | Fails with exit code 1 if `< (3, 10)` |
| **Terminal Encoding**| `sys.stdout.encoding` | UTF-8 capable | Configures standard streams via `reconfigure(encoding="utf-8", errors="replace")` |

---

## 2. Sandbox Isolation Models

Kageyōni strictly isolates downstream dependencies, long-running processes, and third-party tools from polluting the core causal engine.

### A. macOS / Darwin: Native POSIX Sandbox
- **Zero Translation Layer**: Runs natively under Darwin POSIX; no virtual machines or emulation layers required.
- **Outposts Base**: Defaults to `$HOME/outposts/` (customizable via `export KAGEYONI_OUTPOSTS_DIR=...`). Automatically created if missing.
- **Shinobi State Integration**: Automatically detects participant state in `$SHINOBI_ROOT`, `$HOME/shinobi`, or workspace `shinobi/.state/`.
- **Dynamic Path Resolution**: Causal engines dynamically resolve all paths relative to `__file__`, eliminating hardcoded Windows paths (`C:/Kageyoni`) and WSL UNC mirrors.

### B. Windows: WSL2 Ubuntu UNC Mirror
- **Distribution Target**: Ubuntu under WSL2 (`wsl.exe -d Ubuntu`).
- **Outposts Path**: `/home/flowe/outposts/<name>`.
- **Host UNC Mirroring**: Mirrored to Windows via primary UNC path `\\wsl$\Ubuntu\home\flowe\outposts\<name>` or fallback `\\wsl.localhost\Ubuntu\home\flowe\outposts\<name>`.
- **Pre-flight Probe**: Executes `wsl.exe -d Ubuntu -e bash -c "echo WSL_READY"` to verify virtualization daemon readiness.

### C. Repository Root State Directories
On all platforms, bootstrap guarantees that local ephemeral runtime directories are provisioned in the repository root:
- `.state/` - Local runtime checkpoints, SQLite caches, and living health receipt (`.state/system_health.json`).
- `build/` - Ephemeral compiled database outputs (`build/kageyoni.sqlite`).

---

## 3. Zero-Pip Runtime Invariants

Kageyōni enforces a strict **Zero-Pip Core Invariant**:
- The core causal engine (`kageyoni/*`), tool infrastructure (`tools/*`), and 48-channel Ninshū patchbay require **zero external pip dependencies**.
- Out-of-the-box compatibility with default Xcode CLI tools, Homebrew Python 3.10+, or Windows standard Python distributions.
- Any third-party libraries (e.g., parsers, ML frameworks, web scrapers) are strictly quarantined to isolated downstream outposts with their own private `.venv` environments.

---

## 4. Unified Command Invocations

All platform operations are exposed through the single-gate unified runner (`python -m tools.runner`):

### 1. Platform Bootstrap & Health Verification
```bash
# Standard full bootstrap (detects platform, provisions sandboxes, runs tests & audits)
python -m tools.runner bootstrap

# Quick bootstrap skipping test suite execution
python -m tools.runner bootstrap --skip-tests

# Verbose bootstrap with granular cartography and health telemetry
python -m tools.runner bootstrap --verbose

# Quiet mode outputting only the canonical banner
python -m tools.runner bootstrap --quiet
```

### 2. Workspace Hygiene Audit
Verifies that no throwaway files exist in the repository root, legacy scripts are registered, and top-level directories match `ATLAS.md`:
```bash
python -m tools.runner check-hygiene
```

### 3. Sovereign Domain Boundary Cartography Check
Inspects the AST of all Python files to enforce strict architectural fences (Domain 1 Causal Engine cannot import Domain 3 Tactical / Simulation layers):
```bash
python -m tools.runner check-boundaries
```

### 4. Living System Cadence & Health Receipt
Runs smoke test suites, tallies database migrations, parses active outposts, and records receipt to `.state/system_health.json`:
```bash
python -m tools.runner cadence
```

---

## 5. Canonical Banner & Exit Code Contracts

### Banner Format Specification
Upon invocation, `bootstrap` renders the standardized 70-column receipt banner:

```
======================================================================
  KAGEYONI SYSTEM PLATFORM BOOTSTRAP & RUNTIME DETECTION
======================================================================
Platform: <OS> (<Arch>)
Python:   <Version> (<Executable>)
Sandbox:  <Native Darwin POSIX / WSL2 Ubuntu>
Health:   HEALTHY (<commit-hash>)
Status:   READY TO OPERATE
======================================================================
```

When run in standard mode, it appends the verified component checklist:
```
  ✔ Platform:        Windows (x86_64 Intel/AMD) [Python 3.13.12 >= 3.10, UTF-8 (utf-8)]
  ✔ Sandboxes:       WSL2 Ubuntu Available (UNC Mirror: \\wsl$\Ubuntu\home\flowe\outposts)
  ✔ Local Dirs:      .state/ and build/ verified
  ✔ Boundaries:      Passed (Domain 1 / Domain 3 AST isolation clean)
  ✔ Cadence:         Generated .state/system_health.json (PASSED (7 passed, 0 failed in 0.36s))
  ✔ Outposts Fleet:  2 registered active (job-radar, sample-probe)
======================================================================
```

### Exit Code Contracts
- **`0` (READY TO OPERATE)**:
  - Python version $\ge$ 3.10.
  - Local state directories (`.state/`, `build/`, and outpost directory on Darwin) verified.
  - Zero Domain 1 $\rightarrow$ Domain 3 boundary violations detected by AST cartographer.
  - Core test suite passes and git commit hash is resolved (`HEALTHY`).
- **`1` (DEGRADED / ACTION REQUIRED)**:
  - Python version $< 3.10$.
  - Domain boundary fence violated.
  - Core smoke tests fail or system cadence is degraded.
