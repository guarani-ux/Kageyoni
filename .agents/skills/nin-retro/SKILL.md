---
name: nin-retro
description: Operational Scar Registry and feedback loop for Ninshū. Registers system anomalies, broken assumptions, and compiler quirks into persistent memory.
---

# Operational Scar Registry & Feedback Loop (`/nin-retro`)

Captures friction, edge-case regressions, and unexpected protocol behaviors encountered during reverse engineering, casting them into immutable scars within `ScarRegistry` so the system never repeats a solved failure.

## Table of Contents

- [1. The Scar Lifecycle](#1-the-scar-lifecycle)
- [2. Registering an Operational Scar](#2-registering-an-operational-scar)
- [3. Enforcing Scars on the SSL Board](#3-enforcing-scars-on-the-ssl-board)

---

## 1. The Scar Lifecycle

```text
[Failure / Protocol Friction / Bug] ──► 1. Capture Friction & Reproducible Vector
                                                      │
                                                      ▼
[ScarRegistry] ◄─────────────────────── 2. Forge Scar (Invariant Pattern + Mitigation)
      │
      ▼
3. Enforce via Control 18 (Scar Guard) on the SSL Board
      │
      ▼
4. Continuous Regression Guard across All Future Builds
```

---

## 2. Registering an Operational Scar

When a parser fails on a real-world specimen (e.g. an unusual ELF section flag, malformed ASAR header, or minified JS catastrophic backtracking):
1. Extract the minimal reproducible byte sequence or code snippet into `tests/fixtures/`.
2. Formulate the invariant rule (e.g. *"ELF sections with sh_size == 0 must not allocate memory buffer"*).
3. Register the scar into `kageyoni/ninshu/scars.py`:

```python
from kageyoni.ninshu.scars import ScarRegistry, ScarDefinition

registry = ScarRegistry()
registry.register(
    ScarDefinition(
        scar_id="SCAR-SYS-001",
        title="Zero-Length ELF Section Heap Exhaustion",
        trigger_pattern="ELF_SH_SIZE_ZERO",
        remediation_rule="Skip memory allocation when sh_size == 0",
        safety_locked=True,
    )
)
```

---

## 3. Enforcing Scars on the SSL Board

`Control 18 (Scar Guard)` evaluates input substrates against all active scars before routing to downstream strips. Any matching pattern triggers immediate enforcement:
- The strip executes the registered mitigation.
- The master print logs an explicit `SCAR_APPLIED` receipt.
- Safety-locked scars cannot be overridden even when a strip is soloed.
