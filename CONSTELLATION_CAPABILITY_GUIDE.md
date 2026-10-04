# Constellation Capabilities Guide: Use-Case Operational Catalog
Version: 1.0 — 2026-10-03
Status: Authoritative Capability Map for Shinobi Celestials & Autonomous Agents

---

## How to Use This Guide

This catalog codifies the entire estate of capabilities, tools, engines, and substrates developed across the constellation (including Kageyoni, WSL Ubuntu, Star Ocean, Konoha, 10 Shadows, and Booder World).

**CRITICAL RULE FOR AGENTS & CELESTIALS**:
- **Do NOT browse by repository or folder name.**
- **Browse strictly by your immediate USE CASE.**
- When facing an encounter, task, or crisis, find the functional category matching your objective. Identify the specific tool, module, or mechanism, inspect its inputs/prerequisites, and wield it in-place.
- Never duplicate code into your personal files. Discover, inspect, bind, and wield existing organs.

---

## Table of Contents by Use Case

1. [Reconnaissance, Perception & Epistemic Scouting](#1-reconnaissance-perception--epistemic-scouting)
2. [Tactical Intervention, Physics & Encounter Combat](#2-tactical-intervention-physics--encounter-combat)
3. [Resilience, Self-Healing & Antifragility](#3-resilience-self-healing--antifragility)
4. [Continuity, Fermentation & Continuous Learning](#4-continuity-fermentation--continuous-learning)
5. [Real-World Tasks, Research & Creative Production](#5-real-world-tasks-research--creative-production)
6. [Governance, Sandboxing & Security Boundaries](#6-governance-sandboxing--security-boundaries)
7. [Multi-Celestial Coordination, Swarms & Constellations](#7-multi-celestial-coordination-swarms--constellations)

---

## 1. Reconnaissance, Perception & Epistemic Scouting

**Use Case**: When you need to inspect an unfamiliar territory, verify claims, scout code or AST structures, detect hallucinations/illusions, or establish what is known vs. unknown.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Horizon AST & TF-IDF Scout** | Scans surrounding sibling repositories for tools, laws, and capabilities matching task keywords without hardcoded paths. | `shinobi/shinobi.py` / `garganta_scout.py` | `python shinobi.py scout --topic <topic> --task <task>` |
| **Epistemic Partitioning** | Enforces strict truth boundaries on claims: `OBSERVED` (empirically verified), `INFERRED` (hypothesis), `CANDIDATE_RELATION` (unproven correlation), `UNKNOWN` (explicit missing presence). | `kageyoni/constellation.py` | Class `EpistemicStatus`, `SummonScarError` |
| **Perspective-Scoped Lens** | Filters world state so an actor sees only permitted observations and admissible actions. Prevents God-view leakage. | `kageyoni/encounter.py` | `Encounters.inspect(branch, eid, viewer=actor_id)` |
| **Truth & Red-Team Audit** | Audits claims against source receipts, flags ungrounded assertions, and checks for hallucinated citations. | `audit_truth_redteam.py` / `anbu_auditor.py` | `C:\BOODER WORLD\audit_truth_redteam.py` |
| **Dōjutsu Horizon Astrolabe** | Specializes perception across analytical lenses (structural, adversarial, historical, relational) inspired by dōjutsu calculus. | `shinobi/forms/dojutsu.json` & `CONSTELLATION_DOJUTSU_CALCULUS.md` | `python shinobi.py begin --form forms/dojutsu.json` |

---

## 2. Tactical Intervention, Physics & Encounter Combat

**Use Case**: When you need to act on the world, alter physical state, deploy barriers, anchor unstable environments, execute combat techniques, or resolve multi-agent clashes.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Encounter Action Dispatcher** | Validates proposed actions against actor bindings, prerequisites, and branch revisions; executes via `Encounters.act()` with zero partial writes. | `kageyoni/emergence/action_dispatcher.py` | `EncounterActionDispatcher.dispatch(branch, eid, request, reply, viewer)` |
| **Substrate Anchoring & Dampening** | Transmutes volatile or ruptured environments into dense basalt foundations or harmonic dampeners. | `kageyoni/emergence/causal_encounter.py` | Actions `sciel_anchor`, `sciel_harmonic_dampener` |
| **Kinetic Perimeter Locking** | Enforces zero-bypass barriers once substrate conditions are rigid. | `kageyoni/emergence/causal_encounter.py` | Action `maki_enforce` |
| **Nature Transformations (5 Elements)** | Physical transformations across Fire, Water, Earth/Basalt, Wind, and Lightning with strict conservation laws. | `kageyoni/nature/` | `kageyoni/nature/transformations.py` |
| **Primordial Will System** | Modulates will density and antigravity leverage to overcome high-resistance environmental constraints. | `kageyoni/will/` | `kageyoni/will/primordial.py` |
| **Bankai & Sage Mode Launchers** | High-energy situational state transformations for crisis encounters. | `bankai_launcher.py`, `sage_mode_launcher.py` | `\\wsl.localhost\Ubuntu\home\flowe\konoha\sage_mode_launcher.py` |
| **Ten Shadows Shadow-Crawl** | Traverses obstructed boundaries or invokes temporary shadow shikigami constructs. | `C:\10 SHADOWS\loop_engine` | `C:\10 SHADOWS\loop_engine\shadow.py` |

---

## 3. Resilience, Self-Healing & Antifragility

**Use Case**: When a process crashes, an operation is interrupted, code sprawl accumulates, an infinite loop is detected, or you need to recover from failure.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Fail-Closed Crash Recovery** | Reopens a dead or interrupted participant; inspects target residue, records `uncertain_after_interruption`, and refuses blind replay. | `shinobi/shinobi.py` | `python shinobi.py --home <dir> recover` |
| **Immune Healing & Sprawl Cleanup** | Analyzes repository AST sprawl, detects unreferenced or dead scaffolding, and cleanly prunes non-functional mutations. | `heal_sprawl.py` | `\\wsl.localhost\Ubuntu\home\flowe\konoha\heal_sprawl.py` |
| **Zenkai Ledger (Growth via Failure)** | Commits permanent resilience traits and adaptations derived from surviving damage or failed attempts. | `zenkai_ledger.db` / `zenkai_ledger.json` | `\\wsl.localhost\Ubuntu\home\flowe\konoha\zenkai_ledger.json` |
| **Shinra Kill Switch & Loop Breaker** | Circuit breaker that forcibly halts runaway execution, memory leaks, or recursive action loops. | `shinra_kill_switch.py`, `shinra_loop_breaker.py` | `C:\BOODER WORLD\shinra_kill_switch.py` |
| **Bubblewrap Drive Masking** | Mechanically isolates Linux/WSL workspace from Windows host filesystem (`/mnt/c` vanishes into empty tmpfs). | `bwrap` executor | `bwrap --ro-bind / / --bind /workspace /workspace --tmpfs /mnt` |

---

## 4. Continuity, Fermentation & Continuous Learning

**Use Case**: When you need to preserve memory across sessions, ferment insights over time, synthesize reusable techniques from traces, or inherit lessons without conversational drift.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Sourdough Continuous Fermentation** | Long-horizon culture circulation: maintains active starter state, digests receipts, and matures understanding over time. | `sourdough_state.json`, `sourdough_feed` | `\\wsl.localhost\Ubuntu\home\flowe\konoha\sourdough_state.json` |
| **Trace Technique Derivation** | Synthesizes an `ExecutableTechnique` (ordered steps, precondition maps, target state deltas) strictly from validated execution receipts. | `kageyoni/emergence/technique.py` | `derive_technique_from_trace(trace, encounter_spec, eid, branch)` |
| **Structured Returns & Adjudication** | Proposes state or behavioral adjustments with mandatory provenance, supporting encounter hashes, scope, and deterministic reversal rules. | `shinobi/shinobi.py` | `python shinobi.py propose-return` / `adjudicate-return` |
| **Situation Memory & Experience Scars** | Persists experiential scars and memory transfers across situations; ensures prior lessons constrain future actions. | `kageyoni/situations/` | `kageyoni/situations/memory.py`, `test_slice6_experience_scar_writeback.py` |
| **Attributed Learning & Method Registry** | ACID ledger recording proposed lessons, reviewed methods, and attributed outcomes linked to character nodes. | `kageyoni/intelligence/learning.py`, `methods.py` | `Learning(engine).propose()`, `Methods(engine).register()` |

---

## 5. Real-World Tasks, Research & Creative Production

**Use Case**: When executing real-world media production, video review, evidence-backed research, stakeholder communications, or strategic briefs.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **VantageStudio Media Lifecycle** | End-to-end professional video/media pipeline: Opportunity -> Concept -> Brief -> Treatment -> Pre-Production -> Gatekeeper. | `kageyoni/vantage/` | `from kageyoni.vantage import VantageStudio, ProjectBrief` |
| **Fail-Closed Pre-Production Gate 3** | Mechanically halts production if location permits, talent releases, or critical dependencies are unconfirmed. | `kageyoni/vantage/gatekeeper.py` | `Gatekeeper.evaluate_gate_3()` |
| **Research Brief Compiler** | Compiles research briefs linking every substantive claim to inspected source passages, preserving contradictions and coverage limits. | `kageyoni/research_compiler/` | `kageyoni/research_compiler/compiler.py` |
| **Painted Door Packaging Matcher** | Audits titles, thumbnails, and marketing promises against physical demonstrations verified in the treatment. | `governance/skills/constellation/SKILL.md` (Haiku 21) | `kageyoni/vantage/audits.py` |
| **Doctrinal & Synthesis Forge** | Synthesizes disparate requirements, stakeholder mandates, and technical specs into a unified strategic plan. | `doctrinal_synthesizer.py`, `synthesis_forge.py` | `C:\BOODER WORLD\synthesis_forge.py` |

---

## 6. Governance, Sandboxing & Security Boundaries

**Use Case**: When you need to protect core configurations, enforce authority boundaries, sandbox untrusted inputs, or manage execution budgets.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Zero-Trust Execution Engine** | Rejects unverified execution grants; requires explicit capability tokens and evidence receipts before mutations. | `10 SHADOWS/zero_trust_engine` | `C:\10 SHADOWS\zero_trust_engine` |
| **Shinra Hardened Sandboxes & Jails** | Sandboxes Python or WASM execution; isolates processes from unauthorized environment variables and host filesystems. | `shinra_sandbox_hardened.py`, `shinra_jail.py` | `C:\BOODER WORLD\shinra_sandbox_hardened.py` |
| **Protected Change Architecture** | Core invariants, laws, and engine configurations are read-only to ordinary tasks. Requires dedicated, authorized objective to amend. | `SYSTEM_DESIGN_AND_IMPLEMENTATION_GUIDE.md` §8 | Protected System Definitions Layer |
| **Compare-And-Swap (CAS) Revisions** | Prevents stale writes and race conditions by requiring `expected_revision == current_revision`. | `kageyoni/engine.py` / `action_dispatcher.py` | `Engine.apply(command)` |
| **Resource & PnL Watchdog** | Monitors token burn, latency, compute resources, and aborts tasks exceeding bounded allocations. | `shinra_pnl_watchdog.py`, `shinra_resource_monitor.py` | `C:\BOODER WORLD\shinra_resource_monitor.py` |

---

## 7. Multi-Celestial Coordination, Swarms & Constellations

**Use Case**: When coordinating multiple participants or celestials, running swarms, resolving multi-perspective encounters, or merging complementary capabilities.

| Operational Capability | What It Does & When to Wield It | Source Implementation | Entry Point & Interface |
|---|---|---|---|
| **Constellation-Chef-Beast Lifecycle** | The Chef binds an operational constellation; the Beast executes the encounter and dissolves upon completion, committing receipts. | `kageyoni/constellation.py` | `with Beast(field) as beast: ...` |
| **Joy Boy Reground** | Purges obsolete framing, conversational scaffolding, and representation privilege while preserving receipts, scars, and active skills. | `kageyoni/constellation.py:reground` | `reground(field, keep_scars=True)` |
| **Shared Authoritative World (Zero-Sync)** | Multiple participants observe and act upon a single ACID SQLite database via perspective filters, eliminating lossy sync copies. | `kageyoni/workspaces/world.py` | `world.sqlite` with `viewer=actor` |
| **Symbiogenesis Engine** | Fuses capabilities from two distinct participants or agents into an emergent hybrid capability without losing individual lineage. | `kageyoni/developmental/symbiogenesis.py` | `kageyoni/developmental/` |
| **Shinra Meta-Router & Swarm Mesh** | Distributes tasks across specialized agents (scouts, mutators, verifiers) and arbitrates consensus. | `shinra_meta_router.py`, `mesh_node.py` | `C:\BOODER WORLD\shinra_meta_router.py` |
| **Hydrated Character Roster** | Deterministically hydrates persistent characters (Voss, Sciel, Maki, Alexandra, Sebastian) directly from their SQLite databases. | `kageyoni/emergence/hydration.py` | `hydrate_character_from_disk(character_id)` |

---

## 8. Summary: How a Shinobi Wields This Estate

When an encounter begins:
1. **Identify the Use Case**: Do not ask *"what repo am I in?"* Ask *"what is the operational nature of this challenge?"* (Scouting? Combat? Healing? Memory? Governance? Synthesis?).
2. **Consult this Matrix**: Locate the capability that directly addresses that challenge.
3. **Inspect the Organ**: View the target carrier's source code, AST, or CLI interface to verify its inputs, prerequisites, and authority boundaries.
4. **Wield In-Place**: Invoke the capability via subprocess CLI or module import without duplicating or laundering the code.
5. **Record Delta Genesis**: Capture the exact stdout, exit code, or engine receipt. Commit the outcome to SQLite.
