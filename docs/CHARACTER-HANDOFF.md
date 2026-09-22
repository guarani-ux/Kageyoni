# Character component handoff

Project: `/workspace/scratch/05f434ae971b/kageyoni-local-dev`
Campaign: `build/kageyoni.sqlite` relative to the project.
Entry documentation: `docs/CHARACTER-SCHEMA.md`.
Portable delivery: `Kageyoni-Character-Engine-v5.zip`; extract then use Python 3.

```sh
python -m kageyoni --db build/kageyoni.sqlite verify
python -m kageyoni --db build/kageyoni.sqlite session
python -m unittest discover -s tests -v
```

The live development campaign retains its 165 supplied records and one import
event. Schema migration does not claim that this supplied save includes later
story events from other conversations. No character extension was invented for
an existing person. Use `character-readiness` to find explicitly missing detail.

`build/character-fixture.sqlite` is a separate noncanonical resumable example.
Read `visitor` with `character-read`; its motive is GM-only. The example JSON in
`examples/character-create.json` can initialize a new empty fixture database.

Schema version 2, runtime 4, workflow API 3 remain unchanged. Separate component
`character_schema` is 1; migration sequence now includes 005. Registry locators
identify the new domain and command implementations. All skills in this package
are bundled prior sources, not newly installed or updated platform skills.

Migration and recovery: see `docs/CHARACTER-SCHEMA.md`. Preserve newer event
history when recovering; never overwrite it with the old backup. The saved
pre-character database is included for reproducible upgrade testing.
