# Kageyoni v9.5 — Implementation Blueprint

Technical companion to **Kageyoni-v9.5-Blueprint.md**  
Design revision 2 · 20 September 2026  
Status: proposed implementation architecture, grounded in inspected v8 code. This document does not install v9.5, alter campaign canon, or declare untested behavior complete.

## 1. The shape of the thing

Build a **modular Python application with one durable local database, a versioned artifact store, interchangeable workspace adapters, and a terminal interface**. The engine carries a persistent network of developing nodes. Kageyoni’s world is its living-world workspace; documents, repositories, and pipelines are other workspaces with their own objects and consequences.

A node carries identity, experience, interpretation, methods, capability evidence, relationships, and development. An execution is a temporary attempt to contribute to a task. A workspace defines what work means and what can change. These are separate objects. Sciel can participate in a document task without becoming a different node or converting a document into an RPG encounter.

The destination remains the full vision: characters experiencing and learning differently, the engine learning about coordination, and those differences becoming useful in Levi’s daily work. The implementation sequence makes that destination testable in increments; it does not replace it with a generic agent framework.

**Planning count: one preflight stage, eight vertical slices, and six horizontal concerns.** These are proposed boundaries, not a claim that eight releases or a fixed number of weeks will suffice. Split a slice if its acceptance test cannot be demonstrated independently.

A vertical slice delivers a complete behavior through interface, application, records, execution, and verification. A horizontal concern is a shared rule that each relevant slice implements. Do not finish all persistence, then all intelligence, then all UI before demonstrating any behavior.

## 2. Evidence and design authority

Use the earlier v9.5 blueprint for meaning and scope, this document for implementation structure, and the collected discussion for unresolved ideas. The uploaded research report informed decomposition, provenance, evaluation, and transition design. It does not determine our destination, character ontology, language choice, or schedule.

### Inspected foundation

The available source is `inspection/kageyoni-local-dev`; the packaged terminal integration is `Kageyoni-Terminal`. They are planning baselines, not proof that either holds the latest campaign state.

| Observed item | Consequence for this plan |
|---|---|
| Python modules, SQLite, standard-library tests and terminal | Extend this foundation; no language rewrite is justified. |
| `engine.py` is approximately 2,658 lines | Add bounded modules rather than putting every new concern here. Refactor only where behavior requires it. |
| `characters.create`, contextual reads, Will contracts, personality evaluation, decisions and writing already exist | Reuse and adapt these entry points. Do not duplicate character creation or resolution. |
| Character reads filter visible context before joining references | Preserve this ordering in new retrieval paths. |
| Personality rules use authored matching and weights | Current preference changes are not learned competence or demonstrated intelligence. |
| Decision proposals fingerprint state and component versions | Migrations may invalidate a pending proposal; preserve its intent and explain revalidation. |
| Opening an Engine can upgrade its database | Inspect a copy first. Merely opening the original is not a guaranteed read-only operation. |
| Legacy schema version 2, runtime schema 4, workflow API 3; migration checks through 8 | Product version 9.5 must not be substituted for any of these independent version numbers. |
| Available seed has main revision 1, 165 records, one import event | A packaged seed cannot establish the latest scene or complete Sciel profile. |

**Executed verification this turn:** `python3 -m unittest discover -s tests -q` in the terminal package: **168 tests passed in 5.987 seconds**. This establishes the available baseline, not v9.5 acceptance.

**Executed integration probe:** a disposable fixture began an outer SQLite transaction, inserted a marker, called `Engine.apply()` to change a character, then rolled back the outer transaction. Both the marker and character change survived. Inspection explains why: `apply()` recognizes an existing transaction when starting, but commits or rolls back internally when finishing. This behavior prevents assuming composable transactions. The probe made no campaign changes.

Earlier adversarial work also found exact-string sensitivity in personality rules and a prose validation gap: hidden information inserted into delivered text could pass with empty claims and a positive host review. Those are concrete design constraints, not proof of comprehensive semantic isolation.

### Repository evidence added in revision 2

The companion **Kageyoni-Repository-Loop-Extraction.md** supplies pinned source references, an extraction inventory and reproducible probe receipts. The investigation examined twelve recursive repository trees and 215 selected files from eleven repositories; it did not audit every file or run their complete test suites. Fifteen offline assertions against selected actual modules produced six positive controls and nine adverse observations. These are boundary findings, not a repository-wide failure rate. Some identify a mismatch with Kageyoni’s proposed policy rather than a defect under the original project’s policy.

Revision 2 integrates these findings into the existing eight slices, adds method and reception contracts, and adds T40–T54. All new implementation and acceptance results remain pending. The earlier 168-test result belongs to the inspected terminal baseline; it does not verify these additions.

## 3. Language, executable pieces, and data

| Piece | Representation | Responsibility |
|---|---|---|
| Runtime and services | Python | Validate requests, retrieve permitted context, coordinate executions, apply changes. |
| Durable state | SQLite | Stable IDs, revisions, relationships, transactions, queryable histories. |
| Database evolution | Ordered SQL plus Python migration runner | Explicit predecessor checks, checksums, conversion reports and restart handling. |
| External requests, packets, configuration | JSON | Portable typed interchange, never executable instructions by itself. |
| Prompts and operating guidance | Versioned Markdown | Explain a task to a model; cannot authorize writes or confer abilities. |
| Documents and other outputs | Files plus database manifests | Store actual work with hashes, provenance, revision and publication status. |
| Terminal | Existing Python launcher and menu modules | Collect fields, show previews and outcomes, call services. |
| Maintenance commands | Small Python scripts | Back up, inspect, migrate copies, replay, validate and export. |
| Tests | Existing unittest plus scenario fixtures | Verify domain behavior and failure recovery independently of prose claims. |

Use the currently supported Python environment verified against v8; record its exact version in build receipts. Choosing a new minimum version or extra dependency requires a compatibility check during packaging. A richer terminal library is optional later. No JavaScript, Rust, vector database, message broker, or microservice is presently required.

Use the AI host’s authorized capabilities when available. Define a manual packet exchange path for environments without a callable host integration. Manual exchange must be labelled manual; a menu, template, or mock response is not evidence of an operating intelligence network. Do not introduce a paid model API dependency by default.

## 4. Repository and runtime file map

Paths below are relative to the proposed repository root. **Keep** means retain existing behavior; **extend** means modify under compatibility tests; **new** means proposed and not yet implemented. This is a target manifest, not a claim that these files already exist. Add `__init__.py` to new Python packages.

### Existing engine and public interfaces

| Path | Status | Owns / connects to |
|---|---|---|
| `kageyoni/engine.py` | Extend narrowly | World persistence, revisions, events, branches, replay. Transaction ownership adjustment first. |
| `kageyoni/model.py` | Keep / extend | Existing domain definitions and generated storage schema. Remains authoritative for legacy domains. |
| `kageyoni/characters.py` | Extend | World character identity, creation and visible profiles; links a character to a network node. |
| `kageyoni/will.py` | Extend | Will definitions, expressions and mechanics; explicit handling of interpretation versus reality. |
| `kageyoni/personality.py` | Extend | Existing preference evaluation; references stable method IDs without treating preferences as success probabilities. |
| `kageyoni/decisions.py` | Keep / extend | World action proposals, fingerprints, validation and committed resolution. |
| `kageyoni/writing.py` | Extend | World dialogue and delivery; this is not the generic document editor. |
| `kageyoni/workflows.py` | Extend compatibly | Existing host-facing workflow facade; delegates new functions to the application service. |
| `kageyoni/seed.py` | Keep | Explicit sample/import initialization; never silently replaces a current campaign. |
| `kageyoni/__main__.py` | Extend | Scriptable CLI commands using application services. |
| `terminal.py` | Keep launcher | Starts menus; no direct SQL, prompt execution, or domain resolution. |
| `kageyoni/application.py` | New | Coordinates use cases across the modules below; owns operation boundaries. |

### New bounded modules

| Package and files | Responsibility and boundary |
|---|---|
| `kageyoni/intelligence/contracts.py` | Typed node, method, experience, understanding and contribution contracts. |
| `kageyoni/intelligence/nodes.py` | Stable identity and scoped profile revisions; links rather than copies world records. |
| `kageyoni/intelligence/context.py` | Select relevant permitted records and build bounded context packets with source references. |
| `kageyoni/intelligence/visibility.py` | Validate scope and access before retrieval expansion, exports and delivery. |
| `kageyoni/intelligence/expression.py` | Turn a relevant method configuration into a task approach; record why it applies. |
| `kageyoni/intelligence/methods.py` | Versioned operations, causal roles, applicability and destination trial records; durable retrieval after restart. |
| `kageyoni/intelligence/transfer.py` | Propose mappings, expose broken correspondences and qualify destination use; does not grant competence. |
| `kageyoni/intelligence/learning.py` | Propose, qualify, revise and supersede lessons and capability claims. |
| `kageyoni/intelligence/network.py` | Participation, contribution relationships, disagreement and synthesis records. |
| `kageyoni/workspaces/contracts.py` | Adapter inputs, outputs, checks and side-effect declarations. |
| `kageyoni/workspaces/registry.py` | Available workspace types, versions and supported operations. |
| `kageyoni/workspaces/world.py` | Delegates world operations to existing engine and decision APIs. |
| `kageyoni/workspaces/documents.py` | Document brief, source constraints, revisions and deliverables. |
| `kageyoni/workspaces/repository.py` | Repository task context, patches, verification and exact artifact identity. |
| `kageyoni/workspaces/pipeline.py` | Step dependencies, execution state, retries and partial outcomes. |
| `kageyoni/workspaces/transitions.py` | Checkpoints, context transfer, destination opening and return verification. |
| `kageyoni/execution/contracts.py` | Host-neutral execution request, response and receipt. |
| `kageyoni/execution/manual.py` | Export/import a bounded packet, validate returned response and record manual provenance. |
| `kageyoni/execution/host.py` | Implement only against a verified available host capability; otherwise explicitly unavailable. |
| `kageyoni/persistence/unit_of_work.py` | Transaction ownership and savepoint policy shared with the engine. |
| `kageyoni/persistence/network_store.py` | SQL repositories for network records and operational events. |
| `kageyoni/persistence/artifacts.py` | Hashing, staged files, manifests, durable completion and orphan reconciliation. |
| `kageyoni/persistence/migrations.py` | Migration inspection, predecessor checks, dry run and application. |
| `kageyoni/ui/menus.py` | Navigation and session state. |
| `kageyoni/ui/forms.py` | Field validation and human-readable error recovery. |
| `kageyoni/ui/views.py` | Profile, history, contribution, comparison and result views. |

Keep these modules small enough to have one reason to change. A package is a grouping of responsibilities, not a separate server or an obligation to run another process.

### Contracts, configuration, prompts, scripts and tests

| Path | Contents / rule |
|---|---|
| Existing migration files, including `migration_003.sql`–`migration_008.sql` | Preserve paths and checksums. Retain any earlier required migration files. |
| `migrations/009_*.sql` onward | Proposed numbering only; allocate after confirming the actual target predecessor. Runner supports old and new locations. |
| `contracts/generated/` | Generated new JSON schemas from Python contract definitions; do not independently hand-edit both. |
| `contracts/examples/` | Valid and invalid interchange examples; existing Will contract authority remains intact. |
| `config/workspaces.json` | Workspace registrations and enabled operations. |
| `config/policies.json` | Defaults for budgets, retention, qualification and delivery. No personal secrets. |
| `prompts/expression.md`, `reflection.md`, `synthesis.md` | Versioned task guidance, referenced by hash in receipts. No canonical state stored here. |
| `scripts/inspect_baseline.py` | Read-only metadata inspection before opening a mutable engine. |
| `scripts/migrate_copy.py` | Clone, migrate, verify and emit differences. |
| `scripts/verify_restore.py` | Restore drill and comparison with expected revisions. |
| `scripts/run_scenarios.py` | Run selected fixtures and emit evidence; future command, not currently available. |
| `tests/` | Retain existing tests where they are until relocation is separately verified. |
| `tests/unit/`, `tests/contracts/`, `tests/integration/` | New pure rules, API compatibility and real persistence tests. |
| `tests/scenarios/fixtures/` | Source-labelled inputs, expected outcomes, adversarial variants and controlled histories. |
| `tests/scenarios/test_*.py` | End-to-end deterministic checks using actual services. |
| `tests/behavioral/` | Evaluation harness and rubrics; live runs explicitly opt-in and separately reported. |
| `docs/architecture.md`, `migration.md`, `scenario-catalog.md` | Maintained architecture, recovery procedure and acceptance obligations. |
| `pyproject.toml` | Package metadata, supported interpreter and dependencies after verification. |

Runtime files live outside the tracked source by default:

| Runtime path | Purpose |
|---|---|
| `data/engine.sqlite` | World and network tables with separate histories and scope. |
| `artifacts/objects/<digest>` | Immutable document/packet/output bytes. |
| `artifacts/staging/` | Incomplete writes, safe to reconcile by manifest. |
| `runs/<execution-id>/` | Receipts, permitted inputs, outputs and test evidence with retention settings. |
| `exports/` | Explicit portable exports; not the canonical database. |
| `backups/<checkpoint-id>/` | Database plus referenced artifacts and compatibility manifest. |
| `settings.json` | Local user preferences, never campaign canon. |

Search indexes and summaries are derived projections. Rebuild them from durable records; never recover identity or a lost event solely from a summary. Do not check a personal campaign database, private run log or credential into the source repository.

## 5. What connects, what stays separate

The allowed dependency direction is UI/CLI → application services → domain services and adapters → persistence/execution interfaces. The world adapter calls existing world APIs. The persistence layer does not import menus, prompts or workspace behavior.

| Group together | Keep separate | Reason |
|---|---|---|
| Node methods and their evidence | Node identity and temporary execution | One failed run does not replace a character. |
| One use case and its transaction | Database transaction and external file/tool effects | External effects need completion tracking and recovery. |
| World character references and node links | Story events and operational learning events | Drafting a document must not silently happen inside the story. |
| Relevant context and source references | Retrieval authority and generated text | A model cannot expand its own access by claiming relevance. |
| Workspace contract and adapter | Node-specific bespoke code | Sciel is a configuration with history, not `sciel.py`. |
| Method revisions and qualification | Personality, Will affinity and demonstrated mastery | They affect interpretation differently. |
| Shared contribution history | Everyone’s private knowledge | Collaboration must have an explicit exchange boundary. |

A shared database is initially preferable because local consistency is easier to reason about. It does not imply shared omniscient context. Tables and queries must carry scope, branch, owner and visibility as appropriate.

Do not build a continuously running process for every character. Materialize only the nodes relevant to an active task, within an explicit budget. Cache permitted projections by node revision, workspace revision and visibility policy version; invalidate on any of those changes. Filter authorization before retrieval and reference expansion, not after producing a draft.

## 6. Durable model and minimum contracts

Proposed new logical entities are below. Final SQL belongs to each slice’s migration review; these names define responsibilities and required relationships.

| Entity | Minimum fields and relationships |
|---|---|
| `nodes` | `node_id`, kind (character/engine), display name, identity revision, source link. Human user/principal is a separate identity. |
| `node_bindings` | Node → world character, branch and workspace; unique where required; no silent conflation of human Levi and fictional Levi. |
| `methods` / revisions | Stable ID and revision; operation and rationale; directed role relationships; preconditions, applicability and failure conditions; source episode, evidence/counterevidence, checking procedure and qualification status. |
| `node_methods` | Node, method revision, scoped priority, qualification and provenance. |
| `experiences` | Node, scope, event/task reference, observation, outcome, source type and timestamp. |
| `understandings` | Claim, evidence, conditions, uncertainty, counterevidence, supersedes link, qualification state. |
| `capability_claims` | Task/domain, demonstrated behavior, supporting attempts, limitations; no inferred mastery from personality. |
| `workspaces` | ID, type, adapter version, object revision, status and configuration reference. |
| `executions` | ID, node(s), workspace, request hash, input revisions, host/manual mode, status, output refs and cost/time if observable. |
| `contributions` / edges | Author, execution, artifact/claim reference; supports, challenges, adapts, combines or supersedes links. |
| `transitions` | Source checkpoint, destination, transfer policy, state, return check and failure details. |
| `artifact_manifests` | Digest, path, media type, source execution, scope, staged/available state. |
| `method_trials` | Source method revision, destination task/domain, proposed mapping, broken correspondences, adaptations, expected consequence, actual checks and outcome; links rather than duplicates execution receipts. |
| `contribution_receptions` | Contribution, receiving node/execution, accepted/challenged/deferred/rejected disposition, reason and resulting decision/artifact reference. Receipt alone is not demonstrated use. |
| `workflow_policy_revisions` | Versioned routing/closure policy, motivating evidence, comparison trials, activation scope and supersedes link; operational policies are separate from world rules. |
| `network_events` | Operational sequence, request ID, actor, changes and version references; distinct from world story events. |
| `pending_effects` | Idempotent external operation, prerequisites, intent, outcome receipt and reconciliation state. |

Shared identity can be global. A character’s belief, experience and capability expression can be branch-specific. Fork a profile by reference plus revision history; never propagate one branch’s learning into another automatically. Explicit cross-domain applications live in their destination scope. Operational knowledge about a task does not become diegetic character knowledge without a world event that supports it.

A method should say **what operation it performs, when it helps, when it fails, and how to check it**. “Sees connections” alone is insufficient. For example: compare constraints across two domains, propose a correspondence, list where the correspondence breaks, and validate one consequence in the destination. This is an illustrative contract, not an assertion of Sciel’s established method.

An execution request requires `request_id`, `workspace_id`, `expected_workspace_revision`, participant IDs and profile revisions, purpose, authorized operations, context packet reference, output contract and budget. Its receipt records input hashes, adapter/prompt versions, actual execution mode, attempts, result status, artifact references, checks and proposed learning. Reject stale writes; preserve the draft for deliberate revalidation.

Learning states are proposed → reviewed/qualified → active → revised/superseded. Store an experience even when no lesson is justified. Several repeated model outputs are not independent evidence. A generated interpretation remains attributable to its source and uncertainty.

## 7. Will and character introduction

Preserve the meaning established in discussion: a **Named Will is the bearer’s understanding of how they access a greater Primordial Will**. It can be partial, mistaken or evolving. Do not migrate every existing named definition into an objectively distinct primordial entity.

Keep separate: underlying Will reality; the bearer’s interpretation; innate disposition (definition unresolved); practiced abilities; contextual choices; evidence of mastery. Existing records without enough information remain unresolved with preserved source text.

The eight intelligence aspects remain a provisional vocabulary: perceptual–aesthetic, relational–systems, abstractive–analogical, generative–imaginative, critical–epistemic, practical–experimental, metacognitive–developmental and interpersonal–interpretive. Dominant, secondary, tertiary and fourth positions describe proposed emphasis, not psychological measurements. Do not enforce the earlier suggestion that the fourth must represent tension.

Character introduction should produce a **bounded draft profile quickly**, using supplied story and personality evidence, links to existing records, unknown fields and confidence labels. Deterministic validation checks completeness and contradictions. The normal world creation API commits approved fictional facts. Unknown stats remain unknown or explicitly authored game parameters; do not manufacture accurate assessments of real people from a short description.

## 8. Transaction and artifact design

Before coupling world changes to network records, define transaction ownership:

1. An application unit of work starts and owns a transaction when none exists.
2. A composable engine operation uses a savepoint when called inside that transaction.
3. Successful inner work releases its savepoint without committing the outer transaction.
4. Failed inner work rolls back its savepoint. The caller decides the overall transaction outcome.
5. Preview never persists changes and never rolls back unrelated caller work.
6. Duplicate request handling returns the prior result without committing or erasing unrelated pending work.

This is a proposed change to `Engine.apply()`, not an assumed existing guarantee. Preserve standalone behavior. Test success, failure, preview and duplicate paths with and without an outer transaction before using it for network integration.

If this narrow refactor cannot preserve v8 behavior, use a durable intent/outbox and explicit reconciliation instead. Never claim atomicity from an outer wrapper around the current implementation.

Files and external tools cannot be rolled back by SQLite. Stage bytes, calculate a digest, register intent, finalize the immutable file, and mark availability through a recoverable process. A crash between steps leaves a recoverable pending effect, not a fictitious success. External tool writes require an idempotency strategy or explicit reconciliation before retry. Backups must include every referenced available artifact and report incomplete effects.

## 9. Eight vertical slices

| Slice | Complete usable outcome | Main modules | Acceptance / depends on |
|---|---|---|---|
| **V1 — Persistent node** | Open a real character-linked node, inspect permitted identity/history, close and reopen unchanged. | nodes, contracts, store, UI | Stable IDs, private-view exclusion, branch isolation, backup round trip; typed dispositions cannot promote waiting or failure to success. Depends on P0 and transaction decision. |
| **V2 — Consequential expression** | Give one task to a node; its evidenced method changes the approach and produces an inspectable contribution. | context, expression, execution, artifacts | Rename alone does not change reasoning; relevant method revision does; source-bound method retrieval survives restart; unsupported expertise is not granted. V1. |
| **V3 — Experience and development** | Record an outcome, propose a bounded lesson, qualify it and observe a later relevant application. | learning, histories, views | Reopen/replay preserves revision; a qualified lesson changes a later relevant decision with attributable evidence; contrary evidence revises it; irrelevant tasks do not inherit it. V2. |
| **V4 — Character genesis and Will interpretation** | Introduce a coherent provisional character with linked Will interpretation and known/unknown capabilities. | characters, will, contracts, forms | No invented canonical facts; interpretation and underlying reality can disagree; normal world validation still applies. Demonstrate an authored AI-disabled encounter mixing dialogue, ability use and consequence without duplicated effects. V1, with V2–V3 for interaction/development integration. |
| **V5 — Workspace round trip** | Checkpoint the world, use a node on a document task, retain the artifact and return to the exact world checkpoint. | documents, transitions, artifacts | A real draft follows source constraints; decomposition preserves unknowns; a transferred method passes destination checks; no accidental story event or leaked knowledge; interrupted transition recovers. V2–V3. |
| **V6 — Collective contribution** | Two or more configured nodes contribute, challenge and synthesize; engine node records coordination lessons. | network, learning, execution | Contribution ancestry and reception are inspectable; output bodies reach synthesis; disagreements survive; no eligible participant returns an explicit block; matched comparisons show whether added work helps. V3, V5. |
| **V7 — Repository and pipeline work** | Apply methods to a bounded code task or multi-step artifact workflow and verify the exact output. | repository, pipeline, pending effects | No success without checking the exact artifact; all blocking dependency types count; retries execute and retain failure evidence without duplicating effects; domain qualification enforced. V5–V6. |
| **V8 — Operable daily system** | Install, migrate a copy, use menus/fields/settings, recover interrupted work and export/reopen a portable bundle. | packaging, UI, migrations, recovery | Clean-start and upgrade paths pass; limitations visible; representative work remains usable within measured budget; policy changes require evaluated trials and reversible activation. All prior slices. |

Each slice includes its own minimal terminal flow and tests. V8 polishes the entire operational experience; it is not the first time a human can use the system. V4 and parts of V5 can proceed independently after prerequisites, but must converge on common contracts.

### Six horizontal concerns

| Concern | Carried through slices |
|---|---|
| **H1 — Identity and contracts** | Stable IDs, schema versions, explicit unknowns, source links and compatibility. |
| **H2 — Persistence and recovery** | Revisions, transaction boundaries, idempotency, migrations, replay, backups and artifact reconciliation. |
| **H3 — Scope and authority** | Branch/workspace knowledge, visibility, permitted operations and human versus fictional identity. |
| **H4 — Meaning and qualification** | Method applicability, Will interpretation, learning evidence and capability limits. |
| **H5 — Evaluation and traceability** | Scenario oracles, execution receipts, contribution ancestry, costs and outcome comparison. |
| **H6 — Interface and integration** | CLI/menu usability, adapters, host/manual exchange and export/import behavior. |

## 10. Route from v8

**P0: preflight before feature construction.** Identify the authoritative current engine and campaign with their lineage. Inspect without mutating them. Capture source hashes, database/component versions, branch heads, pending decisions, rules, artifact references and interpreter version. Preserve originals. Reproduce baseline tests and known integration failures on disposable copies. Write the scenario expectations before implementation.

Then follow this migration sequence:

1. **Prove restore first.** Create a consistent database/artifact backup; restore to a different path and compare canonical records, branch heads and pending decisions. A copied file that has never been opened and checked is insufficient recovery evidence.
2. **Fix or explicitly replace transaction composition.** Add focused regression cases before changing `apply()`. Preserve old event and replay semantics.
3. **Add storage incrementally.** First node/binding/workspace/operational history tables; later methods/learning, transitions/artifacts, then contribution relationships as slices require. Tentative migrations 009 onward are allocated only after predecessor inspection.
4. **Import links, not invented intelligence.** Link existing characters to stable nodes. Preserve original aspects and Will contracts. Report unresolved mappings. Do not automatically populate four aspect ranks or mastery scores.
5. **Check both installation paths.** Fresh database and migrated historical fixture must produce equivalent supported behavior. Migration runner records checksum and predecessor and refuses unknown or changed history.
6. **Preserve pending work.** Revalidate stale proposals against new component versions. Display the old intent, explain incompatibility, and require a new reviewed proposal when necessary; never silently reroll outcomes.
7. **Compare migration effects.** Produce counts, changed rows, semantic snapshot differences and expected new tables. Database byte hashes may differ legitimately; compare domain state and event behavior, not only whole-file hashes.
8. **Exercise replay and branches.** Historical events use their recorded rules/contracts. Replaying an old event must not invoke today’s intelligence prompt. Branch-local learning must remain local.
9. **Promote the exact verified candidate.** Record the candidate digest and target head. If the real campaign advanced after the copy was made, recreate or reconcile the candidate; never overwrite newer state with the earlier test copy.
10. **Recover by situation.** Before new writes, restoring the verified old checkpoint may be safe. After v9.5 writes, prefer a forward repair or explicit supported export/reconciliation. Blind downgrade or restoring an old backup can lose newer work and is not the default rollback strategy.

No implementation timeline is asserted until P0 and the first slice reveal actual effort. Unresolved mechanics can remain nullable or provisional; database requirements should not force premature fictional truth.

## 11. Tests grounded in the work

Every scenario must identify its source: **reproduced defect**, **reported workflow problem**, or **designed adversarial case**. The latter two are obligations to test, not claims of already observed engine failure. Use sanitized fixtures and a recorded source reference.

| ID / scenario | Kind | Expected outcome / independent oracle | Slice |
|---|---|---|---|
| T01 Outer rollback after world plus network write | Reproduced this turn | Both writes absent after rollback; standalone commit still works. | P0/V1 |
| T02 Preview or duplicate inside caller transaction | Designed adjacent case | No world change from preview; unrelated pending caller write remains uncommitted and intact. | V1 |
| T03 Latest campaign versus packaged seed | Baseline risk | Loader identifies lineage and refuses silent replacement by stale seed. | P0/V8 |
| T04 Branch A learns, branch B does not | Prior fixture behavior to preserve | Revision-linked lesson visible only in A unless an explicit transfer occurs. | V1/V3 |
| T05 Rename the character | Prior fixture behavior to preserve | Same relevant facts/methods produce equivalent structured choices under controlled execution. | V2 |
| T06 Paraphrase a recorded method | Prior exact-string weakness | Same stable method ID behaves consistently; an unrelated similar phrase does not gain its effect. | V2 |
| T07 Same Will, different experience | Prior fixture behavior to extend | Different evidenced methods can produce different approaches without changing success rules by fiat. | V2/V4 |
| T08 Fictional skill moved into technical work | Designed | Analogy offers a candidate approach; competence requires destination evidence and checks. | V3/V5/V7 |
| T09 Hidden fact in unannotated output prose | Earlier adversarial bypass | A unique hidden canary never enters unauthorized generation input; delivery check detects the seeded leak where feasible. Empty claims cannot establish safety. | V2/V5 |
| T10 Private fact reached through nested relation/cache | Designed | Public projection excludes fact, snippet and revealing metadata; authorized projection still works. | V1/V2 |
| T11 World → document → world, interrupted midway | Designed | Durable transition status, preserved world revision, recoverable draft; no fabricated world event. | V5 |
| T12 Named Will disagrees with underlying Will | User-defined semantics | Store both without contradiction overwrite; abilities remain governed by evidence/mechanics. | V4 |
| T13 Sparse character introduction | User goal | Useful provisional profile with unknown stats; no invented history accepted as established fact. | V4 |
| T14 Two nodes repeat one unsupported claim | Designed | Repetition does not become independent corroboration; contribution ancestry points to one source. | V6 |
| T15 Tested artifact differs from promoted artifact | Designed repository risk | Digest/path/revision mismatch blocks success; verify the actual candidate. | V7/V8 |
| T16 Crash after external side effect, before receipt | Designed pipeline risk | Reconcile first; no blind repeat of non-idempotent action. | V7 |
| T17 Host unavailable or budget exhausted | Designed | Honest partial/manual/unavailable state; saved work survives; no simulated success. | V2/V8 |
| T18 Already-selected action offered as unresolved | Reported continuity pattern | Prior confirmed choice remains settled unless a new event explicitly reopens it. | V4/V5 |
| T19 Different media briefs have different obligations | Reported work pattern | A cancelled teaser in one brief does not remove a required teaser in another; obligations traced to the correct source. | V5 |
| T20 Missing schedule or sensory evidence | Reported work pattern | Do not invent event timing or claim audio quality was checked without listening; identify missing evidence. | V5/V7 |
| T21 Unicode names, alias and speaker confusion | Designed / reported identity pattern | Stable identity survives spelling/display changes; Sciel remains Sciel; speaker attribution checked against scene inputs. | V1/V4 |
| T22 Contradictory feedback after apparent learning | Designed | Retain original experience, revise the qualified lesson, and change only applicable future behavior. | V3 |

T18–T20 represent workflow patterns carried into planning; exact source documents and quotations must be attached to fixtures before calling them verified reproductions. Do not fabricate those documents to make a test look historical.

### A scenario fixture is an executable obligation

Each fixture contains: ID; provenance and source status; risk; setup records and versions; authorized actor/view; action sequence; permitted changes; forbidden changes; independent expected outcome; failure injection point; positive control; adversarial variant; cleanup and evidence outputs.

Example T11: use a world with an unresolved choice and one private fact. Start a document workspace with only public relevant methods, create a draft, terminate after artifact staging, reopen, reconcile, then return. Verify the exact prior world head, unresolved choice, artifact hash, transition state and permitted context. Include a successful uninterrupted run and an authorized private-view run. A system that rejects all transitions must fail the positive control.

### What makes a test relevant

- Derive the oracle from the user’s constraint or domain invariant before writing implementation. Do not test only that one function calls another.
- Use real SQLite, actual serializers, and process reopen for durability tests. A mocked store cannot prove persistence.
- Introduce controlled mutations: remove scope filtering, reverse revision comparison, skip receipt reconciliation, or replace a stable method ID with text matching. The corresponding test should fail. A mutation not caught exposes a weak test or an uncovered risk.
- Pair prohibition checks with valid cases. Rejecting every draft, refusing every character, or suppressing all learning is not a successful implementation.
- Test compound failures: stale revision plus retry, interrupted transition plus reopen, hidden context plus cache, pending decision plus migration.
- Keep deterministic contract tests separate from stochastic behavior evaluation. Record model/host identity when available, prompt and input versions, and uncertainty when unavailable.
- Check actual source compliance and usability with an explicit rubric. A text substring or another model saying “looks good” cannot alone establish semantic correctness.

Model output validation cannot guarantee that every paraphrased secret or unsupported inference is caught. Restrict input exposure first, then use structured provenance, targeted checks and review for consequential outputs. Report residual uncertainty rather than calling the entire system semantically safe.

## 12. Proving advantage, rather than merely difference

Run matched tasks under four conditions: **A** plain host with task/source context; **B** character style prompt without persistent methods/history; **C** persistent single node; **D** differentiated network. Give each access to the same authorized source material and comparable total execution budgets. Record extra context and coordination costs rather than hiding them.

Start with four representative tasks: a source-constrained document, a continuity-sensitive world scene, a bounded repository repair, and a cross-domain planning problem. A proposed pilot is two runs per task per condition: 32 runs. This is a diagnostic pilot, not a statistically conclusive benchmark; it has not been executed. Choose a smaller authorized budget if necessary and report the narrower evidence.

Judge source fidelity, useful novelty, correction burden, completion quality, continuity, time and execution budget. For development, compare a qualified lesson against its absence on a new applicable task and on an unrelated control task. For network benefit, inspect whether different contributions changed the result, not merely whether several names appear in a transcript.

Blind the reviewer to condition where practical; preserve gold requirements outside participant context, counterbalance task order, and retain disagreements. Human preference can assess enjoyment and usefulness; deterministic checks assess factual obligations and artifacts. No single composite number should erase a serious correctness failure.

Decision rules: keep a method if it improves relevant work or valued creative experience at an acceptable cost; narrow its applicability if it transfers poorly; revise orchestration if the network only repeats one answer; use one node when a network adds no benefit. The full network remains the destination capability without becoming mandatory overhead for every task.

## 13. Gates before committing to the build

| Gate | Evidence required | Current status |
|---|---|---|
| G0 Baseline understood | Source inventory, existing tests, known incompatibilities | Available package inspected; 168 tests passed; transaction issue reproduced. Latest campaign authority still must be established before migration. |
| G1 Architecture survives paper scenarios | Trace T01, T09, T11, T14, T16 through owners and records | Contracts and traces specified here; implementation untested. |
| G2 Recoverable foundation | Restore drill, migration dry run, transaction cases and branch isolation | Required before migrating authoritative state. |
| G3 Meaningful single-node behavior | V2/V3 demonstration beyond names/style, qualified learning and controls | Not implemented or demonstrated by this document. |
| G4 Safe workspace round trip | Real document output, exact world return, interruption recovery | Not implemented. |
| G5 Useful collective work | Matched evaluation plus contribution ancestry | Not run; no performance benefit claimed. |
| G6 Daily operation | Exact candidate verified on fresh install and historical upgrade with recovery | Not run. |

Stop expanding architecture when a gate fails. Diagnose the failed assumption, revise the relevant contract, and repeat that evidence. Do not compensate for failed persistence with longer prompts or failed differentiation with more characters.

## 14. Requirement-to-implementation traceability

| Requirement from the vision | Primary owner | Slice | Acceptance evidence |
|---|---|---|---|
| Characters persist as configurations of understanding | nodes, learning, network store | V1/V3 | T04, T22, reopen and restore |
| Sciel contributes in another domain as Sciel | expression, context, workspace adapter | V2/V5 | T05–T08 plus evaluated contribution |
| Characters experience what Levi has not | world adapter, decisions, learning | V3/V4 | Consequential world outcomes with scoped interpretation; no claim they become Levi’s lived evidence |
| Primordial and Named Wills remain distinct | will, character contracts | V4 | T12/T13 |
| Engine can change workspace | transitions, registry | V5 | T11 |
| Nodes combine into a greater intelligence network | network, execution | V6 | T14 and A/B/C/D comparison |
| Daily work includes repositories and pipelines | repository, pipeline | V7 | T15/T16/T20 |
| Menus, fields and settings make it usable | UI, application, packaging | Every slice/V8 | Task completion, clear failures, restart and recovery |
| v8 history and newer work survive | migrations, engine, artifacts | P0/V8 | T01–T04, historical replay and promotion check |

## 15. Immediate next implementation packet

The next build should contain **P0 plus V1**, while preserving this complete destination. Its concrete deliverables are a baseline manifest, verified restore report, transaction regression tests and narrow fix (or explicit reconciliation alternative), the first additive node migration, a character-to-node binding service, permitted profile view, reopen/branch-isolation tests, and one terminal flow to inspect it. Include only the minimum shared process envelope needed here: typed waiting/failed/blocked/completed dispositions and explicit closure checks. Add regression fixtures for the repository findings now; implement their domain-specific behavior in the owning later slice. Do not import every repository or build all eighteen mechanisms during V1.

Before writing that code, attach the authoritative current engine/campaign lineage and freeze the first scenario fixtures. Canonical Will assignments, exact aspect affinities, innate-Will mechanics, Sciel’s detailed methods, and host integration availability remain explicit unresolved inputs. None prevents building identity, provenance and recovery correctly; none should be silently invented to fill a schema.

This technical companion preserves the prior v9.5 vision. Future revisions should change a contract, scenario, or slice deliberately and record why. It is ready to guide implementation, but its proposed modules, migrations and test gates must earn their completion status through execution.

## 16. Closed loops: the operating structure

A closed loop is more than a chain of commands. It has an objective, observable state, available actions, an action result, a check against the objective, and a defined next state. Completion, failure, cancellation and suspension must all be represented. A workflow that produces a draft but never checks or records its outcome is open. A feedback loop can finish; it need not run forever.

There is no universal correct number of loops. For this engine, use **three control modes and twelve proposed loop families**. Six families form the minimum for a bounded, replayable CLI game. The remaining six support persistent development and work across domains. These are responsibility categories, not twelve new daemons or twelve copies of the same scheduler.

### Three control modes

| Mode | Who selects or resolves the next step? | Example |
|---|---|---|
| Procedural | Validated rules and code | Spend a resource, resolve an authored action, advance a clock. |
| Judgment-assisted | Human or AI returns a structured proposal | Interpret an ambiguous intention, assess a source, propose an unfamiliar response. |
| Developmental | Outcomes inform a proposed revision to future behavior | Revise a method’s applicability after success and counterevidence. |

Judgment-assisted execution closes only when the proposal comes back through validation, application and outcome checking. Development closes only when a revised method is tested on a later task. Saving a reflection alone does not demonstrate learning.

### Twelve loop families

| Loop | State and feedback cycle | Closure / exception | Initial slice |
|---|---|---|---|
| **L1 Session and attention** | Open checkpoint → inspect visible situation and obligations → select focus → refresh | Correct actor, scene and head established; unresolved tasks remain discoverable. | V1 |
| **L2 Intent and action** | Select command → collect fields → check preconditions → preview → commit → observe | Exactly one accepted action or an explained rejection; next actions recomputed. | V1/V2 |
| **L3 Time and consequences** | Action advances time → find due processes → resolve supported effects → update state → check new triggers | No due supported effect silently lost; bounded cascading and explicit suspension. | V2/V4 |
| **L4 Encounter and objective** | Present stakes → choose move → resolve response → assess progress → continue or conclude | Authored encounter reaches success, failure, withdrawal or declared stalemate. | V2/V4 |
| **L5 Resources and progression** | Spend/gain → check limits → record consequences → apply eligible recovery or earned progression | Invariants hold; no free resources or unearned mastery. | V3/V4 |
| **L6 Persistence and recovery** | Commit → checkpoint → reopen/replay → compare → resume | Confirmed changes survive; partial writes recover without duplication. | V1/V8 |
| **L7 Inquiry and evidence** | Question → source plan → acquire → extract → assess gaps → refine or stop | Answer linked to evidence, or explicit unresolved question with stop reason. | V5/V7 |
| **L8 Judgment handoff** | Detect ambiguity → build bounded packet → obtain proposal → validate → resume | Accepted decision, revision request, human choice or durable blocked state. | V2 |
| **L9 Learning and qualification** | Experience → candidate lesson → evaluate → scope → future trial → revise | Changed future behavior has traceable evidence and limits. | V3 |
| **L10 Workspace transfer** | Checkpoint → project relevant methods → work → reconcile results → return | Artifact retained and source workspace continuity preserved. | V5 |
| **L11 Collaboration and synthesis** | Assign contributions → compare → challenge → synthesize → evaluate outcome | Final contribution has ancestry; unresolved disagreement remains visible. | V6 |
| **L12 Workflow improvement** | Observe repeated friction → propose workflow change → test → version → monitor | Improvement demonstrated or reverted; prior runs remain interpretable. | V6/V8 |

**Minimum playable claim:** L1–L6 suffice for a deliberately bounded game whose actions, encounters, NPC responses, resource rules and endings have been authored. Movement, inspection, inventory use, rule-based combat, rest, authored dialogue branches and save/resume can all run without AI. L8 is needed to gracefully handle an action outside that vocabulary, but its responder can be a human; it need not require an AI subscription.

Six loops do not by themselves produce an open-ended living world. Enough authored content, coherent resolution rules, observable outcomes and accessible choices must exist inside them. Free-form negotiation, novel inventions, ambiguous consequences and rich novel narration may require judgment. Code can still handle many judgments through explicit rules; use the AI where the current rules cannot adequately represent the situation, not because every action sounds intelligent.

Minimum play acceptance: with AI disabled, complete an authored journey containing a route choice, encounter, resource cost, consequence, objective resolution and save/restart. Every enabled menu action must resolve, reject clearly, or suspend with a usable fallback. No hidden AI call, unresolved placeholder outcome, dead-end menu or infinite consequence cascade qualifies as complete play.

## 17. One state-and-action interface for humans and models

The CLI and an LLM should use the same application contract. Instead of asking the model to memorize internal files, expose a small conceptual interface: `observe`, `available_actions`, `describe_action`, `preview`, `commit`, and `resume`. These names are proposed service operations, not currently installed CLI commands.

Each response returns a state envelope containing:

- Workspace, actor/viewer, current revision, active workflow instance and definition version.
- Current step, objective, relevant visible facts and pending obligations.
- Valid action IDs, descriptions, required fields, constraints and expected effect types.
- Why other relevant actions are blocked, without revealing private facts.
- A recommended next action when one is justified, plus alternatives and the reason.
- A durable continuation token for suspended judgment or external work.
- Result status, evidence/artifact references and checks actually performed.

A recommendation describes a likely next step; it does not authorize that step or guarantee it is valid after another write. Validate actor permission, preconditions and revision again at commit. Keep request IDs for retry deduplication. Avoid returning every feature at once: present relevant actions and allow discovery of others.

The common workflow lifecycle is draft → ready → running → waiting for judgment/input/effect → validating → committed → assessing → completed, with explicit blocked, failed and cancelled states. Validation can return to the waiting state with concrete errors. Failed runs remain inspectable. Budgets, maximum iterations, repeated-state detection and progress checks stop unproductive loops.

### Judgment packets

A judgment packet includes the question to decide, relevant permitted evidence, unknowns, available levers, constraints, acceptable response schema and what happens after acceptance. It can ask an AI to choose an existing action, request specific missing information, or propose a new bounded workflow. It must not ask the model to directly modify the database.

The response distinguishes observations, interpretations and proposed actions. For example, “the business states sustainability as a value” is a supported observation about its website; “the business behaves sustainably” needs additional evidence. Store the reasoning necessary to evaluate the decision, not an expectation of access to a model’s private internal reasoning.

A new workflow proposed by AI is a draft definition. Validate allowed operations, termination, effects and fixtures before registering it as reusable. Never execute source-page instructions or newly generated scripts merely because they appear in a packet.

## 18. The information mine: source to useful work

The mine metaphor translates into a source contract: **is this the right source, can we access and process it appropriately, does it contain the required evidence, and can the extraction be checked?** A large collection of text is not automatically useful intelligence.

For the question “What does this business do and sell?”, the proposed workflow is:

1. **Specify the output.** Business identity, offerings, customers, stated values, supporting evidence, contradictions and unknowns. Define intended reuse before collection.
2. **Resolve identity.** Confirm the official domain against supplied context; distinguish namesakes, subsidiaries and outdated sites. An unresolved identity blocks confident attribution.
3. **Plan likely sources.** Home, products/services, pricing, about/mission and relevant supporting pages. “About us” is a search heuristic, not a guarantee that values are there.
4. **Acquire bounded evidence.** Fetch or use an authorized browser adapter, record URLs, capture time, page identity and relevant text. Detect inaccessible pages, redirects, unsupported content and missing material. Do not bypass access controls.
5. **Extract observations.** Connect each offering or stated value to a passage. Distinguish explicit statements from interpretation; do not invent a value because an expected page is missing.
6. **Assess sufficiency.** Which required fields have support? What conflicts? Are sources current enough for the intended use? Request targeted evidence or stop with qualified unknowns.
7. **Interpret with judgment.** Explain how the offerings and positioning fit together, identify alternative readings and constrain claims to evidence.
8. **Produce the requested artifact.** Brief, messaging ideas, comparison or plan. Adapt meaning to the new purpose while preserving facts and attribution; proposed messaging is not an existing company statement.
9. **Check the output and retain outcomes.** Verify source links, required fields, unsupported claims and usefulness. Record which method helped, what failed, and whether a later use confirmed it.

Retrieved pages are untrusted evidence, not engine instructions. Separate their content from executable configuration; bound fetches, validate destinations, avoid exposing credentials, and use controlled parsing. A source’s own claims can reliably establish what it says without independently establishing that those claims are true.

### What this loop measures and retains

| Record class | Useful contents | Avoid mistaking it for |
|---|---|---|
| Metrics | Required-field evidence coverage, conflicting claims, inaccessible sources, extraction errors, time, retries and human corrections | Page count or token volume as a measure of intelligence |
| Schema | Entity, offering, audience, claim, value, evidence passage, source, capture time and qualification | A rule that every business must fill every field |
| Reusable method | Search heuristic, extraction rule, applicability, counterexample and evaluated result | A one-off plausible answer |
| Task output | Source-grounded brief or adapted artifact with open questions | Verified business performance or psychological truth |
| Learning | Which action resolved a gap and under which conditions | Unexamined generalization from one website |

Evidence coverage can be calculated as supported required fields divided by applicable required fields. Preserve unknowns and exclusions; a high score does not establish that all extracted claims are correct. Measure correctness separately using reviewed examples. The example above is a workflow design; no business website was researched for this blueprint.

## 19. Loop implementation additions and acceptance

Add `kageyoni/processes/contracts.py`, `registry.py`, `runner.py`, and `handoff.py` for workflow definitions, permitted state transitions, resumable execution and judgment packets. Add `kageyoni/research/sources.py`, `extract.py`, and `assess.py` for acquisition contracts, evidence extraction and sufficiency assessment. Network/browser implementation remains capability-specific. Store reusable definitions under `workflows/definitions/` and sanitized scenario inputs under `tests/scenarios/fixtures/`.

These modules orchestrate existing v8 processes and consequences; they do not create a second competing clock or resolution system. Inspect and adapt the current `open_session`, `prepare`, `advance_time`, `apply_consequences`, decision and process APIs first. Current workflow responses already include some next-step guidance, but a prose `next` field is not the complete typed action interface proposed here.

Add versioned workflow definitions and resumable instances to the durable model. Instances record step, inputs, observations, attempts, pending handoff, outcome and definition version. A new definition version does not rewrite an in-progress instance; upgrade it explicitly or finish under the pinned compatible definition.

Additional acceptance scenarios:

| ID | Test and success condition |
|---|---|
| T23 | AI-disabled playable journey: complete L1–L6 through actual CLI/application calls, including restart. |
| T24 | Unknown action: emit a bounded judgment packet; valid human response resumes exactly once, invalid response leaves state unchanged. |
| T25 | Cyclic triggers or repetitive research: iteration limit produces a durable blocked/partial outcome and explains the unresolved objective. |
| T26 | Wrong business or stale page: identity/recency uncertainty prevents confident attribution; correct source remains usable. |
| T27 | Missing About page: search other relevant pages and allow unknown values without inventing them. |
| T28 | Source page contains instructions to change engine settings: retain relevant evidence but ignore those instructions as authority. |
| T29 | AI selects a previously valid action after state changes: stale proposal rejected and available actions refreshed. |
| T30 | Workflow upgraded while suspended: instance resumes under its recorded compatible version or undergoes an explicit migration. |
| T31 | Research appears complete but an extracted claim has no supporting passage: fail the evidence check without discarding correctly supported claims. |

This addition does not increase the eight vertical slices: it makes the control flow within them explicit. Establish the runner and state envelope in V1/V2; prove bounded AI-free play across V1–V4; implement inquiry and evidence with V5/V7; add evaluated workflow improvement with V6/V8. Each slice now has to show both its useful output and the route back to a valid next state.

## 20. Interactions contain overlapping, nested loops

The twelve families above classify responsibilities; they are not a limit on the number of live loops. **An interaction is a container of related loop instances.** Conversation, battle, bonding, discovery, abilities and consequences can overlap within it. Some loops nest; others cross interaction boundaries. A relationship can remain unresolved across many completed encounters.

Do not represent every narrative sentence as a separately persisted loop. Instantiate a loop when it has a meaningful objective, pressure, commitment, pending response or consequence that must survive interruption. A descriptive gesture can remain part of an event unless it creates such an obligation.

### An interaction frame

Record participants and their permitted perspectives, location/time, declared intentions, stakes, relevant relationships, active rules, open loops and current opportunities. Track explicit intent separately from inferred intent. Each inference needs an uncertainty/status field and must not silently become an actor’s canonical motive.

Each loop instance needs:

- Stable ID, loop type, interaction reference, optional parent and related-loop edges.
- Initiating event, participants, scope/visibility, rule or workflow version.
- Desired outcome or unresolved question, current pressure and completion criteria.
- State, current phase, pending actor/input, available actions and blockers.
- Observed effects, evidence, costs, timing and next eligible evaluation point.
- Outcome and close reason, or suspension reason and resumption trigger.

Useful states are proposed, active, waiting, suspended and resolved, with cancelled and failed as distinct endings. A resolved loop records an outcome; it does not imply the desired outcome was achieved. Use explicit links for contains, depends-on, interrupts, informs and triggers. A simple parent tree is insufficient for a conversation that affects both a battle and a relationship.

### Built-in intelligence: recognition, routing and feedback

The engine’s first level of intelligence is an inspectable **interaction policy**, not a requirement to generate prose after every action:

1. **Recognize signals.** Receive a typed event or a proposed interpretation of free text. “An offer was made,” “an attack was interrupted,” and “a promise was broken” are candidate signals, not interchangeable action labels.
2. **Match applicable loop definitions.** Use participant state, context, prerequisites, open obligations and visible evidence. Rank candidates with stated reasons. A spoken line does not automatically start a bonding loop; a damaging action does not necessarily start a new encounter.
3. **Route the event.** Update relevant existing loops first. Start another only when its trigger and distinct unresolved purpose justify it. Deduplicate repeated delivery by event/trigger identity.
4. **Determine what needs a response.** Identify the responsible actor, available action schemas, prerequisites and deadlines. Resolve required rules before offering optional narrative developments.
5. **Resolve or request interpretation.** Code handles authored rules. Ask for human/AI judgment when the meaning or appropriate consequence exceeds those rules, with a bounded packet and explicit unknowns.
6. **Apply effects and evaluate closure.** Commit validated changes, then assess each affected loop against its own conditions. The model saying “the scene is over” does not override an unresolved mechanical obligation.
7. **Offer the next situation.** Surface pending responses, changed opportunities and justified new loops. If none require action, allow rest, departure, player initiation or completion. Do not manufacture conflict just to keep the scheduler busy.

Start with authored and tested policies. Later learning may propose changes to recognition and routing, but those changes pass L12 evaluation before becoming active. Store the policy version used for each transition so replay does not reinterpret history using new rules.

### Worked example: an offer during battle

A character offers an opponent a safe withdrawal while preparing a defensive ability. This example is illustrative and creates no campaign canon.

| Active loop | What it waits for | Possible closure and effect |
|---|---|---|
| Encounter | An outcome under the encounter’s actual stakes | Withdrawal, victory, negotiated settlement or another authored ending. |
| Attack/defense exchange | Legal action resolution and responses | Defense succeeds or fails; costs and damage settle once. |
| Conversation offer | The recipient’s response, refusal or meaningful expiry | Acceptance, rejection, counteroffer or no response; promises recorded if actually made. |
| Ability use | Preconditions, resource cost, effects and termination | Activation resolves; a sustained effect may persist as a separate process. |
| Relationship development | Evidence relevant to trust or hostility | A bounded change may be recorded; the overall relationship need not be “completed.” |

Accepting withdrawal might end the encounter after outstanding mechanical effects are settled. It does not automatically prove trust, erase injury, or complete a longer promise. Rejecting the offer closes that offer exchange but can leave the encounter active. An interruption can suspend dialogue while defense resolves, then resume the same offer if it remains meaningful.

Ordering comes from rule dependencies and recorded timing, not whichever loop the model mentions first. Where two effects conflict, identify the governing rule or request adjudication before applying either. Independent effects may be prepared together; shared-state commits still use revision checks and the transaction boundary.

### Closure, continuation and reopening

A parent can close only when its closure contract accounts for children: resolve required children, cancel obsolete ones with reasons, or explicitly detach permitted ongoing processes. A poison effect or promise may outlive the encounter that created it. Preserve that link and its future trigger rather than silently dropping it.

Reopening requires new evidence or a defined trigger. Preserve the previous outcome and create a linked new episode, or record an explicit versioned reopening transition. Never erase the fact that a prior exchange concluded. A timeout is an authored outcome only when the rules define one; otherwise mark the unresolved wait rather than inventing consent or failure.

### Code ownership and tests

Add `kageyoni/interactions/contracts.py`, `recognition.py`, `routing.py`, and `closure.py`. Definitions belong in `workflows/definitions/interactions/`. Reuse the process runner for execution and the world engine for effects; this layer determines which domain loops participate and why. Its state envelope exposes the current focus plus other pending obligations so the CLI and AI see the same actionable situation.

Add these acceptance scenarios to V2–V4 and regression coverage thereafter:

- **T32:** Dialogue during combat updates the proper loops without advancing time or spending resources twice.
- **T33:** Duplicate trigger delivery does not create duplicate offers, ability activations or consequences.
- **T34:** Closing an encounter preserves an ongoing promise or sustained effect through explicit continuation links.
- **T35:** A parent cannot close while a required child response is unresolved; permitted withdrawal/cancellation remains possible.
- **T36:** A low-confidence interpretation requests judgment without writing an inferred motive as fact.
- **T37:** Opposed or cyclic dependencies produce an explained adjudication/block state rather than deadlock or repeated effects.
- **T38:** Save/reopen during an interrupted conversation restores the pending speaker, offer, relevant battle phase and applicable policy versions.
- **T39:** New evidence starts a linked follow-up without deleting the outcome of the original interaction.

Sufficiency is therefore a coverage question: can every supported interaction reach an appropriate outcome, suspension or next choice while preserving its related obligations? Counting loop types alone cannot answer it. The minimum CLI game must test both individual loops and these compositions.


## 21. Repository mechanisms integrated into the plan

### Shared protocol, different scheduling policies

Keep the twelve loop families in §16. The eighteen operations below describe reusable behavior inside those families; they are not eighteen new services, databases or release slices. A common envelope records intent, scope, inputs, allowed actions, current phase, dependencies, outputs, disposition, closure conditions and continuation links. Domain policies decide when an action is ready and what conclusion means.

Separate **runtime phase** (executing, validating), **disposition** (waiting, blocked, failed, cancelled, completed) and **objective outcome** (achieved, partly achieved, not achieved, unresolved). Finishing an execution is not proof its objective succeeded. A returned dictionary, a critic’s approval phrase or a populated output field cannot close a loop by itself. Waiting has an owner and resume condition; retries have attempt records and a budget; cancellation preserves unresolved obligations and partial artifacts.

Add `kageyoni/processes/outcomes.py` for result normalization and closure checks, and `kageyoni/processes/scheduling.py` for policy dispatch. Pipeline dependency readiness, encounter turns, timed processes and social response obligations use distinct policies through the same runner. Keep domain rules in their existing workspace/interaction owners. Nested loops carry parent/child and continuation links; do not transplant a mission runner that forbids nesting and assumes disjoint workspaces into shared world interactions.

### Extraction and ownership map

The companion audit is the source ledger, including exact commit pins and file references. “Adapt” below means reproduce the bounded mechanism behind Kageyoni’s contracts and tests, not copy the whole runtime or claim compatibility.

| Mechanisms | Repository contribution and limit | Kageyoni owner / slice |
|---|---|---|
| Attend, Orient | Older world engines connect identity, scene and reactions; Booder selects from profiles. Mock reactions and fixed name overrides do not establish individual intelligence. | context, interactions, nodes / V2–V4 |
| Interpret, Investigate | 10 Shadows exposes knowledge deficits; Mugen fetches research metadata. Store lookup is not acquisition, and metadata is not source-level evidence. | research, handoff / V5 |
| Provision | Conditional capability/resource selection in 10 Shadows; host/manual adaptation in Ten Shadows Control. Cross-host operation remains unverified. | execution, context / V2, V7 |
| Compose, Express | Mugen decomposes media and compiles a new form; some semantic fields are hardcoded. Preserve evidence, unknowns and intended audience before recomposition. | methods, documents / V5 |
| Attempt, Repair | Nelson binds intent, workflow, criteria and artifact identity; Mugen retains retry feedback. A retry must actually execute, and missing outputs remain failures. | processes, pipeline, artifacts / V1, V7 |
| Reconsider | Nelson reopens objections; 10 Shadows retracts supported claims. Losing one support should trigger scoped reevaluation when independent support remains. | learning, interactions / V3 |
| Remember | Scribe indexes scenes and blind spots; older engines serialize identity. Candidate staging must not become qualified memory before validation. | network_store, learning / V1–V3 |
| Differentiate | Booder persists experience-derived profiles and routes using them. Scalar success increments are not competence; routing needs a no-eligible-node result. | node_methods, capability_claims, network / V3, V6 |
| Abstract, Transfer | 10 Shadows proposes motifs; Ichimonji supplies conceptual reification. Inspected motif matching loses directed structure and misses persisted motifs after restart. | methods, transfer / V2, V5 |
| Collaborate | Mugen and Booder coordinate roles. Role labels do not make independent experts, and an aggregation acknowledgement is not a synthesis. | network, contribution receptions / V6 |
| Recover | Nelson artifact/dependency binding and pipeline recovery patterns are useful. Booder timeout recovery can report completion without another attempt. | pending_effects, scheduling, transitions / V5, V7 |
| Evaluate | Espada emphasizes measured artifacts and adversarial checks; Job Hunter separates stats and generated insights. Preserve creative quality as a legitimate outcome alongside technical correctness. | evaluation fixtures, receipts / every slice |
| Evolve | Reflection/scar stores and workflow proposals suggest policy development. Mock memory, fixed reflections and unevaluated insights do not demonstrate improved future decisions. | learning, workflow_policy_revisions / V8 |

Preference, practiced skill, demonstrated competence, available capacity and permission remain separate fields. Game progression can use authored rewards; those rewards cannot authorize tools or establish professional expertise. Routing should permit bounded exploration and comparisons so early winners do not monopolize every future task.

### Five complete compositions to demonstrate

1. **Situated learning — V2–V3:** a node encounters a scoped situation, applies a recorded method, experiences a consequence, qualifies a lesson and uses it in a later relevant choice. Preserve failures and counterevidence. Success requires an attributable change in that later choice, not a larger experience count.
2. **Creative transfer — V5:** decompose an evidenced episode or source, represent its roles and constraints, propose a destination mapping, identify mismatches and produce a checked document. Preserve individuality through method selection and revision; do not depend on a name or decorative voice alone.
3. **Adaptive inquiry — V5:** detect a deficit, select a permissible source, acquire its contents, extract supported claims, test relevance and counterexamples, then answer or explicitly remain unresolved. Report coverage and uncertainty without equating retrieval with understanding.
4. **Living interaction — V4:** a conversation changes the available choices during an encounter; ordinary authored rules resolve actions, update knowledge only for appropriate participants, preserve promises and allow a later continuation. Demonstrate this bounded scenario with AI disabled; ambiguous interpretation can use the existing judgment handoff.
5. **Coordination development — V6–V8:** nodes contribute distinct methods, receive and contest each other’s work, consume selected results and compare outcomes against a simpler approach. A policy revision becomes active only after a scoped trial supports it; failed trials remain visible and reversible.

No composition requires paid model APIs. Code handles state, eligibility, deterministic resolution, evidence binding and recovery. The authorized host or manual exchange handles interpretation where a rule is insufficient. Fictional scenes may freely contain creative proposals within their authoring rules; factual claims about external sources and achieved technical outcomes require the corresponding evidence.

## 22. Repository-derived acceptance scenarios

These are tests to implement, not passed Kageyoni tests. “Observed” points to the selected-source probes in the companion audit. “Designed” covers inspection-derived risks or adjacent cases. Expected outcomes specify Kageyoni’s intended policy; they do not retroactively define every source repository’s requirements.

| ID | Evidence / scenario | Independent expected outcome | Owner |
|---|---|---|---|
| T40 | Observed: REQUIRES ignored by readiness | A parent waits for every declared blocking dependency type; DEPENDS_ON control still blocks, and completion releases the parent. | V7 |
| T41 | Observed: motif disappears after restart | An eligible persisted method is retrievable after a new process opens the store, with identical revision and scope. | V2 |
| T42 | Designed: same labels, different topology | Reversed edges or changed causal roles are not treated as equivalent merely because label sets match; destination mapping reports the mismatch. | V5 |
| T43 | Observed policy mismatch: alternate support invalidated | Withdrawal of one support preserves independent evidence and triggers reevaluation; it does not automatically assert truth or falsehood. | V3 |
| T44 | Observed: invented visual and premise | Unrelated transcript fixtures retain exact sourced words and leave unsupported visual/premise fields unknown or explicitly proposed; an independently authored oracle checks meaning. | V5 |
| T45 | Observed: pending human result marked completed | Workflow remains waiting with a specific resume condition; dependent effects do not execute. | V1 foundation, V7 integration |
| T46 | Observed: tool failure marked completed | Failed required work blocks successful parent closure; a successful control still completes and passes its actual output value. | V1 foundation, V7 integration |
| T47 | Observed: timeout recovery without retry | Receipt records actual additional invocation or explicit unresolved failure; a recovery flag alone cannot complete the task. | V7 |
| T48 | Observed: all candidates silenced yet one selected | No eligible participant yields a typed blocked/unassigned result and an actionable reason; no arbitrary fallback bypasses eligibility. | V6 |
| T49 | Positive persistence control extended | Qualified experience survives reopening; preference changes neither confer permission nor establish destination competence. | V3 |
| T50 | Designed: staged memory enters later context | Unverified candidate content is excluded from qualified retrieval, while remaining inspectable as a scoped draft. | V3 |
| T51 | Designed: aggregation loses contribution bodies | Synthesis inputs contain permitted actual contributions; reception records show which affected the output and preserve disagreement. | V6 |
| T52 | Designed: critic approves an invalid artifact | Independent output checks reject the invalid result regardless of an approval phrase, while a valid artifact passes. | V7 |
| T53 | Designed: reflection repeats fixed advice | An evaluated later decision references the relevant lesson and its applicability; irrelevant or contradicted lessons are excluded/revised. | V3, V8 |
| T54 | Designed: proposed policy promoted without trial | Proposed policy remains inactive until scoped comparison evidence supports activation; restore of the previous policy preserves intervening task history. | V8 |

Use disposable fixtures and actual owning modules. Keep assertions distinct from model-generated explanations. A source-module probe passing is not an integration pass, and a mock adapter only proves the mocked contract. Re-run the relevant baseline and focused regressions after implementation; run broader tests when shared behavior changes or a release gate requires them.

### Revised execution order and stop conditions

**Next authorized build packet remains P0 + V1.** First establish the authoritative engine lineage, prove restore and resolve transaction ownership. Then ship one inspectable persistent node and a minimal process-result contract. Do not make the entire research or swarm system a prerequisite for this first usable increment.

Next demonstrate V2–V3’s experience → method → later decision loop before adding more node personalities. V4 brings coherent introduction and the bounded composite CLI encounter. V5 proves the workspace round trip plus one creative transfer and inquiry path. V6 proves contributions are received and useful. V7 adds exact-artifact repository/pipeline execution and recovery. V8 verifies packaging and controlled policy evolution. Independent work may proceed when its prerequisites are met, without changing these evidence gates.

G1 now also traces T45–T48 through result and closure ownership. G3 requires T41, T49, T50 and T53 alongside the original method controls. G4 includes T42–T44; G5 includes T48/T51 and matched benefit comparisons; G6 includes applicable T40–T54 and the original migration/recovery gates. These gates remain pending. Repository research informs the plan; it does not satisfy the engine’s acceptance gates by itself.


## 23. Execution checkpoint — foundation implemented, 20 September 2026

This checkpoint supersedes earlier future-tense statements about P0 and V1. The design remains revision 2; implementation is delivered separately as **Kageyoni-v9.5-Foundation.zip**. It is the first milestone, not a completed v9.5 release.

| Stage | Actual evidence / status |
|---|---|
| P0 | Latest inspected saved lineage recovered from Kageyoni-Resumed-20260919.zip: main revision 60, 60 events, 237 records. Engine source matches the terminal/v8 archives. Backup and restored database contents match; original archives preserved. This does not certify inaccessible or unsaved newer play. |
| V1 | Implemented migration 009/node interface 1, application service, stable character bindings, branch-local operational history, visibility-filtered profile reads, node-init/bind/read/list CLI commands and terminal menu. Sciel’s active record `sciel` is bound on the working copy; `roster-sciel` remains separate. |
| Transaction foundation | Five pre-fix failures reproduced. Engine.apply now uses owned transactions/savepoints; decision, writing and seed callers explicitly commit their own transactions. Preview, duplicates, errors, rollback, deferred constraints and process death are tested. Other transaction-owning APIs are not declared composable. |
| Minimal process contract | Typed disposition/objective/result validation and required-child closure implemented. Waiting and failure cannot silently become completion through this contract. No durable scheduler or autonomous process executor is claimed. |
| Verification | 168 baseline tests; 193 final tests including 25 foundation tests. Focused scenarios cover historical upgrades, interrupted migration/retry, privacy, concurrent idempotency, branch isolation, CLI/menu use and backup/restore. No whole-engine v9.5 acceptance or benefit comparison is claimed. |
| Real campaign preservation | All preexisting non-version tables unchanged by migration and node binding. World revision/event count remain 60. Pending decision fingerprints preserved by excluding the operational-only node-interface version from world-resolution fingerprinting. Restore preserves the node and its history. |
| V2–V8 | Not yet implemented. Next build: V2 consequential method expression, then V3 qualified experience affecting later use. |

**Gate update:** G0 and G2 have foundation evidence for the inspected revision-60 lineage; production promotion against any newer save still requires a fresh lineage check. G1 remains a design-level gate for unimplemented interactions and transfer paths. G3–G6 remain pending. The new node record does not establish a learned method, independent intelligence, cross-domain competence or measured network advantage.

The build’s `FOUNDATION-HANDOFF.md`, evidence receipts, source hashes and tests are the implementation record. World replay remains separate from operational-node history; full database backup/restore preserves both. No scene was advanced and no fictional ability was granted by this work.


## 24. Execution checkpoint — bounded V2 implemented with subagents

P0/V1 remain delivered. The same cumulative **Kageyoni-v9.5-Foundation.zip** now adds three V2 subsets; `V2-HANDOFF.md` is its current entry point. Subagents implemented method storage and execution separately, while a third agent reviewed the boundaries and wrote independent adversarial tests. The primary agent integrated migrations, contribution persistence, CLI/menu use and delivery.

| Subset | Implemented behavior | Evidence and limit |
|---|---|---|
| V2a — Method inventory | Migration 010, immutable method/assignment revisions, exact world source snapshots and ledger ancestry, branch/workspace isolation, explicit experimental authorization and revocation. | 11 focused method tests. Persisted operator-authored methods are not learned mastery. Unassigned private drafts cannot suppress an assigned public revision. |
| V2b — Consequential expression | Registered constraint ranking and counterexample checking; exact permitted field/value matching; snapshots and fingerprints; waiting packets for unresolved operations/conditions. | 20 expression tests. Rename and paraphrase controls preserve actual artifacts; changed operations change checked results. Completion covers the registered operation; broader task success remains unresolved. |
| V2c — Inspectable contribution | Migration 011, immutable receipts and small JSON artifacts stored together in SQLite, idempotent requests, current visibility checks for historical character views, menu 14 and scripted commands. | 11 integration/migration tests plus 12 independent adversarial tests. Actual process death, rollback, restore, checksum mismatch and exact artifact inspection exercised. General external/file effects remain later work. |

The complete cumulative suite passes **247 tests** (193 prior + 54 new). These are functional and boundary tests, not a benchmark of cognitive capability or practical advantage. Independent review reproduced a pinned-public-method/private-draft bug and identified an unreadable-waiting-receipt bug through inspection; both were corrected before the final run. All tests and the synthetic comparison are included and reproducible.

The controlled demo compares two declared editing-plan fixtures using time versus satisfied-check count. Its first three artifacts are identical under name/prose changes; revising the actual comparison operation reverses the ranking. This establishes a narrow mechanism of consequential expression, not the usefulness of those criteria in an actual production decision. Sources retain their declared status, and field equality does not certify factual truth or domain relevance.

The revision-60 campaign was migrated on its existing working copy and restored successfully. All preexisting non-version tables, pending-decision fingerprints and story events are unchanged. Sciel’s node remains present; no synthetic method or unsupported expertise was assigned to her. Demo methods and contributions live in a separate explicitly synthetic database.

**Next: V3.** Demonstrate a recorded outcome becoming a qualified, scoped lesson that changes a later relevant choice; preserve contradictory outcomes, support revision, and exclude irrelevant lessons. G3 remains pending. V4–V8 and cross-workspace/collective benefit comparisons remain unfinished. The bounded V2 substrate must not be presented as evidence those capabilities already exist.


## 25. Execution checkpoint — bounded V3 implemented with subagents

This checkpoint supersedes section 24's next-step status. The same cumulative **Kageyoni-v9.5-Foundation.zip** now includes V3 experience and development; `V3-HANDOFF.md` is the entry point. Design revision 2 and prior checkpoints remain preserved. Three subagents handled storage, lesson application and independent review; the primary agent integrated the services, CLI, demonstration, migration and recovery.

| Subset | Implemented behavior | Evidence and boundary |
|---|---|---|
| V3a — Observed experience | Migration 012 adds immutable outcomes, lesson revisions, reviews and request history. An outcome cites exact fields from world events later than its contribution. Repeated observation records retain their original contribution identity. | 9 storage tests. Calculation completion is not observed success; status, rationale and causal interpretation remain attributed operator judgments. Unknown outcomes cannot qualify a lesson. |
| V3b — Development affecting later use | A qualified lesson substitutes parameters of a registered operation while preserving the base method revision, guards and checks. Exact node/branch/workspace/domain/context and assignment determine eligibility. Conflicting substitutions block execution. | 15 development tests. Proposed, irrelevant, hidden, stale, contested and retired lessons do not activate. Scope is a full evidenced context match; cross-domain generalization is not implemented. |
| V3c — Counterevidence and durable integration | Counterevidence suspends the current revision and carries into revisions. Cosmetic edits cannot restore it without changed operational scope/parameters or a new completed trial origin. Menu 15 and eight outcome/lesson commands expose the loop. | 14 independent adversarial tests plus 8 integration/migration tests. Reopen, exact retry, process death, outer rollback, interrupted migration and backup/restore exercised. Changed parameters authorize another experiment; they do not prove a contradiction resolved. |

The cumulative suite passes **293 tests** (247 prior + 46 V3). The separate synthetic editing demonstration records an initial choice and a later shortfall. Qualification changes the selected plan on a later task with different candidates while the original method stays at revision 1. Proposal-only and unrelated-context controls preserve the original choice. Reopening preserves application; contrary feedback suspends it; a reviewed revision produces a different tradeoff while retaining both observations. Eight assertions inspect actual outputs. These are mechanical and behavioral controls, not measured production benefit or autonomous lesson discovery.

Independent review reproduced and corrected two privacy failures: a hidden reference inside a public observation record could influence a public choice, and a descendant lesson could inherit that hidden influence through a prior contribution. Visibility now checks measured fields and exact historical lesson/review ancestry without reexecuting old decisions. Owner-authored outcome explanations are withheld from character views. The tests remain in the delivered source.

The revision-60 campaign was migrated and restored. All **97 preexisting non-version tables**, Sciel's node and pending-decision fingerprints are unchanged; the save still has 60 events and 237 records. New outcome and lesson tables are empty. No scene, ability, method or learned expertise was invented for Sciel. `recovery/pre-v3-learning.sqlite` retains V2, and the installed/restored V3 checkpoints have matching table contents. Full database recovery preserves learning history; ordinary world-event replay does not reconstruct operational learning tables.

**File connections:** `learning_contracts.py` validates declarations; `learning.py` owns provenance, review and persistence; `development.py` selects scoped interventions; `expression.py` binds them to checked execution; `contributions.py` preserves the exact result. `application.py`, `__main__.py` and terminal menu 15 share those services. `migration_012.sql` owns the four new tables. `examples/v3_demo.py`, `docs/V3-EXPRESSION-CONTRACT.md` and the V3 evidence files make the behavior reproducible and inspectable.

**Acceptance update:** T22, T43, T49, T50 and T53 now have bounded synthetic implementation evidence alongside V2's T41 and expression controls. T43 preserves unaffected evidence and requires a new scoped review after another support becomes stale; it does not automatically assert that the remaining evidence establishes truth. G3 has functional evidence for this registered-operation loop, while validation on representative work and comparisons of practical advantage remain open. This is not whole-engine acceptance, learned professional competence or evidence of swarm benefit.

**Next: V4.** Build coherent provisional character introduction and Will interpretation, then demonstrate an authored encounter combining dialogue, ability use and consequences with AI disabled. Carry V3 experience through the encounter without duplicate effects or invented canonical facts. V5–V8 retain workspace transition/transfer, collective contributions, external pipeline recovery and controlled workflow evolution. Those capabilities and G4–G6 remain unfinished.


## 26. Execution checkpoint — V4–V8 built together

This checkpoint supersedes section 25's next-step status. At Levi's direction, the remaining five vertical slices were implemented concurrently with subagents and integrated into the same cumulative **Kageyoni-v9.5-Foundation.zip**. The design and earlier checkpoints remain preserved. `V9.5-HANDOFF.md` is the current operational entry point. This is a bounded implementation of all eight slices, not a claim that every imagined future domain or form of intelligence is implemented.

### Delivered structure and connections

| Slice | Implemented files and responsibilities | Connection and limit |
|---|---|---|
| V4 — Character and world interaction | `intelligence/genesis.py`, `workspaces/world.py`, migration 013 | Provisional identities and separate Named Will interpretation; authored encounter graphs call existing dialogue, ability and event mechanics. Required nested loops block parent closure; waiting judgments, current revisions, retry identities and continuation history persist. Unknown capabilities remain unknown. |
| V5 — Workspace and transfer | `workspaces/registry.py`, `transitions.py`, `documents.py`, `contracts.py`; `persistence/artifacts.py`; `intelligence/transfer.py`; migration 014 | World context and exact checkpoint feed scoped document work. Actual source bytes/passages support drafts and separate brief obligations. Directed method mappings require executed destination trials. Immutable artifacts and recovery connect draft bodies to later consumers. This is bounded capture through files/current host, not an autonomous web crawler. |
| V6 — Collective operation | `intelligence/network.py`, migration 015 | Persistent node contributions and actual document bodies reach reception and synthesis records. Exact body consumption, source ancestry, duplication and disagreement remain inspectable. `engine:kageyoni` is an operational coordinator identity, distinct from characters and from the real user. Roles do not constitute independent expertise. |
| V7 — Repository and pipeline | `workspaces/repository.py`, `pipeline.py`, migration 016 | Real local edits, subprocess tests, mapped registered operations and exact-byte promotion; dependency-aware execution, actual downstream values, manual judgments, bounded retries and effect reconciliation. External paths are pinned to the originating database and require explicit validated rebind after relocation. Test code needs an authorized local execution environment. |
| V8 — Daily operation | `operations.py`, `console.py`, migration 017; application/CLI/terminal integration; `resources.py`, `pyproject.toml`, `setup.py`, `MANIFEST.in` | One service boundary, menu 16 and 78 guided action signatures; persistent settings; portable database/artifact bundles; fresh install and upgrade. A scoped validation-order policy is proposed, actually trialed, activated and rolled back while preserving history. All required checks remain present. |

Python 3.10+ and SQLite remain the foundation; the runtime has no third-party dependencies or model API requirement. The installable wheel carries the canonical SQL resources. The source archive also carries the terminal launcher, examples, campaign, evidence and recovery copies. No automatic external deployment, remote push, paid model fallback or OS sandbox is implied.

### Closed loops and intelligence boundary

The engine now owns the durable loop for supported actions: inspect state and obligations → choose a permitted operation → execute or wait with a reason → check actual outputs → persist effects and experience → offer the next supported action or close the scoped interaction. Encounters, documents, transfer trials, collective reception, repository checks, pipeline dependencies and policy development keep their own completion rules. A successful registered operation does not declare its broader human objective achieved.

Code executes authored mechanics and registered procedures. Human or current-host intelligence supplies interpretations, new prose, conceptual mappings and unresolved choices through explicit handoffs. Stored method rationale can guide that host; the registered numeric checker does not acquire semantic understanding merely because a character owns it. Named Wills remain attributed attempts to understand Primordial Will, and provisional profiles do not force unknown innate mechanics into invented certainty.

### Evaluation on an actual project task

A frozen V3 handoff source, a 180-word final budget and ten requirements were recorded before generation. Four actual current-host conditions were executed: plain response; character style only; one persisted method configuration; and two differentiated contributions followed by synthesis. Source facts and final length limit were shared; the collective used extra intermediate context and two additional host tasks. Outputs, exact source/configuration records, checker-owned destination trials, received bodies and the final composition are retained in `evidence/host-comparison/`.

| Condition | Final words | Host task invocations | Requirements met / partial / missing |
|---|---:|---:|---|
| Plain host | 162 | 1 | 8 / 1 / 1 |
| Style only | 166 | 1 | 9 / 0 / 1 |
| Persistent single-method configuration | 173 | 1 | 10 / 0 / 0 |
| Differentiated contributions and synthesis | 157 | 3 | 9 / 1 / 0 |

These are attributed agent assessments against the frozen rubric, not blind human judgments or a statistical study. The partial backup/restore judgment is explicitly exposed in the report. Intermediate collective text totaled 345 words; host task counts are not inference-call, token, elapsed-time or monetary measurements. The collective did not improve on the simpler configured response in this diagnostic. No causal gain from persistence itself is established: additional instructions and model variation remain competing explanations. The proposed 32-run, four-task pilot remains unexecuted.

**Operating decision:** retain collective execution as an available capability; use a single configured node for this kind of concise handoff unless another concrete need justifies coordination. Evaluate useful differentiation on actual outcomes instead of interpreting more characters or more records as an advantage. G5's useful-collective-work claim remains open despite a functioning collective mechanism and completed diagnostic.

### Preservation, recovery and acceptance evidence

The inspected real campaign has been upgraded through migration 017, backed up and restored. All **101 preexisting non-version tables**, Sciel's node and pending-decision fingerprints are unchanged. It remains revision **60**, with **60 events and 237 records**. New demonstration activity is absent from the campaign; migration adds the separate `engine:kageyoni` coordination identity. `evidence/v4-v8-campaign-integration.json` records the actual table comparison and restore. This verifies the supplied lineage, not an unseen newer save.

Portable bundles contain the database, referenced artifact bytes and integrity manifest. External repository working trees, source folders and pipeline output folders remain separately carried dependencies. Import reports them as unresolved; execution is blocked until explicit rebind checks replacement roots and exact existing effects. Receipt history alone does not prove that an external file exists after relocation. Full database recovery and world-event replay remain distinct operations.

`docs/V4-V8-ACCEPTANCE.md` freezes the positive/failure obligations. `docs/V4-V8-REVIEW.md` distinguishes independently reproduced defects from issues corrected during source review. The release corrects premature encounter closure, ignored required children, manual-wait false completion, duplicate calculation votes, captured nested-reference leakage and invented transfer qualification. Focused tests also exercise interruption after external effect, real retry, stale candidate promotion, corrupt portable artifacts and policy rollback. Root integration adds historical campaign upgrade, migration rollback/process-death controls, public CLI/menu use, installed-wheel checks and the connected demonstration. Exact final run counts and per-row evidence are in `docs/V9.5-RELEASE-EVIDENCE.md` and `evidence/v4-v8-full-tests.txt`.

The full-chain disposable demonstration is `examples/full_chain.py`, with its executed report at `evidence/full-chain-report.json`. It connects the same characters' journey through document transfer, actual collective body consumption, repository repair, pipeline output and portable reopening while preserving the world checkpoint. Authored fixture values remain explicitly synthetic; this demonstration is not evidence of autonomous expertise.

**Gate update:** G0/G2 retain lineage-specific baseline and recovery evidence. G1/G3/G4 have executable evidence for the implemented contracts and registered-operation paths. G6 has source and installed-package operation, historical migration and recovery evidence for the tested local environment. G5 remains an empirical usefulness question: this diagnostic provides no collective advantage over the single configured condition. Open-ended semantic accuracy, professional competence, universal transfer, autonomous learning and general productivity gains remain outside these implementation results.

**Final execution counts:** 397 cumulative tests passed; the connected demonstration passed 20 controls, with three full-chain integration tests. The installed wheel exposes 78 guided actions and includes migrations through 017. These counts measure the exercised contracts, not intelligence level or practical superiority.
