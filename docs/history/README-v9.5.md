Current play checkpoint: Voss avatar revealed. See LATEST-SCENE.md; player controls Lucretia, next action pending.

Save backups now verify before publication. An opt-in isolated coliseum prototype tests combat conditions; campaign now at notebook investigation. See COLISEUM-AND-SAVE-VALIDATION.md for evidence and limits.

> **Latest play checkpoint: notebook investigation (internal revision 156).** Read `LATEST-SCENE.md` and `play/20260920-notebook/scene.md`. Earlier revision-60 counts below describe the engineering release checkpoint.

# Current build: Kageyoni v9.5, V1–V8 integrated

Start with [V9.5-HANDOFF.md](V9.5-HANDOFF.md). The engine connects persistent nodes and reviewed experience to authored encounters, document workspaces, checked method transfer, collective composition, local repository tasks, pipelines and portable operation. Menu 16 opens guided services and fields. No model API is required. The bundled campaign remains at revision 60; demonstrations are separate.

The release evidence and remaining judgment boundaries are in the handoff. Earlier sections below describe historical milestones.

# Kageyoni coordinated world-state engine

Historical release: **Writing integration v8** — see [WRITING-HANDOFF.md](docs/WRITING-HANDOFF.md) and [WRITING-EVIDENCE.md](docs/WRITING-EVIDENCE.md). Migration 008 adds writing interface 1 and retains the actual campaign and prior regression coverage.

Previous release: **Personality integration v7**, migration 007 / personality
interface 1. Start with [PERSONALITY-HANDOFF.md](docs/PERSONALITY-HANDOFF.md)
and [PERSONALITY-SYSTEM.md](docs/PERSONALITY-SYSTEM.md). The new context,
weighted approaches and grounded dialogue use the existing coordinated
decision/event workflow. Earlier release descriptions below are historical.

This is an isolated local development build of the Kageyoni event and background-process engine. The original `kageyoni-local` directory and its database were left untouched. The runtime uses Python 3.10+ and SQLite from the standard library; it does not call GitHub, a model API, a network service, or a paid subscription.

The engine stores source-grounded records, branch state, properties, rules, event resolutions, observations, consequences, background processes, dependency metadata, and versioned replay evidence. Skills and workflows are an agent-facing coordination layer. The engine owns validation, supported mechanics, random results, time advancement, transactions, and durable state. A GM or agent still supplies semantic judgments and narration where the canon does not define a mechanic.

## Run the build

From this directory:

```bash
python3 -m unittest discover -s tests -v
python3 -m kageyoni --db build/kageyoni.sqlite verify
python3 -m kageyoni --db build/kageyoni.sqlite session --input session.json
python3 -m kageyoni --db build/kageyoni.sqlite opportunities --input opportunities.json
```

The current `build/kageyoni.sqlite` preserves the resumed revision-60 campaign. The historical seed workflow below creates a separate new database:

```bash
python3 -m kageyoni --db build/fresh.sqlite init
python3 -m kageyoni --db build/fresh.sqlite seed --source-dir sources
python3 -m kageyoni --db build/fresh.sqlite verify
```

Use `workflow` to create a preview command, inspect it, and submit the unchanged command with `apply`. `preview` runs the same validation in a rolled-back transaction. `simulate` advances explicit simulation time and processes due background work. `consequences` applies structured pending effects. `history`, `replay`, `dependencies`, `registry`, `backup`, `restore`, `fork`, and `snapshot` expose the maintenance and continuity operations.

All examples and tests use clearly marked noncanonical fixtures. No fixture event is in the supplied campaign seed.

## Files

- `kageyoni/engine.py` — transactional engine, validation, property/rule evaluation, action stages, background processes, branches, replay, backup, and recovery.
- `kageyoni/workflows.py` — structured Play and Maintain operation helpers.
- `kageyoni/model.py` — authoritative domain definitions and generated `schema.sql`.
- `kageyoni/seed.py` — lossless source archive plus conservative structured extraction.
- `schemas/will/` — the uploaded `will-contract/0.1` JSON schemas, proposed table additions, fixture witness, and implementation analysis used as the Will design input.
- `migration_002.sql` — legacy schema v1 to v2 migration.
- `migration_003.sql` — runtime schema v2 to runtime v3 migration.
- `migration_004.sql` — additive versioned Will contracts and attempt metadata.
- `docs/REQUIREMENT-CHECKLIST.md` — requirement-to-behavior checklist fixed before implementation.
- `docs/REQUIREMENT-EVIDENCE-v3.md` — requirement-to-evidence report.
- `docs/WORKFLOWS.md` — executable workflow and installed-skill contract.
- `docs/TEST-REPORT.md` — observed tests, upgrade, recovery, and package checks.
- `docs/WILL-SYSTEM-HANDOFF.md` — compact Will-specific run, interface, recovery, and boundary handoff.
- `build/recovery/` — preserved prior delivery archives, the property-review candidate (kept proposed), copies of the prior v1/v2 databases, and tested upgrade candidates; see `archive-inventory.json`.
- `build/Kageyoni-Integrated-World-State-v3.zip` — verified handoff archive; its SHA-256 is in `build/PACKAGE-SHA256.txt`.

## Version and recovery rules

The legacy `schema_version` remains `2` for compatibility. Runtime components carry separate versions in `engine_versions`; the delivered runtime schema is `4` and the workflow API is `3`. Migration 004 records its checksum and predecessor in `migration_checks`, creates a `.pre-v4.bak` recovery copy before applying to a v3 database, and leaves the earlier recovery candidate intact. Back up before any migration and never overwrite the only save.

Historical event rows, rule/property versions, input declarations, judgments, random results, before/after images, and pending work are retained. A direct `set_property` call is a compatibility/administrative path and marks replay as incomplete for that auxiliary write; normal play must assign properties through an event command.

## Canon and judgment boundaries

The seed preserves confirmed and unresolved source statements with provenance. Freedom’s numerical formula, restrained intelligence, detailed Haki mechanics, unknown clock conversions, and unsupported free-text consequences remain unresolved. The engine does not invent those meanings, silently advance time because a chat message arrived, run an external scheduler, or turn relevance into a success modifier.
# Character schema release

The current development build adds character schema 1 through migration 005.
See [the executable character contract](docs/CHARACTER-SCHEMA.md) and
[acceptance checklist](docs/CHARACTER-ACCEPTANCE.md). New operations are
`character-create`, `character-read`, and `character-readiness`. They reuse the
event ledger and existing domain records. Older release descriptions below are
historical and do not expand this release's tested claims.
# Connected gameplay release

Use [CONNECTED-PLAY.md](docs/CONNECTED-PLAY.md) for the current proposal,
commitment, resolution and consequence workflow. Migration 006 adds decision
interface 1. Earlier release sections below are historical.
