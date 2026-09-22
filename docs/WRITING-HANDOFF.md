# Writing integration v8

Start a fresh session in the extracted `kageyoni-local-dev` directory. The actual campaign is `build/kageyoni.sqlite`; the deliberately noncanonical demonstration is `build/writing-fixture.sqlite`. Python 3.10+ and SQLite suffice; no model service or subscription is required.

## Run

```bash
python -m kageyoni --db build/kageyoni.sqlite verify
python -m unittest discover -s tests -v
python -m kageyoni --db build/writing-fixture.sqlite writing-publish --input examples/writing-resume.json
```

The last command resumes the fixture at revision 8 and records a recap at revision 9. Repeating it returns the same receipt. Use a copy if retaining the pristine fixture matters.

## Agent writing workflow

Opening a campaign through the existing session workflow returns `writing_contract` version 1. Existing installed Play/Maintain skills are preserved; this release does not claim a new skill installation. Project workflows expose the new commands.

1. Request `writing-brief` with branch, form, audience, purpose, optional perspective, scene, focus identifiers and event identifiers. Ten forms cover narration, dialogue, situation, scenario, event, history, discovery, reflection, recap and description.
2. Treat private authoring context separately from audience evidence. Use existing personality, Will, knowledge, relationships and current situation. A personality label supplies neither a mandatory line nor a success modifier.
3. Draft concrete prose for this audience and purpose. Suspense can arise from an unresolved question; quietness, humor, curiosity, beauty and play need no compulsory conflict or roll. Preserve motives, resolved outcomes and open decisions. Distinguish witnessed details, beliefs and inference.
4. For an actual utterance use the existing `dialogue-propose` decision path. Optional rhetoric records purpose, strategy, subtext and fallible assumptions about named listeners. Resolve the action before describing its outcome. `dialogue-receive` records an explicitly judged interpretation only after matching hearing evidence exists. The listener's current interpretation enters later personality/decision context.
5. Publish delivered prose with `writing-publish`: request_id, expected_revision, exact brief_spec and brief_hash, text, claims and review. Each claim has statement, status (fact/belief/possibility) and exact-version source basis. Review names its author and rationale and attests grounding, perspective, voice, agency and pacing. See `examples/writing-resume.json` and `examples/writing_journey.py` for executable payloads.
6. Corrections create a new record with supersedes; never patch a prior delivery or reception. An interpretation does not automatically alter trust, knowledge, Will or objective truth. Use ordinary event/decision operations for such changes.

Publishing records presentation and advances recording revision, not simulation time. It cannot prove a human read the text. A newly recorded presentation conservatively invalidates earlier state-dependent proposals. The engine supplies context and validates structured references, audience scope, versions, transactions and retries. The host still writes and reviews prose.

## Storage and evolution

`kageyoni/writing.py` owns writing interface 1, form guidance, scoped briefs, evidence validation, delivery and reception operations. `migration_008.sql` follows migration 007 and is checksum verified. Generic records, branch history, snapshots and replay remain authoritative; no parallel world database was introduced. New domains are `writing_delivery` and `dialogue_reception`. Exact briefs, claims, source versions and reviews remain private event evidence. Decision fingerprints include the new component while explicitly supporting authentic pre-v8 pending decisions.

The research text and provenance are in `docs/research/`. Its citations are retained as supplied, not independently verified. Its recommendations guide composition, not numerical mechanics or canon. Canon sources remain unchanged.

## Upgrade and recovery

Back up with the engine before opening an earlier campaign in this build. Opening applies ordered migrations, validates predecessor/checksum and takes its own pre-migration backup. `build/recovery/pre-writing-v1.sqlite` is the preserved real v7 campaign; prior recovery candidates remain bundled. An interrupted migration rolls back and can be retried. Tests cover actual-v7 pending decisions and interrupted migration, not merely fresh table creation.

Before any new story writes, restore a verified pre-upgrade backup to a separate path with a compatible engine if needed. After new writes, retain the current database and its history: do not overwrite it with an older save. Reconcile or export newer events explicitly before any rollback; automatic cross-version reconciliation is not claimed. Keep concurrent sessions on revision-checked operations and retain request identifiers on retries. CLI viewer selection is filtering, not authentication.

## Boundaries

The engine cannot prove arbitrary prose is faithful, engaging or free of a hidden detail. Structured references are filtered and checked; the named GM review covers semantics, emotional credibility, subtext and literary quality. Raw trusted authoring APIs remain available and do not enforce every specialized workflow annotation. Context represents stored evidence, not a complete psychological simulation. No external scheduler, model API, new freedom formula, Haki interpretation or inferred canonical personality was added.

See `WRITING-ACCEPTANCE.md`, `WRITING-EVIDENCE.md` and `build/writing-delivery-verification.json` for acceptance and delivery evidence.
