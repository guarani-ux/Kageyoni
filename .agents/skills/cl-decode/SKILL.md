---
name: cl-decode
description: "Cover letter JD X-Ray: strip a job description into Layer 1 (Table Stakes), Layer 2 (Hidden 90-Day Mandate), and Layer 3 (Screener Anxieties), detect the Selection Regime, map against vault/career-quarry.md, and write jd-xray.md."
disable-model-invocation: true
---

# Job Description 3-Layer X-Ray (`/cl-decode`)

A job description is not a neutral wishlist; it is an organizational symptom log disguised in HR boilerplate. Treating every bullet point equally produces a keyword-stuffed checklist. `/cl-decode` performs a **3-Layer X-Ray** and maps the role's true mandate against `vault/career-quarry.md`.

Uses the vocabulary and rules in [`cl-craft`](../cl-craft/SKILL.md).

## Table of Contents

- [1. Classify the Selection Regime](#1-classify-the-selection-regime)
- [2. Run the 3-Layer JD X-Ray](#2-run-the-3-layer-jd-x-ray)
- [3. Cross-Reference Against `vault/career-quarry.md`](#3-cross-reference-against-vaultcareer-quarrymd)
- [4. Write `jd-xray.md` & Trigger Gap Mining if Needed](#4-write-jd-xraymd--trigger-gap-mining-if-needed)

---

## 1. Classify the Selection Regime

Before analyzing the bullets, classify the target employer into one of two regimes (see [`SMELLS-AND-REGIMES.md`](../cl-craft/SMELLS-AND-REGIMES.md)):

- **`Private Mandate Mode`** *(Tech scale-ups, corporate B2B, agencies, commercial brands)*:
  - Target length: **250–320 words** (4 short paragraphs).
  - Evaluator: Time-pressed hiring manager asking *"Can this person solve my bottleneck next month?"*
- **`Institutional Rubric Mode`** *(Universities, municipalities, public libraries, healthcare, civil service, unionized panels)*:
  - Target length: **400–550 words**.
  - Evaluator: Multi-member search committee scoring explicit **Minimum & Desirable Qualifications (KSAs)**. Every required qualification must be explicitly evidenced in the letter so panel scorers can award rubric points.

---

## 2. Run the 3-Layer JD X-Ray

Strip the job posting into three operational layers:

1. **Layer 1: Table-Stakes HR Boilerplate (Resume Gate)**:
   - Standard software lists, generic communication clichés, baseline years of experience.
   - *Rule*: Satisfy on the resume; **exclude from the cover letter** (except in `Institutional Rubric Mode` where a Minimum Qualification requires a 1-clause confirmation).
2. **Layer 2: The Hidden 90-Day Mandate (Cover Letter Core)**:
   - Decode the operational friction that forced leadership to allocate budget for this seat right now (for example: *"Must thrive in ambiguity"* $\rightarrow$ *"Processes are undocumented; build repeatable production rails without slowing down active requests"*).
   - State the **90-Day Mandate Thesis** in one sentence.
3. **Layer 3: Implicit Screener Anxieties (Preemption Gate)**:
   - Identify the #1 unspoken reason a screener looking at the candidate's resume might hesitate (for example: *Public-to-Private sector translation*, *Specialist-to-Lead jump*, or *Overqualification / Flight risk*) and define how the letter will disarm it.

---

## 3. Cross-Reference Against `vault/career-quarry.md`

Read `vault/career-quarry.md` in full:
- Map the top 2–3 Mandate Capabilities to exact `STORY-*` and `PHIL-*` IDs in the quarry.
- Check `SCOPE-NEG-*` to ensure no planned claim crosses a negative boundary.
- Identify any **Unmatched Requirement Gap**.

---

## 4. Write `jd-xray.md` & Trigger Gap Mining if Needed

Save the structured diagnostic to `vault/applications/<company-role>/jd-xray.md` (with a `## Table of Contents` at the top).

- **If all core requirements match existing `STORY-*` IDs**: Tell the user `jd-xray.md` is ready for `/cl-angles`.
- **If a critical requirement has no matching story in `vault/career-quarry.md`**: **Halt** before `/cl-angles` and ask the 2-Question Incremental Gap Interview from [`/cl-vault`](../cl-vault/SKILL.md) to capture the missing story or register an Honest Adjacent Pivot.
