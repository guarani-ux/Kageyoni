# Kageyoni clean-base build plan

Status: ready for implementation planning; no runtime changes executed by this document.
Repository: guarani-ux/Kageyoni.
Source baseline: c7a6f8dc595b3acada63a9cb4693dbf2b55c7784.
Branch: codex/consolidate-existing-capabilities.
Design rationale: [Clean-base consolidation plan](CLEAN_BASE_CONSOLIDATION_PLAN.md).

## Build objective

Consolidate the existing system into a clean operational base: fewer competing implementations, coherent state ownership, connected public operations, reliable persistence, and inspectable consequences.

Preserve existing narrative, research, production, character, and developmental capabilities. Do not add a replacement framework, new model integration, new game mechanics, or a universal ledger migration. Repair existing advertised behavior and reconnect existing machinery. Explicitly record any repair that changes public behavior.

The implementing agent owns integration and verification. Levi retains direction and review authority; he does not run the test suite, copy state between components, or supply routine technical decisions.

## Architecture to converge on

| Responsibility | Existing carrier to use | Consolidation action |
| --- | --- | --- |
| Authoritative world changes | Engine and domain services | Eliminate routes that substitute unrelated writes for an accepted proposal |
| Internal transaction lifetime | UnitOfWork | Remove premature commits from helpers participating in an outer operation |
| Service access | Application and console | Reuse service construction and dispatch rather than add another controller |
| Participant persistence | PersistentParticipant and character/node services | Delegate overlapping kernel behavior |
| Host turns | Shinobi Participant | Preserve request/reply validation and interruption semantics |
| Topology | CausalDAG | Replace competing adjacency and traversal implementations |
| Generic predicates | GateEngine | Reuse only with demonstrated semantic equivalence |
| Durable situations | KageyoniSituationAdapter and SQLiteSituationStore | Route durable construction through the existing adapter |
| Reviewed methods | Learning and Methods | Keep candidates and observations distinct from approved development |
| Consequence history | Actual engine/domain receipts | Supplementary ledgers reference authoritative outcomes |

This specifies logical ownership, not one database, one class, or one representation for every concern.

## Work packages and order

| Package | Depends on | Proposed commit boundary | Exit result |
| --- | --- | --- | --- |
| B0 | None | Baseline and consumer inventory | Reproducible source/test baseline and explicit ownership decisions |
| B1 | B0 | Graph atomicity repair | Failed updates preserve existing state |
| B2 | B1 | Domain graph consolidation | Coherent views and one topology mutation owner |
| B3 | B0 | Participant proposal consolidation | Existing replies bind correctly to existing handlers |
| B4 | B3 | Transaction and dispatch continuity | Effects, required receipts, and retries agree |
| B5 | B4 | Durable context and situation wiring | Fresh-process continuation through existing services |
| B6 | B2, B4, B5 | Operational surface consolidation | Menus and direct calls share behavior |
| B7 | B6 | Proven redundancy retirement | Replaced implementations removed without capability loss |
| B8 | B7 | Clean-base acceptance report | Verified release candidate, limitations, and recovery instructions |

Keep main unchanged during execution. Each package may need several small commits. Do not combine code removal, schema migration, and unrelated behavior changes into an unreviewable commit.

### B0 — Establish the executable baseline

1. Obtain a complete pinned checkout, including package data, fixtures, governance checks, and entry scripts. The current downloaded source subset is not a complete checkout.
2. Read applicable repository instructions. Record runtime versions and install test-only dependencies in an isolated environment; preserve the zero-runtime-dependency policy.
3. Collect tests recursively across tests, tests/v10, and other actual test roots found in the checkout. Record collection failures, duplicate collection, deselection, and standalone probes separately.
4. Run engine verification on disposable initialized databases. Take uniquely named, verified backups before exercising migration against copied state.
5. Run existing baseline suites and preserve failures without editing expectations to conceal them.
6. Trace producers, consumers, registries, CLI entry points, serializers, and external compatibility for every proposed removal.
7. Capture existing narrative, participant, research invalidation, and production approval scenarios.

Artifacts: baseline manifest, ownership/consumer table, scenario results, and known-defect list. Store them with the branch's implementation evidence, excluding secrets and canonical character data.

Gate: every selected consolidation has a replacement owner, affected callers, and preserved semantics.

### B1 — Repair the shared graph

Files: kageyoni/graph.py; tests/test_causal_dag.py.

- Stage or prevalidate add_node updates before mutating metadata or topology.
- Preserve existing edges during rejected updates; distinguish already-present edges from newly introduced ones.
- Define additive versus replacement dependency operations explicitly.
- Recompute payload-scoped hashes when payload changes; preserve an explicit domain hash only according to its documented meaning.
- Validate graph restoration for cycles, dangling references, and incompatible serialized fields.
- Preserve prior invalidation and timestamp state on rejected changes.

Checks: existing node update containing an existing edge followed by a cycle-causing edge; self-loop; missing dependency; successful update; payload/hash consistency; dictionary and SQLite round trips; malformed restoration.

Gate: exact prior state survives every tested rejection, while valid nearby changes still succeed.

### B2 — Finish domain graph consolidation

Files: kageyoni/vantage/graph.py; kageyoni/research_compiler/claims.py; kageyoni/research_compiler/invalidation_engine.py.
Tests: graph_consolidation, vantage, research_compiler, g5_invalidation_cascade.

- Replace ClaimEdgeList's split backing state with coherent sequence behavior.
- Make indexing, iteration, length, membership, slicing, equality, and serialization agree.
- Route supported mutations through checked DAG operations. Reject unsupported bound mutations explicitly.
- Prevent Vantage views from exposing uncontrolled mutable adjacency.
- Remove duplicated traversal where the shared algorithm preserves required ordering and cycle behavior.
- Keep claim sources, uncertainty, epistemic status, and production approvals in their domains.
- Give mirrored metadata one owner or an explicit projection update path; remove independent writable status copies.
- Retain domain-level invalidation effects on projects, packages, and sections.

Checks: the four previously reproduced defects; multi-parent invalidation; unrelated branches; approval revocation; saved stale-state recovery; legitimate callers using old APIs.

Important test correction: the existing G5 test injects a cycle through list.append. Once that bypass is closed, test cycle rejection at the public mutation boundary and separately test malformed persisted input where appropriate. Do not preserve a shadow graph just to retain a bypassing test.

Gate: no hidden adjacency buffer, no inconsistent sequence view, and no rejected update that damages existing topology.

### B3 — Reconnect participant proposals

Files: kageyoni/participant_kernel.py; kageyoni/celestial.py; kageyoni/emergence/action_dispatcher.py; shinobi_agent/cli.py; relevant hydration/encounter adapters.
Tests: persistent_participant_lifecycle, celestial_kernel, action_dispatcher, character_hydration, participant_coupling.

- Map the live participant path before selecting deletions.
- Use existing persistent character/node services for identity and continuity.
- Make CelestialKernel delegate overlapping behavior or retire it after migrating its real consumers.
- Preserve unique host-turn, expression, and recovery behavior.
- Resolve action.payload versus action.fields at one validated compatibility boundary.
- Bind branch, encounter, actor, issued request, permitted action, reply, and observed revision.
- Stop hard-coding main during observation.
- Do not accept a supplied actor/digest as sufficient authentication or authorization.
- Do not update a stale expected revision to the latest revision merely to permit execution.
- Keep actual host input distinguishable from fixture-generated decisions.

Checks: accepted response reaches the existing handler; action:none causes no unrelated write; wrong actor/action; malformed reply; stale observation; non-main branch; conflicting payload; missing host input.

Gate: no separate operator script is needed to translate an accepted proposal into its advertised effect.

### B4 — Consolidate transaction and retry behavior

Files: persistence/unit_of_work.py; emergence/action_dispatcher.py; ledger.py; engine.py and workspaces/world.py only where nesting requires a targeted repair.
Tests: action_dispatcher, evidence_ledger, engine, v4_world, existing transaction/adversarial suites.

- Audit helper commits before composing transactions.
- Let the outer operation own same-database commits through UnitOfWork.
- Bind required dispatch/provenance persistence to the actual internal effect where the transaction permits.
- Define operation identity and uniqueness using branch and bound input, not merely encounter/actor/action names.
- Return prior outcomes for exact retries; reject conflicting reuse.
- Preserve repeated legitimate turns with the same action.
- Reference authoritative receipts rather than produce independently authoritative copies.
- Keep rejection diagnostics distinct from prohibited world changes.
- Preserve explicit recovery semantics for external effects and interruptions.

If schema changes are necessary, add an ordered migration through existing migration machinery. Never rewrite applied migration checksums. Audit existing duplicate records before enforcing uniqueness; do not silently discard them.

Checks: failure injection before effect, after effect, and during receipt recording; exact/conflicting retry; repeated action; branch isolation; process restart; supported concurrency; uncertain external write.

Gate: the required internal trace cannot silently disappear after a committed effect, and retry does not execute conflicting work.

### B5 — Reuse durable context and situation machinery

Files: application.py; situations/integration.py; situations/service.py; situations/storage.py; participant_kernel.py; intelligence/learning.py and methods.py only where shared retrieval/delegation is needed.
Tests: situation_storage, situation_connected_lifecycle, situation_integration_adapter, persistent_participant_lifecycle, learning_integration, methods.

- Reuse KageyoniSituationAdapter.service(), which already supplies SQLiteSituationStore.
- Make durable versus transient construction explicit.
- Remove independently writable store/cache copies or define their invalidation and reload behavior.
- Restore pending situations, workflows, participant bindings, and relevant context through existing services.
- Reuse current Learning and Methods rather than create a second learning system.
- Preserve observation, retained history, proposal, reviewed lesson, qualified method, and transfer outcome distinctions.
- Treat migrate.py's generic ledger export as an export until it preserves the semantics required for a real application migration.
- Correct unsupported deterministic-export claims; unknown timestamps remain unknown.

Checks: terminate and restart a separate process; recover pending work and the same identity/branch; retrieve relevant evidence; preserve stale/revoked state; keep an unreviewed candidate unqualified; inspect duplicate-export behavior.

Gate: continuation works without manual state copying, while no restart fabricates qualification.

### B6 — Align operation discovery and public access

Files: application.py; console.py; __main__.py; scout.py; gate.py; composition/gates.py; gateway.py; domain CLI adapters.
Tests: terminal, carrier_scout, gate_engine, production_gates, v10 CLI/gate suites, v11 production/pipeline mediation suites.

- Consolidate overlapping handlers behind existing service boundaries.
- Preserve domain-specific presentation as adapters.
- Compare advertised menu options with direct execution.
- Reuse signature inspection and registries without mistaking file/import presence for availability.
- Reuse predicates only where type, missing-value, and failure semantics match.
- Keep authorization and protected-operation enforcement outside generic predicate evaluation.
- Inspect all direct and indirect routes affected by consolidation.
- Distinguish mechanical admission checks from independent empirical qualification. Authored expected outcomes cannot qualify substantive competence.

Checks: missing module/prerequisite; unsupported operation; restricted perspective; direct-call bypass; typed equality; stale assessment; counterfeit authorization; menu/direct-call agreement.

Gate: one relevant behavior is enforced across entry paths, with no broader permissions introduced by composition.

### B7 — Retire verified redundancy

Files: determined by the B0 consumer inventory and completed migrations.

- Remove superseded implementations after callers use their replacements.
- Retain necessary compatibility adapters without copied business logic.
- Delete dead wrappers, duplicate traversal, shadow state, and obsolete command routing only with supporting consumer evidence.
- Keep historical migrations, domain models, retained evidence, and independent verification.
- Reconcile current entry documentation, imports, packaging, launchers, and code descriptions.

Removal record for each item:
old implementation; unique behavior; replacement; redirected callers; compatibility decision; verification; recovery.

Gate: every deletion has a verified replacement or a demonstrated absence of needed behavior. Similar names and lower line counts are insufficient.

### B8 — Verify the clean base

Execute paired baseline/refactored scenarios:

| Scenario | Required comparison |
| --- | --- |
| Narrative encounter | Same legitimate consequences, visibility, and meaningful options |
| Participant turn | Request/reply drives the authorized effect; dialogue-only remains distinct |
| Research retraction | Dependent claims/projects become stale; unrelated work remains valid |
| Production approval | Approval is revoked when its basis fails; refusal and valid neighboring cases work |
| Interrupted operation | Recovery reports committed, refused, pending, or uncertain accurately |
| Fresh-process continuation | Existing durable state resumes without operator reconstruction |

Then run affected regressions, complete collected suites, migration checks, and clean package installation with the required data. Record discovered, selected, passed, failed, skipped, and unavailable checks separately. Do not report a historical test count as current collection.

Final artifacts:
- ownership and public interface map;
- actual implementation/consumer removal report;
- baseline comparison and failure-injection results;
- migration/recovery instructions where applicable;
- remaining deficits and compatibility limits;
- reviewable branch/PR with main unchanged.

## Acceptance and stop conditions

Accept the clean base when existing supported capability is preserved, reproduced defects are fixed, competing mutation owners are removed in scope, public paths agree, durable continuation is demonstrated, and removed handoffs no longer require Levi to integrate them.

Measure actual implementations removed, callers redirected, duplicate writable state eliminated, manual handoffs eliminated, behavior preserved, and recovery failures resolved. Line-count reduction is secondary.

Stop a deletion when it erases a meaningful distinction or an unidentified consumer remains. Stop an operation when authority is absent. Resolve implementation uncertainty through inspection or testing where possible; do not stop routine work to ask Levi to become the integrator.

Do not expand this phase into new mechanics or autonomy infrastructure. Record genuinely absent capabilities as later candidates.

## Immediate first execution

Start B0, then B1 and B2. They repair the graph failures already observed and establish a reliable shared mechanism for the subsequent wiring work. Follow with B3/B4 before claiming end-to-end participant execution. The clean base is complete only after B8, not after the first passing graph suite.
