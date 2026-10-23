---
name: av-paper-edit
description: "AV writing, post-shoot exploit: assemble a documentary Paper Edit strictly from recorded .srt or .txt interview transcripts, preserving verbatim quotes and writing minimal VO bridges."
disable-model-invocation: true
---

# AV Paper Edit (Post-Shoot Transcript Quarry)

Use this skill when the shoot has already happened and the user passes recorded interview transcripts (`.srt`, `.vtt`, `.txt`, or markdown notes) to assemble a **Paper Edit**.

Treat every transcript file as a **read-only primary source**. You may never edit the raw transcript files or invent a quote that is not in them.

Uses the vocabulary in [`av-craft`](../av-craft/SKILL.md): **Paper Edit**, **Quarry**, **Dual-Channel Grounding**, **Visual-First Subtraction**, **Physical Bridge**, **Mouth-Shape Syntax**.

## Table of Contents

- [Process](#process)
  - [1. Read the Transcript Quarry & Map the Best Soundbites](#1-read-the-transcript-quarry-map-the-best-soundbites)
  - [2. Documentary Custody Rules for Verbatim Quotes](#2-documentary-custody-rules-for-verbatim-quotes)
  - [3. Build the Paper Edit Table](#3-build-the-paper-edit-table)

---

## Process

### 1. Read the Transcript Quarry & Map the Best Soundbites
1. Read all supplied transcript files end to end.
2. Extract the strongest candidate soundbites: moments where a speaker tells a concrete story, reveals emotion, or turns an expectation.
3. Group the candidate soundbites along a causal **Story Spine (`Because -> But -> Therefore`)**. If `spine.md` exists, check where the real recorded quotes confirm, sharpen, or change the planned spine. If a recorded moment is stronger than the pre-shoot plan, follow the real tape.
4. Present the proposed 4–6 beat soundbite sequence to the user before building the full table.

### 2. Documentary Custody Rules for Verbatim Quotes
When placing transcript quotes into the `AUDIO` column of `paper-edit.md`:
- **Verbatim Fidelity**: Copy the speaker's actual words from the transcript. Never rewrite an interviewee's quote into brochure prose or merge two unrelated claims to manufacture a statement they did not make.
- **Transparent Trimming**: When cutting mid-sentence false starts or bridging across two sentences from the same answer, mark the internal cut with `[...]` and include the transcript locator (`[TC 04:12]` or line reference) beside the speaker header so the video editor can find the exact clip on the timeline.
- **Minimal VO Bridges**: Only write a scripted `[V.O. BRIDGE]` when the interview soundbites cannot cross a transition on their own through a **Physical Bridge** or **J-Cut**. Every VO bridge must pass the **Mouth-Shape Syntax** check.

### 3. Build the Paper Edit Table
Write `paper-edit.md` beat by beat (re-reading the file from disk before every write to preserve user edits):
- **`SECTION / BEAT` Column**: Log `Requires`, `Grounds`, and `Shift: [State A] -> [State B]`.
- **`AUDIO` Column**: Verbatim interviewee quotes (with source locator for the editor), `[NAT SOUND POCKET]` breathing spaces, and minimal `[V.O. BRIDGE]` lines where needed.
- **`VIDEO` Column**: Specify where the interviewee is seen on camera (`[A-ROLL ON-CAMERA]`, typically at the emotional turn of their sentence) versus where their voice plays under **Visual-First Subtraction** B-roll sequences (`[B-ROLL OVER SOUNDBITE]`).

When complete, offer to run `/av-review` to verify quote custody against the source transcripts.