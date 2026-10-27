# Kageyōni Outpost Registry

The **Outpost Architecture** establishes WSL2 (`/home/flowe/outposts`) as an isolated runtime sandbox for new downstream systems, tool chains, and micro-applications. This guarantees that the Kageyōni core causal engine and repository remain pristine and frozen, while downstream development proceeds with native Linux tooling, dedicated `.venv` environments, and independent lifecycles.

## Invariant Fences
1. **Core Freeze**: Outposts are downstream consumers and experimental satellites. They never mutate or import core Kageyōni files without formal qualification.
2. **Runtime Isolation**: Each outpost maintains its own `.venv`, `.state/`, and `out/` directories inside `/home/flowe/outposts/<name>`.
3. **Single-Gate Entrypoint**: Every outpost implements `runner.py` with `test`, `run`, and `status` subcommands.
4. **Host Mirroring**: Windows host tools interact with outposts via the UNC path `\\wsl$\Ubuntu\home\flowe\outposts\<name>` and `python -m tools.runner outpost <command>`.

## Outposts Table

| Outpost Name | Created At | Primary Mandate | Status | Tests | Path (WSL) | Path (Host) |
|---|---|---|---|---|---|---|
| sample-probe | 2026-10-27 03:44 UTC | Downstream isolated subsystem | ACTIVE | PASSED | `/home/flowe/outposts/sample-probe` | `\\wsl$\Ubuntu\home\flowe\outposts\sample-probe` |
