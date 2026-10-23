---
name: nin-smelt
description: Molten Metal Dynamic Capability Smelter for Ninshū. Discovers structural grammar, casts new channel parsers, and hot-mounts them into the console.
---

# Molten Metal Dynamic Smelter (`/nin-smelt`)

The Molten Metal Dynamic Smelter gives Ninshū the capacity to reconfigure itself on the fly. When faced with an unfamiliar binary format, proprietary archive, or custom wire protocol, the smelter probes structural grammar, casts a verified channel strip, audits it through the Zero-Trust gate, and hot-mounts it into `ninshu_codex.sqlite`.

## Table of Contents

- [1. The 4-Stage Smelting Lifecycle](#1-the-4-stage-smelting-lifecycle)
- [2. Probing Specimen Grammar](#2-probing-specimen-grammar)
- [3. Casting & Mechanical Quenching](#3-casting--mechanical-quenching)
- [4. Hot-Mounting & Console Modulation](#4-hot-mounting--console-modulation)

---

## 1. The 4-Stage Smelting Lifecycle

```text
[Raw Specimen Samples] ──► 1. Probe Grammar (Magic, Fields, TLV, AST)
                                     │
                                     ▼
[CastArtifact] ◄────────── 2. Cast Channel (Synthesizes Module + Test Suite)
      │
      ▼
3. Quench & Audit (Mechanical Gate + In-Memory AST Mutation Kill)
      │
      ▼
4. Hot-Mount (Registers into SQLite Codex & ActiveConsole as CH N)
```

---

## 2. Probing Specimen Grammar

Run `ninshu_bridge.py probe` or use `MoltenSmelter`:

```bash
python domains/systems/scripts/ninshu_bridge.py probe --file /path/to/specimen
```

The probe analyzes byte entropy, magic markers, field widths, endianness, length-value prefixes, string tables, and structural invariants, returning a `StructuralBlueprint`.

---

## 3. Casting & Mechanical Quenching

`MoltenSmelter.cast_channel()` generates:
1. `kageyoni/ninshu/smelted_<name>.py`: Pure Python standard library parser with fail-closed bounds checking and `ThermodynamicProfiler` memory ceilings ($\le 64\text{ KB}$).
2. `tests/test_ninshu_smelted_<name>.py`: Discriminating `unittest` suite containing valid golden vectors, truncated headers, corrupted magic, and out-of-bounds adversarial mutants.

The cast artifact is quenched through `MechanicalAuditorGate.audit_channel()`. Any unconditional promotions, swallowed exceptions, or surviving AST mutants cause immediate rejection.

---

## 4. Hot-Mounting & Console Modulation

Upon passing the gate, `quench_and_mount()` hot-mounts the channel into `ninshu_codex.sqlite` (e.g. Channel 49) on its target bus. The newly smelted channel is immediately available to:
- `Patchbay.execute_channel(channel_number, payload)`
- `ActiveConsole` 20-control modulation
- `NinshuPowerSystem` 8-knob Will carrier shaping
