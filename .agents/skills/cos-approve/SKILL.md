---
name: cos-approve
description: "Cognitive OS approval & verification gateway: review pending actions in vault/approvals.md, execute only user-approved items, and verify actual outcomes (VERIFIED vs. FAILED)."
disable-model-invocation: true
---

# Cognitive OS Approval & Verification Gateway (`/cos-approve`)

In a Collaborator-Model Cognitive OS, the AI never takes consequential external action silently. Every proposed external action, application submission, schedule change, or major vault mutation sits in `vault/approvals.md` (`AWAITING_APPROVAL`) until the human turns the key—and every executed action must be verified against reality before closing.

Uses the constitutional rules in [`cos-craft`](../cos-craft/SKILL.md).

## Table of Contents

- [1. The Approval Lifecycle (`PROPOSED -> APPROVED -> VERIFIED`)](#1-the-approval-lifecycle-proposed---approved---verified)
- [2. Enqueueing an Item (`AWAITING_APPROVAL`)](#2-enqueueing-an-item-awaiting_approval)
- [3. Reviewing & Executing Approved Items](#3-reviewing--executing-approved-items)
- [4. Mandatory Post-Action Verification](#4-mandatory-post-action-verification)

---

## 1. The Approval Lifecycle (`PROPOSED -> APPROVED -> VERIFIED`)

Every item (`APR-YYYY-NNN`) in `vault/approvals.md` moves through strict, auditable states:

```text
[AI Prepares Draft / Action]
             │
             ▼
    AWAITING_APPROVAL ──(User Rejects)──► REJECTED (Reason logged)
             │
      (User Approves)
             │
             ▼
   EXECUTED_UNVERIFIED ──(Verification Check)──► VERIFIED  (Receipt logged)
                                             └──► FAILED    (Alert + Recovery)
```

---

## 2. Enqueueing an Item (`AWAITING_APPROVAL`)

When any skill (such as `/cos-briefing`, `/cl-draft`, or `/av-beats`) prepares a consequential action, append it to `vault/approvals.md`:

```markdown
### `APR-YYYY-NNN`: "<Action Summary>"
- **Status**: `AWAITING_APPROVAL`
- **Authority Tier**: `TIER-A`
- **Domain**: `#professional` | `#creative` | `#personal`
- **Prepared Artifact / Action**: <Link to file or exact command/submission details>
- **Rationale & Provenance**: <Why this is proposed; link to goal or task>
- **Verification Method**: <How we will confirm the outcome actually succeeded>
<!-- src: <skill-name> | date: YYYY-MM-DD -->
```

---

## 3. Reviewing & Executing Approved Items

When the user invokes `/cos-approve`:
1. Read `vault/approvals.md` and present all items currently in `AWAITING_APPROVAL` or `EXECUTED_UNVERIFIED`.
2. For each `AWAITING_APPROVAL` item, ask the user to **Approve**, **Edit**, or **Reject**:
   - If **Approved**: Execute the action (or hand the verified export package to the user for external submission) and transition status to `EXECUTED_UNVERIFIED`.
   - If **Rejected**: Mark `REJECTED` and record the user's 1-line reason so the system learns not to repeat unwanted proposals.

---

## 4. Mandatory Post-Action Verification

Never assume that an approved action succeeded simply because it was triggered:
1. Check the **Verification Method** defined on the approval record (for example, checking that `export_cover_letter.py` exited `0` and produced the HTML file, or confirming with the user that an application portal accepted the submission).
2. Once confirmed, update the status to `VERIFIED` with an ISO timestamp and verification receipt.
3. If an action failed, mark `FAILED`, alert the user immediately, and propose a recovery step.
