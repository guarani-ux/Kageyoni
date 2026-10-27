# Start here — Kageyoni System Estate

> [!IMPORTANT]
> **READ `ATLAS.md` FIRST.**
> The complete architectural map, domain boundaries, and 6-domain estate topology are canonically documented in [`ATLAS.md`](ATLAS.md). Any agent or engineer entering this repository must orient using `ATLAS.md` before initiating work.

For the core causal simulation engine and v10/v11 operations, read [`KAGEYONI.md`](KAGEYONI.md).

Verify the available tools or causal state:

```sh
python -m tools.runner --list
# or verify the causal database state:
python -m kageyoni --db build/kageyoni.sqlite verify
```

Ask the engine what it can represent:

```json
{"service":"simulation","action":"capabilities","arguments":{}}
```

Run JSON commands through the single operation surface:

```sh
python -m kageyoni --db build/kageyoni.sqlite operate --input command.json
```

For engineering status and evidence, read `V10-HANDOFF.md`.
For the previous v9.5 start document, see `docs/history/START-HERE-v9.5.md`.
