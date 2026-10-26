---
name: nin-console
description: SSL 4000 Mixing Console operator for Ninshū. Manages channel strip routing, 20 controls, 8 knobs, fader scheduling, and master prints.
---

# SSL 4000 Console Operator (`/nin-console`)

Operates the Ninshū SSL 4000 mixing desk to route, modulate, filter, and freeze systems execution across the 48-channel capability estate. Every control maps directly to a verified computational behavior under the SSL Control Contract.

## Table of Contents

- [1. Console Routing Architecture](#1-console-routing-architecture)
- [2. The 20 SSL Controls Quick Reference](#2-the-20-ssl-controls-quick-reference)
- [3. Running a Mix Session](#3-running-a-mix-session)
- [4. Master Print Freezing](#4-master-print-freezing)

---

## 1. Console Routing Architecture

The board routes signals across 6 dedicated busses:
- **Bus A**: Low-Level Binary & Executable Transduction (CH 01–08)
- **Bus B**: Managed Runtimes & Embedded Transduction (CH 09–16)
- **Bus C**: Dynamic Tracers & Memory Interception (CH 17–24)
- **Bus D**: App Containers & Semantic Boundary Transduction (CH 25–32)
- **Bus E**: Telemetry, Network Protocols & Forensics (CH 33–40)
- **Bus F**: Causal Governance & Kageyōni Core Engine (CH 41–48)

---

## 2. The 20 SSL Controls Quick Reference

- **Route & Membership**: `Discovery/Route` (resolves tier and entrypoint), `Patch/Bus Membership` (attaches strip to bus DAG).
- **Ingress & Scope**: `Preamp Trim` (enforces max input bytes and recursion depth), `HPF/LPF Scope` (filters confidence floors and time ceilings with disclosed omissions).
- **Budgets & Flow**: `Four-Band EQ` (allocates compute across LF headers, LMF CFG, HMF runtime state, HF strings), `Dynamics Backpressure` (bounded queue with overflow receipts).
- **Channel State**: `Fader/Priority` (governs scheduling order under contention), `Mute` (suppresses projection while preserving raw failure evidence), `Solo` (isolates strip while keeping mandatory Scar guards active).
- **Epistemic Lenses**: `Noise Gate` (squelches ungrounded chatter, preserves high-reliability negative findings), `Phase Compare` (computes constructive lock vs contradiction), `Phase Invert` ($\varnothing$ adversarial disconfirmation mode), `Predicate Selector` (restricts extraction to selected families), `Compression` (lossless summarization with SHA-256 evidence pointers), `Insert/Bypass` (chained transform slots).
- **Master Stage**: `Meter Bridge` (strictly measured runtime telemetry), `Ageing/Patina` (empirical SQLite drift tracking), `Scar Guard` (enforces registered invariants), `Master Print` (freezes canonical `master_print.json`), `Pause/Resume/Stop` (`ProcessSupervisor` run tokens).

---

## 3. Running a Mix Session

Execute a channel or patch via the in-tree CLI or Python API:

```bash
# Query the desk and list channels
python -m kageyoni.ninshu.cli channels

# Route an intent to the optimal channel mix
python -m kageyoni.ninshu.cli route "inspect elf binary header" --subject elf

# Or run via Python API inside active scripts:
from kageyoni.ninshu.patchbay import Patchbay
from kageyoni.ninshu.console import ActiveConsole

pb = Patchbay()
console = ActiveConsole()
res = pb.execute_channel(2, raw_bytes, console=console)
```

---

## 4. Master Print Freezing

Every complete multi-channel analysis run must freeze a cryptographically signed `master_print.json` binding input hashes, active strip parameters, raw channel receipts, and thermodynamic metrics. Master prints are stored in the session artifacts directory and verified in cold processes.
