---
name: cos-curate
description: "Cognitive OS weekly curation, forgetting & dormant revival: prevent PARA-bloat by pruning stale tasks, archiving dormant ideas into vault/dormant.md, resurfacing neglected possibilities, and tuning user preferences."
disable-model-invocation: true
---

# Cognitive OS Weekly Curation & Forgetting (`/cos-curate`)

Comparative research on Second Brain and PKM systems shows that almost all systems eventually collapse under **`PARA-bloat`**: thousands of untouched notes and stale tasks that turn retrieval into noise. A true Cognitive OS requires an explicit **Forgetting, Curation, and Re-Surfacing** routine.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. Run Mechanical Staleness & Health Scan](#1-run-mechanical-staleness--health-scan)
- [2. Prune Active Tasks & Prevent PARA-Bloat](#2-prune-active-tasks--prevent-para-bloat)
- [3. Resurface Neglected Possibilities from `vault/dormant.md`](#3-resurface-neglected-possibilities-from-vaultdormantmd)
- [4. Longitudinal Reflection & Preference Calibration](#4-longitudinal-reflection--preference-calibration)

---

## 1. Run Mechanical Staleness & Health Scan

1. Read `vault/tasks.md`, `vault/dormant.md`, `vault/decisions.md`, `vault/approvals.md`, and recent `vault/journal/*.md` files.
2. *(Optional)* Run `python scripts/cos_cli.py status --vault ./vault` to flag:
   - Tasks in `vault/tasks.md` untouched for >14 days.
   - Decisions in `vault/decisions.md` approaching or past `reconsider_on`.
   - Unverified items in `vault/approvals.md`.

---

## 2. Prune Active Tasks & Prevent PARA-Bloat

Cap active `OPPORTUNITY / NEXT ACTIONS` in `vault/tasks.md` at **no more than 7–10 active items**:
- Flag any task that has been postponed 3+ times or untouched for >14 days.
- Propose moving non-urgent items to `vault/dormant.md` (preserving the idea and its provenance tag without cluttering daily briefings) or archiving them cleanly.

---

## 3. Resurface Neglected Possibilities from `vault/dormant.md`

Scan `vault/dormant.md` ("Someday / Maybe"):
- Select **1 or 2 dormant ideas** that now connect to an active goal in `vault/goals.md` or a recent project in `domains/creative` or `domains/professional`.
- Ask: *"You parked `[DORM-NNN]` earlier. Does it connect to what you're building now, or keep it dormant?"*

---

## 4. Longitudinal Reflection & Preference Calibration

Review the past week's `vault/journal/` entries and `vault/approvals.md` outcomes:
- Report completion patterns across domains (`#professional` vs. `#creative` vs. `#personal`).
- Notice if the user repeatedly rejected or edited a certain kind of AI proposal in `vault/approvals.md`.
- Propose a 1-line update to `vault/profile.md` (or `vault/voice-profile.md`) so the Cognitive OS adapts to the user's real habits rather than forcing rigid rules.
