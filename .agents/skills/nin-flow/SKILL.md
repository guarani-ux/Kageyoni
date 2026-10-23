---
name: nin-flow
description: Router over the ninshu systems engineering cartridge (nin-probe, nin-console, nin-smelt, nin-audit, nin-quarry, nin-retro, nin-craft) and its handoffs to Cognitive OS core.
disable-model-invocation: true
---

# Ninshū Systems Flow Router (`/nin-flow`)

Ask `/nin-flow` which systems capability or channel fits your current binary analysis, protocol reverse-engineering, or dynamic capability task. Never execute ungrounded mutations or claim capability completion without empirical tool receipts.

## Table of Contents

- [1. The Main Systems Flow](#1-the-main-systems-flow)
- [2. On-Ramps by Situation](#2-on-ramps-by-situation)
- [3. Shared Craft & Governance Layer](#3-shared-craft--governance-layer)
- [4. Handoff to Cognitive OS Core](#4-handoff-to-cognitive-os-core)

---

## 1. The Main Systems Flow

1. **[`/nin-probe`](../nin-probe/SKILL.md)** *(Inspect Format & Structural Invariants)*:
   Probes binary headers, entrypoints, imported symbols, section boundaries, or wire packets using native channels (PE, ELF, Mach-O, ASAR, APK, PCAP, TLS).
2. **[`/nin-console`](../nin-console/SKILL.md)** *(SSL 4000 Channel Strip & Bus Modulation)*:
   Assembles a multi-channel sub-mix across Busses A–F, calibrates preamp trim/4-band EQ/dynamics backpressure, schedules fader execution, and freezes cryptographically signed `master_print.json` receipts.
3. **[`/nin-smelt`](../nin-smelt/SKILL.md)** *(Molten Metal Dynamic Smelter)*:
   When encountering an unfamiliar binary format, custom packet structure, or external library, probes structural invariants, casts a new pure-Python channel parser + test suite, passes the mechanical audit gate, and hot-mounts Channel $N$ into `ninshu_codex.sqlite`.
4. **[`/nin-audit`](../nin-audit/SKILL.md)** *(Zero-Trust Qualification Gate)*:
   Enforces AST shortcut scanning, test discrimination, and in-memory AST mutation kills ($\ge 90\%$). Validates all 48 channels and runs cold-process persistence checks.
5. **[`/nin-quarry`](../nin-quarry/SKILL.md)** *(Capability & AST Pattern Vault)*:
   Extracts and stores reusable AST slices, reverse-engineered protocol schemas, and transducer patterns for future project builds.
6. **[`/nin-retro`](../nin-retro/SKILL.md)** *(Scar Registry & Feedback Loop)*:
   Registers discovered protocol anomalies, compiler quirks, or execution frictions into `ScarRegistry` to prevent regressions.

---

## 2. On-Ramps by Situation

- **You have an unknown binary file, game archive, or custom protocol dump** $\rightarrow$ Start at **`/nin-smelt`** to probe its grammar and cast a parser.
- **You have an existing executable (ELF, PE, ASAR, APK) and want security/structure inspection** $\rightarrow$ Start at **`/nin-probe`**.
- **You want to run a multi-channel analysis with budgets, priority, and master print** $\rightarrow$ Run **`/nin-console`**.
- **You modified a channel or parser and need zero-trust verification** $\rightarrow$ Run **`/nin-audit`**.

---

## 3. Shared Craft & Governance Layer

- **[`nin-craft`](../nin-craft/SKILL.md)**: Constitutional rules, 3-tier reversibility boundaries, memory ceilings ($\le 64\text{ KB}$ heap), and zero-theater evidence standards.

---

## 4. Handoff to Cognitive OS Core

Once a systems task completes, enqueue actions requiring human authorization into `vault/approvals.md` (`TIER-B` for local changes, `TIER-A` for irreversible mutations) via [`/cos-approve`](../../../skills/cos-approve/SKILL.md), and log architectural decisions (e.g. chosen protocol layouts or budget ceilings) in `vault/decisions.md` via [`/cos-decide`](../../../skills/cos-decide/SKILL.md).
