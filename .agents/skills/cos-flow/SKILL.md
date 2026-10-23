---
name: cos-flow
description: Master router for the Collaborator-Model Cognitive OS and its mounted domain cartridges (script-builder for Creative A/V scripting and cover-letter-builder for Professional applications).
disable-model-invocation: true
---

# Cognitive OS Flow Router

You do not need to memorize every skill across the operating system and its domain cartridges. Invoke `/cos-flow` whenever you want to know which skill or workflow fits your immediate situation.

Before recommending that a step be skipped, read that skill's `SKILL.md`: the summaries below are for orientation only.

## Table of Contents

- [1. Core Daily & Weekly Operating Loops](#1-core-daily--weekly-operating-loops)
- [2. Mounted Domain Cartridge: Creative (`script-builder`)](#2-mounted-domain-cartridge-creative-script-builder)
- [3. Mounted Domain Cartridge: Professional (`cover-letter-builder`)](#3-mounted-domain-cartridge-professional-cover-letter-builder)
- [4. Shared Constitutional & Craft Layers](#4-shared-constitutional--craft-layers)
- [5. Domain Isolation & Bridging Rules](#5-domain-isolation--bridging-rules)

---

## 1. Core Daily & Weekly Operating Loops

The core Cognitive OS runs on six plain-text vault files (`vault/inbox.md`, `vault/goals.md`, `vault/tasks.md`, `vault/decisions.md`, `vault/approvals.md`, `vault/dormant.md`):

```text
[Raw Note / Voice / Transcript] ──► /cos-capture ──► vault/inbox.md (Triaged)
                                                           │
[Morning Kickoff] ────────────────► /cos-briefing ◄────────┼──► /cos-decide (vault/decisions.md)
                                         │                 │
                                         ▼                 ▼
                                    /cos-approve (vault/approvals.md)
                                         │
                                         ▼
[End of Day / Weekly] ────────────► /cos-reconcile ──► /cos-curate (vault/dormant.md)
```

1. **[`/cos-capture`](../cos-capture/SKILL.md)** *(Perception & Triage)*:
   Appends or processes raw entries in `vault/inbox.md`, distinguishing each item into `[OBSERVATION]`, `[IDEA]`, or `[COMMITMENT]`, tagging its domain (`#personal`, `#professional`, `#creative`), and binding source provenance (`<!-- src: ... -->`).
2. **[`/cos-briefing`](../cos-briefing/SKILL.md)** *(Morning Kickoff & Capacity Calibration)*:
   Reads `vault/goals.md`, `vault/tasks.md`, `vault/approvals.md`, and `vault/decisions.md`. Surfaces any decisions whose **Reconsideration Trigger** (`reconsider_on` or conflicting evidence) has fired, asks or reads your energy level (`HIGH`, `STEADY`, `LOW`), and proposes a realistic day plan.
3. **[`/cos-decide`](../cos-decide/SKILL.md)** *(Decision Support & Reconsideration Engine)*:
   Helps weigh a major choice against `vault/goals.md`, checks for conflicts with prior decisions, and logs the commitment in `vault/decisions.md` with explicit rationale, rejected options, and a **Reconsideration Trigger**.
4. **[`/cos-approve`](../cos-approve/SKILL.md)** *(Approval Queue & Verification Gateway)*:
   Reviews pending items in `vault/approvals.md` (`AWAITING_APPROVAL`). Executes only what you approve, then runs **Post-Action Verification** (`VERIFIED` vs. `FAILED`).
5. **[`/cos-reconcile`](../cos-reconcile/SKILL.md)** *(End-of-Day Reconciliation)*:
   Summarizes what was completed today into `vault/journal/YYYY-MM-DD.md`, moves unfinished tasks cleanly without guilt spirals, and parks non-urgent sparks.
6. **[`/cos-curate`](../cos-curate/SKILL.md)** *(Weekly Curation & Forgetting)*:
   Prevents `PARA-bloat`. Scans for stale tasks (>30 days untouched), moves unready ideas into `vault/dormant.md`, resurfaces neglected possibilities, and updates `vault/profile.md`.

---

## 2. Mounted Domain Cartridge: Creative (`script-builder`)

Mounted at `domains/creative/skills/`. Use this cartridge whenever you are developing an Audio-Video (A/V) script, documentary treatment, YouTube video, interview guide, or post-shoot paper edit:

- **Main Flow**: [`/av-quarry`](../../domains/creative/skills/av-quarry/SKILL.md) *(Explore into `quarry.md` + coin Leading Word)* $\rightarrow$ [`/av-spine`](../../domains/creative/skills/av-spine/SKILL.md) *(3 parallel sub-agents pitch causal Story Spines into `spine.md`)* $\rightarrow$ [`/av-beats`](../../domains/creative/skills/av-beats/SKILL.md) *(Build 3-column A/V script + Interview Guide into `script.md`)* $\rightarrow$ [`/av-review`](../../domains/creative/skills/av-review/SKILL.md) *(2-axis parallel sub-agent audit)* $\rightarrow$ [`/av-retro`](../../domains/creative/skills/av-retro/SKILL.md).
- **Post-Shoot On-Ramp**: [`/av-paper-edit`](../../domains/creative/skills/av-paper-edit/SKILL.md) *(Sequence verbatim `.srt`/`.txt` interview transcripts into a paper edit)*.

---

## 3. Mounted Domain Cartridge: Professional (`cover-letter-builder`)

Mounted at `domains/professional/skills/`. Use this cartridge whenever you are updating your career evidence vault, decoding a job description, or drafting a high-leverage cover letter:

- **Main Flow**: [`/cl-vault`](../../domains/professional/skills/cl-vault/SKILL.md) *(Maintain `vault/career-quarry.md` & `vault/voice-profile.md`; run 2-question gap interviews)* $\rightarrow$ [`/cl-decode`](../../domains/professional/skills/cl-decode/SKILL.md) *(3-Layer JD X-Ray into `jd-xray.md`)* $\rightarrow$ [`/cl-angles`](../../domains/professional/skills/cl-angles/SKILL.md) *(3 parallel sub-agents pitch competing positioning hooks into `angle.md`)* $\rightarrow$ [`/cl-draft`](../../domains/professional/skills/cl-draft/SKILL.md) *(Draft 4-beat letter with `<!-- ref: STORY-ID -->` custody tags)* $\rightarrow$ [`/cl-review`](../../domains/professional/skills/cl-review/SKILL.md) *(2-axis parallel audit: Hiring Manager Slop vs. Fact Custody)* $\rightarrow$ [`/cl-retro`](../../domains/professional/skills/cl-retro/SKILL.md).

---

## 4. Shared Constitutional & Craft Layers

Three model-invoked reference skills run automatically beneath their respective domains:
- **[`cos-craft`](../cos-craft/SKILL.md)**: Enforces the Collaborator Model (*"AI prepares, human decides"*), the 4 Authority Tiers, provenance tags, and anti-bloat discipline across the OS.
- **[`av-craft`](../../domains/creative/skills/av-craft/SKILL.md)**: Enforces Dual-Channel Grounding, Visual-First Subtraction, Physical Bridges, and Mouth-Shape Syntax for A/V scripts.
- **[`cl-craft`](../../domains/professional/skills/cl-craft/SKILL.md)**: Enforces Selection Regime Calibration (`Mandate Mode` vs. `Institutional Rubric Mode`), the 4-Sentence Transduction Formula, and the 12 Cover Letter Anti-Smells.

---

## 5. Domain Isolation & Bridging Rules

Read [`DOMAIN-MOUNTS.md`](./DOMAIN-MOUNTS.md) for how data flows between the core `vault/` and the mounted domain cartridges without breaking privacy or provenance.
