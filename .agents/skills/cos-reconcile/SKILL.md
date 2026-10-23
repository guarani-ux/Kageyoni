---
name: cos-reconcile
description: "Cognitive OS end-of-day reconciliation: compile completed work into an episodic journal entry, reschedule unfinished items without guilt spirals, and park new ideas."
disable-model-invocation: true
---

# Cognitive OS End-of-Day Reconciliation (`/cos-reconcile`)

Continuity across days is where most personal systems break down: unfinished tasks pile up as overdue guilt, and completed progress vanishes without a trace. `/cos-reconcile` closes the daily loop in under 3 minutes.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. Gather Today's Activity](#1-gather-todays-activity)
- [2. Compile the Episodic Journal (`vault/journal/YYYY-MM-DD.md`)](#2-compile-the-episodic-journal-vaultjournalyyyy-mm-ddmd)
- [3. Clean Rollover of Unfinished Tasks (Zero Guilt)](#3-clean-rollover-of-unfinished-tasks-zero-guilt)
- [4. Park New Ideas & Set Tomorrow's Anchor](#4-park-new-ideas--set-tomorrows-anchor)

---

## 1. Gather Today's Activity

Read `vault/tasks.md`, `vault/inbox.md`, `vault/approvals.md`, and `vault/decisions.md` from disk. Ask the user (or inspect recent changes):
- Which tasks or applications were completed today?
- Which items were started, blocked, or deferred?
- Were any new ideas or job leads captured along the way?

---

## 2. Compile the Episodic Journal (`vault/journal/YYYY-MM-DD.md`)

Write or update today's episodic log at `vault/journal/YYYY-MM-DD.md` (including a `## Table of Contents`):
1. **Completed Outcomes**: Tasks finished, scripts drafted, or applications shipped (with links to artifacts).
2. **Decisions & Approvals Logged**: Any `DEC-*` or `APR-*` records updated today.
3. **Carried Forward / Blocked**: Items intentionally moved to tomorrow or backlogged.
4. **Energy & Friction Note**: 1 sentence on what flowed well vs. where friction hit.

---

## 3. Clean Rollover of Unfinished Tasks (Zero Guilt)

For every unfinished item that was on today's plan in `vault/tasks.md`:
- Do **not** leave a wall of red "overdue" items.
- Ask the user to classify each unfinished item into one of three honest moves:
  1. **Roll to Tomorrow**: Still top priority for tomorrow's `/cos-briefing`.
  2. **Return to Backlog**: Important, but not this week's priority.
  3. **Move to Dormant (`vault/dormant.md`) or Drop**: No longer worth cognitive load.

---

## 4. Park New Ideas & Set Tomorrow's Anchor

1. Triage any leftover fragments in `vault/inbox.md` (or move speculative sparks to `vault/dormant.md`).
2. Ask the user to name **1 Single Anchor Task** for tomorrow morning so `/cos-briefing` starts with zero decision fatigue.
