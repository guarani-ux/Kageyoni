---
name: cos-capture
description: "Cognitive OS intake & triage: capture raw notes, voice transcripts, meeting takeaways, or links into vault/inbox.md and classify them into Observations, Ideas, or Commitments with source provenance and domain tags."
disable-model-invocation: true
---

# Cognitive OS Capture & Triage (`/cos-capture`)

Human-Computer Interaction (HCI) and Personal Information Management (PIM) studies show that capture fails whenever the system forces heavy categorization at the moment of thought. `/cos-capture` separates **Zero-Friction Intake** from **AI-Assisted Triage**.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. Zero-Friction Raw Intake](#1-zero-friction-raw-intake)
- [2. The 3-Way Ontological Distinction](#2-the-3-way-ontological-distinction)
- [3. Domain Tagging & Source Provenance](#3-domain-tagging--source-provenance)
- [4. Conflict & Duplicate Detection](#4-conflict--duplicate-detection)
- [5. Triage Handoff Proposal](#5-triage-handoff-proposal)

---

## 1. Zero-Friction Raw Intake

Before writing anything, read `vault/inbox.md` from disk so manual entries are never overwritten.

If the user drops a quick thought, voice dictation, meeting transcript, job link, or fragment:
1. Immediately preserve the raw entry in `vault/inbox.md` with an ISO timestamp (`YYYY-MM-DD HH:MM`) and origin tag (`<!-- src: user-chat | date: YYYY-MM-DD -->`).
2. Never discard an incomplete thought because it seems vague.

---

## 2. The 3-Way Ontological Distinction

Classify each raw item in `vault/inbox.md` into one of three distinct types:

1. **`[OBSERVATION]`** *(Semantic / Episodic Fact)*:
   - A fact, metric, quote, career accomplishment, or meeting note that needs to be remembered, not acted on today.
   - *Destination proposal*: `vault/career-quarry.md` (if a professional achievement), project notes, or `vault/journal/YYYY-MM-DD.md`.
2. **`[IDEA]`** *(Speculative Possibility)*:
   - A creative spark, potential feature, video concept, or "what if" inquiry (*"What if we structure how-to shoots as two-parters?"*).
   - *Destination proposal*: Active project `quarry.md` (if immediate) or `vault/dormant.md` (if non-urgent, preventing `tasks.md` clutter).
3. **`[COMMITMENT]`** *(Concrete Action or Decision)*:
   - An action item with an implied or explicit deadline, follow-up, or external obligation (*"Apply to UCalgary Faculty of Social Work Comms role by Friday"*).
   - *Destination proposal*: `vault/tasks.md` (with capacity tag `[HIGH-FOCUS]`, `[STEADY]`, or `[QUICK-WIN]`) or `vault/approvals.md` (if an external action is ready to queue).

---

## 3. Domain Tagging & Source Provenance

Assign every classified item:
- **Domain Tag**: `#professional`, `#creative`, or `#personal` (enforcing strict domain isolation per `CLAUDE.md`).
- **Provenance Comment**: `<!-- src: inbox#YYYY-MM-DD | domain: <domain> -->` so every downstream task or note can trace where it came from.

---

## 4. Conflict & Duplicate Detection

Before moving triaged items out of `vault/inbox.md`, check `vault/tasks.md` and `vault/decisions.md`:
- Does a captured commitment contradict an active decision in `vault/decisions.md`?
- Does a meeting transcript name or deadline conflict with an existing record?
If a discrepancy exists, **flag the conflict explicitly** before writing to `vault/tasks.md`.

---

## 5. Triage Handoff Proposal

Present a crisp triage table to the user:

```markdown
| # | Item Summary | Type | Domain | Proposed Destination | Conflict / Note |
|---|---|---|---|---|---|
```

Wait for user confirmation (`"Approve all"` or adjustments) before moving items from `vault/inbox.md` into `vault/tasks.md`, `vault/dormant.md`, or `vault/career-quarry.md`.
