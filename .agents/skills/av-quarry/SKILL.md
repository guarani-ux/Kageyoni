---
name: av-quarry
description: "AV writing, explore: grill the brief, research real audience friction, mine visual and acoustic fragments into quarry.md, and coin the Leading Word. No script table yet."
disable-model-invocation: true
---

# AV Quarry (Explore)

This is pure **explore**: widen the space of what could be filmed and spoken without committing to a script table or beat structure. Committing to a spine is `/av-spine`'s job; writing the table is `/av-beats`'s job.

If the user did not specify where to save the quarry file, ask once (defaulting to `quarry.md` in the current project folder) and remember the path for the session.

## Table of Contents

- [Process](#process)
  - [1. Capture Initial Fragments Immediately](#1-capture-initial-fragments-immediately)
  - [2. Delegate Fact & Audience Research](#2-delegate-fact-audience-research)
  - [3. Grill Along the Decision Frontier](#3-grill-along-the-decision-frontier)
  - [4. Mine Audiovisual Fragments & Coin the Leading Word](#4-mine-audiovisual-fragments-coin-the-leading-word)
- [Completion Criterion](#completion-criterion)

---

## Process

### 1. Capture Initial Fragments Immediately
From the user's very first message, extract every concrete fact, stakeholder requirement, runtime target, cast/talent note, and visual idea into `quarry.md`.

On first write, put a single `# <Working Title> - Quarry` heading at the top. Separate fragments with `\n---\n`. Before every subsequent write, re-read `quarry.md` from disk so any manual edits the user made are preserved.

### 2. Delegate Fact & Audience Research
Finding **facts** and **authentic audience language** is your job, never the user's.
When a topic or institution is named:
- Dispatch a background research sub-agent (or run targeted searches) to uncover:
  1. **Lived Audience Language & Friction**: How real people (parents, community members, viewers) talk about this problem in forums, comments, or everyday life (for example, *"lifeline"*, *"get out of the house"*, *"cabin fever"*), and what misconceptions they hold.
  2. **Concrete Visual & Physical Facts**: Specific locations, physical structures, dates, and tangible objects that can be filmed in close-up.
- Append verified findings as fragments into `quarry.md`.

### 3. Grill Along the Decision Frontier
Map the remaining creative and production unknowns as a **decision tree** and work it in **rounds**. The **frontier** is every question you can ask right now without guessing at answers you have not heard yet:
- Who is the primary viewer (New stranger, Casual community member, or Core insider), and what friction are they feeling before they click?
- What is the production custody mode: fully scripted presenter/VO, pre-shoot SME interview + VO hybrid, or observational?
- Can we capture candid 10-second community voices on location?
- Which stakeholder points are true non-negotiables, and which can be relegated to the end-card?

Format each frontier round with a recommended answer so the user can simply reply "yes" or override:

```markdown
❓ **Q1** - **<Decision Title>**: <Question body>

➡️ **Recommended**: <Your recommended choice and why>
```

### 4. Mine Audiovisual Fragments & Coin the Leading Word
As the user answers, translate abstract ideas into five specific kinds of fragments in `quarry.md`:
1. **Visual Handles**: Concrete physical actions or objects a camera can capture in a 5-Shot Sequence (for example, *small fingers twisting a stubborn wooden gear*; *snow boots kicked off at the cubbies*).
2. **Acoustic Handles**: Signature room tones and spot sounds that prove the space is real before a word is spoken.
3. **Human Anecdotes**: Specific moments of struggle, relief, or transformation a speaker can tell or the camera can witness.
4. **Audience Objections / Myths**: The surface assumption a stranger holds (*"It's just a noisy play area"*).
5. **The Leading Word**: Push to coin a single compact phrase or physical image that names the emotional center of the whole piece (for example, *"the look back"*, *"first living room"*). The **Leading Word** is the highest-leverage fragment in the quarry: once landed, it shapes the spine, the transitions, and the ending.

## Completion Criterion

The session is complete when:
1. Every branch of the decision frontier is settled.
2. `quarry.md` holds at least 2 concrete **Visual Handles**, 2 **Acoustic Handles**, the **Stakeholder Non-Negotiables**, and a candidate **Leading Word**.

When done, tell the user `quarry.md` is ready for `/av-spine`. Do not write a script table here.