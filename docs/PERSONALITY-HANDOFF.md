# Kageyoni personality integration — handoff

Extract `Kageyoni-Personality-Engine-v7.zip`; use its `kageyoni-local-dev` root.
Read `docs/PERSONALITY-SYSTEM.md` and `docs/PERSONALITY-EVIDENCE.md`.

```bash
python -m kageyoni --db build/kageyoni.sqlite verify
python -m kageyoni --db build/kageyoni.sqlite session
python -m unittest discover -s tests -v
```

`build/kageyoni.sqlite` is the preserved campaign import upgraded in the
development copy: 165 source-derived records, one import event. It does not
assert that an older source save is latest canon. New personalities are unassigned.

`build/personality-fixture.sqlite` is NONCANONICAL. Resume it with:

```bash
python -m kageyoni --db build/personality-fixture.sqlite personality-context --input examples/personality-context.json
python -m kageyoni --db build/personality-fixture.sqlite decision-read --input examples/personality-resume-read.json
python -m kageyoni --db build/personality-fixture.sqlite decision-commit --input examples/personality-resume-commit.json
```

Repeated commitment returns the existing receipt. Changed circumstances require
a new proposal ID. Private GM output belongs outside participant narration.
To reproduce the journey use a NEW path (the script refuses overwrite):

```bash
python -m examples.personality_journey --db build/new-personality-fixture.sqlite --report build/new-personality-results.json
```

## Upgrade/recovery

1. Close writers and use `backup` to a new path. Preserve prior saves/ledgers.
2. Open a COPY with this engine. Ordered migrations validate predecessors and
   checksums. Migration 007 creates `.pre-v7.bak` before transactional DDL. It
   preserves existing aspect columns and creates no story events.
3. Integrity and foreign keys are checked before the migration receipt commits.
   Run `verify`, `replay` and inspect branch/revision after upgrade.
4. Migration failure rolls back DDL/receipt together. Correct its cause and reopen
   using the intact versioned scripts. Checksum modifications are rejected.
5. `build/recovery/pre-personality-v1.sqlite` is the verified v6 recovery save.
   Restore to a NEW path. Before new story writes it supplies the prior consistent
   state; after new writes preserve the newer ledger and reconcile explicitly.
   No automatic destructive downgrade or event merge is provided.

An authentic old-engine pending decision fixture is included as
`build/recovery/legacy-personality-pending.sqlite` for portable upgrade testing.
Only the added personality component is omitted in its old fingerprint check;
other state, rule or property changes still make it stale. Concurrent sessions
use revisions/transactions. Never replace a newer save with an older archive.

Use personality context/evaluation and dialogue proposal through the existing
decision commit path. Define policies with `maintain / add_rule`; apply growth
as structured outcomes. Ordinary play needs no improvised SQL. Installed skills
were preserved; load the project workflow guide for the new capacities.

Will associations remain contextual and authored. Freedom, Will mastery,
learned competence, power and agency stay distinct. GM interpretation and
expressive prose remain essential.
