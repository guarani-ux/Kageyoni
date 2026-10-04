# Kageyoni clean-base consolidation plan

Status: proposed implementation plan; documentation only.
Source baseline: `c7a6f8dc595b3acada63a9cb4693dbf2b55c7784`.
Working branch: `codex/consolidate-existing-capabilities`.

## Objective and scope

Make the capabilities already in Kageyoni easier to operate together, with fewer competing owners, fewer manual handoffs, consistent continuation, and less implementation duplication. Preserve narrative play, character differences, research semantics, production workflows, history, and meaningful authority boundaries.

This is a repository-wide consolidation, delivered in reviewable changes. It is not a replacement engine, a new autonomy framework, or a guarantee of model competence. New behavior is out of scope unless necessary to repair an existing advertised operation; identify such repairs explicitly. A missing capability remains missing rather than being concealed by an authored substitute.

The operator should supply a purpose and legitimate decisions. The runtime should handle its existing context preparation, routing, persistence, receipts, and resumption without requiring the operator to reconstruct those connections.

## Grounded starting point

Inspection of the pinned source identifies the following priorities:

- Application and console already provide a shared service surface. Preserve and extend their wiring where existing services are disconnected rather than introducing a second general controller.
- Engine, UnitOfWork, versioned migrations, encounters, protected-operation services, participant methods, learning, and SQLite situation storage already exist.
- CausalDAG is used by Vantage and ClaimGraph, but their compatibility views and update paths still produce inconsistencies.
- Four independent probes reproduced loss of an existing edge after a rejected update, domain VALID versus DAG STALE after an update, list iteration versus indexing disagreement, and a manually appended edge appearing in the claim view without appearing in the DAG.
- CelestialKernel contains another local graph and ledger. Within the downloaded kageyoni package, no other runtime module imports this class. Its advertised consolidation does not establish that it owns the active participant path.
- CelestialKernel proposals emit action.payload while EncounterActionDispatcher reads action.fields.
- Dispatcher persistence and EvidenceLedger perform separate commits after encounter execution. Request identity, branch binding, and conflicting retry behavior need repair.
- SituationService defaults to MemorySituationStore even though SQLiteSituationStore exists. Its dictionaries and persistent store need explicit ownership and reload semantics.
- EvidenceLedger coexists with the engine and domain histories. Its name is not proof that it replaced them.
- DatabaseMigrator exports rows into a ledger; that is not a complete migration of application semantics. Missing timestamps currently fall back to wall-clock time, undermining its claimed deterministic ordering.

These are source observations and bounded probes, not a complete qualification of every repository area. During planning, ten research/compiler unittest cases completed successfully; the combined run failed to import the pytest-dependent Vantage suite because pytest is unavailable in this environment. No full-suite pass is claimed.

## Target ownership

Logical responsibilities need not become additional packages.

| Concern | Proposed owner | Preserve as distinct |
| --- | --- | --- |
| World facts, branch revisions, event receipts | Engine and its existing domain services | Observation, belief, dialogue, proposal |
| Composition of internal writes | UnitOfWork | External-effect recovery |
| Service construction and operational access | Application and console | Domain-specific menus as thin adapters |
| Persistent participant identity and continuation | Existing character/node services through PersistentParticipant | Shinobi host request, response, and interruption state |
| Dependency topology and traversal | CausalDAG | Claim provenance, epistemic status, production approvals |
| Generic predicate evaluation | GateEngine where semantics match | Authorization, typed world constraints, qualifications |
| Durable situations | SQLiteSituationStore in durable runtime paths | MemorySituationStore as explicit transient/test mode |
| Method history and reviewed development | Existing Learning and Methods | Raw experience, candidate methods, transfer evidence |
| Execution provenance | References to the actual operation and domain receipts | Cross-domain inspection projections |

Choose owners after consumer and semantics checks. This table is the preferred direction, not an instruction to erase every alternative representation. Multiple views are useful; independently mutable copies of the same fact are the problem.

## 1. Freeze behavior and map consumers

Create a baseline manifest of commit, entry commands, service interfaces, schema versions, discovered test cases, fixtures, supported Python versions, and relevant data formats. Obtain the required fixtures and package data before treating a local test run as representative.

For each candidate consolidation, record: current producers and consumers; authoritative state; duplicate implementations; meaningful differences; target owner; compatibility strategy; and the implementation to be removed. Include dynamic registries, CLI entry points, serializers, tests, and documented external APIs, not just static imports.

Capture a small existing scenario from each of narrative play, participant continuation, research invalidation, and production approval. Compare authoritative consequences and refusal behavior before and after refactoring. Preserve intentionally changing defect behavior separately from unchanged behavior.

Do not edit canonical campaign databases. Use disposable databases and verified copies. Record pre-existing failures separately from regressions.

Exit: every proposed removal has an identifiable replacement and affected consumers.

## 2. Repair and complete graph consolidation

Repair CausalDAG insertion/update atomicity first. A failed operation must preserve prior nodes, edges, payload, hashes, validity, and timestamps within the operation's stated boundary. Validate all proposed dependencies before modifying the live graph, or use a staging strategy with exact rollback.

Make Vantage and ClaimGraph delegate topology mutations to the owner. Define dependency-update semantics explicitly: additive insertion and replacement must not be confused. Existing valid edges must survive failed updates.

Replace the partially implemented list proxy with coherent sequence behavior. Indexing, iteration, membership, length, equality, slicing, and serialization must agree. Bound view mutations must either invoke checked graph operations or be explicitly rejected; they must never create a hidden second graph. Preserve caller compatibility only where it can uphold these guarantees.

Align domain and graph metadata ownership. Domain epistemic status and production approval are different concepts; do not flatten them into generic VALID. Avoid independently mutable mirrors, and update content hashes according to their actual scope.

Validate restored graphs for missing references and cycles. Preserve historical invalidity and revoked approval rather than silently reinstating them.

Move duplicate traversal in invalidation code to the shared graph only where its ordering and failure semantics match. Keep project/package invalidation and retraction auditing in their domain layer.

Verification: the four reproduced defects; failed updates containing both existing and cycle-causing edges; successful replacement; multi-parent cascades; unrelated branches; coherent views; stale-state restart; malformed restores; and existing production/research callers.

Exit: one topology owner, no hidden adjacency buffer, and no competing mutation path.

## 3. Consolidate participant and proposal wiring

Trace actual usage of PersistentParticipant, CelestialKernel, entity instances, hydration, Shinobi Participant, and the encounter scheduler. Assign identity, context preparation, host interaction, and execution to their proper existing owners.

Prefer PersistentParticipant as the persistent service facade. Retain Shinobi's host-turn and recovery responsibility. Turn overlapping convenience kernels into thin adapters when they have users; remove them only after consumers migrate and unique behavior is preserved.

Normalize the existing proposal format at one boundary. Resolve payload versus fields, bind branch and actor explicitly, and stop hard-coding main in participant observation.

Bind execution to the issued request, permitted actions, delivered observation revision, and validated reply. A client-supplied actor, digest, or host label cannot establish authority or invocation provenance. Do not replace stale expected revisions with the latest revision to make an action succeed.

Keep declared fixture scheduling visibly distinct from actual human/model decisions. Where no host can be invoked, report pending input or unavailable host rather than selecting a scripted answer.

Verification: a real supplied response reaches the handler; action:none causes no unrelated mutation; unauthorized actor/action and stale requests fail appropriately; proposal fields reach the handler unchanged; non-main branches work; context and history remain perspective scoped.

Exit: one supported request-to-effect route per operation, without an operator applying a separate patch to finish the character's action.

## 4. Consolidate transactions, retries, and execution history

Audit nested helpers for unconditional commit calls. Reuse UnitOfWork so the outer operation controls its internal transaction. Do not assume adding a transaction wrapper fixes helpers that commit inside it.

For same-database encounter execution, bind the effect and its dispatch/provenance record within the supported atomic boundary. Test the actual engine nesting behavior before claiming atomicity.

Use stable operation identity bound to branch, participant, encounter, request, and input digest. Exact retries recover the previous outcome; conflicting reuse is rejected. Repeated legitimate turns must not collide because they share actor and action names.

Choose an authoritative receipt for each consequence. Make supplementary ledgers reference that receipt or serve an explicit projection/index role. Do not copy all domain tables into a universal ledger and discard the types needed to operate them.

External file/tool effects retain intent, observation, and recovery records. Cancellation or transaction rollback cannot be advertised as undoing an external write.

Verification: injected failures before effect, after effect, and during receipt persistence; exact and conflicting retries; restart; repeated turns; concurrent calls where supported; uncertain external residue; and cross-branch isolation.

Exit: committed internal effects have their required trace, and continuation never depends on guessing whether a hidden commit happened.

## 5. Reconnect persistence, situations, and learning

Wire durable SituationService construction to SQLiteSituationStore. Make transient mode explicit. Eliminate duplicate writable caches, or define their invalidation and reload behavior. Recover templates, workflows, projections, pending runs, and relevant participant context through existing facilities.

Reuse existing Learning and Methods for durable reviewed development. Keep observations, scars, proposals, reviewed lessons, and qualified methods semantically distinct. Historical storage does not imply learning.

Unify repeated context-preparation logic only where it conveys equivalent information. Preserve exact evidence references, relevant corrections, uncertainties, and permission limits. No universal summary should replace the sources.

Treat DatabaseMigrator as an export until its actual scope is corrected. Any consolidation of stored data must preserve source IDs, schema/version meaning, chronology, references, repeatability, and provenance. Unknown time remains unknown. Backups, copy migration, count/reference checks, restart, and recovery precede any source retirement.

Verification: close the process and resume a pending operation; restore participant identity and branch; retrieve relevant history; retain invalidation; keep a candidate unqualified; repeat an export/migration without silent duplicate history.

Exit: durable operation resumes through the runtime rather than manual file copying or transcript reconstruction.

## 6. Consolidate discovery, gates, and entry points

Audit CarrierScout against existing discovery and capability menus. Use inspected signatures and existing service registries where useful, but separate importability, implementation, authorization, feasibility, and tested behavior. File presence is not an executable capability.

Reuse GateEngine for equivalent predicates. Preserve typed equality and domain-specific constraints; Python true==1 must not silently alter a typed rule. Generic gating cannot replace the protected-operation authority model.

Route overlapping CLIs through existing service boundaries. Preserve useful domain presentation and existing entry commands as adapters during transition. Align menu availability, structured dispatch, and direct invocation.

Remove duplicate command handling and launchers after replacement routes are verified. Keep domain rules near their owning service rather than moving every condition into one giant generic module.

Exit: displayed operations and actual invocation agree; discovery does not grant authority; old and new entry paths enforce the same relevant constraints.

## 7. Retire proven redundancy and reconcile documentation

For each removal, show the redirected consumers and preserved behavior. Eligible targets include obsolete parallel traversal, unused shadow state, duplicate serialization, superseded routing, dead wrappers, and fixture logic in production paths. Similar names or low line counts are insufficient grounds for deletion.

Preserve versioned migrations, historical evidence, required compatibility, distinct domain models, and genuinely independent checks.

Update entry documents and runtime descriptions to match the selected ownership. Replace unsupported words such as universal, autonomous, and qualified with the observed scope. Keep one current operational guide with linked domain contracts and migration history.

Remove unused code only after examining registries, entry points, reflective loading, documentation, and public compatibility. A module with no static imports may still be a supported external API.

Exit: the removed mechanism no longer has active consumers or an unpreserved role.

## Completion and measurement

Completion requires:

1. Existing supported scenarios still run through their actual public entry points.
2. Graph and proposal defects are repaired, with failure cases exercised.
3. Identity, branch, revision, authority, and consequence stay bound across handoffs.
4. Fresh-process recovery works for the existing durable operations in scope.
5. Tests cover the affected baseline suites, nested suites, packaging, and relevant integration scenarios; unavailable checks and pre-existing failures are reported.
6. Each retired implementation has a verified replacement; retained adapters contain no competing business logic.
7. Documentation identifies actual hosts, fixtures, authority boundaries, and unresolved capability limits.
8. The operator no longer performs the machine-owned handoffs removed by this work.

Measure competing owners, duplicate mutation paths, manual handoffs, public behavior regressions, restart recovery, and failure consistency. Report literal deleted implementations and redirected callers. Net line reduction is supporting evidence, not the objective.

Use paired baseline/refactored runs for existing scenarios and separately test intentionally repaired behavior. Do not accept one winning sequence or builder-authored success labels as system qualification.

## Delivery order and responsibility

Deliver graph repair, participant/proposal consolidation, transaction/history consolidation, persistence/context consolidation, entry-point cleanup, then final retirement and regression evidence. Adjust ordering when the consumer map exposes a prerequisite.

Each change includes purpose, before/after behavior, redirected callers, removals, checks, limits, and recovery. Preserve main until review; leave the completed work on the isolated branch. The implementing agent owns inspection, integration, tests, and evidence. The user is not the manual integrator or verification runner.

The result is a clean operational base for Kageyoni's existing capabilities. Its reach is then assessed against the user's intended tasks using observed configuration-level behavior; this cleanup alone does not confer an unsupported rank, emergence claim, or new cognitive capability.
