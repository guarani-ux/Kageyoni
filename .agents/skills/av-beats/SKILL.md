---
name: av-beats
description: "AV writing, exploit: build a pre-shoot A/V script beat by beat from spine.md and quarry.md, enforcing Dual-Channel Grounding, Visual-First Subtraction, Voice-Off Completers, Physical Bridges, and Mouth-Shape Syntax."
disable-model-invocation: true
---

# AV Beats (Pre-Shoot Script Exploit)

This is **exploit**: the exploration is done, `quarry.md` and `spine.md` are fixed. Treat both input files as read-only and mine them to build the A/V script in `script.md`.

Uses the vocabulary and rules in [`av-craft`](../av-craft/SKILL.md): **Dual-Channel Grounding**, **Visual-First Subtraction**, **Voice-Off Completer**, **Physical Bridge**, **Mouth-Shape Syntax**, **Soundbite Target**.

If the user did not specify where to save the script, default to `script.md` in the current project folder and remember the path.

## Table of Contents

- [Process](#process)
  - [1. Read the Spine & Quarry, Establish Prerequisites](#1-read-the-spine-quarry-establish-prerequisites)
  - [2. Draft Beat by Beat (Or Full Pass on Request)](#2-draft-beat-by-beat-or-full-pass-on-request)
  - [3. Clean Table Contract](#3-clean-table-contract)

---

## Process

### 1. Read the Spine & Quarry, Establish Prerequisites
1. Read `spine.md` and `quarry.md` in full.
2. Confirm with the user the **Walk-In Prerequisites**: the concepts, assumptions, or feelings the viewer brings at second zero. Everything else must be grounded by an earlier beat before a later beat can lean on it.
3. If the project films real subject-matter experts (SMEs) or community members, write the **Director's Field Interview Guide** at the top of `script.md` first:
   - Write 3–5 open-ended prompts for the SME designed to elicit concrete stories (*"Walk me through a moment you watched..."*), never institutional definitions.
   - Write 2 quick, eye-level lived-experience prompts for candid community/parent grabs.

### 2. Draft Beat by Beat (Or Full Pass on Request)
By default, build the script table one beat at a time (or run the full beat sequence if the user says *"write the full script"*).

Before writing each beat to `script.md`, re-read `script.md` from disk so any manual edits the user made to earlier beats are preserved and inform what comes next.

For every beat row, execute these **five steps in exact order** to counterbalance default AI print-prose habits:

1. **Log Dual-Channel Grounding (`SECTION / BEAT` Column)**:
   Write the beat title, followed by:
   - `Requires:` What spatial geography, person, or feeling was already grounded in an earlier beat.
   - `Grounds:` What new visual geography or emotional fact this beat plants for the next beat.
   - `Shift:` `[Entry State] -> [Exit State]`. (If nothing changes polarity, cut or merge the beat).

2. **Draft `VIDEO` + `NAT SOUND` First (`Visual-First Subtraction`)**:
   Write the `VIDEO` column before drafting a single spoken word:
   - Specify **Camera Height & Axis** (for example, `28" toddler eye-level`, `seated bench axis`, `90-degree tabletop`), **Focal Proximity** (`35mm close presence` vs. `85mm candid compression`), and **5-Shot Sequence coverage** *(Tight on hands, Tight on eyes, Wide context, Over-the-shoulder POV, Creative foreground)*.
   - Ask: *"What does the viewer already see and understand from watching this shot silently?"*
   - Subtract that literal description from what the voice is allowed to say.

3. **Insert a `Voice-Off Completer`**:
   In every beat, choreograph a 1.5–3 second `[NAT SOUND POCKET]` where the speaker sets up an expectation and **stops talking** while a physical action and spot sound finish the thought on screen.

4. **Lock the `Physical Bridge`**:
   End the beat's `VIDEO` column on a concrete physical action, gesture, or eye-line inside the frame (such as a child spinning around to look at a perimeter bench) that motivates the cut into the next beat.

5. **Run the `Mouth-Shape Syntax` Pass on `AUDIO`**:
   Before placing any spoken line into the `AUDIO` column, apply all four spoken-ear transformations:
   - **Right-Branching Only**: Cut dependent openers (*"Long before a child reads a word..."*, *"When we opened in 2016..."*). Start directly with the person, the action, or a screen pointer.
   - **Singular Screen Pointers**: Replace generic plurals (*"toddlers," "parents," "users"*) with singular demonstratives pointing at the frame (*"Look at her hands here. She's two."*).
   - **No Literary Triads**: Break three-item parallel lists into a single concrete observation.
   - **Jagged Breath Cadence**: Follow a 10–14 word sentence with a 2–4 word fragment (*"It doesn't fit. She tries again. Click."*).
   - Separate scripted `[V.O.]` / `[ON-CAMERA]` lines from `[SOUNDBITE TARGET — SPEAKER]` beats.

### 3. Clean Table Contract
Format the table in `script.md` with three columns:

`| SECTION / BEAT | AUDIO (VOICE / NAT SOUND / SFX) | VIDEO (FRAMING / ACTION / COVERAGE) |`

Never include timestamps (`00:00 - 00:20`) or WPM calculation numbers in the table.

When all beats are complete, offer to run `/av-review` (two-axis parallel audit) or export print-ready Landscape HTML via `python scripts/export_av_script.py`.