# Start here — Kageyoni v10.0.0

Read `KAGEYONI.md` first.

Verify the included state:

```sh
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
