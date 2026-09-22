---
name: kageyoni-architecture
description: Permanent architecture invariants and structural laws for Kageyoni v11.
---

# Kageyoni Architecture Invariants

These invariants are permanent and non-negotiable. No agent, workflow, or optimization may violate them.

## 1. Core Architectural Distinctions
- **There is ONE shared Kageyoni engine.** Do not create separate Research, Campaign, Production, character, or agent engines.
- **Workspace ≠ Situation Template.**
  - `Workspace`: Defines the domain and runtime boundary (filesystem, isolated state, external execution).
  - `Situation Template`: Defines structural prerequisites, schema, unknowns, and constraints required for a recurring class of situation.
- **Situation Template ≠ Situation.**
  - `Situation Template`: Class-level definition containing no specific work.
  - `Situation`: Instantiated working world with objective, state, participants, constraints, and provenance.
- **Situation ≠ Workflow.**
  - `Situation`: Working world state and context.
  - `Workflow`: Temporal, directed process graph with stages, gates, dependencies, and recovery rules.
- **Workflow ≠ Frame.**
  - `Workflow`: Process execution and state progression.
  - `Frame`: Composition and view layer over situation state.
- **Frame ≠ Method.**
  - `Frame`: Structural perspective/view.
  - `Method`: Learned or adaptable participant technique.
- **Method ≠ Domain Projection.**
  - `Method`: Executable technique.
  - `Domain Projection`: Reorganization of attention, constraints, and possibilities derived from participant history and authorized Will.

## 2. Epistemic and Participant Laws
- **Characters and agents do NOT receive private engines.**
- **Unknowns remain unknown.** Do not invent missing information to satisfy schema completeness. Contradictions must be preserved.
- **Local Situation extensions do not automatically become global schema.** Promotion requires repeated, consequential, evidenced utility.
- **Completion alone does not prove a workflow is good.** Evolution requires observed friction, candidate revisions, and qualified comparison.
- **Cross-domain transfer requires destination-appropriate evidence.** Competence in one domain (e.g. story) cannot grant external competence in another (e.g. repository repair).
- **The existing event/state store remains authoritative.** No parallel or unverified state store is permitted.
- **Preserve core qualities:** Play, surprise, attachment, character agency, and unresolved mystery.
