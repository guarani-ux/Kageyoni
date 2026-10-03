# Kageyoni-Shinobi

One persistent participant served by replaceable host cognition, executing natively on the Kageyoni Engine. Python 3.10+, standard library and Kageyoni core dependencies.

The participant directory lives at `shinobi/` within the Kageyoni repository.

## Architecture & Integration

Unlike standalone Shinobi which maintained an isolated SQLite schema, Kageyoni-Shinobi anchors directly into Kageyoni's transactional engine:
* **Persistent Identity**: Registered via `PersistentParticipant` with a durable character ID (`shinobi`) and node binding in `network_nodes`.
* **Bounded Turn Briefs**: Every `begin` call derives a live Kageyoni turn context via `prepare_turn(domain=...)`, delivering qualified lessons and eligible methods into the request packet.
* **Communication**: Host `message` emissions are formally committed into Kageyoni's event stream and `dialogue_turn` table as attributed turns to an `operator` character.
* **Returns & Learning**: Candidate Returns can be linked to Kageyoni lessons. Upon adjudication (`ACCEPTED`), lessons are qualified through `Learning.review()` and saved configurations are updated.
* **Schema Migration**: Protocol state (encounters, responses, returns) is managed via `migration_024.sql` (`shinobi_identity`, `shinobi_encounters`, `shinobi_returns`).
* **Scout Horizon**: Reads sibling directories and local `forms/*.json` statically via AST and token intersection without importing or executing external code.

## Quickstart

```sh
# Initialize new participant identity
python shinobi/shinobi.py --home shinobi/.state/itachi init --name Itachi --configuration-file shinobi/profiles/first-participant.json

# Begin an encounter
python shinobi/shinobi.py --home shinobi/.state/itachi begin --topic handoff --task "Prepare a note from the brief." --input shinobi/examples/brief.txt --allow-write > shinobi/.state/itachi/request.json

# Reply to an encounter (host response)
python shinobi/shinobi.py --home shinobi/.state/itachi reply shinobi/.state/itachi/response.json

# Inspect participant status & ledger
python shinobi/shinobi.py --home shinobi/.state/itachi inspect
```

## Testing

Run the test suite:

```sh
python shinobi/tests/test_shinobi.py
```
