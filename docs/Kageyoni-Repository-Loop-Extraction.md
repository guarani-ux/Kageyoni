# Kageyoni — Recursive Repository Loop Extraction

20 September 2026 · Research and proposed integration, not an engine release

## 1. What the deeper investigation changes

The repositories contain different sections of the same larger process: preserve an intention, encounter a situation, select a way of acting, create a consequence, interpret what happened, and use that experience later. The strongest opportunity is to connect these sections without flattening their meanings.

The earlier extraction map leaned too heavily on routing and verification. It missed three substantial sources of creative capability:

1. **Decomposition and recomposition:** media structures can become reusable methods for turning experience into an adaptable representation and expressing it in another form.
2. **Situated individuality:** older world engines carry identity, perception, reactions and state evolution, while later operational systems carry execution and evidence. Their conjunction is relevant to characters that remain themselves across workspaces.
3. **Conditional development:** the Booder differentiation code already persists experience-derived profiles and uses profiles in routing. That is a partial precursor to the proposed intelligence inventory, although its updates and success criteria need substantial qualification.

The integration target should be **a shared protocol for loops and their connections**, with domain-specific resolvers. One large universal scheduler is not enough: build dependencies, social reciprocity, time-based processes and open-ended relationships have different scheduling and completion semantics.

The source has mechanisms worth adapting, but also places where the data says “complete,” “qualified,” “learning” or “structural” more strongly than the implementation supports. Preserve the useful operation; do not import the label as proof.

## 2. Scope and evidence

This pass inspected recursive Git trees across twelve repositories and downloaded **215 selected source, test and design files from eleven** into a disposable audit directory. Of those, **187 Python files were parsed into a symbol/import index**. Selection followed relevant definitions into storage, callers, schemas and tests. It was not a line-by-line audit of every file on GitHub, nor a complete runtime validation of these applications.

The twelfth repository, `komorebisans`, was compared by Git blob identities with `Outer-Sanctum`: 753 of 754 files match exactly at the inspected revisions; only `.gitignore` differs. Its shared source was not redundantly downloaded or counted as independent evidence.

Evidence labels used below:

- **Observed source:** directly inspected implementation or design text.
- **Executed probe:** actual selected modules exercised offline, with temporary storage.
- **Proposed transfer:** an adaptation for Kageyoni that has not been implemented.
- **Unestablished:** not demonstrated by this investigation; not necessarily absent everywhere.

Fifteen focused probe assertions were executed: nine exposed incompatibilities with proposed integration requirements and six positive controls behaved as expected. These were deliberately selected boundary cases, **not a representative pass rate or a ranking of repository quality**. No model APIs, live agents, external side effects, campaign updates or repository writes were used. The ordinary pytest command could not run because pytest is unavailable in this runtime. Full upstream suites are therefore unrun. The standalone probes load actual submodules while bypassing broad package initialization; they do not prove whole-application startup compatibility.

Pinned revisions and the retrieved-file inventory appear in the appendices. Links in the report resolve to those revisions.

## 3. The unit to extract

Extract a small operation with its state and feedback contract—not a project name, character title or prompt alone.

A portable loop definition needs:

| Field | Purpose |
|---|---|
| Trigger and scope | Why it starts, whose perspective it uses, and which workspace/branch it can affect. |
| Question, intention or obligation | What is unresolved; an interaction need not be framed as an optimization target. |
| Required context | Relevant observations, applicable rules, permissions, methods and known unknowns. |
| Available actions | Legal operations with typed inputs and effects; optional proposals outside the current vocabulary. |
| Resolver | Rule, tool, human or AI judgment that performs a bounded step. |
| Observation | What actually happened, distinct from what was proposed or expected. |
| Assessment | What the observation establishes, contradicts or leaves open. |
| Continuation | Resume, retry with changed information, branch, wait, interrupt, conclude or start a related loop. |
| Retained consequence | Durable world change, artifact, commitment, belief revision or candidate lesson. |
| Applicability and limits | Conditions under which the method can be reused. |

The same definition can have many instances. Each instance keeps its own participant state, evidence, pending response, revision and outcome. Shared mechanics do not imply shared knowledge.

A character's distinctiveness can influence attention, preferred questions, method selection, interpretation, stopping choices and willingness to collaborate. It should not automatically alter factual truth, grant tool permission or certify expertise.

## 4. Extractable mechanisms, recursively traced

### 4.1 Nelson: obligations remain connected to changing evidence

**Trace:** task contract → workflow state/events → execution records → criterion/assessment evaluation → dependency binding → delivery or reopened objection. Mission status additionally checks child completion and whether predecessor evidence still matches the binding used when the child began.

**Extractable loops:** preserve original intent; bind a judgment to its inputs; investigate an objection; repair and re-evaluate; suspend/resume an obligation; revisit downstream work after its basis changes.

**Kageyoni application:** a promise, unresolved question or disputed consequence can persist beyond the scene. Completion becomes specific: an offer was accepted, a cost settled, a source checked, or a question left unresolved. A changed map can reopen a route plan without deleting the original decision.

**Boundary:** `missions.validate()` forbids nested missions and requires disjoint workspaces. This is incompatible with directly nesting conversation, battle and ability loops that affect one shared world. Extract obligation and revision-binding ideas; implement interaction-specific scheduling and transactions in Kageyoni. Nelson's sequential UNDERSTAND→RESEARCH→TOOLS→EXECUTE→VERIFY→DELIVER workflow should not be imposed on every gesture or line of dialogue.

**Design lesson:** depend on the particular facts that matter. A character learning an unrelated recipe should not invalidate a pending sword strike. Nelson's dependency bindings offer a useful starting point for selective re-evaluation, but world-record dependencies need their own representation.

Sources: [workflow][nelson-workflow], [dependencies][nelson-dependencies], [missions][nelson-missions], [objections][nelson-objections].

### 4.2 10 Shadows: a deficit can become the next action

**Trace:** model response declares a deficit → resolver checks knowledge/tool/evidence stores → provision result merges into context → context is recompiled → model is invoked again, within a bound. A separate capability-gap planner searches registered capabilities, creates acquisition targets and replans after a supplied qualification callback.

**Extractable loops:** notice what is missing; distinguish missing knowledge from missing tools or evidence; obtain the missing item; rebuild the relevant context; resume the original objective.

**Kageyoni application:** “I don't know how this inscription works” can offer inspect, ask, compare, experiment, leave or seek someone else. The player does not need to formulate an entire new workflow. In a business-research workspace, “we have products but no supported account of customers” can trigger a targeted inquiry.

**Boundary:** the in-process resolver performs dictionary lookup, not open-world acquisition. Provisioning labelled evidence does not establish its truth. The inspected context compiler places caller-supplied domain knowledge under an authoritative category; the new context service must retain source status and perspective rather than trusting the category name.

Sources: [deficit protocol][shadows-deficit], [context compiler][shadows-context], [gap planner][shadows-gap].

### 4.3 10 Shadows: conditional capabilities and selective effort

**Trace:** capability declares supported environments and conditions → applicability check → search policy selects a single attempt, critique/repair or several candidates → evaluator produces feedback → revised attempt.

**Extractable loops:** check fitness for the situation; spend effort proportionate to uncertainty; carry a specific failure explanation into the next attempt.

**Kageyoni application:** familiar commands run through rules. Ambiguous or unfamiliar situations get a bounded judgment request. A character can try a practiced method, seek help, or explore another approach. More voices are used when their distinct contributions are needed, not as a default ritual.

**Boundary:** a default smoke evaluator in `candidate_search.py` compiles and executes candidate code with normal builtins and checks a marker string. It is neither isolation nor a general task-correctness oracle. Do not port it as the execution boundary. Fictional resource statistics must not automatically purchase larger real execution privileges or budgets.

Sources: [conditional capability][shadows-capability], [candidate search][shadows-search].

### 4.4 10 Shadows: analogy as a candidate, not a fact

**Trace:** register a motif → store its type/relation labels → compare against target labels → rank transfer proposals.

**Extractable loop:** recognize a potentially similar structure → explain the mapping → identify where it breaks → try a destination-specific consequence → retain or revise the transfer.

**Observed limits:** matching uses Jaccard overlap over sets of node types and relation types. It does not compare edge endpoints, direction patterns, multiplicity, causal roles or constraints. Different graph structures with the same labels therefore look identical to this function. Registered motifs are persisted to SQLite, but retrieval uses an in-memory list; an executed probe found one proposal before constructing a fresh engine and zero afterward.

**Proposed upgrade:** a transferable method records roles, directed relationships, causal rationale, preconditions, failure modes, source episode, adaptation and destination evidence. This is the core of moving Sciel's way of thinking across domains without merely copying Sciel's voice. Exact Sciel methods must be drawn from established character evidence; this audit does not assign them.

Source: [structural transfer][shadows-transfer].

### 4.5 10 Shadows: feedback on beliefs and dependencies

**Trace:** a source is retracted → incoming support/derivation edges locate affected claims → dependent nodes are invalidated → later planners must reconsider their use.

**Extractable loop:** changed evidence → identify dependent interpretations → re-evaluate supported conclusions → expose changed options.

**Observed limits:** the executed alternative-support probe invalidated a claim when one of two supports was retracted. For Kageyoni, losing one support usually means re-evaluation, not automatic falsity. Also distinguish the engine's world truth from an individual's belief: a character cannot update from information they never received.

The scheduler has a related semantic mismatch: topological ordering accounts for REQUIRES and DEPENDS_ON, but the ready-frontier method checks outgoing DEPENDS_ON only. A probe returned a parent as ready despite an unfinished REQUIRES prerequisite. Explicit edge semantics are necessary before importing this scheduler.

Sources: [truth maintenance][shadows-truth], [scheduler][shadows-scheduler].

### 4.6 Mugen: production, repair and declared targets

**Trace:** router → planner → declared target contract → worker → gate → retry with previous artifact and failure reason → attempt-specific ledger entries. The orchestration layer captures worker/checker exceptions as unknown outcomes.

**Extractable loops:** interpret intent into a specific action; produce; inspect; revise using the actual rejection; retain each attempt; stop when retry cannot help.

**Kageyoni application:** an ability proposal names the target, intended effect, costs and conditions before resolution. A failed crafting or document attempt returns a concrete reason that can change the next action. Free prose remains expressive; executable fields remove ambiguity at the action boundary.

**Boundary:** Mugen's planner checks mostly structural features, and its critic gate accepts a phrase in generated text. That phrase is a signal to inspect, not independent proof. Separate producer/checker labels do not establish independent expertise. The inspected retry function also assumes a produced artifact exists after orchestration returns; a worker exception can leave no artifact, making retry handling itself a further integration risk.

Sources: [planning][mugen-planning], [orchestrator][mugen-orchestrator], [retry][mugen-retry].

### 4.7 Mugen and Scribe: experience can be decomposed and recomposed

**Trace:** source material → deconstruction schema → stored template → compiler → new artifact. Separately, Scribe indexes video/scene/blindspot records → queries pacing and recurring anomalies → provides reports or conditioned source artifacts to later work.

**Extractable loops:** observe → represent relevant structure → compare experiences → select a reusable pattern → adapt to a new situation → inspect the result.

This is more than document templating. The proposed transferable unit might be an explanation sequence, an approach to uncertainty, a way of teaching, a contrast that makes an idea visible, or a method for coordinating contributions. The destination can change while the relation between its parts survives.

**Critical boundary:** Mugen's transcript decompiler assigns fixed camera/mood/hook/premise defaults. A gardening transcript produced a talking-head close-up and “Manual coding is too slow.” Its existing decompiler test uses a coding-themed transcript and checks type, title, hook text, nonempty rows and positive pacing; those assertions would not reveal the unrelated-domain problem. Transcript-derived observations, authored proposals and unobserved visual fields must be separate.

Scribe's “pattern miner” performs real SQL aggregation, but counts and pacing rankings do not establish why a video worked. Its runner indexes during the staging step, before the later verification/commit stages; adaptation needs candidate-versus-accepted storage so a rejected run cannot silently become qualified memory.

Sources: [decompiler][mugen-decompiler], [decompiler tests][mugen-decompiler-tests], [compiler][mugen-compiler], [Scribe miner][shadows-miner], [Scribe runner][shadows-scribe-runner].

### 4.8 Mugen research: retrieval is one subloop of understanding

**Trace:** source-specific fetcher → titles/URLs and metadata → mechanical artifact-shape gate → model relevance assessment function.

**Extractable loop:** ask → locate material → inspect what it actually says → relate it to the question → identify gaps → refine or stop.

**Boundary:** the mechanical gate checks a nonempty result list and URL/source fields. The relevance function sends result metadata to an AI; this does not establish that full pages were read or that a passage entails an answer. Fetchers include social/news sources that should not automatically become the default evidence policy for every domain.

For the business example, use an official-source acquisition adapter, preserve passages and capture times, distinguish stated values from demonstrated behavior, and retain unresolved contradictions. Keep “no source returned,” “source inaccessible,” “irrelevant source” and “source contradicts the hypothesis” as different outcomes. The mine is useful only when the sample remains linked to where and how it was collected.

Source: [research skill][mugen-research].

### 4.9 Hidden Booder Village: differentiated profiles already affect routing

**Trace:** `record_experience()` changes a persisted domain score → threshold activates a specialization → profile coefficients/tool lists change → `route_task()` ranks candidate profiles → swarm task selection calls the router.

**Extractable loop:** attempt → qualified outcome → revise situated capability evidence → choose differently on a later task → compare the effect.

**Observed strengths:** score updates persist and are read by later profile loads. Task routing is actually connected to profile lookup. This is more than a character description.

**Observed limits:** scores come from caller-supplied success and fixed increments; twenty successes can activate a specialization without representing difficulty, independent outcomes, recency or contradictory evidence. A name-specific Maki branch grants special coefficients. The inspected swarm file invokes routing but contains no call to `record_experience`; end-to-end learning through this execution path remains unestablished. An executed probe found that when every candidate silenced the requested domain, routing still returned the first candidate.

**Proposed adaptation:** keep preference, practiced technique, demonstrated competence, permission and current capacity as separate fields. Add eligibility before ranking and a “no suitable participant” result. Preserve room for exploration so the most-used character does not receive every task and monopolize all future evidence. Fictional progression can be authored; real-domain competence requires corresponding checks.

Sources: [differentiation][booder-differentiation], [swarm orchestration][booder-swarm].

### 4.10 Hidden Booder Village: declared workflow state needs outcome semantics

**Trace:** mission text → proposed steps → tool registry → output mapping → next step → workflow completion.

**Extractable loop:** reusable steps that pass typed outputs, wait for missing input and recover from interruption.

**Executed limits:** a `pending_human` result was marked completed; a returned `success: false` was marked completed; a timeout was treated as recoverable but not retried, and the workflow still completed. The state enum has no waiting state. These are false closures relative to Kageyoni's requirements.

The separate swarm runner adds mission events, retry counts and compensation records, but its inspected VERIFYING handler directly marks completion. Its aggregation path passes the literal “Aggregation complete” instead of the actual task result bodies. Those parts cannot establish successful collective synthesis merely because the lifecycle advances.

**Proposed adaptation:** each operation returns a typed disposition: succeeded, failed, waiting, unavailable, cancelled or partial. Output existence is separate from objective satisfaction. A verification state must perform a relevant check. A synthesis step must receive actual contributions and their provenance.

Sources: [workflow orchestrator][booder-workflow], [swarm orchestrator][booder-swarm].

### 4.11 Outer-Sanctum: remembering reasons, structures and failures

**Trace A:** objective → structural/semantic/decision-history query functions → structured memory synthesis.

**Observed boundary:** all three queried functions in the inspected vector-store file return explicit MOCK strings. The memory-swarm synthesis node invokes one model with three described personas; this is not three independently operating agents or verified retrieval.

**Trace B:** traceback → failure signature → durable rule/graveyard tables → `memory_fetch()` provides past rules and summaries. Tests inspect frozen models, storage, retrieval and signature extraction.

**Extractable loop:** preserve what happened and why a choice was made → retrieve when relevant → use it as a candidate constraint → test whether it helps → revise its scope. This includes useful lessons from successes, discovery and delight, not only defensive rules from failures.

**Boundary:** a recorded warning is not automatically a valid general rule. `scar_digest` creates a warning from a failure signature; it does not demonstrate prevention. Booder's separate reflection module is even more limited: its “build defensive filters” method returns a fixed list rather than querying recorded experience.

Sources: [memory swarm][outer-memory], [vector queries][outer-vector], [staging/memory implementation][outer-staging], [reflection][booder-reflection].

### 4.12 Entonkageyoni, Komorebi and Ichimonji: identity must have a return path

**Trace:** world state → scene/messages → character turn → orchestration → world changes and transcript → save. Komorebi's `SovereignIndividual` serializes identity/directives and appends reflections. Ichimonji's reification handbook explicitly describes selecting a stored actor, extracting state, instantiating an agent and connecting behavior back to database constraints.

**Extractable loop:** instantiate a participant from durable identity → provide a situated view → obtain a proposal → resolve it under domain rules → persist the consequences → use them in the next activation.

This is directly related to the goal of Sciel, Angela, Sebastian, Levi and Voss becoming persistent participants across workspaces. It is not merely a new use for a software-verification tool.

**Boundaries:** the older engine includes explicit mock behavior and broadcasts common scene messages. Its evolution method advances tiers from step milestones and numerical thresholds; this is game progression, not demonstrated conceptual learning. `SovereignIndividual.reflect()` logs a perception but does not itself change the decision process. The reification handbook is an architectural proposal, not evidence of a complete portable execution bridge. Historical character mappings are source material, not permission to overwrite current canon.

Sources: [older world engine][enton-engine], [base agent][enton-base], [sovereign individual][komorebi-individual], [reification handbook][ichi-reification].

### 4.13 Espada: the same action interface can serve a person or automation

**Trace:** look/board/engage/strike → engine measurement → ledger → rendered state. Scripted sessions use the same command handling. Separately, sealed expectations, differential checks, metamorphic relations and mutation tests try to establish that a check can catch a relevant failure.

**Extractable loops:** discover available actions → select → execute → observe refreshed state; and define expectation → challenge the checker → evaluate a change → keep known limits visible.

**Kageyoni application:** the CLI and AI call the same typed operations. Rules can resolve routine play without model calls. Equivalent state-preserving transformations—save/reload, renaming a display label, replaying an idempotent request—should not change mechanical outcomes.

**Boundary:** Espada's game is a code-measurement interface, not a complete social RPG. Its rule that narration cannot claim progress is appropriate for software verification; Kageyoni must allow narration to propose fictional events through authorized world resolution. Non-application of a test must remain unknown, and a sealed expectation establishes timing/integrity rather than independent authorship or universal correctness.

Sources: [command loop][espada-loop], [expectations][espada-expectation], [metamorphic checks][espada-metamorphic].

### 4.14 Job Hunter and Ten Shadows Control: two narrower reusable pieces

Job Hunter separates outcome statistics from model-generated interpretations. Extract attempt/outcome collection and bounded pattern review. Its insight generation is not a tested causal explanation or an automatic policy update; retain hypothesis status and replace API-specific invocation with the authorized host handoff.

Ten Shadows Control provides an adapter/manual-submission orchestration pattern. Extract the explicit boundary between a request packet, available execution host and returned result. Do not assume its host commands exist or are authorized in another environment, and do not auto-sync repositories as a side effect of a game action.

Sources: [Job Hunter learning][jobs-learning], [control orchestrator][control-orchestrator].

## 5. A compact vocabulary of reusable loops

These eighteen mechanisms are **extraction candidates inside the previously proposed twelve loop families**, not eighteen more mandatory subsystems.

| Mechanism | Smallest useful cycle | Main source | What it can become |
|---|---|---|---|
| Attend | Situation → relevant concern → focus → updated situation | World agents / context compilation | Distinct attention rather than distinct wording |
| Orient | Focus → applicable actions → choice → feedback | Espada / Mugen | Shared CLI and AI action discovery |
| Interpret | Ambiguous input → proposed meaning → check → typed intention | Mugen planner | Free expression with explicit action targets |
| Investigate | Question → evidence → gap → refined question | Mugen research / deficit protocol | Research, exploration, detective work |
| Provision | Missing item → locate/acquire → validate → resume | 10 Shadows | Training, collaboration, tool or source acquisition |
| Compose | Goal → dependencies → executable step → updated frontier | Nelson / 10 Shadows | Connected workflows and encounters |
| Attempt | Method → action → observation → outcome | Mugen orchestration / world engine | Rule-based or judgment-assisted action |
| Repair | Failure → cause candidate → changed attempt → check | Mugen retry / Alchemist | Learning within one task |
| Reconsider | Changed basis → affected beliefs/plans → reevaluation | Nelson / truth maintenance | Continuity under new information |
| Remember | Episode → structured record → contextual retrieval → use | Scribe / memory stores | Experience beyond a context window |
| Differentiate | Evidence → profile revision → changed selection → outcome | Booder | Persistent, situated specialization |
| Abstract | Episodes → proposed relation → counterexample → method | Media decomposition / motifs | Reusable understanding |
| Transfer | Method → role mapping → destination trial → qualification | Structural transfer / media compiler | Cross-domain synthesis |
| Collaborate | Contributions → exchange/challenge → synthesis → outcome | Mission/swarm patterns | Team effects beyond summed outputs |
| Express | Meaning → form → reception → revision | Media/story frameworks | Narration, teaching, visual explanation |
| Recover | Interrupted work → reconcile durable state → resume | Nelson / Booder / Mugen | Long-lived play and daily work |
| Evaluate | Requirement → falsifiable observation → challenge → verdict | Espada / Nelson | Evidence of advantage and limits |
| Evolve | Repeated outcomes → proposed loop change → trial → version | Several partial precursors | Improvement of the engine's methods |

The final Evolve loop is a proposed synthesis. None of the inspected naming, counters or reflection logs alone establishes it.

## 6. Five combinations that matter more than individual modules

### A. Situated learning

Combine world identity + Booder profiles + Nelson evidence binding + Scribe retrieval.

A character attempts something; an outcome is recorded; a lesson remains distinct from the episode; the lesson applies to a bounded class of situations; the next relevant decision uses the new method; contrary evidence can revise it. The proof is a changed later action attributable to the qualified lesson—not a higher score or a reflection paragraph.

### B. Cross-domain creative transfer

Combine media decomposition/recomposition + richer structural motifs + character method profiles + destination validation.

A method learned while creating an image might suggest how to organize a document: establish a focal point, arrange supporting contrasts, then examine whether the reader notices the intended relationship. That is an illustrative method transfer, not a claim about Sciel's canon or proof that visual expertise confers writing expertise. The source domain contributes a candidate structure; the destination supplies its own tests.

### C. Adaptive inquiry

Combine research acquisition + deficit declarations + evidence dependencies + counterexample search.

A question generates a source plan. Extracted claims expose missing evidence. New sources narrow or challenge the answer. The next search is chosen to resolve a specific uncertainty. Completion means an adequately supported answer or a clear boundary, rather than a pile of URLs.

### D. Living interaction

Combine character attention + typed actions + nested loop instances + rule resolution + knowledge-limited belief updates.

During an encounter, a question creates an offer loop; an interruption creates a response obligation; an ability changes the environment; participants interpret only what they perceive; the resulting promise can outlive the encounter. A dependency scheduler handles prerequisites within an episode, while time and new events allow cyclic relationships across episodes. Do not force the living world into a single acyclic build graph.

### E. Engine learning about coordination

Combine contribution ancestry + outcome comparison + scoped evaluation + versioned workflow definitions.

The engine can propose that a particular kind of task benefits from a contrasting reader, fewer participants, a different order of inquiry or a specific tool. Test that proposal on later work under comparable conditions. Keep character growth, team coordination learning and engine policy changes separate so one successful task does not rewrite all three.

## 7. What is still missing between the repositories

The main missing connective structure is a **method record with causal scope**. Existing projects often retain text, scores, artifacts or statuses. A reusable method needs its operation, rationale, applicability, failure modes, evidence, counterevidence and observed downstream effects.

Other missing or incomplete links relevant to the destination:

- **Reception:** an output exists, but what did its recipient understand, feel or choose? Dialogue, teaching and communication need response, not only production.
- **Knowledge distribution:** participants must have different permitted views and acquisition histories. A global claim graph cannot substitute for situated understanding.
- **Opportunity generation:** missing capabilities should expose choices, not only refusals. Curiosity, beauty, rest, play and voluntary exploration are legitimate initiators.
- **Credit assignment:** distinguish an effective method from an easy task, a collaborator's contribution, luck or a favorable environment.
- **Method revision:** preserve exceptions and counterexamples instead of accumulating permanent “never” rules.
- **Transfer validation:** explain where an analogy stops and test its destination effect.
- **Contribution exchange:** multiple generated answers need actual interaction and ancestry before they constitute collective reasoning.
- **Result consumption:** show exactly where retained experience is retrieved and changes a later action. Storage without consumption leaves the development loop open.

These are proposed design obligations. This audit does not claim every related idea is absent from every uninspected file.

## 8. Integration architecture

Keep Kageyoni's world engine and durable identity as the center. Add a shared loop protocol and adapt selected mechanisms into it. A repository remains a source of ideas/code, not a separate mandatory runtime.

| Proposed owner | Responsibilities | Initial extraction |
|---|---|---|
| Interaction service | Active concerns, nested/overlapping loops, pending responses, closure | World agents + obligation patterns |
| Context service | Authorized perspective, relevant memories, source/claim status | Context compiler + Scribe + scoped memory |
| Method registry | Operations, conditions, evidence, revisions, adaptation history | Capability contracts + motifs + profiles |
| Workflow runner | State transitions, scheduling policy, handoffs, effect reconciliation | Mugen + Nelson + Booder patterns |
| Workspace adapters | Domain objects, legal effects, output forms and checks | Media compiler, research, repository tooling |
| Development service | Episodes, candidate lessons, qualification and later-use observation | Differentiation + outcome review |
| Evaluation service | Mechanical invariants, source review, behavioral comparisons | Espada + Nelson |

Use one transaction/revision authority for a shared world mutation. Keep artifact staging, external effects and reconciliation explicit. No direct transplantation of API clients, default execution of generated code, name-based privilege grants or duplicated databases that claim to be the same canonical state.

A scheduler can support multiple policies through the same protocol: immediate rules, prerequisite frontiers, turn order, clock triggers, waiting for another actor, or bounded judgment. Share persistence and action envelopes; preserve different meanings of progress.

## 9. Concrete integrated walkthroughs

### CLI game with optional judgment

The player inspects a situation. The engine exposes authored actions and relevant open obligations. A chosen action checks resources and resolves through existing rules. Its event updates related loops, schedules consequences and changes what participants can perceive. A later interaction retrieves only that participant's established experience. Save/reload restores the same obligations and methods.

An unfamiliar action suspends only the affected loop, with a question, permitted context and possible levers. A human or authorized AI returns a proposal. Validation checks its target, applicability, costs and effect scope before applying it. Other independent processes can continue according to world time rules.

### Researching what a business sells

Resolve the company → locate official product/service pages → capture relevant passages → extract offerings and stated values separately → mark gaps → ask targeted follow-up questions → produce a source-grounded brief → inspect whether the result answers the original question.

A character method can influence what is noticed or compared. It cannot invent source content or treat a stylish summary as verified research. Retain useful techniques such as how a misleading category label was disambiguated, then check their applicability in another business.

### Two characters co-creating a document

Assign differentiated contributions from established methods. Preserve the source brief. Each participant receives relevant context and the other contributions they are allowed to see. Record a disagreement and the reason for a synthesis choice. Evaluate the final artifact against source obligations and intended audience use. Record individual lessons separately from the coordination lesson. A team that simply paraphrases one answer fails the collective-contribution criterion even if its final prose sounds polished.

## 10. Integration priorities and proof obligations

These priorities fit inside the existing eight vertical slices; they do not replace the full destination.

1. **State and outcome truth:** typed dispositions, pending input, revision bindings, duplicate handling and actual loop closure. Prove these before adding autonomous routing.
2. **Identity and situated context:** a character's stable record plus branch/workspace scope and permitted knowledge. Prove reopened sessions and divergent perspectives.
3. **Method expression:** one established method measurably changes a structured contribution. Name-only changes should not produce a false claim of differentiated intelligence.
4. **Development return path:** persist an outcome, qualify a lesson, retrieve it on a new applicable task and observe its effect. Include an unrelated task and a counterexample.
5. **Cross-workspace transfer:** propose a role/relationship mapping, test the destination artifact, retain source-world continuity.
6. **Collective contribution:** show that an exchange changes the result, then compare quality and effort against a single participant.
7. **Workflow evolution:** propose and evaluate a policy revision without rewriting prior history or relaxing acceptance criteria to get a pass.

Before porting any module, require: compatible inputs/outputs, known dependencies, source pin, no unexpected external calls, correct scope, failure behavior, a positive control, an adverse case and a demonstrated downstream consumer. API-specific dependencies are replaced only with verified subscription-native capabilities or an explicit manual packet handoff.

## 11. What the evidence justifies

The repositories provide substantial raw material for a persistent creative engine. The most developed reusable pieces are stateful execution, evidence binding, typed records, source/artifact handling and bounded workflow control. There are also meaningful precursors for individuality, memory, differentiated routing and cross-domain adaptation.

The strongest prospective advantage lies in connecting **experience → method → situated use → consequence → revised understanding**. The current inspection does not establish that this full cycle already operates reliably across the repositories. It identifies the pieces, the broken or missing connections, and the tests that can establish it without shrinking the creative goal.

## Appendix A. Source pins

| Repository | Inspected Git tree revision | Retrieved files |
|---|---|---|
| 10-shadows | `ee4a16a07edee11cb810f83dded036b71b56261a` | 41 |
| Hidden-Booder-Village | `c216ad9ea3cf236535b311d24140a3e095b3e1f9` | 10 |
| Komorebi | `0baea524ebf71984d29cc184745ac0022cca6bee` | 6 |
| Nelson | `150e64582b733160516b2d8bfc09760b2ac63798` | 35 |
| Outer-Sanctum | `6d9db3d11d356365e2961b27e5269108e677ddee` | 9 |
| entonkageyoni | `337488a75359facf0747a52eafa7de05cb34664e` | 7 |
| espada | `6fade687382feeb52f3a7a16219c6a7bc0bf2184` | 28 |
| ichimonji | `66aa840a83cc5aa2787feb2a90fa62b706f9105a` | 22 |
| job-hunter | `b6417a555430607710a1407aef9ee04080768589` | 4 |
| komorebisans | `9612dade9b1ecf2507643b31b06ce0e2c335488a` | 0 |
| mugen | `7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad` | 51 |
| ten-shadows-control | `ce2915f02ad797215d5c739be05ac4bc168037f9` | 2 |

## Appendix B. Executed boundary probes

Expectations below are proposed integration requirements. In particular, the alternative-support case tests the need for re-evaluation rather than declaring every upstream invalidation policy intrinsically wrong. Six positive controls passed; nine selected adverse assertions did not. No whole-repository success percentage is implied.

```json
{
  "probes": [
    {
      "name": "requires_prerequisite_blocks_parent",
      "expected": [
        "need"
      ],
      "observed": [
        "need",
        "root"
      ],
      "meets_proposed_requirement": false
    },
    {
      "name": "persisted_motif_available_after_engine_recreation",
      "expected": 1,
      "observed": 0,
      "meets_proposed_requirement": false
    },
    {
      "name": "alternative_support_requires_reevaluation_not_automatic_falsity",
      "expected": "CONTESTED",
      "observed": "INVALIDATED",
      "meets_proposed_requirement": false
    },
    {
      "name": "transcript_only_does_not_establish_camera_shot",
      "expected": "unknown",
      "observed": "talking_head_closeup",
      "meets_proposed_requirement": false
    },
    {
      "name": "transcript_only_does_not_establish_business_premise",
      "expected": "unknown",
      "observed": "Manual coding is too slow",
      "meets_proposed_requirement": false
    },
    {
      "name": "human_input_suspends_workflow",
      "expected": "waiting",
      "observed": "completed",
      "meets_proposed_requirement": false
    },
    {
      "name": "returned_tool_failure_fails_workflow",
      "expected": "failed",
      "observed": "completed",
      "meets_proposed_requirement": false
    },
    {
      "name": "timeout_without_retry_not_completed",
      "expected": "failed",
      "observed": "completed",
      "meets_proposed_requirement": false
    },
    {
      "name": "positive_depends_on_blocks_parent",
      "expected": [
        "need"
      ],
      "observed": [
        "need"
      ],
      "meets_proposed_requirement": true
    },
    {
      "name": "positive_completed_dependency_releases_parent",
      "expected": [
        "root"
      ],
      "observed": [
        "root"
      ],
      "meets_proposed_requirement": true
    },
    {
      "name": "positive_successful_workflow",
      "expected": "completed",
      "observed": "completed",
      "meets_proposed_requirement": true
    },
    {
      "name": "positive_output_propagated",
      "expected": 3,
      "observed": 3,
      "meets_proposed_requirement": true
    },
    {
      "name": "positive_transcript_words_preserved",
      "expected": "We plant native flowers beside the river.",
      "observed": "We plant native flowers beside the river.",
      "meets_proposed_requirement": true
    },
    {
      "name": "all_candidates_silenced_returns_no_eligible_agent",
      "expected": null,
      "observed": "a",
      "meets_proposed_requirement": false
    },
    {
      "name": "positive_experience_persists",
      "expected": 0.1,
      "observed": 0.1,
      "meets_proposed_requirement": true
    }
  ],
  "timeout_tool_calls": 1,
  "scope": "Executed actual selected modules, no full application suite; expected behaviors are proposed Kageyoni integration requirements."
}

```

### Reproduction script

Use the pinned files in the inventory below under matching repository directories. Run `python3 probe_boundaries.py` from that audit directory. Namespace setup bypasses broad package startup and leaves the tested implementation bodies unchanged. This is a component-level probe, not an installed application test. Temporary SQLite and profile files are deleted on exit.

```python
"""Offline probes of pinned upstream source; temporary SQLite only; no model calls."""
import sys,json,tempfile,importlib.util,types
from pathlib import Path
R=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'10-shadows'),str(R/'mugen')]
# Load selected actual submodules without broad package startup side effects.
for name,path in [('loop_engine',R/'10-shadows/loop_engine'),('mugen',R/'mugen/mugen'),('mugen.modules',R/'mugen/mugen/modules'),('mugen.modules.media',R/'mugen/mugen/modules/media')]:
 m=types.ModuleType(name);m.__path__=[str(path)];sys.modules[name]=m
from loop_engine.relational import RelationalGraphStore,RelationalNode,RelationalEdge,NodeType,RelationType,EpistemicStatus,DependencyScheduler,StructuralTransferEngine,RelationalMotif,TruthMaintenanceEngine
from mugen.modules.media.decompiler import decompile_transcript_to_blueprint
spec=importlib.util.spec_from_file_location('isolated_workflow',R/'Hidden-Booder-Village/core/workflow_orchestrator.py')
w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
spec2=importlib.util.spec_from_file_location('isolated_differentiation',R/'Hidden-Booder-Village/core/differentiation.py')
diff=importlib.util.module_from_spec(spec2);sys.modules[spec2.name]=diff;spec2.loader.exec_module(diff)
results=[]
def add(name,expected,observed):results.append(dict(name=name,expected=expected,observed=observed,meets_proposed_requirement=expected==observed))
with tempfile.TemporaryDirectory() as d:
 store=RelationalGraphStore(Path(d)/'g.sqlite')
 for id in ['root','need']:
  store.upsert_node(RelationalNode(id,NodeType.SUBPROBLEM,id,epistemic_status=EpistemicStatus.OBSERVED))
 store.upsert_edge(RelationalEdge('req','root','need',RelationType.REQUIRES))
 ready=sorted(n.node_id for n in DependencyScheduler(store).get_ready_frontier('root',set()))
 add('requires_prerequisite_blocks_parent',['need'],ready)
 tr=StructuralTransferEngine(store)
 tr.register_motif(RelationalMotif('m','shared pattern','source',(NodeType.SUBPROBLEM,), (RelationType.REQUIRES,),.8))
 before=len(tr.find_transferrable_strategies('root',[NodeType.SUBPROBLEM],[RelationType.REQUIRES]))
 after=len(StructuralTransferEngine(store).find_transferrable_strategies('root',[NodeType.SUBPROBLEM],[RelationType.REQUIRES]))
 add('persisted_motif_available_after_engine_recreation',before,after)
 for id in ['a','b','claim']:
  store.upsert_node(RelationalNode(id,NodeType.CLAIM,id,epistemic_status=EpistemicStatus.VERIFIED))
 for id in ['a','b']:
  store.upsert_edge(RelationalEdge('support'+id,'claim',id,RelationType.SUPPORTED_BY))
 TruthMaintenanceEngine(store).retract_and_cascade('a','probe')
 add('alternative_support_requires_reevaluation_not_automatic_falsity','CONTESTED',store.get_node('claim').epistemic_status.value)
 bp=decompile_transcript_to_blueprint('We plant native flowers beside the river.','Gardening')
 add('transcript_only_does_not_establish_camera_shot','unknown',bp.rows[0].visual_shot_type.value)
 add('transcript_only_does_not_establish_business_premise','unknown',bp.brief.core_premise_stakes)
 runner=w.WorkflowOrchestrator(None)
 wf=w.Workflow('wait','wait','probe',[w.WorkflowStep('s','ask','Which route?','human_input',{},[])])
 runner.execute_workflow(wf)
 add('human_input_suspends_workflow','waiting',wf.status.value)
 wf=w.Workflow('fail','fail','probe',[w.WorkflowStep('s','read','missing path','file_read',{},[])])
 runner.execute_workflow(wf)
 add('returned_tool_failure_fails_workflow','failed',wf.status.value)
 calls=[]
 def timed(step,inputs):calls.append(1);raise TimeoutError('timeout')
 runner.TOOL_REGISTRY['probe_timeout']=timed
 wf=w.Workflow('timeout','timeout','probe',[w.WorkflowStep('s','time','probe','probe_timeout',{},[])])
 runner.execute_workflow(wf)
 add('timeout_without_retry_not_completed','failed',wf.status.value)
 # Positive controls establish the probes can recognize valid behavior.
 store.upsert_edge(RelationalEdge('dep','root','need',RelationType.DEPENDS_ON))
 add('positive_depends_on_blocks_parent',['need'],sorted(n.node_id for n in DependencyScheduler(store).get_ready_frontier('root',set())))
 add('positive_completed_dependency_releases_parent',['root'],sorted(n.node_id for n in DependencyScheduler(store).get_ready_frontier('root',{'need'})))
 runner.TOOL_REGISTRY['positive']=lambda step,inputs: {'success':True,'value':3}
 wf=w.Workflow('positive','positive','probe',[w.WorkflowStep('s','p','probe','positive',{},['value'])])
 out=runner.execute_workflow(wf)
 add('positive_successful_workflow','completed',wf.status.value)
 add('positive_output_propagated',3,out['outputs']['value'])
 add('positive_transcript_words_preserved','We plant native flowers beside the river.',bp.rows[0].audio_voiceover_text)
 dr=diff.DifferentiationEngine(str(Path(d)/'profiles'))
 for name in ['a','b']:
  profile=dr.get_profile(name);profile.silenced_genes=['WEB_SEARCH'];profile.save()
 add('all_candidates_silenced_returns_no_eligible_agent',None,dr.route_task('WEB_SEARCH',['a','b']))
 dr.record_experience('learner','CUSTOM_DOMAIN',True)
 add('positive_experience_persists',0.1,diff.DifferentiationEngine(str(Path(d)/'profiles')).get_profile('learner').masteries['CUSTOM_DOMAIN'])
 print(json.dumps({'probes':results,'timeout_tool_calls':len(calls),'scope':'Executed actual selected modules, no full application suite; expected behaviors are proposed Kageyoni integration requirements.'},indent=2))

```

## Appendix C. Retrieved file inventory

Retrieval/indexing does not mean every file received equal line-by-line scrutiny. The substantive chains and tested functions are identified in the main report. Binary assets, campaign databases, vendored runtimes and complete historical branches were not audited.

### 10-shadows

```text
loop_engine/__init__.py
loop_engine/alchemist/__init__.py
loop_engine/alchemist/repair_strategy.py
loop_engine/alchemist/trace_parser.py
loop_engine/base.py
loop_engine/capability_registry.py
loop_engine/constitution/__init__.py
loop_engine/constitution/capability.py
loop_engine/constitution/evidence.py
loop_engine/constitution/lifecycle.py
loop_engine/constitution/sufficiency.py
loop_engine/context.py
loop_engine/governor.py
loop_engine/model/__init__.py
loop_engine/model/benchmark.py
loop_engine/model/boundary.py
loop_engine/model/candidate_search.py
loop_engine/model/context_compiler.py
loop_engine/model/deficit_protocol.py
loop_engine/orchestrator.py
loop_engine/relational/__init__.py
loop_engine/relational/dependency_scheduler.py
loop_engine/relational/gap_planner.py
loop_engine/relational/graph_db.py
loop_engine/relational/projection.py
loop_engine/relational/schema.py
loop_engine/relational/structural_transfer.py
loop_engine/relational/truth_maintenance.py
loop_engine/router.py
loop_engine/runners/scribe_runner.py
loop_engine/runners/slicer_runner.py
loop_engine/schema.py
loop_engine/scribe/__init__.py
loop_engine/scribe/memory_store.py
loop_engine/scribe/pattern_miner.py
loop_engine/slicer/__init__.py
loop_engine/slicer/schema.py
loop_engine/slicer/slicer_engine.py
loop_engine/tests/test_slice2_scribe_miner.py
loop_engine/transition.py
tests/test_relational_intelligence.py
```

### Hidden-Booder-Village

```text
core/agent_runtime.py
core/differentiation.py
core/growth_metrics.py
core/harvester.py
core/semantic_memory.py
core/swarm_orchestrator.py
core/workflow_orchestrator.py
engine/reflection.py
media_engine/kernel.py
tests/test_swarm_orchestrator.py
```

### Komorebi

```text
Citadel/memory.py
src/kageyoni/agents/sovereign.py
src/kernel/chronicle_engine.py
src/kernel/genesis_engine.py
src/kernel/room.py
src/kernel/sovereign_core.py
```

### Nelson

```text
nelson/__init__.py
nelson/__main__.py
nelson/amendments.py
nelson/authority.py
nelson/common.py
nelson/coverage.py
nelson/dependencies.py
nelson/environment_probe.py
nelson/evidence.py
nelson/execution.py
nelson/identity.py
nelson/intake.py
nelson/launcher.py
nelson/levi.py
nelson/lifecycle.py
nelson/locking.py
nelson/logic.py
nelson/missions.py
nelson/objections.py
nelson/orchestration.py
nelson/privacy.py
nelson/providers.py
nelson/quality.py
nelson/recovery.py
nelson/review.py
nelson/runtime.py
nelson/sovereign.py
nelson/store.py
nelson/workflow.py
nelson/workspace.py
nelson_tests/test_admission.py
nelson_tests/test_missions.py
nelson_tests/test_objections.py
nelson_tests/test_quality.py
nelson_tests/test_workflow.py
```

### Outer-Sanctum

```text
Komorebi/software_factory/src/agents/memory_swarm.py
Komorebi/software_factory/src/agents/planner.py
Komorebi/software_factory/src/tools/vector_store.py
Komorebi/staging_buffer.py
Komorebi/tests/test_memory_invariants.py
Komorebi/tests/test_microkernel_invariants.py
README.md
Sovereign_Media_Engine/SME_execution/orchestrator/adversarial_swarm.py
Sovereign_Media_Engine/SME_execution/orchestrator/colosseum_adjudicator.py
```

### entonkageyoni

```text
src/kageyoni/agents/base.py
src/kageyoni/agents/characters.py
src/kageyoni/agents/orchestrator.py
src/kageyoni/agents/world.py
src/kageyoni/engine.py
src/kageyoni/events.py
src/kageyoni/transference_run.py
```

### espada

```text
espada/__init__.py
espada/cpg.py
espada/deceptive.py
espada/differential.py
espada/evidence.py
espada/exit_condition.py
espada/expectation.py
espada/fact_check.py
espada/gates.py
espada/instruments.py
espada/ledger.py
espada/metamorphic.py
espada/mutation.py
espada/ratchet.py
espada/restore.py
espada/roles.py
espada/stability.py
espada/structural.py
espada/units.py
espada/worlds.py
game/__init__.py
game/__main__.py
game/engine_view.py
game/loop.py
game/render.py
tests/test_expectation.py
tests/test_metamorphic.py
tests/test_ratchet.py
```

### ichimonji

```text
AGENT_CORE_DRIVES.md
AGENT_REIFICATION_HANDBOOK.md
CHRONICLE.md
ICHIMONJI_ASCENSION_V2.md
ICHIMONJI_DOCUMENTARY_MASTER_PLAN.md
PLAYER_CHARACTER_CODEX.md
README.md
REAL_WORLD_SUPPORT_SYSTEM.md
SOVEREIGN_SUBSTRATE_EXPEDITION.md
SOVEREIGN_SYSTEM_DOSSIER.md
SOVEREIGN_WORLD_BIBLE.md
STORYWEAVER_FRAMEWORK.md
STRATEGIC_ORCHESTRATION_CORE.md
WORLD_MAP_KINGDOMS.md
debug_aeon.ts
drizzle.config.ts
hash_tool.ts
init_game.ts
log_event.sql
reify.sql
scratch_status.ts
story_mode_singularity.py
```

### job-hunter

```text
engine/fit_scorer.py
engine/learning.py
engine/resume_tailor.py
tests/test_learning.py
```

### mugen

```text
mugen/__init__.py
mugen/airgap_checker.py
mugen/ast_extractor.py
mugen/board.py
mugen/budget.py
mugen/core_loader.py
mugen/delivery.py
mugen/division_of_labor_checker.py
mugen/engage_runner.py
mugen/errors.py
mugen/factbase_compressor.py
mugen/gates.py
mugen/hooks_ledger.py
mugen/intent_gate.py
mugen/intent_router.py
mugen/json_verdict.py
mugen/ledger.py
mugen/ledger_immune_bridge.py
mugen/memory_filter.py
mugen/modules/media/__init__.py
mugen/modules/media/brief_reality.py
mugen/modules/media/compiler.py
mugen/modules/media/decompiler.py
mugen/modules/media/doc_advisor.py
mugen/modules/media/proof.py
mugen/modules/media/schema.py
mugen/modules/media/state_machine.py
mugen/modules/media/template_vault.py
mugen/orchestrator.py
mugen/path_engine.py
mugen/planning.py
mugen/reaudit_gate.py
mugen/report_gate.py
mugen/report_gate_cli.py
mugen/retry.py
mugen/router.py
mugen/routing_rules.py
mugen/sanitize.py
mugen/schemas/ledger_schema.py
mugen/skills/research.py
mugen/sovereign_runner.py
mugen/ts_bridge.py
mugen/worker.py
mugen/zk_dispatcher.py
mugen/zk_interceptor.py
tests/test_media_decompiler.py
tests/test_memory_filter.py
tests/test_orchestrator_crash_safety.py
tests/test_planning.py
tests/test_research_intent_gate.py
tests/test_retry.py
```

### ten-shadows-control

```text
README.md
scripts/orchestrator.py
```

[nelson-workflow]: https://github.com/guarani-ux/Nelson/blob/150e64582b733160516b2d8bfc09760b2ac63798/nelson/workflow.py
[nelson-dependencies]: https://github.com/guarani-ux/Nelson/blob/150e64582b733160516b2d8bfc09760b2ac63798/nelson/dependencies.py
[nelson-missions]: https://github.com/guarani-ux/Nelson/blob/150e64582b733160516b2d8bfc09760b2ac63798/nelson/missions.py
[nelson-objections]: https://github.com/guarani-ux/Nelson/blob/150e64582b733160516b2d8bfc09760b2ac63798/nelson/objections.py
[shadows-deficit]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/model/deficit_protocol.py
[shadows-context]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/model/context_compiler.py
[shadows-gap]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/relational/gap_planner.py
[shadows-capability]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/constitution/capability.py
[shadows-search]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/model/candidate_search.py
[shadows-transfer]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/relational/structural_transfer.py
[shadows-truth]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/relational/truth_maintenance.py
[shadows-scheduler]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/relational/dependency_scheduler.py
[shadows-miner]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/scribe/pattern_miner.py
[shadows-scribe-runner]: https://github.com/guarani-ux/10-shadows/blob/ee4a16a07edee11cb810f83dded036b71b56261a/loop_engine/runners/scribe_runner.py
[mugen-planning]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/planning.py
[mugen-orchestrator]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/orchestrator.py
[mugen-retry]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/retry.py
[mugen-decompiler]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/modules/media/decompiler.py
[mugen-decompiler-tests]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/tests/test_media_decompiler.py
[mugen-compiler]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/modules/media/compiler.py
[mugen-research]: https://github.com/guarani-ux/mugen/blob/7d57ee0fdac16d935b6ff10ac6c9915fc69b54ad/mugen/skills/research.py
[booder-differentiation]: https://github.com/guarani-ux/Hidden-Booder-Village/blob/c216ad9ea3cf236535b311d24140a3e095b3e1f9/core/differentiation.py
[booder-swarm]: https://github.com/guarani-ux/Hidden-Booder-Village/blob/c216ad9ea3cf236535b311d24140a3e095b3e1f9/core/swarm_orchestrator.py
[booder-workflow]: https://github.com/guarani-ux/Hidden-Booder-Village/blob/c216ad9ea3cf236535b311d24140a3e095b3e1f9/core/workflow_orchestrator.py
[booder-reflection]: https://github.com/guarani-ux/Hidden-Booder-Village/blob/c216ad9ea3cf236535b311d24140a3e095b3e1f9/engine/reflection.py
[outer-memory]: https://github.com/guarani-ux/Outer-Sanctum/blob/6d9db3d11d356365e2961b27e5269108e677ddee/Komorebi/software_factory/src/agents/memory_swarm.py
[outer-vector]: https://github.com/guarani-ux/Outer-Sanctum/blob/6d9db3d11d356365e2961b27e5269108e677ddee/Komorebi/software_factory/src/tools/vector_store.py
[outer-staging]: https://github.com/guarani-ux/Outer-Sanctum/blob/6d9db3d11d356365e2961b27e5269108e677ddee/Komorebi/staging_buffer.py
[enton-engine]: https://github.com/guarani-ux/entonkageyoni/blob/337488a75359facf0747a52eafa7de05cb34664e/src/kageyoni/engine.py
[enton-base]: https://github.com/guarani-ux/entonkageyoni/blob/337488a75359facf0747a52eafa7de05cb34664e/src/kageyoni/agents/base.py
[komorebi-individual]: https://github.com/guarani-ux/Komorebi/blob/0baea524ebf71984d29cc184745ac0022cca6bee/src/kageyoni/agents/sovereign.py
[ichi-reification]: https://github.com/guarani-ux/ichimonji/blob/66aa840a83cc5aa2787feb2a90fa62b706f9105a/AGENT_REIFICATION_HANDBOOK.md
[espada-loop]: https://github.com/guarani-ux/espada/blob/6fade687382feeb52f3a7a16219c6a7bc0bf2184/game/loop.py
[espada-expectation]: https://github.com/guarani-ux/espada/blob/6fade687382feeb52f3a7a16219c6a7bc0bf2184/espada/expectation.py
[espada-metamorphic]: https://github.com/guarani-ux/espada/blob/6fade687382feeb52f3a7a16219c6a7bc0bf2184/espada/metamorphic.py
[jobs-learning]: https://github.com/guarani-ux/job-hunter/blob/b6417a555430607710a1407aef9ee04080768589/engine/learning.py
[control-orchestrator]: https://github.com/guarani-ux/ten-shadows-control/blob/ce2915f02ad797215d5c739be05ac4bc168037f9/scripts/orchestrator.py
