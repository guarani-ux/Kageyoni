# Maintain operation routing

| Request | Operation | Evidence to read before mutation |
| --- | --- | --- |
| inspect campaign or engine | `verify`, `session`, `registry`, `replay` | branch revisions, runtime versions, pending work, source hashes |
| inspect impact | `dependencies` or `maintain dependencies` | registry entries, rule/property dependencies, event usage |
| add supported property | `maintain define_property` | type, unit, facets, constraints, consumers, provenance |
| change meaning/unit/type | `maintain revise_property` | old references, replacement mapping, historical usage |
| retire property | `maintain retire_property` | downstream dependency report and replacement decision |
| add mechanic | `maintain add_rule` | inputs, outputs, units, preconditions, version, cycle check |
| add module | `maintain register_module` | triggers, context, commands, dependencies, compatibility |
| migrate SQL | ordered migration script | predecessor, checksum, backup, fresh and upgrade tests |
| recover or branch | `restore` or `fork` | candidate verification, revision, source hashes, newer events |

Maintenance operations may update registry and schema metadata. They do not append fictional history unless the user explicitly requests a story event through Play.
