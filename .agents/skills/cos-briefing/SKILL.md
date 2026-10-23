---
name: cos-briefing
description: "Cognitive OS morning kickoff: synthesize active goals, due tasks, pending approvals, and triggered decision reconsiderations into an energy-calibrated daily plan."
disable-model-invocation: true
---

# Cognitive OS Morning Briefing (`/cos-briefing`)

A morning briefing should never be a static to-do list dump. It is a **situational awareness and capacity calibration loop** that links today's available time and energy to your long-horizon goals in `vault/goals.md`.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. Read Canonical Vault State](#1-read-canonical-vault-state)
- [2. Check Decision Reconsideration Triggers](#2-check-decision-reconsideration-triggers)
- [3. Surface Pending Approval Queue](#3-surface-pending-approval-queue)
- [4. Capacity & Energy Calibration](#4-capacity--energy-calibration)
- [5. Output the Daily Briefing & Wait for Approval](#5-output-the-daily-briefing--wait-for-approval)

---

## 1. Read Canonical Vault State

Read the following files from disk in full before generating any advice:
1. `vault/profile.md` (user constitution, energy patterns, and active focus).
2. `vault/goals.md` (long-horizon targets).
3. `vault/tasks.md` (open commitments, deadlines, and capacity tags).
4. `vault/decisions.md` (active decisions and reconsideration dates/conditions).
5. `vault/approvals.md` (items awaiting human sign-off or post-action verification).
6. `vault/inbox.md` (check if untriaged items are waiting).

*(Optional)*: Run `python scripts/cos_cli.py status --vault ./vault` to get a deterministic mechanical summary of due items.

---

## 2. Check Decision Reconsideration Triggers

Scan every `ACTIVE` record in `vault/decisions.md`:
- Has `reconsider_on` (`YYYY-MM-DD`) arrived or passed?
- Does any recent note in `vault/inbox.md` or `vault/tasks.md` trigger a `reconsider_if` condition?

If yes, highlight the decision at the top of the briefing under **🔄 Decisions Due for Reconsideration**, citing the original rationale and asking whether to **Reaffirm**, **Revise**, or **Retire** via `/cos-decide`.

---

## 3. Surface Pending Approval Queue

List every item in `vault/approvals.md` with status `AWAITING_APPROVAL` or `EXECUTED_UNVERIFIED` so the user can batch-approve or verify them in seconds.

---

## 4. Capacity & Energy Calibration

Propose a daily plan calibrated to human cognitive load:
- Select **1 Primary High-Focus Block** (`[HIGH-FOCUS]`, tied directly to the #1 goal in `vault/goals.md`—for example, shipping 1–2 high-fit Calgary >$75k applications via `/cl-decode` and `/cl-draft`).
- Select **1–2 Steady / Coordination Tasks** (`[STEADY]`).
- Select **1–2 Quick Wins** (`[QUICK-WIN]`, <15 minutes).
- **Conflict Guard**: If total proposed work exceeds realistic daily capacity, explicitly recommend what to defer and why.

---

## 5. Output the Daily Briefing & Wait for Approval

Present the briefing in four compact sections:
1. **🎯 Today's North Star** (linked to `vault/goals.md` with source citation).
2. **⚡ Proposed Day Plan** (`High-Focus`, `Steady`, `Quick Wins`—adaptable if the user states *"I'm low energy today"*).
3. **🚦 Approval Queue & Reconsiderations** (`vault/approvals.md` & `vault/decisions.md`).
4. **📥 Untriaged Inbox Count** (`vault/inbox.md`).

Ask the user: *"Confirm this plan, tell me your energy level (`High` / `Steady` / `Low`) to recalibrate, or approve queued items."*
