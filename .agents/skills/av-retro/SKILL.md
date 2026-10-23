---
name: av-retro
description: "Look back over an A/V scripting session or diff the user's manual script edits against the agent's draft, then propose permanent updates to av-craft, av-review smells, or templates so the user never has to repeat the correction."
disable-model-invocation: true
---

# AV Retro (Environment & Craft Loop Closure)

Run this skill after finishing an A/V script or after you have edited `script.md` by hand. Its job is to upgrade the **skill environment** (`av-craft`, `av-review` smells, `GLOSSARY.md`), not the script itself, so you never have to give the same writing correction twice.

## Table of Contents

- [Process](#process)

---

## Process

1. **Inspect the Session & Diffs**:
   - Review the conversation history for any moment where the user corrected a line, rejected a transition, pushed back on tone, or removed clutter.
   - If `script.md` was edited by the user on disk, compare the user's final lines against what the agent originally proposed.
2. **Classify Each Finding**:
   Rank findings from most severe to least severe across three buckets:
   - **New or Sharpened Script Smell (`av-review`)**: A recurring AI writing habit that needs an explicit smell entry in `skills/av-review/SKILL.md`.
   - **Anti-Inclination Checkpoint (`av-craft` / `av-beats`)**: A drafting order or syntactic rule that should be tightened in `skills/av-craft/SKILL.md` and `skills/av-beats/SKILL.md`.
   - **Exporter / Layout Rule (`scripts/export_av_script.py`)**: A formatting or typography adjustment that belongs in code.
3. **Propose & Apply**:
   Present the proposed updates clearly (quoting the exact before/after rule). Once approved, edit the skill files in place and sync linked copies.