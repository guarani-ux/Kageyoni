---
name: cl-draft
description: "Cover letter exploit: draft the 4-beat cover letter into cover-letter.md from angle.md, jd-xray.md, vault/career-quarry.md, and vault/voice-profile.md, enforcing the 4-Sentence Transduction Formula and mandatory inline proof custody tags."
disable-model-invocation: true
---

# Cover Letter 4-Beat Drafter (`/cl-draft`)

This is **exploit**: `jd-xray.md`, `angle.md`, `vault/career-quarry.md`, and `vault/voice-profile.md` are locked. Treat `vault/career-quarry.md` as strictly read-only. Every substantive claim or metric in `cover-letter.md` must cite a verified Story ID (`<!-- ref: STORY-... -->`).

Uses the anti-slop rules and topologies in [`cl-craft`](../cl-craft/SKILL.md).

## Table of Contents

- [1. Pre-Draft Custody & Regime Check](#1-pre-draft-custody--regime-check)
- [2. The 4-Beat Structural Blueprint](#2-the-4-beat-structural-blueprint)
- [3. The 4-Sentence Transduction Pass (Beats 2 & 3)](#3-the-4-sentence-transduction-pass-beats-2--3)
- [4. Anti-Slop & Voice Profile Pass](#4-anti-slop--voice-profile-pass)
- [5. Write `cover-letter.md` with Custody Tags](#5-write-cover-lettermd-with-custody-tags)

---

## 1. Pre-Draft Custody & Regime Check

Read `angle.md`, `jd-xray.md`, `vault/career-quarry.md`, and `vault/voice-profile.md` in full:
1. Verify that every `STORY-*` and `PHIL-*` ID named in `angle.md` exists in `vault/career-quarry.md`.
2. Check `SCOPE-NEG-*` (Negative Scopes) in `vault/career-quarry.md` so no sentence implies an unverified credential.
3. Lock the word budget by **Selection Regime**:
   - `Private Mandate Mode`: **250–320 words total** (4 crisp paragraphs, max 65–75 words per paragraph).
   - `Institutional Rubric Mode`: **400–550 words total** (explicitly evidencing Minimum & Desirable Qualifications).

---

## 2. The 4-Beat Structural Blueprint

Draft the letter across four distinct movements matched to the chosen **Argument Topology** (`Topology A, B, C, or D` in [`TOPOLOGIES-AND-TRANSDUCTION.md`](../cl-craft/TOPOLOGIES-AND-TRANSDUCTION.md)):

1. **Beat 1 — The Mandate Hook (2–3 sentences, $\le 55$ words)**:
   - Open directly with the operational tension or institutional mission at the center of the role and your thesis for solving it.
   - **Hard Ban**: Never open with *"I am thrilled/excited to apply"*, *"When I saw your posting"*, or generic flattery (`RULE_NO_FLATTERY_OPENER`).
   - Append `<!-- ref: PHIL-01 -->` (or the relevant philosophy/story tag).
2. **Beat 2 — Primary Proof Pillar (4 sentences, $\le 110$ words)**:
   - Execute the **4-Sentence Transduction Formula** on the primary `STORY-*` anchor.
   - Append `<!-- ref: STORY-XXX-NNN -->`.
3. **Beat 3 — Secondary Proof Pillar / Force Multiplier (3–4 sentences, $\le 100$ words)**:
   - Execute the secondary proof story (or cross-disciplinary bridge) that disarms `Layer 3 Screener Anxiety` and satisfies the secondary JD requirement.
   - Append `<!-- ref: STORY-XXX-NNN -->`.
4. **Beat 4 — The Peer-Level Forward Close (2 sentences, $\le 45$ words)**:
   - Name the immediate 90-day contribution and invite a direct conversation. Zero groveling (`RULE_CONFIDENT_DIRECT_CLOSE`).
   - Append `<!-- ref: PHIL-01 -->`.

---

## 3. The 4-Sentence Transduction Pass (Beats 2 & 3)

Never copy-paste or lightly reword a resume bullet (`Action + Metric`). Every proof paragraph must walk through four causal steps:
1. **Sentence 1 (Friction / Constraint)**: Name the messy operational reality, resource limit, or stakeholder tension before you intervened.
2. **Sentence 2 (Judgment Call & Trade-off)**: State the specific decision you made—and what approach you deliberately rejected or traded off.
3. **Sentence 3 (Measurable / Tangible Result)**: State the exact verified outcome from `vault/career-quarry.md` (zero metric rounding or inflation).
4. **Sentence 4 (Direct Transfer to Target Mandate)**: Connect that proven mechanism directly to the employer's Day-1 reality in `jd-xray.md`.

---

## 4. Anti-Slop & Voice Profile Pass

Before writing `cover-letter.md` to disk, check every sentence against [`SMELLS-AND-REGIMES.md`](../cl-craft/SMELLS-AND-REGIMES.md) and `vault/voice-profile.md`:
- Cut every participial opener (*"Having led..."*, *"Leveraging..."*).
- Break any 3-item symmetric triad (`X, Y, and Z`) into a focused 1-or-2 item anchor.
- Strip all banned intensifiers (*passionate, thrilled, seamlessly, spearheaded, synergy, testament, pivotal*).

---

## 5. Write `cover-letter.md` with Custody Tags

Save the draft to `vault/applications/<company-role>/cover-letter.md`. Ensure every paragraph ends with its `<!-- ref: STORY-... -->` or `<!-- ref: PHIL-... -->` tag so `/cl-review` and `export_cover_letter.py` can mechanically verify custody.
