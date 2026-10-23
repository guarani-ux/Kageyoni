---
name: nin-craft
description: Shared constitutional principles, 3-tier reversibility boundaries, thermodynamic memory laws, and anti-theater standards for Ninshū and systems engineering.
---

# Systems Engineering & Ninshū Craft Standard (`/nin-craft`)

The craft and discipline layer governing all systems engineering, binary inspection, reverse-engineering, and console modulation tasks.

## Table of Contents

- [1. The 3 Constitutional Laws](#1-the-3-constitutional-laws)
- [2. 3-Tier Reversibility Matrix](#2-3-tier-reversibility-matrix)
- [3. Thermodynamic Memory Ceiling ($\le 64\text{ KB}$)](#3-thermodynamic-memory-ceiling-le-64text-kb)
- [4. Defensive & Analytical Boundary](#4-defensive--analytical-boundary)

---

## 1. The 3 Constitutional Laws

1. **Bit-Perfect Grounding**: Treat plans, agent summaries, and status fields as unverified claims until grounded by raw tool execution records, exit codes, and verifiable outputs.
2. **Zero-Theater**: No placeholder stubs (`pass`, `TODO`), no import-only verification, and no decorative audio math. Every control and channel must have an executable consumer.
3. **No Silent Escapes**: Code and tests execute strictly within designated workspace and sandbox boundaries.

---

## 2. 3-Tier Reversibility Matrix

- **Tier 0 (Autonomous Fast Loop)**: Read-only inspections (`view_file`, `git status`, binary file parsing, disassembly, AST analysis, unit test runs). Proceeds immediately with zero human latency.
- **Tier 1 (Local Destructive Gate)**: Potentially destructive local actions (file deletions, `git reset --hard`, binary patching, dropping tables, installing dependencies). Requires explicit human approval preceded by:
  `WARNING: POTENTIALLY DESTRUCTIVE ACTION`
- **Tier 2 (Irreversible External Gate)**: Remote repository mutations (`git push`, remote PR merges), firmware flashing, cloud mutations. Strictly requires sovereign human key-turn.

---

## 3. Thermodynamic Memory Ceiling ($\le 64\text{ KB}$)

All in-tree parsers and channel strips must execute under `ThermodynamicProfiler`:
- Memory overhead must remain strictly bounded: $\le 64\text{ KB}$ peak heap allocation for metadata inspection.
- Streaming large binary inputs or packets must process via incremental chunking or windowing, never slurping arbitrary megabytes into unconstrained lists.

---

## 4. Defensive & Analytical Boundary

All reverse engineering, binary parsing, and telemetry capabilities are strictly confined to defensive forensics, static/dynamic format inspection, symbol recovery, and architectural analysis. No offensive exploit generation or unauthorized external network probing is permitted.
