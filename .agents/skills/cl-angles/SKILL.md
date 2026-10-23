---
name: cl-angles
description: "Cover letter positioning 3 ways: spawn 3 parallel sub-agents to pitch competing positioning hooks, argument topologies, and story pairings from jd-xray.md and vault/career-quarry.md, compare them, and lock angle.md."
disable-model-invocation: true
---

# Cover Letter 3-Way Positioning Angles (`/cl-angles`)

There is never just one way to position your background for a senior role. Left to default instincts, an LLM will write a generic chronological summary. `/cl-angles` spawns **3 parallel sub-agents** to pitch radically different positioning strategies from `jd-xray.md` and `vault/career-quarry.md`, compares them, and locks your chosen strategy into `angle.md` before drafting begins.

Uses the vocabulary and topologies in [`cl-craft`](../cl-craft/SKILL.md).

## Table of Contents

- [1. Frame the Diagnostic Constraints](#1-frame-the-diagnostic-constraints)
- [2. Spawn 3 Parallel Positioning Sub-Agents](#2-spawn-3-parallel-positioning-sub-agents)
- [3. Compare Across 3 Axes & Recommend](#3-compare-across-3-axes--recommend)
- [4. Lock `angle.md`](#4-lock-anglemd)

---

## 1. Frame the Diagnostic Constraints

Read `jd-xray.md` and `vault/career-quarry.md`. Summarize in 4 lines for the user:
- **Selection Regime**: `Private Mandate Mode` vs. `Institutional Rubric Mode`.
- **The 90-Day Mandate**: The primary operational bottleneck the hire must solve.
- **Top Screener Anxiety**: The hesitation the letter must disarm.
- **Available Quarry Stories**: Which `STORY-*` and `PHIL-*` IDs are in play.

---

## 2. Spawn 3 Parallel Positioning Sub-Agents

Spawn 3 sub-agents in parallel, passing each `jd-xray.md` and `vault/career-quarry.md`, with a distinct strategic mandate:

- **Agent 1 — The Production & Systems Multiplier (`Topology A / B`)**:
  *"Position the candidate around operational throughput, repeatable workflows, and measurable channel growth—proving how they get 2x output from constrained resources without burning out the team."*
- **Agent 2 — The Institutional & Multi-Stakeholder Bridge (`Topology B / D`)**:
  *"Position the candidate as the translator across siloed departments, external community partners, and public/accessibility standards—proving high-trust governance paired with broadcast-grade execution."*
- **Agent 3 — The Audience-First Creative Director & Craftsman (`Topology B / C`)**:
  *"Position the candidate around narrative sharpness, audience-segmented scripting, and multi-camera / audio craft—proving they elevate dry institutional or technical briefs into work people actually watch."*

Each sub-agent must return under 250 words:
1. **Positioning Title & Selected Topology** (`Topology A, B, C, or D`).
2. **The Opening 2-Sentence Hook**: Zero flattery (`RULE_NO_FLATTERY_OPENER`); names the employer's mandate and the candidate's thesis within 35 words.
3. **Primary & Secondary Proof Pairing**: Exact `STORY-*` IDs from `vault/career-quarry.md` and the specific **Judgment Call** each story will highlight.
4. **How It Disarms Layer 3 Anxiety**: How this angle neutralizes screener hesitation.
5. **Trade-off**: What this angle emphasizes vs. what it leaves to the resume.

---

## 3. Compare Across 3 Axes & Recommend

Present all three pitches clearly and compare them across:
- **3-Second Triage Punch**: Which hook stops a tired hiring manager fastest?
- **Mandate / Rubric Fit**: Which pairing best answers the hidden 90-day pain?
- **Differentiation**: Which angle separates the candidate from generic applicants in the stack?

Give an **opinionated recommendation** (or propose a specific hybrid, such as Agent 1's throughput proof + Agent 2's stakeholder bridge) and wait for the user's choice.

---

## 4. Lock `angle.md`

Write the approved positioning strategy, selected topology, opening hook, and locked `STORY-*` IDs to `vault/applications/<company-role>/angle.md` (with a `## Table of Contents`). Tell the user `angle.md` is locked and ready for `/cl-draft`.
