---
name: outpost-workflow
description: Canonical workflow for instantiating, verifying, and running isolated downstream systems in WSL2 outposts without polluting Kageyoni core.
---

# Outpost Workflow & Tooling Engine

The **Outpost Workflow** establishes WSL2 (`/home/flowe/outposts`) as the sovereign, isolated runtime sandbox for new downstream systems, micro-applications, tool chains, and experimental engines.

By enforcing strict physical and virtual boundaries, the Outpost architecture protects the **Kageyōni Core Causal Engine** (`c:\Kageyoni`) from dependency bloat, foreign package contamination, and architectural rot, while providing downstream projects with a native Linux execution environment.

---

## Architectural Invariants & Boundary Laws

1. **Frozen Core Invariant**: Kageyōni core files (`kageyoni/*`, `tools/*`, `data/*`) are frozen and pristine. Outposts must never write back to or directly import Kageyōni core without formal extraction, packaging, and qualification gates.
2. **Runtime Isolation Invariant**: Every outpost resides at `/home/flowe/outposts/<name>`. Third-party dependencies are strictly installed inside the outpost's private virtual environment (`.venv`). Global pip installations are banned.
3. **Single-Gate Entrypoint**: Every outpost must provide a `runner.py` implementing `test`, `run`, and `status`. External runners interact solely through this single gate.
4. **Day-0 Qualification Invariant**: An outpost is not valid until its Day-0 smoke tests pass 100% inside WSL2 immediately upon creation.
5. **Host-Sandbox Parity**: Outposts are mirrored to Windows via the UNC path `\\wsl$\Ubuntu\home\flowe\outposts\<name>` for editing, and invoked from Windows PowerShell via `python -m tools.runner outpost <subcommand>`.

---

## Directory Topology of an Outpost

```
/home/flowe/outposts/<name>/
├── .state/              # Isolated local runtime state (checkpoints, SQLite, cache)
├── .venv/               # Linux Python 3 virtual environment
├── config/              # Configuration files
│   └── settings.json    # Outpost runtime configuration & parameters
├── out/                 # Generated deliverables, exports, reports
│   └── .gitkeep
├── src/                 # Outpost domain modules
│   ├── __init__.py      # Package root and version metadata
│   ├── ingest.py        # Input data, feed, or telemetry ingestion
│   ├── filter.py        # Boundary validation, filtering, deduplication
│   ├── core.py          # Primary domain computation & business logic
│   └── export.py        # Deliverable serialization (JSON, Markdown)
├── tests/               # Test suite
│   ├── __init__.py
│   └── test_smoke.py    # Day-0 verification smoke tests
├── CHARTER.md           # Outpost contract, scope, and reversibility tiers
├── pyproject.toml       # Linux Python project metadata
└── runner.py            # Single-gate entrypoint CLI
```

---

## 5-Step Operational Lifecycle

### Step 1: Charter & Mandate Definition
Before scaffolding code, define the outpost's operational boundary:
- **Outpost Name**: Alphanumeric identifier (`^[a-zA-Z0-9_\-]+$`), e.g., `signal-harvester`, `market-indexer`, `telemetry-probe`.
- **Primary Mandate**: A concrete 1-2 sentence statement of what the subsystem ingests, computes, and exports.
- **Reversibility Tiers**:
  - *Tier 0*: Local test execution, pipeline dry-runs, editing `src/` modules.
  - *Tier 1*: Purging `.state/`, clearing `out/`, destroying and recreating `.venv`.
  - *Tier 2*: External network mutations, pushing deliverables to remote registries.

### Step 2: Mechanical Scaffolding
Instantiate the outpost using the unified tool runner:

```powershell
python -m tools.runner outpost create <name> --mandate "<Description>"
```

The scaffolding engine automatically:
1. Creates the complete directory topology in WSL2 Ubuntu (`/home/flowe/outposts/<name>`) and verifies the host UNC mirror (`\\wsl$\Ubuntu\home\flowe\outposts\<name>`).
2. Generates canonical contracts: `CHARTER.md`, `runner.py`, `pyproject.toml`, `config/settings.json`.
3. Generates the 4-stage pipeline scaffolding: `src/ingest.py`, `src/filter.py`, `src/core.py`, `src/export.py`.
4. Provisions an isolated Linux virtual environment (`python3 -m venv .venv`).
5. Grants executable permissions to `runner.py`.

### Step 3: Day-0 Qualification Verification
Upon creation, the tooling engine automatically triggers the Day-0 qualification smoke test inside WSL:

```bash
cd /home/flowe/outposts/<name>
.venv/bin/python runner.py test
```

Verification verifies:
- `config/settings.json` schema validity.
- Clean module importability.
- End-to-end execution of `ingest` -> `filter` -> `core` -> `export`.
- Production of valid artifacts in `out/`.
- Strict runtime isolation.

The result is registered in `c:\Kageyoni\OUTPOSTS.md`.

### Step 4: Iterative Outpost Development inside WSL
Develop and customize the outpost within its isolated sandbox:

- **File Editing from Windows**: Open and edit files via the Windows UNC path:
  ```
  \\wsl$\Ubuntu\home\flowe\outposts\<name>\
  ```
- **Dependency Management inside WSL**:
  If external packages are required, install them strictly into `.venv`:
  ```bash
  wsl -d Ubuntu -e bash -c "cd /home/flowe/outposts/<name> && .venv/bin/pip install <package>"
  ```
- **Running Tests**:
  ```powershell
  python -m tools.runner outpost test <name>
  # Or with verbose output:
  python -m tools.runner outpost test <name> -v
  ```

### Step 5: Deliverable Export and Monitoring
Execute the outpost pipeline to produce verified artifacts:

```powershell
# Execute the full pipeline:
python -m tools.runner outpost run <name>

# Execute with custom input:
python -m tools.runner outpost run <name> --input path/to/input.json

# Check health, venv status, and deliverable inventory:
python -m tools.runner outpost status <name>
```

Deliverables are written to:
- JSON deliverables: `out/export_<timestamp>.json`
- Human-readable summaries: `out/export_summary.md`

All outputs remain within the outpost directory, leaving Kageyōni core completely untouched.

---

## Outpost CLI Quick Reference

| Action | Command |
|---|---|
| **Create Outpost** | `python -m tools.runner outpost create <name> --mandate "<mandate>"` |
| **List Outposts** | `python -m tools.runner outpost list` |
| **Test Outpost** | `python -m tools.runner outpost test <name> [-v]` |
| **Run Outpost** | `python -m tools.runner outpost run <name> [args...]` |
| **Inspect Status** | `python -m tools.runner outpost status <name>` |
| **Audit Hygiene** | `python -m tools.runner check-hygiene` |
