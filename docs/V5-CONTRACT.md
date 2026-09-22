# V5: destination work with an exact return

V5 supports operational document, repository and pipeline workspaces linked to existing node identities. A document task can retain an actual Markdown artifact and return to the same world checkpoint. Creating the workspace, capturing sources, testing a transferred method and drafting the document do not create story events.

## Public services

| Service | Entry points |
|---|---|
| `Registry` | `open(branch, character_id, kind, request_id, config=None, viewer=None, source_ids=None)`, `read`, `list` |
| `Transitions` | `enter`, `read`, `return_to_world`, `recover` |
| `Artifacts` | `put`, `read`, `manifest`, `verify`, `recover` |
| `Documents` | `acquire_file`, `ingest`, `world_source`, `source`, `inquire`, `decompose`, `draft`, `read` |
| `Transfers` | `propose`, `run_trial`, `record_trial`, `read`, `require_qualified` |

`Application` exposes these services. The ordinary world node bindings and world-only method assignments remain intact. Destination qualification is an explicit separate record; opening a document workspace does not bypass world method scope.

## World state and visibility

A checkpoint binds the branch revision, event head and full world-state/context digest. A return verifies all three. If another operation advanced the world, return becomes blocked and preserves the newer world. It never silently rewinds or invents a return scene. Active and blocked transitions survive reopening and remain inspectable.

Destination context is selected from the caller's permitted world projection. Administrative evidence and audience metadata are removed from its records. A nonowner can only reopen their original viewer scope, and the saved projection must still equal the current permitted projection. This catches nested references whose target becomes hidden while the referring record itself stays public. Sources can also be selected explicitly, limiting the destination context.

## Durable artifacts and interruption

Artifacts have exact bytes, media type, size and SHA-256 identity. Authoritative bytes are stored in SQLite and materialized under `<database-stem>.artifacts/objects/<digest>`. This keeps backups portable while providing real standalone files. A database-committed artifact interrupted before file materialization can be recovered without rerunning generation. Existing corrupted files fail verification; explicit recovery rematerializes them from verified database bytes.

Artifact reads enforce workspace/viewer scope. Staging files are replaced atomically, symlink roots are rejected, and content files are checked against their recorded digest. General external effects are owned by the pipeline slice, not this artifact store.

## Evidence acquisition and inquiry

`Documents.acquire_file` reads the actual bytes of an explicitly provided UTF-8 text file, bounded to one megabyte. `ingest` captures actual text supplied by the current authorized host. Both preserve an artifact, source identity, expected identity, locator, capture time and optional expiry. No external model API is called. Web acquisition can be performed by the current host and then captured with its source locator; this module does not claim to have browsed a website.

Identity matching is an explicit operator-supplied attribution. Code distinguishes mismatched identities and expired sources, but does not independently establish which business a webpage belongs to. A passage reference contains exact source ID, revision, content digest and character offsets. Wrong versions, changed bytes or invalid spans are rejected. Claimed numeric values must equal the cited source text; an unrelated citation cannot certify an invented number.

Inquiry receives a question, required fields, supported passage mappings and contrary passage mappings. It retains supported fields, marks missing fields unknown, preserves conflicts, calculates evidence coverage and points to the next missing evidence. The fourth attempt at the exact same question closes as blocked for review instead of looping indefinitely. Source instructions are retained as data and cannot change engine settings or story state.

Semantic classification remains attributed judgment: a passage mapped to "stated values" establishes the words supplied for that field, not that the business lives those values. `decompose` preserves exact transcript words and leaves unsupported visual and premise fields explicitly unknown.

## Actual document generation

A brief identifies its own audience, purpose, sections and obligations. The deterministic draft renders checked literal source passages with source references, explicit unknown sections and obligations associated with that brief. A cancellation in another brief does not alter this one. Missing schedules, visuals and sensory evidence remain unknown.

The resulting Markdown is an inspectable source-constrained draft. It does not claim literary adaptation, independent audience judgment or completion of a required production task merely because that obligation appears in the draft. `objective_scope` is `source_constrained_draft`, the broader `task_objective` remains unresolved, and `obligation_satisfaction` is not established.

## Directed transfer and destination qualification

A proposed transfer pins the original method revision, digest and assignment. Its role mapping must be complete and injective. The destination relationships must preserve source, relation, target, direction and multiplicity. Reversing an edge fails even when role labels are the same. A field map explicitly connects the registered operation's source fields to destination metrics.

`run_trial` executes that mapped operation against source-bound destination cases. Qualification requires both a positive case and a blocked negative case with independently supplied expected outcomes. Actual checker results and their exact artifact are retained. Inventing a JSON report containing `passed: true` cannot qualify a document transfer. Repository trials use the repository adapter's validation of a real persisted candidate and completed test receipt, bound to exact candidate and check digests.

Trials establish only the bounded procedure under the tested destination conditions. They do not prove causal equivalence, professional expertise or character mastery. Unknown semantic guards still require judgment. New source revisions or assignment changes make a prior transfer stale.

Qualified transferred ranking changes document section order from verified numeric destination metrics. The draft records the original method identity, trial artifact, mapped operation and actual result. This is a behavioral consequence of the transferred method, not a decorative persona name or an unused qualification record. Failed later trials prevent active reuse; owner access can still inspect historical drafts.

## Reproduction

```bash
python -m examples.v5_demo --output /path/to/new-demo-directory
python -m unittest discover -s tests -p 'test_v5_workspaces.py' -v
```

The demo acquires a real local fixture file, qualifies a source-bound transfer, changes the resulting draft's section order, preserves a missing schedule and required teaser, deletes the materialized draft file, reopens and recovers it, and verifies exact world return with an unresolved fictional choice preserved. The fixtures are synthetic, not historical reproductions of real production documents or measurements of creative advantage.
