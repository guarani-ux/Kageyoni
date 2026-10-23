---
name: av-spine
description: "AV writing, design it 3 ways: spawn 3 parallel sub-agents to pitch radically different causal Story Spines and opening hooks from quarry.md, compare them, and lock spine.md."
disable-model-invocation: true
---

# AV Spine (Design It 3 Ways)

Your first idea for a video's structure is rarely the best one, and left to default instincts an agent will group talking points into thematic buckets. This skill uses the parallel sub-agent pattern ("Design It Twice") to generate three radically different causal **Story Spines** from `quarry.md`, compare them, and lock the strongest one into `spine.md` before beat writing begins.

Uses the vocabulary in [`av-craft`](../av-craft/SKILL.md): **Quarry**, **Leading Word**, **Story Spine**, **Dual-Channel Grounding**, **Physical Bridge**.

## Table of Contents

- [Process](#process)
  - [1. Read the Quarry & Frame the Problem Space](#1-read-the-quarry-frame-the-problem-space)
  - [2. Spawn 3 Parallel Sub-Agents](#2-spawn-3-parallel-sub-agents)
  - [3. Present, Compare & Recommend](#3-present-compare-recommend)
  - [4. Lock `spine.md`](#4-lock-spinemd)

---

## Process

### 1. Read the Quarry & Frame the Problem Space
Read `quarry.md` in full (or gather the raw brief if the user came straight here). Write a short user-facing summary of the constraints every spine must satisfy:
- **Walk-In State (Prerequisites)**: Who the viewer is and what assumption or friction they bring at second zero.
- **Stakeholder Pillars**: The required institutional facts that must become causal stops along the journey (never standalone topic buckets).
- **Available Handles**: The best visual and acoustic handles in `quarry.md`.

Show this summary and immediately spawn the 3 sub-agents in Step 2.

### 2. Spawn 3 Parallel Sub-Agents
Spawn 3 sub-agents in parallel. Pass each sub-agent the full contents of `quarry.md` and the shared vocabulary from `av-craft`, but enforce a different narrative design constraint on each:

- **Agent 1 (Revealed Design / Hidden Architecture)**:
  "Build a causal Story Spine that opens with what this space, object, or program looks like to a casual outsider, then pulls back the curtain to reveal how every physical detail was engineered for a deeper human purpose."
- **Agent 2 (Lived Friction -> Sanctuary / Relief)**:
  "Build a causal Story Spine anchored entirely in the viewer's most visceral lived problem (such as isolation, exhaustion, intimidation, or overwhelm). Track the emotional shift from walking in carrying that weight to the physical exhale inside."
- **Agent 3 (Micro-to-Macro / The Single Gesture)**:
  "Build a causal Story Spine that starts on one tiny, specific 10-second human interaction on the floor (hands, eyes, a single look between two people) and expands outward in a continuous `Because -> But -> Therefore` chain to explain the entire 10-year or city-wide system."

Each sub-agent must return under 300 words:
1. **The Leading Word**: The load-bearing phrase or image for this angle.
2. **The Opening 10 Seconds (Picture + Sound + First Spoken Line)**: How the video earns attention immediately.
3. **The Causal Spine (`Because -> But -> Therefore`)**: A 4-to-5 sentence paragraph where every stakeholder pillar is forced into existence by the previous beat (zero *"And also"* transitions).
4. **Beat Value-Shift Map**: 4–6 numbered beats showing `[Entry State] -> [Exit State]` and the **Physical Bridge** that connects each beat to the next.
5. **Trade-offs**: Where this spine hits hardest, and what it sacrifices.

### 3. Present, Compare & Recommend
Present all three spines clearly. Then compare them across three axes:
- **Emotional Gravity**: Which spine makes a stranger care fastest?
- **Causal Tightness**: Which spine eliminates brochure seams most cleanly?
- **Visual Shootability**: Which spine gives the camera the strongest physical actions to film?

Give an **opinionated recommendation**: name which spine (or specific hybrid of two spines, such as Agent 3's micro-interaction inside Agent 2's emotional arc) is strongest and why. Wait for the user to pick or adjust.

### 4. Lock `spine.md`
Once the user chooses or hybridizes a spine, write the locked **Leading Word**, **Causal Spine**, **Audience Prerequisites**, and **Beat Value-Shift Map** to `spine.md`.

Tell the user `spine.md` is locked and ready for `/av-beats`.