---
name: cos-decide
description: "Cognitive OS decision & reconsideration engine: evaluate options against goals.md, detect conflicts with past commitments, and log decisions with rationale and explicit Reconsideration Triggers in vault/decisions.md."
disable-model-invocation: true
---

# Cognitive OS Decision & Reconsideration Engine (`/cos-decide`)

Most personal systems forget *why* a decision was made, causing users to either relitigate the same choice every week or cling to an outdated strategy after the facts have changed. `/cos-decide` logs **Commitments with Reasons and Reconsideration Triggers**.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. Load Context & Prior Decisions](#1-load-context--prior-decisions)
- [2. Structured Option Analysis (Collaborator Mode)](#2-structured-option-analysis-collaborator-mode)
- [3. The Decision Record Schema (`vault/decisions.md`)](#3-the-decision-record-schema-vaultdecisionsmd)
- [4. Reconsideration Protocol (When a Trigger Fires)](#4-reconsideration-protocol-when-a-trigger-fires)

---

## 1. Load Context & Prior Decisions

1. Read `vault/goals.md` and `vault/decisions.md` in full.
2. Check whether the question under consideration overlaps with or contradicts an existing `DEC-*` record. If it contradicts an active decision, surface the original rationale first:
   > *"In `DEC-2026-001`, you decided X because of Y. Has condition Z changed?"*

---

## 2. Structured Option Analysis (Collaborator Mode)

When the user is weighing a choice (for example, which job archetype to prioritize, whether to accept a contract, or how to scope a creative project):
1. Frame **2 to 3 distinct options** (never a false binary).
2. For each option, state:
   - **Alignment with `vault/goals.md`**: Which goal it advances and what it costs in time/capacity.
   - **Hidden Assumptions**: What must be true in the real world for this option to succeed.
   - **Downside / Reversibility**: What happens if this assumption proves false.
3. Give a grounded recommendation, but leave the final call strictly to the user (`TIER-H`).

---

## 3. The Decision Record Schema (`vault/decisions.md`)

Once the user decides, append the record to `vault/decisions.md` using this exact structure:

```markdown
### `DEC-YYYY-NNN`: "<Concise Decision Title>"
- **Date Logged**: YYYY-MM-DD
- **Domain**: `#professional` | `#creative` | `#personal`
- **Status**: `ACTIVE` | `RECONSIDER_DUE` | `SUPERSEDED` | `RETIRED`
- **Decision**: <1-2 sentence statement of what we are doing and what we are NOT doing>
- **Rationale & Evidence**: <Why this path was chosen; cite goals or quarry records>
- **Rejected Alternatives**: <What we turned down and why, so we don't relitigate it next Tuesday>
- **Core Assumptions**: <What we believe to be true right now>
- **Reconsideration Trigger**:
  - `reconsider_on`: YYYY-MM-DD
  - `reconsider_if`: <Concrete observable condition that invalidates the assumptions>
<!-- src: cos-decide | goal: GOAL-01 -->
```

---

## 4. Reconsideration Protocol (When a Trigger Fires)

When `/cos-briefing` or new evidence triggers a reconsideration:
1. Present the original `DEC-YYYY-NNN` record alongside the new conflicting evidence or elapsed date.
2. Ask the user to choose one of three outcomes:
   - **Reaffirm**: Extend `reconsider_on` to a new date and log a 1-line verification note.
   - **Revise**: Mark the old decision `SUPERSEDED by DEC-YYYY-NNN+1` and log the updated decision with the new evidence.
   - **Retire**: Mark `RETIRED` if the goal or context is finished.
Never delete historical decision records; preserve the causal chain.
