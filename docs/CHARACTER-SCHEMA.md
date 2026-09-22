# Character schema 1 — implemented contract

This document supersedes the earlier illustrative nested YAML. The nested
sections are a conceptual view; executable input uses the normalized domains
listed below. Authoritative field names, permitted values and required fields
are returned by `python -m kageyoni contract` and generated in
`schemas/character-contract.json`. This component adds no canonical people,
names, motivations, statistics or story events during installation.

## Storage and ownership

| Concept | Authoritative storage |
| --- | --- |
| Stable ID, working label, aliases, legacy characterization | `character`, with the common `records` envelope |
| Established/provisional/alleged existence, canonical name status, continuity | One `character_identity` per character per branch |
| Composable nature descriptions, embodiment, constituents | `character_aspect` section `nature`; optional related character/item; existing `entity_links` for general composition |
| Agency, control, overall nature | Existing `entity_profiles`; `character-create.profile` accepts its validated fields |
| Principles, drives, commitments, preferences, boundaries, contradictions | Separate `character_aspect` records in `interiority` |
| Description, voice, mannerisms, habits, pleasures, attachments | Separate `character_aspect` records in `portrayal` |
| Injury, fatigue, memory/recognition/intention impairment, agency constraints, communication | `character_aspect` section `condition`; quantitative mechanics remain versioned properties |
| Location and embodied/distributed presence | Legacy `character.location`; additional `character_presence` rows |
| Origins, splits, merges, succession, copies, fragments | `character_lineage`; each row links two continuing identities |
| Capabilities and learned mastery | Existing `capability`, `ability`, `progression` |
| Will | Existing `will_expression`, `will_development`, other Will domains |
| Relationships, membership, offices, obligations | Existing `relationship`, `affiliation`, `office`, `accord` |
| Objectives and choices | Existing `objective`, `decision`, event choices |
| Knowledge, observations, accounts, memories | Existing `knowledge`, `observations`, `historical_account`; character-aspect `memory` for subjective memories |
| Resources, possessions, equipment access | Existing `resource`, `loadout`, `item`; no duplicated inventory |
| Classification | Existing attributed `classification_claims`; no automatic effect without a rule |
| Unresolved questions | `character_aspect` section `development`, kind `question`; existing `thread` for shared plot questions |
| History, evidence, revision and visibility | Existing event ledger, `changes`, `records`; all added domains use these mechanisms |

Every new domain record has the common envelope: ID, domain, branch, version,
epistemic status, visibility, audience, nonempty evidence, and updated event.
No nested reference arrays are used as a second authority for existing facts.
Zero remains a known numeric property value; absent/unknown/not-applicable
character-aspect values carry no invented statement. Nature descriptions do not
activate mechanical facets automatically: use the existing explicit facet and
property operations when a defined rule needs them.

## Commands

From the project root:

```sh
python -m kageyoni --db build/kageyoni.sqlite character-read --input request.json
python -m kageyoni --db build/kageyoni.sqlite character-readiness --input request.json
python -m kageyoni --db build/fixture.sqlite character-create --input examples/character-create.json
```

Read request: `{"character_id":"visitor","branch":"main"}`.
Participant read: add `"viewer":"<existing-character-id>"` or use `--viewer`.
Readiness adds `"level":"existence"`, `"scene"` or `"action"`.
Action checks require a nonempty `requirements` array, each containing exactly
`record_id`, `field`, and `equals`. They check linked visible inputs, not arbitrary
world state. They do not evaluate feasibility or resolve outcomes.

Python equivalents: `Workflows(engine).character_create/read/readiness(**params)`.
Updates use existing structured `apply` create/patch commands. A patch requires
expected record version and new evidence; each command requires branch revision
and request ID. A retry with identical content returns the original receipt.
Changing content under a used request ID is rejected.

## Readiness and judgment boundaries

- Existence readiness checks an explicit identity extension, including alleged
  existence. Alleged entities remain reported records, not objective scene actors.
- Scene readiness checks established existence, visible presence, a known active
  drive/principle, and a communication assessment. These are a conservative context
  checklist, not conditions for personhood. A nonverbal/unconscious character can
  have a known assessment describing that condition. GM judgment still supplies
  scene-specific perspective and portrayal; no NPC decision policy is invented.
- Action readiness checks scene completeness plus explicitly declared input
  predicates. It cannot discover every input required by arbitrary actions.
- Time bounds use the referenced clock, start inclusive and end exclusive.
  Ending-condition prose requires GM evaluation and an explicit phase change;
  it is not an executable trigger. Hidden clocks cannot supply participant readiness.
- Direct field changes preserve old records in history. For an explicit principle
  replacement, end the old aspect and create a new aspect with `supersedes` and
  `change_basis` in one event. Voluntary, compelled, deceived and disrupted changes
  remain distinguishable; their truth is supported by supplied evidence/judgment.
- A lineage claim records provenance; it does not itself transfer resources,
  memories, relationships, agency or powers. Multiple predecessors/successors use
  multiple rows in one event. Disputed temporal origins may be cyclic; aspect
  supersession cycles are rejected.
- Record visibility is enforced. Free prose must be authored for its assigned
  audience; semantic secret detection is not claimed. Raw classification claims
  lack per-claim visibility in the pre-existing schema and are GM-only in the new
  character view. Participant profiles expose only scoped scalar fields.
- CLI/Python are trusted GM tools, not an authenticated multiuser server. Viewer
  filtering is a projection boundary, not access control against a local DB owner.

## Migration, versions and recovery

Migration 005 requires predecessor 004, runtime 4 and API 3, and installs separate
`character_schema=1`. Runtime/API versions remain compatible. Its SQL, integrity
checks and checksum receipt commit together. New connections reject a changed
005 checksum or unsupported character component version. The new unique events
ID index also repairs the incomplete legacy schema used by regression fixtures;
duplicate event IDs cause migration failure rather than data removal.

The pre-upgrade campaign is `build/recovery/pre-character-v1.sqlite`. Automatic
backup is `build/kageyoni.sqlite.pre-v5.bak`. Original project/source files are
outside this development build. Migration creates no character records or events.
Existing legacy characters continue to load; missing extensions are reported by
readiness rather than populated with guesses.

Before new story writes, recover by copying the pre-upgrade backup to a NEW path
and opening it with the previous engine, or retrying this migration with this
engine. After new writes, do not replace the campaign with an older backup: retain
the newer database and ledger, repair a copy, and reconcile events explicitly.
There is no automatic downgrade or arbitrary semantic conflict reconciliation.

## Acceptance evidence

`tests/test_characters.py` covers minimal identity and retry, rumors, hidden
details, scene/action inputs, atomic validation failures, canonical name status,
duplicate identity rejection, voluntary change history, competing sessions,
fork/snapshot/replay/reload, actual prior campaign upgrade, interrupted migration,
and CLI operations. `tests/test_engine.py` includes all four added domains in its
roundtrip regression. Full-suite and extracted-package results are stored in
`build/character-test-results.txt` and `build/character-delivery-verification.json`.

This is a character schema extension, not a completion claim for every earlier
world/Will simulation requirement. Existing Will execution and broad simulation
boundaries are not expanded by this change. Installed platform skills are not
updated; project workflow commands and this contract are the new interface.
