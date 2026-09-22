# Kageyoni Will system handoff

This build is the isolated local implementation at
`/workspace/scratch/05f434ae971b/kageyoni-local-dev`.

## Run

```bash
cd /workspace/scratch/05f434ae971b/kageyoni-local-dev
python3 -m kageyoni --db build/kageyoni.sqlite verify
python3 -m unittest discover -s tests -v
```

The delivered database contains the source-preserving campaign seed (165
records, one import event) and no Will fixture events. Fixture campaigns are
created only in temporary test databases.

## Will interface

- `will_definition`, `will_expression`, `will_technique`, `will_awakening`,
  `will_development`, and `will_effect` are additive versioned record domains.
- `will_contract_history` preserves exact contract versions through patches and
  branches. The legacy flat `will` record remains available.
- `will-prepare` checks exact versions, bearer ownership, typed preconditions,
  target scope, and units; it records an attempt reservation and one stable
  random result without creating a fictional event.
- `will-apply` commits only the stored engine-compiled result as one atomic
  `will_attempt` event. It rejects stale inputs, altered outcomes, rerolls, and
  caller-injected state deltas.

Example CLI shapes are in
`skills/kageyoni-play/references/command-contract.md`; the uploaded design
schemas and analysis are under `schemas/will/`.

## Versions and recovery

The legacy SQL marker remains `2`. Runtime schema is `4`; workflow API is `3`.
`migration_004.sql` records predecessor `3` and its checksum in
`migration_checks`. The prior runtime-v3 database is retained as
`build/kageyoni.sqlite.pre-v4.bak`; the original source project/database remain
outside this development directory and were not modified.

The verified handoff archive is
`build/Kageyoni-Integrated-World-State-v4.zip` with SHA-256 in
`build/PACKAGE-SHA256-v4.txt`. It was extracted into a temporary directory and
passed the full 98-test suite, manifest hash verification, and database
verification.

## Boundaries

The engine does not invent the numerical freedom formula, restrained
intelligence, detailed Haki mechanics, universal awakening semantics, or
unsupported prose effects. Those remain explicit proposed mechanics or bounded
GM judgments.
