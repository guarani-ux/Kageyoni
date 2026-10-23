---
name: nin-audit
description: Zero-Trust Qualification Gate for Ninshū and systems engineering tasks. Enforces AST linting, in-memory mutation kills, and cold-process verification.
---

# Zero-Trust Qualification Gate (`/nin-audit`)

The Zero-Trust Qualification Gate enforces rigorous, anti-theater standards for every systems module, test suite, and channel modification. Built to eliminate AI reward hacking, ungrounded completions, and weak test suites.

## Table of Contents

- [1. The 4 Verification Pillars](#1-the-4-verification-pillars)
- [2. AST Shortcut Detection](#2-ast-shortcut-detection)
- [3. In-Memory AST Mutation Testing](#3-in-memory-ast-mutation-testing)
- [4. Running Cold-Process Qualification](#4-running-cold-process-qualification)

---

## 1. The 4 Verification Pillars

1. **AST Shortcut Elimination**: Rejects code containing swallowed exceptions (`except: pass`), unconditional promotions (`promoted = True` outside conditional checks), and unmounted stubs.
2. **Test Discrimination Verification**: Verifies that test suites import the candidate module under test, execute valid golden vectors, assert positive invariants, and explicitly enforce fail-closed rejection via `assertRaises`.
3. **In-Memory AST Mutation Testing**: Injects synthetic AST faults (operator inversion, return modification) into the candidate module in memory; requires $\ge 90\%$ mutation kill rate.
4. **Cold-Process Execution**: Spawns separate subprocesses to verify database persistence, receipts, and exit codes without in-process memory bleed.

---

## 2. AST Shortcut Detection

`tools/mechanical_audit_gate.py` parses Python ASTs directly to flag:
- Generic `except Exception: pass` without logging or re-raising.
- Unconditional `verdict = "ACCEPT"` assignments.
- Missing stride or bounds checks in binary parsers.
- Tautological test assertions (`assertTrue(True)`).

---

## 3. In-Memory AST Mutation Testing

The gate mutates comparisons (`<` $\leftrightarrow$ `<=`, `==` $\leftrightarrow$ `!=`) and strips safety guards in an isolated child process. If the candidate's test suite still passes when the logic is broken, the gate flags **TEST_FAILURE_MUTANT_SURVIVED** and rejects the PR.

---

## 4. Running Cold-Process Qualification

Run the master 7-gate cold-process verifier:

```bash
python tools/verify_ninshu_complete.py
```

Gates verified:
1. `audit_completion.py` (48/48 live Patchbay execution).
2. `test_ninshu_patchbay_wiring` (8/8 wiring & real WSL tests).
3. `test_ssl_control_contract` (40/40 expected-effect and absence-of-effect tests).
4. `test_ninshu_rea_parity` (19/19 parity & provider bridge tests).
5. `test_ninshu_molten_smelter` (8/8 dynamic smelting & modulation tests).
6. `test_ninshu_zero_trust_gate` (6/6 AST linting & mutation tests).
7. Cold-process SQLite persistence and master print verification.
