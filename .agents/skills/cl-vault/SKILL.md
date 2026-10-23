---
name: cl-vault
description: "Cover letter explore & custody vault: build and update vault/career-quarry.md (CFJOV schema) and vault/voice-profile.md, or run a 2-question Incremental Gap Interview when a JD needs missing proof."
disable-model-invocation: true
---

# Career Evidence Vault & Gap Miner (`/cl-vault`)

A resume only stores compressed 1-line outcomes (`Action + Metric`). A great cover letter requires **the story behind the bullet**: the messy constraint, the competing priorities, and the specific judgment call you made. `/cl-vault` mines and preserves those stories permanently in `vault/career-quarry.md` so you never start from scratch.

Uses the vocabulary and rules in [`cl-craft`](../cl-craft/SKILL.md).

## Table of Contents

- [1. Re-Read Existing Vault Files First](#1-re-read-existing-vault-files-first)
- [2. The CFJOV Story Schema (`vault/career-quarry.md`)](#2-the-cfjov-story-schema-vaultcareer-quarrymd)
- [3. Negative Scopes & Honest Boundaries](#3-negative-scopes--honest-boundaries)
- [4. Incremental 2-Question Gap Mining Protocol](#4-incremental-2-question-gap-mining-protocol)
- [5. Voice Profile Calibration (`vault/voice-profile.md`)](#5-voice-profile-calibration-vaultvoice-profilemd)

---

## 1. Re-Read Existing Vault Files First

Always read `vault/career-quarry.md` and `vault/voice-profile.md` from disk before adding or updating entries so manual user edits are preserved.

---

## 2. The CFJOV Story Schema (`vault/career-quarry.md`)

When ingesting a resume, project note, or user interview answer, structure every achievement into an atomic `STORY-<ORG>-<NNN>` block:

```markdown
### `STORY-CPL-001`: "<Descriptive Story Title>"
- **Domain**: <Core Functional Domain>
- **Role & Org**: <Title, Organization, Dates>
- **Context**: <Operational baseline and scale>
- **Friction (The Hard Reality)**: <What was broken, constrained, backlogged, or politically difficult before intervention>
- **Judgment (The Trade-off / Decision)**: <What specific approach you chose and what you deliberately sacrificed or refused>
- **Outcome (Quantified & Qualitative)**: <Exact verified metrics, deliverables shipped, and stakeholder impact>
- **Verification & Custody**: <Public channel, artifact link, or resume line reference>
```

---

## 3. Negative Scopes & Honest Boundaries

Always maintain a `## Hard Negative Scopes & Boundaries (`SCOPE-NEG-*`)` section at the bottom of `vault/career-quarry.md`:
- Explicitly record what was a proposal vs. enacted policy, what was an independent R&D project vs. enterprise deployment, and which adjacent tasks were handled by other teams.
- Downstream skills (`/cl-draft` and `/cl-review`) treat `SCOPE-NEG-*` as hard anti-fabrication boundaries.

---

## 4. Incremental 2-Question Gap Mining Protocol

When `/cl-decode` flags that a target Job Description requires a capability not yet in `vault/career-quarry.md` (or when a resume bullet lacks `Friction` and `Judgment`), run a **2-Question Frontier Round**:

1. **Question 1 (Friction & Judgment)**:
   > *"For [Project / Requirement X], what was the hardest real-world constraint or bottleneck you faced, and what specific workflow or creative decision did you make to solve it?"*
2. **Question 2 (Outcome & Honest Boundary)**:
   > *"What was the concrete result, and where was the honest boundary of your role on it?"*

**The Honest Adjacent Pivot**:
If the user says *"I haven't used Tool/Process X directly, only Y"*, record an `ADJACENT` entry in `vault/career-quarry.md` so `/cl-draft` can frame an honest, high-agency bridge (*"While my production pipeline used X rather than Y, the underlying operational mechanic is identical..."*) with **zero fabrication**.

---

## 5. Voice Profile Calibration (`vault/voice-profile.md`)

Ensure `vault/voice-profile.md` captures:
- **Tone Register** (for example: *Pragmatic Media & Systems Lead — Understated, Concrete, Peer-to-Peer*).
- **Sentence Cadence** (right-branching active clauses; alternating 12–16 word analytical sentences with crisp 4–6 word statements).
- **Banned Slop Tokens** (the 12 LLM Cover Letter Smells).
