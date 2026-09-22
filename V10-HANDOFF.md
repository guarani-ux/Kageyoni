# Kageyoni v10.0.0 handoff

## Implemented vertical slices

### 1. Existing JRPG world → v10 composition → existing causal engine
- Migration 018 installs the composition substrate without rewriting campaign history.
- Existing v9.5 world records are projected into Frame/Slot/Aspect packets.
- `narrative_scene.v1` fails closed when causal state is missing.
- Resolution Governor binds the compiled proposal to exact record versions/source events, previews through existing `Engine.apply`, requires explicit authorization, rebinds before commit, and verifies after commit.

### 2. Non-JRPG content development through the same compiler
- `content_development.v1` uses the same Slot/Aspect compiler with no narrative participant-count special case.
- Evidence-bounded audience, intent, channel, idea, offering, perspective, action-space and consequence-contract slots compile through the same machinery.
- Qualitative effects produce inspectable pressures rather than demographic/content prescriptions.

### 3. External knowledge → evidence → routed encounter state
- Living Knowledge Ledger stores source/claims/hash/status separately from world truth.
- Routes move explicitly through ROUTED → ENCOUNTERED → INTERPRETED → TESTED/INTEGRATED/etc.
- A ledger entry can become an `evidence` Aspect, but ingestion never becomes a belief or canonical fact automatically.

### 4. Existing pipeline execution → recoverable/current verification
- The v9.5 interrupted-write dead-end is repaired with an explicit recoverable state.
- Owner-restored exact bytes can reconcile the same attempt without another write.
- Completed external output is re-audited in present tense; divergence returns `reconcile_required` rather than inheriting historical completion indefinitely.

## Implemented horizontal hardening

- 108 initial slottable Aspect types with causal-family/purpose/reaction metadata.
- Machine-readable ontology graph: families, types, Frames, Slots, `can_fill`, dependencies, `reacts_with`.
- Versioned authored Aspect registry.
- Fail-closed cardinality, type, slot-compatibility, authority, provenance, dependency, and verification-gate admission.
- `UNKNOWN`, `UNPLACED`, `INVALID`, `CONFLICTED`, `STALE`, `NOT_APPLICABLE` retained distinctly.
- Typed deficits propose bounded resolution routes but never auto-certify evidence.
- Effect Resolver preserves opposing pressures as conflict.
- Expression Contract separates engine truth/constraints from host performance.
- Metamorphic compiler tests cover order independence, JSON roundtrip, and optional-pressure enrichment.
- Additive interface changes are excluded from pending-world-decision fingerprints so tooling installation does not alter world meaning.

## Qualified ancestral hardening actually integrated

- **Nelson dependency binding:** proposals are bound to exact causal source records/versions instead of caller-supplied state claims.
- **Outer Sanctum fail-closed gate registry:** declared Frame verification is executable; unknown/broken gates block admission.
- **10 Shadows deficit pattern:** missing knowledge/state/capability becomes explicit deficit/resolution routes, but its unsafe `verified_evidence` label promotion was not inherited.
- **Espada metamorphic discipline:** transformations expected to preserve meaning are tested; non-applicability is not treated as evidence.
- **v9.5 challenge evidence:** the two documented pipeline defects became regression tests and repairs.

These were inherited only where they hardened an already-existing Kageyoni workflow.

## Preproduction status

- Canonical v9.5 campaign file is not mutated by development.
- Migrated copy preserves main revision 167, 394 records, and 167 events.
- 413 legacy tests have been executed successfully in isolated modules/groups after the latest changes.
- 23 v10 tests pass.
- Frozen v9.5 challenge: 9/9 cases pass against the candidate.
- Portable export/import preserves revision 167, 394 records, 167 events, both Frames, and all 106 registered types.
- Migration/release-integration tests pass after migration 018 expansion.

The monolithic wrapper can exceed this hosted execution window because some legacy tests leave resource warnings/open-connection cleanup work. Tests were therefore also executed as isolated processes; wrapper timeout is not counted as a product PASS or FAIL.

## Deliberately not claimed

- No Rust trusted kernel yet. Python remains the v10 reference/runtime while semantics stabilize.
- No HTTP server, MCP server, TypeScript workbench, or WASM build yet. The self-description/JSON command surface is intended to support those adapters later.
- No claim that synthetic audience/persona simulation predicts real people.
- No automatic semantic learning: experience, lesson qualification, downstream manifestation, and transfer remain distinct.
- No automatic promotion from evidence into world truth or a character's belief.
- Not every Foundry failure class is mechanically solved. Identity-lineage counterfeit detection, semantic duplicate causal effects, large-population resolution scaling, and experiential-adequacy evaluation remain explicit v10 follow-on work.

## Promotion rule

Promote rc1 to final v10 only after the packaged artifact itself passes isolated install/reopen, preflight, portable-state verification, frozen challenge evidence, and the remaining release evidence is consolidated without weakening the open Foundry boundaries above.
