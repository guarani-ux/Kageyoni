# Domain Mounts & Cross-Cartridge Bridging

`cognitive-os` keeps the core personal operating state lean by delegating specialized creative and professional workflows to modular **Domain Cartridges** mounted under `domains/`.

## Table of Contents

- [1. Mounted Cartridge Map](#1-mounted-cartridge-map)
- [2. Shared State & Provenance Rules](#2-shared-state--provenance-rules)
- [3. Cross-Domain Handoff Examples](#3-cross-domain-handoff-examples)

---

## 1. Mounted Cartridge Map

| Domain Tag | Cartridge Name | Mount Path | Primary Vault / Artifacts |
| :--- | :--- | :--- | :--- |
| `#core` | **Cognitive OS Core** | `skills/cos-*` | `vault/inbox.md`, `goals.md`, `tasks.md`, `decisions.md`, `approvals.md`, `dormant.md` |
| `#creative` | **`script-builder`** | `domains/creative/skills/av-*` | Project-level `quarry.md`, `spine.md`, `script.md`, `paper-edit.md` |
| `#professional` | **`cover-letter-builder`** | `domains/professional/skills/cl-*` | `vault/career-quarry.md`, `vault/voice-profile.md`, `applications/<org>-<role>/` |

---

## 2. Shared State & Provenance Rules

1. **Strict Privacy Isolation (`#personal` vs. `#professional` / `#creative`)**:
   Items tagged `#personal` in `vault/inbox.md`, `vault/tasks.md`, or `vault/journal/` are never read by `/cl-*` or `/av-*` skills unless the user explicitly commands a bridge.
2. **Unified Approval Gateway (`vault/approvals.md`)**:
   When a domain cartridge produces a final deliverable ready for external submission (for example, an exported cover letter in `/cl-draft` or a final production package in `/av-beats`), it can enqueue an approval item in `vault/approvals.md` so `/cos-briefing` and `/cos-approve` track its submission and follow-up.
3. **Unified Decision Ledger (`vault/decisions.md`)**:
   Strategic career or creative choices (such as selecting a job search positioning strategy or locking a documentary distribution plan) are logged in `vault/decisions.md` with a **Reconsideration Trigger**.

---

## 3. Cross-Domain Handoff Examples

- **Morning Job Radar $\rightarrow$ Professional Cartridge**:
  Your 8:00 AM scheduled Job Radar drops a high-match Calgary posting into `vault/inbox.md` $\rightarrow$ `/cos-capture` tags it `[COMMITMENT] #professional` $\rightarrow$ `/cl-decode` runs the 3-Layer JD X-Ray $\rightarrow$ `/cl-draft` produces `cover-letter.md` $\rightarrow$ `/cos-approve` queues the final application submission and schedules a 14-day reconsideration check in `vault/decisions.md`.
- **Creative Idea $\rightarrow$ Creative Cartridge**:
  You capture a voice note in `vault/inbox.md` (*"Idea for a 2-minute documentary on community radio mastering"*) $\rightarrow$ `/cos-capture` tags it `[IDEA] #creative` $\rightarrow$ When prioritized in `/cos-briefing`, it seeds `quarry.md` for `/av-quarry`.
