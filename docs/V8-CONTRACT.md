# V8 daily operation

`python -m kageyoni.console --db PATH --initialize` installs additive interfaces and opens the daily menu. `--input command.json` runs one allowed service call. `python -m kageyoni --db PATH operate --input command.json` uses the same dispatch. The historical terminal exposes menu 16. These local operational controls are owner-only; they are not a character-authorized remote API. The guided menu lists services/actions and shows required/optional fields with defaults from their actual signatures; nested values accept JSON and text fields accept plain text. Command files use explicit JSON arguments and failures remain visible; there is no model API, key or paid fallback.

A command has `service`, `action`, and `arguments`. For example:

```json
{"service":"operations","action":"settings","arguments":{"values":{"max_checks":300,"max_artifact_bytes":10485760,"host_available":false}}}
```

Settings persist in append-only history. Availability describes an externally supplied host; setting it true does not install or invoke one. Semantic requests continue through the pipeline's persisted manual handoff.

## Portable state

`Operations.export_bundle(path)` writes a new ZIP containing a consistent SQLite backup, immutable artifact content files and a SHA-256 manifest. Existing destinations, absent referenced files, corrupt artifacts and symlink sources are rejected. `Operations.import_bundle(bundle,destination)` requires a new directory, validates member names, sizes, checksums, every referenced artifact and the engine before promotion. It never replaces a newer save. SHA-256 detects changed bytes; it does not authenticate an untrusted author's identity.

A portable bundle does **not** mirror repository working trees, original source directories or external pipeline outputs. Its manifest lists these dependencies and import reports them as unresolved. The saved workflow and receipts survive, but relocated execution must explicitly rebind validated replacement roots/trees before accessing external paths. A completed historical external effect is a receipt, not proof the file exists on the new machine. Rebinding and reconciliation preserve that distinction. Imported work must never automatically reach back to the original machine's paths.

`Operations.migrate_copy(source,destination)` copies SQLite through its backup API, opens and upgrades only that copy, and verifies it. A failed copy remains inspectable without modifying the source. Full database backup preserves operational history; world-event replay remains a different operation.

## Evaluated policy

The registered policy is deliberately bounded: order of UTF-8, size and expected-digest checks on an artifact. Every accepted artifact passes all three. A proposal cannot remove, duplicate or invent checks. `trial_policy` executes baseline and candidate checks against identical byte inputs, requires positive and negative controls, and calculates check invocations itself. There is no caller-supplied success flag. Only unchanged accept/reject decisions with fewer check invocations support activation. Corpus selection is attributed to the operator; this is an operation-count comparison, not a wall-time or domain-quality benchmark.

Activation is exact-scope and binds the baseline policy. Subsequent actual pipeline writes consume the selected check order through `check_artifact`; each run records policy, byte digest, count, time and disposition. Unrelated scopes retain their own policies. Rollback appends a new activation pointing to the previous policy; intervening artifact checks and trials remain visible. `verify_operations` recomputes trial outputs and checks policy ancestry, migration checksum and immutable row hashes.

Budget exhaustion blocks the artifact check rather than pretending it succeeded. The check-order policy cannot confer permissions, interpret narrative intent, change a character or grant professional competence. Representative production benefit and the broad four-condition benchmark remain separate from these mechanical controls.
