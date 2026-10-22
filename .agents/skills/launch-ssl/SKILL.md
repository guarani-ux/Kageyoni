---
name: launch-ssl
description: Operational Launch & Mixing Console for the Ninshū SSL 4000 Capability Estate. Wields the 48-channel desk to route user intent, assemble reactive sub-mixes, and patch live capabilities across reverse engineering (REA) and causal governance (Kageyōni) without code duplication.
---

# Launch SSL: The Ninshū 4000 Mixing & Launch Console

You operate the **Launch SSL** skill—the active flight deck and master fader section for the **Ninshū 4000 Capability Estate** (`kageyoni.ninshu`). 

Whenever a user, situated daimon, or Shinobi participant needs to execute complex technical work (reverse-engineering binaries, intercepting network protocols, managing causal world-state, or compiling multi-agent encounters), you do **not** write raw ad-hoc scripts or clone folders. You **patch and launch channels directly from the 48-Channel SSL Desk**.

---

## 1. Quick Launch CLI Reference

The desk is permanently available in-tree via Python stdlib:

```sh
# 1. Inspect the 6 Master Busses
python -m kageyoni.ninshu.cli busses

# 2. List all channels or filter by bus (BUS_A to BUS_F)
python -m kageyoni.ninshu.cli channels --bus BUS_A

# 3. Route any natural language intent to the minimum-sufficient channel sub-mix
python -m kageyoni.ninshu.cli route "extract electron ipc channels and secrets" --subject electron --max-tier 0

# 4. Patch selected channels into an active Daimon Sub-Mix
python -m kageyoni.ninshu.cli patch 25,26,38 --name "electron_triage_submix"

# 5. Inspect an individual channel strip (1 to 48)
python -m kageyoni.ninshu.cli channel 34
```

---

## 2. In-Code Python Launch (Zero-Latency Programmatic Access)

Any agent, Shinobi participant, or test harness can patch channels dynamically:

```python
from kageyoni.ninshu import Patchbay

# Initialize the patchbay (loads/caches SQLite index in milliseconds)
desk = Patchbay()

# 1. Route intent to channels
submix_channels = desk.route(
    intent="find ssl certificate pinning and intercept traffic",
    subject="pcap",
    max_tier=1,     # Allow up to Tier 1 (gated dynamic inspection)
    limit=3
)

# 2. Build the live patch manifest
channel_ids = [ch["channel_number"] for ch in submix_channels]
patch_manifest = desk.patch(channel_ids, daimon_name="ssl_barrier_breaker")

# 3. Check governance tier before firing
if patch_manifest["requires_human_gate"]:
    # Tier 1 action: Must notify and await human key-turn if executing foreign hooks
    print(f"WARNING: POTENTIALLY DESTRUCTIVE ACTION (Tier {patch_manifest['reversibility_tier']})")
```

---

## 3. The 6 Master Busses at a Glance

| Bus ID | Master Bus Name | Channel Range | Typical Use Cases |
| :--- | :--- | :--- | :--- |
| **`BUS_A`** | **NATIVE MACHINE & DECOMPILATION** | CH 01 – 08 | PE/ELF/Mach-O headers, Ghidra P-Code, Hopper CFG, Cutter/Rizin, IDA telemetry, Objdump. |
| **`BUS_B`** | **MANAGED RUNTIMES & BYTECODE** | CH 09 – 16 | .NET CLR BSJB streams, NativeAOT, WASM (`wabt`), EVM (`evmole`), Go `pclntab`, Rust demangling, bare-metal ROMs. |
| **`BUS_C`** | **DYNAMIC MEMORY & PROCESS HOOKS** | CH 17 – 24 | Frida stalker, memory interceptor, GDB/Pwndbg core dumps, Rizin debugging, LLDB native tracer, process supervisor. |
| **`BUS_D`** | **APP BUNDLES & MOBILE RUNTIMES** | CH 25 – 32 | Electron ASAR unpacking, IPC boundary scanning, Chrome DevTools (CDP), Android APK/DEX, Jadx, Apktool, Flutter Dart AOT. |
| **`BUS_E`** | **NETWORK, PROTOCOLS & SIGNALS** | CH 33 – 40 | PCAP flow reassembly, TLS/SSL handshake & SNI, Mitmproxy flow decode, Protobuf sniffer, SQLite forensics, secret radar. |
| **`BUS_F`** | **CAUSAL GOVERNANCE & SYNTHESIS** | CH 41 – 48 | Kageyōni SQLite ACID event store, Composition Compiler, EffectResolver polyphony, V11 ProtectedOperations, Levi Epistemic Firewall. |

---

## 4. Standard Patch Templates (Battle-Tested Sub-Mix Presets)

When facing common technical encounters, load these pre-wired 3-track channel patches:

### Preset 1: The "SSL / TLS Barrier Breaker" Patch
* **Objective**: Bypass SSL certificate pinning and inspect encrypted API traffic.
* **Channels**:
  - **CH 34**: TLS / SSL Handshake & SNI Extractor (`rea_forge/src/pcap`) — *Passive, Tier 0*
  - **CH 18**: Dynamic Memory Interceptor (`rea_forge/src/contracts/fridaToolContracts.ts`) — *Active Hook, Tier 1*
  - **CH 35**: Mitmproxy Offline Flow Decoder (`rea_forge/bridge/mitmproxy/capture.py`) — *Passive, Tier 0*
* **Command**: `python -m kageyoni.ninshu.cli patch 34,18,35 --name "ssl_barrier_breaker"`

### Preset 2: The "Electron Desktop App Triage" Patch
* **Objective**: Deconstruct a desktop application (Slack, Discord, VSCode extension), scan IPC channels, and extract API keys.
* **Channels**:
  - **CH 25**: Electron ASAR Archive Unpacker (`rea_forge/src/contracts/javascript/electronToolContracts.ts`) — *Tier 0*
  - **CH 26**: Electron Active Hook & IPC Scanner (`rea_forge/scripts/electron-active-hook.cjs`) — *Tier 0*
  - **CH 38**: Fast Token & Secret Regex Radar (`tools/reverse_engineer.py`) — *Tier 0*
* **Command**: `python -m kageyoni.ninshu.cli patch 25,26,38 --name "electron_triage"`

### Preset 3: The ".NET CLR & NativeAOT Reverse" Patch
* **Objective**: Extract types, properties, methods, and Protobuf contracts from compiled Windows .NET binaries.
* **Channels**:
  - **CH 01**: PE / COFF Architecture Stripper (`tools/reverse_engineer.py`) — *Tier 0*
  - **CH 09**: .NET CLR Metadata Extractor (`tools/reverse_engineer.py`) — *Tier 0*
  - **CH 10**: .NET NativeAOT Bridge (`rea_forge/bridge/nativeaot/NativeAotExtension.java`) — *Tier 0*
  - **CH 36**: Protobuf Contract Sniffer (`tools/reverse_engineer.py`) — *Tier 0*
* **Command**: `python -m kageyoni.ninshu.cli patch 1,9,10,36 --name "dotnet_decomp"`

### Preset 4: The "Autonomous Agent Reality Check" Patch
* **Objective**: Prevent agent hallucination during code generation or database updates.
* **Channels**:
  - **CH 42**: Composition Compiler & Deficit Engine (`kageyoni/composition/compiler.py`) — *Tier 0*
  - **CH 43**: EffectResolver Opposing Pressure Harmonizer (`kageyoni/composition/effects.py`) — *Tier 0*
  - **CH 45**: Levi Sim Epistemic Firewall (`levi_sim/epistemic_firewall.py`) — *Tier 0*
  - **CH 44**: V11 ProtectedOperations Lifecycle Machine (`kageyoni/v11/runtime.py`) — *Tier 0*
* **Command**: `python -m kageyoni.ninshu.cli patch 42,43,44,45 --name "agent_epistemic_check"`

---

## 5. Operational Invariants

1. **Tier 0 Autonomy**: Channel inspection, routing queries, static binary analysis, and PCAP reads proceed instantly without human confirmation.
2. **Tier 1 Sovereign Gate**: Any patch containing a channel with `reversibility_tier: 1` (such as Frida injection, GDB breakpoints, or target byte patching) MUST emit:
   `WARNING: POTENTIALLY DESTRUCTIVE ACTION`
   and await explicit human authorization before executing the target binary.
3. **No Code Duplication**: Never clone or copy donor files from `rea_forge/` or `kageyoni/`. Wield them in-place through their registered channel paths and entrypoint functions.
