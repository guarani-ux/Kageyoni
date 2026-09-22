Current play checkpoint: Voss avatar revealed. See LATEST-SCENE.md; player controls Lucretia, next action pending.

> **Latest play checkpoint: notebook investigation (internal revision 156).** Read `LATEST-SCENE.md` and `play/20260920-notebook/scene.md`. Earlier revision-60 counts below describe the engineering release checkpoint.

# Start here — Kageyoni v9.5

Open a terminal in the extracted `Kageyoni-v9.5-Foundation` directory:

```sh
python3 terminal.py --db build/kageyoni.sqlite
```

Read [V9.5-HANDOFF.md](V9.5-HANDOFF.md) for current features, installation, connected demonstration and recovery. Menu 16 opens workspaces and daily operation. The included campaign is the revision-60 checkpoint; use your newer working save if play has continued. Runtime requires Python 3.10+ and no model API.

The notes below preserve the original terminal release; their counts and feature limits are historical.

# Historical Kageyoni Terminal release

A working, numbered-menu terminal interface for the bundled Kageyoni v8 world-state engine. Python 3.10 or newer; standard library only. No pip installation, API keys, paid calls, browser, or server.

## Launch

Extract the ZIP, open a terminal in `Kageyoni-Terminal`, and run:

```sh
python3 terminal.py
```

On Windows:

```powershell
py -3 terminal.py
```

Choose **Workspace → Import database into a new working copy** to import your authoritative SQLite campaign. Or choose **Start a copy of the bundled historical seed** to explore the interface. The bundled seed is NOT the latest played campaign. It has one import event and 165 records.

To open a working copy directly:

```sh
python3 terminal.py --db /path/to/world.sqlite
```

Paths with spaces must be quoted. Settings and imported databases default to `terminal-data` beside the launcher; use `--data-dir` to choose another location. Opening an existing database creates a SQLite recovery backup before the inherited engine opens or migrates it. Sources imported via the menu remain untouched. Directly opened working databases may receive engine migrations and confirmed edits.

## Menus and fields

- Workspace: open/import databases, copy seed, switch existing branches.
- Characters: searchable/paged list, profile and linked records through the character API.
- Inspect records: searchable/paged records across all existing engine domains.
- Edit a record field: field names/types come from the engine schema; numeric/structured inputs use JSON. The preview shows the old value, new value, command, and validation result.
- Preview imported event command: load a JSON command supported by Engine.apply, validate without applying, then commit separately. Decision and writing reserved commands must still use their dedicated engine workflows; this import is not a substitute for those APIs.
- Commit/discard: explicit COMMIT saves the exact previewed payload, with a backup first. Stale revisions are rejected rather than silently rebased. Failed preview clears an older pending command. Cancel leaves a preview pending until discarded or exit.
- History, verification, export, backup, and settings.
- Character perspective filters displayed/exported context and disables authoring/history/backup in that view. This is a single-user trusted-owner application, NOT an account security boundary. The owner can switch perspective and owns the database.

Records commit immediately to SQLite; exiting does not require an additional Save. Uncommitted previews are discarded on exit. Settings save atomically. No story time advances merely by opening or inspecting records. Field editing is explicitly administrative authorship with a reason/provenance note, not an automatic played action.

## Current boundaries

This is a portable line-oriented terminal UI, not a mouse-driven full-screen interface. It includes real code and the existing engine, not a mockup. It does not implement the proposed v9 intelligence network, new Will semantics, new character genesis, or document/repository workspaces. The roadmap menu states this explicitly.

No AI provider is connected. Use an already authorized assistant environment to prepare engine inputs, then inspect and validate them here. The interface does not treat a ChatGPT subscription as an API credential. Existing engine semantics still require human/GM judgment: structural validation cannot guarantee that arbitrary prose preserves meaning or agency.

No engine source, schema or migration was changed to add the terminal app. `terminal.py` and `tests/test_terminal.py` are the new integration. Existing engine documentation and source provenance remain included. Build/recovery artifacts retain historical names; their presence does not imply new verification of all old reports.

## Validation

```sh
python3 -m unittest discover -s tests -q
```

Observed in the development environment: **168 tests passed**, comprising the 160 inherited tests and eight new terminal integration tests. New tests cover preview isolation, exact commit, save/reopen/replay, stale writes, invalid input rollback, perspective restrictions, non-overwriting imports, missing databases, typed inputs, terminal control-character filtering, settings persistence, and menu exit.

An interactive terminal smoke run also launched, copied the seed, verified the working database, and exited. Linux/Python 3.12 was executed; native Windows/macOS execution was not available for testing.

## Files

- `terminal.py`: menu app and engine adapter.
- `tests/test_terminal.py`: integration and failure tests.
- `terminal-test-results.txt`: observed test output.
- `kageyoni/`, migrations, schemas, sources, skills, docs: preserved v8 engine package.
- `SHA256SUMS.json`: archive-entry integrity manifest (excludes itself).

To reproduce the menu demonstration without touching your latest campaign, use a separate data directory and the seed-copy option. Backups accumulate deliberately; remove only copies you have independently decided are no longer needed.
