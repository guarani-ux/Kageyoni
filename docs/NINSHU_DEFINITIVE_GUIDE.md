# Ninshū: The Definitive Operational & Architectural Guide
**Inspected Commit Baseline:** `277afd99cb7acea55a9a6c0de1049cde79c7783a` (`feature/ninshu-telemetry-bus`)  
**Companion Executable Verification Suite:** [`tools/ninshu_worked_encounters.py`](file:///c:/Kageyoni/tools/ninshu_worked_encounters.py)

---

## Epistemic Notice for Cold-Start Agents and Operators

This guide strictly separates **The Operating Contract** (what Ninshū is designed to achieve and what conditions must hold for a result to be trusted) from **The Inspected Implementation** (what the code at commit `277afd99cb7acea55a9a6c0de1049cde79c7783a` actually enforces, what it leaves to the caller, and where catalogue metadata diverges from source symbols).

Never treat a specification or a catalogue entry as proof that an operation executed. Before acting on any channel, consult **Part IV (Verification Laws)**, **Part V (Commit-Bound Capability Ledger)**, and **Part VI (Complete Worked Encounters)**.

---

## Part I: Core Identity — What Ninshū Is, Its Lineage from REA, and Present Boundaries

### 1. What Ninshū Is
* **For Humans**: Ninshū is a capability routing and signal-conditioning console modelled on a 48-channel Solid State Logic (SSL 4000) mixing desk. Its goal is to take raw digital material ("liquid metal"—binaries, archives, packet captures, debug traces, and candidate claims), route that material through explicit analytical modules and memory/safety checks, preserve contradictions when sources disagree, and commit verified consequences into Kageyōni’s causal engine.
* **For Agents**: `kageyoni.ninshu` is an in-tree Python standard library package providing:
  1. An SQLite/FTS5 capability catalogue and intent router ([`Patchbay`](file:///c:/Kageyoni/kageyoni/ninshu/patchbay.py)).
  2. Thirty-eight pure-Python binary, archive, protocol, and tool-export parsers/scanners across Buses A–E (`kageyoni/ninshu/*_parser.py`, [`tools/reverse_engineer.py`](file:///c:/Kageyoni/tools/reverse_engineer.py)).
  3. Signal-conditioning, memory-profiling, adversarial-mutation, and scar-annotation modules ([`console.py`](file:///c:/Kageyoni/kageyoni/ninshu/console.py), [`shaper.py`](file:///c:/Kageyoni/kageyoni/ninshu/shaper.py), [`thermodynamics.py`](file:///c:/Kageyoni/kageyoni/ninshu/thermodynamics.py), [`adversary.py`](file:///c:/Kageyoni/kageyoni/ninshu/adversary.py), [`scars.py`](file:///c:/Kageyoni/kageyoni/ninshu/scars.py)).
  4. Interfaces to Kageyōni’s causal persistence, composition compiler, opposing-pressure resolver, epistemic firewall, and portable save kernel (Bus F, Channels 41–48).

### 2. Lineage from REA (`rea_forge`) — Inheritance, Not Obsolescence
Ninshū did **not** render the upstream Reverse Engineering Architecture (`rea_forge`) obsolete, nor did it replace every external tool in REA:
* **What REA (`rea_forge`) Provides**: 44 domain integrations and 17 adapter families that orchestrate live external reverse-engineering engines—including headless Ghidra JVM decompilation, IDA Pro headless sessions, Hopper scripts, Cutter/Rizin CLI pipelines, live Frida process injection, GDB/Pwndbg/LLDB attachment, Jadx/JEB decompilation, and Chrome DevTools Protocol (CDP) browser automation.
* **What Ninshū Reconstructs In-Tree**: Selected zero-dependency Python standard library parsers that can directly dissect binary headers/containers (PE, ELF, Mach-O, WASM, EVM, Go, Rust symbols, ASAR, APK/DEX, PCAP, TLS ClientHello, Protobuf) **or** parse the structured JSON/XML/binary exports produced by external tools (Ghidra XML/JSON exports, Hopper JSON documents, Rizin `iIj`/`aflj`/`pdfj` JSON, IDA JSON dumps, Frida Stalker event streams, LLDB traces, CDP event logs, Jadx/JEB JSON reports, Mitmproxy dumps).
* **Critical Rule**: Do not discard or ignore `rea_forge` when an encounter requires *live external tool execution* (such as decompiling a raw native binary into P-Code via Ghidra or attaching Frida to a running process). In-tree parsers like [`ghidra_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/ghidra_parser.py) or [`frida_stalker_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/frida_stalker_parser.py) interpret the *outputs* of those tools; they do not run the external decompiler or injector themselves.

### 3. Present Architectural Boundaries
1. **Representation vs. Execution**: `Patchbay.route()` and `Patchbay.patch()` select channels and return a descriptive JSON manifest. They do not automatically import the Python modules, invoke their methods, or pipe outputs from one channel into the next.
2. **Fixed 48-Channel Topology Is a Navigation Aid, Not a Ceiling**: Grouping capabilities into 6 buses of 8 channels helps humans and agents orient, but a single module may expose multiple distinct operations, and real encounters may require capabilities outside the 48 slots.

---

## Part II: Anatomy of the Machine — Operating Contract vs. Inspected Implementation

### 1. The Patchbay & SQLite Catalogue (`patchbay.py`, `seeds.py`, `schema.py`)
* **Operating Contract**:
  - Maintain an authoritative index of available capabilities across 6 Master Buses (`BUS_A` through `BUS_F`), searchable via FTS5 keywords, `subject_formats`, and `reversibility_tier`.
  - Provide accurate `carrier_path` and `entrypoint` bindings so an agent can locate and invoke the corresponding code.
* **Inspected Implementation (`277afd99`)**:
  - [`Patchbay.__init__()`](file:///c:/Kageyoni/kageyoni/ninshu/patchbay.py#L23-L28) only calls `self.seed()` when `ninshu_codex.sqlite` does not exist or `SELECT COUNT(*) FROM channels` is `0`. If `seeds.py` is edited after the SQLite file is created, `Patchbay()` will serve stale rows unless `patchbay.seed()` is explicitly called.
  - [`Patchbay.patch()`](file:///c:/Kageyoni/kageyoni/ninshu/patchbay.py#L140-L186) returns a dictionary (`patch_id`, `reversibility_tier`, `requires_human_gate`, `channel_strips`, `combined_effects`). It does **not** resolve or execute the entrypoints.
  - At commit `277afd99`, **33 of the 48 `entrypoint` strings in `seeds.py` do not match the exact class or method name in their target source file** (for example, `seeds.py` lists `ElfBinaryParser.parse` and `AsarArchive.parse`, whereas the source files define `ElfBinaryParser.parse_bytes` and `AsarArchiveParser.parse_bytes`). Always use the verified source symbols documented in **Part V**.

### 2. The 6 Master Buses
| Bus ID | Range | Domain | In-Tree Scope vs. Upstream Dependency |
| :--- | :--- | :--- | :--- |
| **`BUS_A`** | CH 01–08 | Native Machine & Decompilation | Direct binary header parsers for PE (CH 01), ELF (CH 02), and Mach-O (CH 03); text/JSON/XML export parsers for Ghidra (CH 04), Hopper (CH 05), Cutter/Rizin (CH 06), IDA (CH 07), and `objdump` (CH 08). |
| **`BUS_B`** | CH 09–16 | Managed Runtimes & Bytecode | Direct binary/symbol analyzers for .NET CLR BSJB (CH 09), NativeAOT `RTR` headers (CH 10), WASM sections (CH 11), EVM 4-byte selectors (CH 12), Go buildinfo/`pclntab` (CH 13), Rust v0/legacy symbols (CH 14), raw instruction markers (CH 15), and firmware magic/entropy (CH 16). |
| **`BUS_C`** | CH 17–24 | Dynamic Memory & Process Hooks | Offline trace/dump analyzers for Frida Stalker streams (CH 17), ELF `ET_CORE` dumps (CH 19), Rizin debug JSON (CH 20), LLDB stop traces (CH 21), crash register dumps & De Bruijn offsets (CH 22), and PE N-API/MSVC exports (CH 24); in-memory interval validator (CH 18) and HMAC/SHA-256 run-token supervisor (CH 23). |
| **`BUS_D`** | CH 25–32 | App Bundles & Mobile Runtimes | Direct archive/source parsers for Electron ASAR (CH 25), Electron JS IPC regex (CH 26), Android APK/DEX headers (CH 28), Apktool XML/YAML resources (CH 30), and Dart snapshot headers (CH 31); JSON export parsers for Chrome CDP messages (CH 27), Jadx reports (CH 29), and JEB AST exports (CH 32). |
| **`BUS_E`** | CH 33–40 | Network, Protocols & Signals | Direct binary/stream decoders for PCAP (CH 33), TLS ClientHello/SNI (CH 34), Mitmproxy MsgPack/tnetstring dumps (CH 35), Protobuf wire varints/tags (CH 36), regex/entropy secret scanning (CH 38); SQLite Patchbay router (CH 37), bounded telemetry queue (CH 39), and in-memory provenance DAG (CH 40). |
| **`BUS_F`** | CH 41–48 | Causal Governance & Synthesis | Kageyōni core engines: SQLite causal event store [`Engine`](file:///c:/Kageyoni/kageyoni/engine.py) (CH 41), Frame/Slot [`Compiler`](file:///c:/Kageyoni/kageyoni/composition/compiler.py) (CH 42), [`EffectResolver`](file:///c:/Kageyoni/kageyoni/composition/effects.py) (CH 43), [`ProtectedOperations`](file:///c:/Kageyoni/kageyoni/v11/runtime.py) (CH 44), [`EpistemicFirewall`](file:///c:/Kageyoni/levi_sim/epistemic_firewall.py) (CH 45), [`scout_horizon`](file:///c:/Kageyoni/shinobi_agent/cli.py) (CH 46), [`SymbiogenesisAgent`](file:///c:/Kageyoni/kageyoni/developmental/symbiogenesis.py) (CH 47), and [`SaveState`](file:///c:/Kageyoni/kageyoni/playable_world/kernel.py) (CH 48). |

### 3. Signal Conditioning, Memory Profiling, and Console (`console.py`, `thermodynamics.py`, `scars.py`)
* **Operating Contract**:
  - Bound memory consumption ($\le 64\text{ KB}$ default ceiling), filter unsubstantiated claims, surface historical failure patterns (scars), preserve opposing pressures via `EffectResolver`, and seal session outputs in a `MasterTape`.
* **Inspected Implementation (`277afd99`)**:
  - **Thermodynamic Memory Ceiling**: [`ThermodynamicProfiler.profile_callable()`](file:///c:/Kageyoni/kageyoni/ninshu/thermodynamics.py#L64-L120) uses `tracemalloc` to measure peak heap delta and raises `ThermodynamicCeilingBreachError` if `peak > memory_ceiling_bytes`. However, calling a parser directly (e.g. `ElfBinaryParser.parse_bytes(data)`) does **not** automatically invoke `ThermodynamicProfiler`; the caller must explicitly wrap the call in `ThermodynamicProfiler.profile_callable(...)` or `console.audit_channel_thermodynamics(...)`.
  - **Epistemic Noise Gate**: [`ActiveConsole.stream_track()`](file:///c:/Kageyoni/kageyoni/ninshu/console.py#L100-L126) checks `confidence = sig.get("confidence_score", 1.0)` and drops signals where `confidence < strip.noise_gate_threshold` (`0.5`). Two implementation hazards exist:
    1. If a signal dictionary omits `confidence_score`, it defaults to `1.0` and passes the gate automatically.
    2. In [`ActiveConsole.print_master()`](file:///c:/Kageyoni/kageyoni/ninshu/console.py#L230), thermodynamic receipts set `"confidence_score": 1.0 if tr.get("passed") else 0.0`. If a failed check is given `confidence_score: 0.0` and passed through `stream_track()`, **the failure record itself is filtered out**. Agents must keep `confidence_score` as the *certainty of the observation* (`1.0` for an observed failure) and record pass/fail status in a separate field (`"passed": False`).
  - **Scar Feedback Matrix**: [`ScarFeedbackMatrix.apply_scar_feedback()`](file:///c:/Kageyoni/kageyoni/ninshu/scars.py#L101-L157) matches string markers against 4 seeded scars and annotates dictionaries or raises `CircuitBreakerTrippedError` when `action == "CIRCUIT_BREAK"`. It only runs when explicitly called or inside `SSLMixingSession.process_signal_packet()`.
  - **MasterTape Digest**: [`MasterTape.freeze()`](file:///c:/Kageyoni/kageyoni/ninshu/console.py#L61-L66) computes an RFC 8785 canonical SHA-256 hash over the `MasterTape` fields. This binds the bytes of the data structure produced in memory; it does not independently prove that the input claims were true or provide external tamper-proof storage unless persisted to an audited store.

---

## Part III: Operating the Desk — Executable Agent Procedures

### 1. The Governing Principle on Existing Capabilities vs. New Construction

> **Recover and use a suitable existing capability before constructing a new one. If no suitable capability exists, identify whether the deficit is implementation, configuration, access, compatibility, or authority. Build only what the encounter actually requires.**

When an encounter cannot be completed immediately with a single call, classify the deficit accurately before writing code:
1. **`IMPLEMENTATION_DEFICIT`**: No module in `kageyoni/`, `tools/`, or `rea_forge/` implements the required algorithm.
2. **`CONFIGURATION_DEFICIT`**: The implementation exists in-tree, but `seeds.py` or `ninshu_codex.sqlite` has a stale `entrypoint` name or unseeded table.
3. **`ACCESS_OR_PROVIDER_DEFICIT`**: The in-tree channel is an export parser (e.g., `GhidraParser`, `JadxParser`, `CdpParser`), and the external binary/runtime required to produce that export is not installed or accessible in the current environment.
4. **`COMPATIBILITY_DEFICIT`**: Channel A produces an output structure (e.g., `AsarArchiveSummary` entry offsets) that requires a byte-slicing or schema-adaptation bridge before Channel B (`ElectronIpcScanner`) can consume it.
5. **`AUTHORITY_DEFICIT`**: The operation requires Tier 1 (local destructive / process attach) or Tier 2 (external network / remote git push) sign-off that has not been granted by the human operator.

### 2. Step-by-Step Procedure for Operating Ninshū

#### Step 1: Synchronize and Query the Patchbay
Because `Patchbay()` only seeds automatically when `ninshu_codex.sqlite` is missing or empty, always verify or re-seed if `seeds.py` has been updated:
```python
from kageyoni.ninshu.patchbay import Patchbay

desk = Patchbay()
# Reconcile SQLite catalogue with current seeds.py definitions if needed:
desk.seed()

matches = desk.route(
    intent="unpack electron asar scan ipc channels and secrets",
    subject="asar",
    max_tier=0,
    limit=4,
)
```

#### Step 2: Check Reversibility Tier Before Any Consequential Action
```python
patch_manifest = desk.patch([m["channel_number"] for m in matches], daimon_name="triage_session")
if patch_manifest["requires_human_gate"] or patch_manifest["reversibility_tier"] >= 1:
    raise RuntimeError(
        f"WARNING: POTENTIALLY DESTRUCTIVE ACTION (Tier {patch_manifest['reversibility_tier']}). "
        "Halt and await explicit human authorization."
    )
```

#### Step 3: Resolve the Actual Callable and Execute Under `ThermodynamicProfiler`
Do not assume `strip["entrypoint"]` in `patch_manifest` can be called blindly without checking **Part V**. Wrap the actual parser callable in `ThermodynamicProfiler.profile_callable` so the 64 KB heap ceiling is actively enforced and a `ThermodynamicReceipt` is generated:
```python
from kageyoni.ninshu.asar_parser import AsarArchiveParser
from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler

summary, receipt = ThermodynamicProfiler.profile_callable(
    AsarArchiveParser.parse_bytes,
    raw_asar_bytes,
    candidate_id="CH25_ASAR_UNPACK",
    memory_ceiling_bytes=64 * 1024,
    fail_closed=True,
)
```

#### Step 4: Transfer Evidence Between Channels & Preserve Contradictions
* Explicitly extract bytes or structured fields from upstream parser outputs and pass them to downstream scanners.
* Always include an explicit `"confidence_score"` on every signal passed to `ActiveConsole.stream_track()`.
* For failed checks or security violations that were **directly observed**, set `"confidence_score": 1.0` (certainty of observation) and `"passed": False` so `stream_track()` does not mute the failure.
* Convert channel findings into Kageyōni `Compiler` aspects (`family`, `type`, `authority`, `provenance`, `effects`) and run `EffectResolver().resolve(aspects)` via `console.print_master()`.

#### Step 5: Persist Consequences & Verify in a Cold Process
When claiming persistent state changes, commit the verified observation to `kageyoni.engine.Engine` (CH 41) or `SaveState` (CH 48) and verify readability in a separate OS process.

---

## Part IV: Verification and Anti-Theater Laws

### 1. Correction Table: Architectural Claims vs. Inspected Code (`277afd99`)

| Claim in Earlier Summaries | What the Inspected Code at `277afd99` Actually Establishes | Operational Requirement for Agents |
| :--- | :--- | :--- |
| **"All 48 capabilities have been fully reconstructed in Python"** | All 48 channels exist in `seeds.py` and point to local `.py` files. However, 13 channels (CH 04, 05, 06, 07, 08, 17, 20, 21, 22, 27, 29, 30, 32) parse **exported outputs/logs** from external tools rather than running those tools live. | Check the **Scope Type** column in Part V. If an encounter starts from a raw binary and needs Ghidra/Jadx/Frida execution, report an `ACCESS_OR_PROVIDER_DEFICIT` or invoke the upstream external tool first. |
| **"Every channel has a 64 KB memory ceiling"** | `ThermodynamicProfiler` (`tracemalloc`) enforces a 64 KB peak heap delta **only when a call is wrapped in `ThermodynamicProfiler.profile_callable()`** (or `audit_channel_thermodynamics`). Direct calls to parser methods are unprofiled, and several parsers enforce higher internal input size limits (e.g. 1 MB–16 MB). | Explicitly wrap parser invocations in `ThermodynamicProfiler.profile_callable(..., memory_ceiling_bytes=65536, fail_closed=True)` when claiming thermodynamic compliance. |
| **"The noise gate prevents hallucinations"** | `ActiveConsole.stream_track()` filters dicts by `sig.get("confidence_score", 1.0) >= threshold`. Missing scores default to `1.0`, and caller-supplied floats are not independent proof. Worse, `confidence_score=0.0` on a failed test causes the gate to drop the failure record. | Never rely on `confidence_score` as proof of validity. Always attach cryptographic byte digests/provenance, and set `confidence_score=1.0` on observed failures so they are never muted. |
| **"Scars prevent repeated mistakes"** | `ScarFeedbackMatrix` matches string substrings against registered scar patterns inside `apply_scar_feedback()`. It does not hook the Python runtime or block arbitrary module calls outside that function. | Treat `ScarFeedbackMatrix` as an explicit signal-annotation step inside `SSLMixingSession`, not an automatic global sandbox. |
| **"Tier 1 and Tier 2 actions require human authorization"** | `Patchbay.patch()` sets `requires_human_gate = True` when `reversibility_tier >= 1`, and workspace governance rules require human sign-off. The Python modules themselves do not kernel-block execution. | Agents must inspect `patch_manifest["reversibility_tier"]` and halt before executing any Tier 1 or Tier 2 mutation. |
| **"MasterTape produces tamper-proof results"** | `MasterTape.freeze()` computes a canonical SHA-256 hash (`master_sha256`) over its own dict fields. A hash binds bytes; it does not validate that the input dicts were truthful or prevent an agent from generating a new `MasterTape`. | Pair `MasterTape` digests with raw tool execution logs, exit codes, and cold-process SQLite verification in `kageyoni.engine.Engine`. |
| **"Mechanical auditing guarantees legitimate qualification"** | In [`tools/mechanical_audit_gate.py`](file:///c:/Kageyoni/tools/mechanical_audit_gate.py#L49-L56), `visit_Assign` has a `pass` placeholder, and `audit_channel` runs `unittest` without independently checking that the test imports the target implementation or runs `ThermodynamicProfiler`. Additionally, [`tools/audit_completion.py`](file:///c:/Kageyoni/tools/audit_completion.py#L432-L437) credits 6 Bus F channels (`probes_passed += 6`) from a single `from kageyoni.engine import digest` import. | Do not cite `audit_completion.py` or `mechanical_audit_gate.py` as standalone proof of end-to-end integration. Verify the specific channel callable and its output assertions directly. |
| **"The three-track submix executes the selected capabilities"** | `Patchbay.patch()` returns a metadata dictionary. Importing modules, calling the right method, and converting outputs to inputs across channels must be performed explicitly by the orchestrating code. | Use the explicit composition pattern demonstrated in **Part VI, Encounter 2**. |

---

## Part V: Capability Status and Limitations (Commit-Bound Ledger at `277afd99`)

The table below lists all **48 channels**, comparing the catalogued `entrypoint` in `kageyoni/ninshu/seeds.py` at commit `277afd99` against the **Actual Verified Callable** in the source file, its true functional scope, and its limitations.

* **Scope Key**:
  * **Direct Binary/Format Parser**: Parses raw target artifact bytes directly in pure Python stdlib.
  * **Tool Export/Trace Parser**: Parses structured JSON, XML, text, or binary trace outputs produced by an external tool (requires the external tool or `rea_forge` bridge to generate live exports from raw targets).
  * **In-Tree Validator/Supervisor**: Stateful in-memory validator, queue, or DAG structure.
  * **Kageyōni Core Engine**: Causal SQLite store, compiler, resolver, firewall, or agent runtime.

| CH | Bus | Channel Name | Carrier File | `seeds.py` Entrypoint (`277afd99`) | **Actual Verified Callable in Source** | Scope Type & Limitations |
| :- | :- | :--- | :--- | :--- | :--- | :--- |
| **01** | A | PE / COFF Architecture Stripper | [`tools/reverse_engineer.py`](file:///c:/Kageyoni/tools/reverse_engineer.py) | `DotNetPEParser.parse` | `DotNetPEParser(bytes).parse()` | **Direct Binary Parser** — Parses DOS/PE headers, sections, CLR metadata root. |
| **02** | A | ELF Multi-Architecture Transducer | [`kageyoni/ninshu/elf_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/elf_parser.py) | `ElfBinaryParser.parse` *(Mismatch)* | `ElfBinaryParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses 32/64-bit ELF headers, program segments, section headers, symbols. |
| **03** | A | Mach-O Universal Slicer | [`kageyoni/ninshu/macho_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/macho_parser.py) | `MachOBinaryParser.parse` *(Mismatch)* | `MachOBinaryParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses thin/FAT Mach-O headers, architecture slices, load commands; rejects Java `.class` `0xCAFEBABE` collisions. |
| **04** | A | Ghidra Headless Decompiler Bridge | [`kageyoni/ninshu/ghidra_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/ghidra_parser.py) | `GhidraDecompilerParser.parse` *(Mismatch)* | `GhidraParser.parse_bytes(bytes)` / `parse_json` / `parse_xml` | **Tool Export Parser** — Parses exported Ghidra XML/JSON ASTs and P-Code tokens. Does not launch headless Ghidra JVM. |
| **05** | A | Hopper Disassembler Bridge | [`kageyoni/ninshu/hopper_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/hopper_parser.py) | `HopperDecompilerParser.parse` *(Mismatch)* | `HopperParser.parse_bytes(bytes)` / `parse_dict` | **Tool Export Parser** — Parses Hopper JSON document exports (segments, procedures, basic blocks, pseudocode AST). |
| **06** | A | Cutter / Rizin Static Engine | [`kageyoni/ninshu/cutter_rizin_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/cutter_rizin_parser.py) | `CutterRizinParser.parse` *(Mismatch)* | `CutterRizinParser.parse_bytes(bytes)` / `parse_pipeline` | **Tool Export Parser** — Parses Rizin/Cutter JSON command outputs (`iIj`, `iSj`, `aflj`, `pdfj`). Does not spawn `rizin`. |
| **07** | A | IDA Pro Headless Telemetry | [`kageyoni/ninshu/ida_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/ida_parser.py) | `IdaProExportParser.parse` *(Mismatch)* | `IdaHeadlessParser.parse_session(dict)` | **Tool Export Parser** — Parses IDA JSON telemetry dicts (functions, disassembly blocks, xrefs). |
| **08** | A | Native Diagnostics & Objdump | [`kageyoni/ninshu/objdump_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/objdump_parser.py) | `ObjdumpParser.parse` | `ObjdumpParser.parse(str \| bytes)` | **Tool Export Parser** — Parses GNU/LLVM `objdump -d` / `-x` text output across x86, ARM, RISC-V. |
| **09** | B | .NET CLR Metadata Extractor | [`tools/reverse_engineer.py`](file:///c:/Kageyoni/tools/reverse_engineer.py) | `DotNetPEParser.parse` | `DotNetPEParser(bytes).parse()` | **Direct Binary Parser** — Extracts CLR `BSJB` streams (`#Strings`, `#US`, `#GUID`, `#Blob`) and Protobuf descriptor candidates. |
| **10** | B | .NET NativeAOT Bridge | [`kageyoni/ninshu/nativeaot_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/nativeaot_parser.py) | `NativeAotParser.parse` *(Mismatch)* | `NativeAotParser.inspect(bytes)` | **Direct Binary Parser** — Scans ReadyToRun (`RTR\x00`) headers, `Rhp*` symbols, method tables, GC info, thunks. |
| **11** | B | WebAssembly (WASM) Disassembler | [`kageyoni/ninshu/wasm_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/wasm_parser.py) | `WasmBinaryParser.parse` *(Mismatch)* | `WasmParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses `\x00asm` header, LEB128 section headers, imports, exports, memory limits. |
| **12** | B | EVM Selector Miner | [`kageyoni/ninshu/evm_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/evm_parser.py) | `EvmBytecodeParser.parse` *(Mismatch)* | `EvmBytecodeParser.parse_bytes(bytes)` / `parse_hex_string` | **Direct Binary Parser** — Scans EVM opcodes for `PUSH4` function selectors (`JUMPI` dispatch) and CBOR Solidity metadata. |
| **13** | B | Go Binary Reconstructor | [`kageyoni/ninshu/go_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/go_parser.py) | `GoBinaryParser.parse` *(Mismatch)* | `GoBinaryParser.parse_bytes(bytes)` | **Direct Binary Parser** — Extracts `\xff Go buildinf:` headers, Go versions, module dependencies, and `pclntab` magic. |
| **14** | B | Rust Symbol Demangler | [`kageyoni/ninshu/rust_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/rust_parser.py) | `RustDemangler.demangle` | `RustDemangler.demangle(str)` & `RustBinaryParser.parse_bytes(bytes)` | **Direct Symbol/Binary Parser** — Demangles Rust legacy (`_ZN`) and v0 (`_R`) symbols; extracts `.cargo-auditable` JSON and rustc hashes. |
| **15** | B | Raw Binary Disassembler | [`kageyoni/ninshu/raw_binary_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/raw_binary_parser.py) | `RawBinaryParser.parse` *(Mismatch)* | `RawBinaryDisassembler.parse_raw(bytes, base_address=...)` | **Direct Binary Scanner** — Scans headerless ROM/binary slices for prologue/instruction markers across x86_64, ARM64, MIPS, RISC-V. |
| **16** | B | Firmware Unpacker & Entropy Scanner | [`kageyoni/ninshu/firmware_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/firmware_parser.py) | `FirmwareParser.parse` *(Mismatch)* | `FirmwareScanner.analyze_firmware(bytes)` | **Direct Binary Scanner** — Detects SquashFS, JFFS2, U-Boot, gzip, LZMA, XZ, DTB magic offsets and computes sliding-window Shannon entropy. |
| **17** | C | Frida Stalker Engine | [`kageyoni/ninshu/frida_stalker_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/frida_stalker_parser.py) | `FridaStalkerParser.parse` *(Mismatch)* | `FridaStalkerParser().inspect_trace(bytes \| str \| list)` | **Tool Trace Parser** — Reconstructs call trees, recursive loops, and block coverage from Frida Stalker binary/JSON event streams. Does not inject Frida into live processes. |
| **18** | C | Dynamic Memory Interceptor | [`kageyoni/ninshu/memory_interceptor.py`](file:///c:/Kageyoni/kageyoni/ninshu/memory_interceptor.py) | `MemoryInterceptor.validate` *(Mismatch)* | `DynamicMemoryInterceptor().validate_access(addr, size, perm)` | **In-Tree Validator** — Interval-tree (`bisect`) virtual memory map & permission (`rwx`) validator. Does not hook OS process memory directly. |
| **19** | C | GDB / Pwndbg Core Inspector | [`kageyoni/ninshu/coredump_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/coredump_parser.py) | `ElfCoreDumpParser.parse` *(Mismatch)* | `CoreDumpParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses Linux ELF `ET_CORE` files, `PT_NOTE` (`NT_PRSTATUS`, `NT_PRPSINFO`, `NT_AUXV`, `NT_FILE`), registers, and `PT_LOAD` segments. |
| **20** | C | Rizin Debug Session Controller | [`kageyoni/ninshu/rizin_debug_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/rizin_debug_parser.py) | `RizinDebugParser.parse` *(Mismatch)* | `RizinDebugParser.parse_bytes(bytes)` / `parse_session` | **Tool Export Parser** — Parses Rizin debug JSON dumps (`drj` registers, `dmj` maps, `dbj` breakpoints, `dbtj` backtraces). |
| **21** | C | LLDB Native Tracer Bridge | [`kageyoni/ninshu/lldb_tracer_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/lldb_tracer_parser.py) | `LldbTracerParser.parse` *(Mismatch)* | `LLDBTracerParser.parse(str \| bytes \| dict)` | **Tool Trace Parser** — Parses LLDB JSON and text stop-reason dumps (`breakpoint`, `watchpoint`, `signal`, `exception`) and stack frames. |
| **22** | C | Pwntools Exploit & Crash Replay | [`kageyoni/ninshu/crash_replay_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/crash_replay_parser.py) | `CrashReplayParser.parse` *(Mismatch)* | `CrashReplayEngine.analyze(str \| bytes \| dict)` & `cyclic_find` | **Tool Trace Parser & Utility** — Pure-Python De Bruijn `cyclic`/`cyclic_find`, ELF/PE mitigation detector, and crash register triage. |
| **23** | C | Process Lineage & Run Token Supervisor | [`kageyoni/ninshu/process_supervisor.py`](file:///c:/Kageyoni/kageyoni/ninshu/process_supervisor.py) | `ProcessSupervisor.validate_token` | `ProcessSupervisor(salt).issue_token(...)` / `validate_token(tok)` | **In-Tree Supervisor** — Tracks PID/PPID lineage trees and validates SHA-256 time-bounded execution lease tokens. |
| **24** | C | Windows Native C++ N-API Bridge | [`kageyoni/ninshu/napi_bridge_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/napi_bridge_parser.py) | `NapiBridgeParser.parse` *(Mismatch)* | `NapiBridgeParser.inspect(bytes)` & `MsvcDemangler.demangle(str)` | **Direct Binary/Symbol Parser** — Parses PE export tables for Node-API entrypoints (`napi_register_module_v1`), property descriptors, and MSVC C++ mangled symbols. |
| **25** | D | Electron ASAR Archive Unpacker | [`kageyoni/ninshu/asar_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/asar_parser.py) | `AsarArchive.parse` *(Mismatch)* | `AsarArchiveParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses Chromium Pickle header and JSON file tree from `.asar` archives; blocks path traversal (`..`). |
| **26** | D | Electron Active Hook & IPC Scanner | [`kageyoni/ninshu/electron_ipc_scanner.py`](file:///c:/Kageyoni/kageyoni/ninshu/electron_ipc_scanner.py) | `ElectronIpcScanner.scan` | `ElectronIpcScanner.parse_bytes(bytes)` / `scan(str)` | **Direct Source Scanner** — Scans Electron JS preload/main scripts for `ipcRenderer`/`ipcMain`/`contextBridge` calls and unsafe `WebPreferences`. |
| **27** | D | CDP Browser Automator | [`kageyoni/ninshu/cdp_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/cdp_parser.py) | `CdpEventParser.parse` *(Mismatch)* | `CdpParser.parse_stream(bytes \| str \| list)` | **Tool Trace Parser** — Correlates Chrome DevTools Protocol JSON commands, responses, and `Network`/`Page`/`Runtime`/`DOM` events. Does not drive a live browser socket. |
| **28** | D | Android APK / DEX Parser | [`kageyoni/ninshu/apk_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/apk_parser.py) | `ApkDexParser.parse` *(Mismatch)* | `ApkParser.parse_apk(bytes)` & `DexParser.parse_header(bytes)` | **Direct Binary Parser** — Inspects APK ZIP central directory and verifies Dalvik `.dex` 112-byte headers (magic, Adler32, table offsets). |
| **29** | D | Jadx Android Decompiler Bridge | [`kageyoni/ninshu/jadx_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/jadx_parser.py) | `JadxExportParser.parse` *(Mismatch)* | `JadxParser.parse_bytes(bytes)` / `parse_project_data` | **Tool Export Parser** — Parses Jadx JSON exports (packages, classes, methods, fields, smali-to-Java line mappings). |
| **30** | D | Apktool Resource Reconstructor | [`kageyoni/ninshu/apktool_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/apktool_parser.py) | `ApktoolProjectParser.parse` *(Mismatch)* | `ApktoolResourceReconstructor.parse_manifest_xml(bytes)` / `parse_apktool_yml` / `parse_strings_xml` | **Direct XML/YAML Parser** — Parses decoded `AndroidManifest.xml`, `apktool.yml`, and `res/values/strings.xml` (rejects XXE/DOCTYPE). |
| **31** | D | Flutter & Dart Snapshot Inspector | [`kageyoni/ninshu/dart_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/dart_parser.py) | `DartSnapshotParser.parse` *(Mismatch)* | `DartSnapshotParser.inspect(bytes)` | **Direct Binary Scanner** — Locates Dart VM snapshot magic (`0xf5f5dcdc`), snapshot kinds, version hashes, and package/widget strings. |
| **32** | D | JEB Decompiler Automation | [`kageyoni/ninshu/jeb_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/jeb_parser.py) | `JebExportParser.parse` *(Mismatch)* | `JebParser.parse_bytes(bytes)` / `parse_dict` | **Tool Export Parser** — Parses JEB JSON AST units, class hierarchy, method overrides, and cross-references. |
| **33** | E | PCAP Packet Flow Reconstructor | [`kageyoni/ninshu/pcap_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/pcap_parser.py) | `PcapCaptureParser.parse` *(Mismatch)* | `PcapParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses libpcap headers, Ethernet/IPv4/IPv6/TCP/UDP headers, and aggregates 5-tuple network flows. |
| **34** | E | TLS / SSL Handshake & SNI Extractor | [`kageyoni/ninshu/tls_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/tls_parser.py) | `TlsHandshakeParser.parse` *(Mismatch)* | `TLSHandshakeParser.parse_bytes(bytes)` | **Direct Binary Parser** — Parses TLS records (`0x16`), ClientHello cipher suites, SNI hostnames, ALPN, and computes JA3 fingerprints. |
| **35** | E | Mitmproxy Offline Flow Decoder | [`kageyoni/ninshu/mitmproxy_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/mitmproxy_parser.py) | `MitmproxyFlowParser.parse` *(Mismatch)* | `MitmproxyDumpParser.parse_bytes(bytes)` | **Direct Binary Parser** — Decodes MsgPack/tnetstring offline Mitmproxy flow captures (HTTP requests, responses, headers, TLS metadata). |
| **36** | E | Protobuf Message & Contract Sniffer | [`kageyoni/ninshu/protobuf_parser.py`](file:///c:/Kageyoni/kageyoni/ninshu/protobuf_parser.py) | `ProtobufContractSniffer.parse` *(Mismatch)* | `ProtobufParser.parse_bytes(bytes)` | **Direct Wire Parser** — Decodes raw Protobuf wire-format byte streams (varint, 64-bit, length-delimited, 32-bit) and synthesizes `.proto` schemas. |
| **37** | E | SQLite Schema & Query Engine | [`kageyoni/ninshu/patchbay.py`](file:///c:/Kageyoni/kageyoni/ninshu/patchbay.py) | `Patchbay.route` | `Patchbay().route(...)` / `list_channels()` | **In-Tree SQLite Engine** — FTS5/multi-axis SQLite query router for the Ninshū codex. |
| **38** | E | Fast Token & Secret Regex Radar | [`kageyoni/ninshu/secret_scanner.py`](file:///c:/Kageyoni/kageyoni/ninshu/secret_scanner.py) | `SecretRadarScanner.scan` *(Mismatch)* | `SecretScanner.parse_bytes(bytes)` / `scan(str)` | **Direct Scanner** — Regex + Shannon entropy detector and redactor for AWS, GitHub, Google, Slack, Stripe, Private Keys, and JWTs. |
| **39** | E | Signal & Telemetry Decoupler | [`kageyoni/ninshu/telemetry_decoupler.py`](file:///c:/Kageyoni/kageyoni/ninshu/telemetry_decoupler.py) | `TelemetryDecoupler.push` | `TelemetryDecoupler().push(TelemetryPacket)` / `drain()` | **In-Tree Queue** — SHA-256 verified bounded packet queue with watermark hysteresis, sequence gap detection, and drop policies. |
| **40** | E | Artifact Graph & Provenance Mapper | [`kageyoni/ninshu/provenance_mapper.py`](file:///c:/Kageyoni/kageyoni/ninshu/provenance_mapper.py) | `ArtifactProvenanceGraph.build` *(Mismatch)* | `ProvenanceGraph().add_node(...)` / `add_derivation(...)` / `topological_sort()` | **In-Tree DAG** — Cycle-rejecting artifact derivation DAG with SHA-256 digest verification and topological sort. |
| **41** | F | Kageyoni Causal SQLite Event Store | [`kageyoni/engine.py`](file:///c:/Kageyoni/kageyoni/engine.py) | `Engine.apply` | `Engine.create(path)` / `Engine(path).apply(command)` / `verify()` | **Kageyōni Core Engine** — ACID SQLite causal event store with revision locking, hash chains, and world validation. |
| **42** | F | Composition Compiler & Deficit Engine | [`kageyoni/composition/compiler.py`](file:///c:/Kageyoni/kageyoni/composition/compiler.py) | `Compiler.compile` | `Compiler(frame, aspects).compile(bindings)` | **Kageyōni Core Engine** — Fail-closed Frame/Slot/Aspect admission and dependency closure; emits typed `Deficits` via `DeficitPlanner`. |
| **43** | F | EffectResolver (Pressure Harmonizer) | [`kageyoni/composition/effects.py`](file:///c:/Kageyoni/kageyoni/composition/effects.py) | `EffectResolver.resolve` | `EffectResolver().resolve(aspects)` | **Kageyōni Core Engine** — Preserves opposing pressures (`activate`/`suppress`, `increase`/`decrease`) and action gate conflicts without averaging. |
| **44** | F | V11 ProtectedOperations Machine | [`kageyoni/v11/runtime.py`](file:///c:/Kageyoni/kageyoni/v11/runtime.py) | `ProtectedOperations.transition` | `ProtectedOperations(engine).declare(...)` / `transition(...)` | **Kageyōni Core Engine** — 10-state transactional lifecycle state machine (`DECLARED` $\rightarrow$ `VERIFIED`). |
| **45** | F | Levi Sim Epistemic Firewall | [`levi_sim/epistemic_firewall.py`](file:///c:/Kageyoni/levi_sim/epistemic_firewall.py) | `EpistemicFirewall.record_observation` | `EpistemicFirewall().record_observation(obs, src_id)` | **Kageyōni Core Engine** — Partitions `USER_INTENT`, `OBSERVATION`, `VERIFIED_FACT`, `HYPOTHESIS`, `BELIEF`, `UNKNOWN`, and `ENGINE_SCAR`. |
| **46** | F | Shinobi Participant Horizon Scout | [`shinobi_agent/cli.py`](file:///c:/Kageyoni/shinobi_agent/cli.py) | `scout_horizon` | `scout_horizon(topic, task)` & `Participant(db)` | **Kageyōni Core Engine** — AST + TF-IDF reconnaissance across surrounding sibling repositories and situated participant lifecycle. |
| **47** | F | Symbiogenesis Ecology Recomposer | [`kageyoni/developmental/symbiogenesis.py`](file:///c:/Kageyoni/kageyoni/developmental/symbiogenesis.py) | `SymbiogenesisAgent.recompose` *(Mismatch)* | `SymbiogenesisAgent(id).inspect_ecology(...)` / `construct_niche(...)` | **Kageyōni Core Engine** — Evaluates multi-agent ecological niches and qualifies generators on blind holdouts. |
| **48** | F | Playable World Portable Save Kernel | [`kageyoni/playable_world/kernel.py`](file:///c:/Kageyoni/kageyoni/playable_world/kernel.py) | `SaveState.from_file` | `SaveState.from_file(path)` / `write_to_file(path)` | **Kageyōni Core Engine** — Portable JSON world-state serializer that strips host execution permissions across AI runtimes. |

---

## Part VI: Complete Worked Encounters (Verified Executable Recipes)

All five encounters below are implemented in [`tools/ninshu_worked_encounters.py`](file:///c:/Kageyoni/tools/ninshu_worked_encounters.py) and regression-tested in [`tests/test_ninshu_worked_encounters.py`](file:///c:/Kageyoni/tests/test_ninshu_worked_encounters.py). Any cold-start agent can reproduce all five receipts with:

```bash
python tools/ninshu_worked_encounters.py
```

---

### Encounter 1: Catalogue vs. Source Entrypoint Audit & Single-Channel Inspection (`CH 02`)
* **What This Establishes**: Demonstrates why an agent must verify a channel's AST before trusting `seeds.py`, and how to execute `ElfBinaryParser.parse_bytes` inside `ThermodynamicProfiler.profile_callable` ($\le 64\text{ KB}$ heap ceiling).
* **Code**:
  ```python
  import ast
  from pathlib import Path
  from kageyoni.ninshu.elf_parser import ElfBinaryParser
  from kageyoni.ninshu.patchbay import Patchbay
  from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
  from tools.ninshu_worked_encounters import build_minimal_elf64_x86_64

  desk = Patchbay()
  ch_meta = desk.get_channel(2)
  carrier_file = Path(ch_meta["carrier_path"])
  catalog_entrypoint = ch_meta["entrypoint"]  # 'ElfBinaryParser.parse' at 277afd99

  # 1. Verify whether catalog_entrypoint exists in the Python source AST
  tree = ast.parse(carrier_file.read_text(encoding="utf-8"))
  actual_methods = {
      node.name: [n.name for n in node.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
      for node in tree.body if isinstance(node, ast.ClassDef)
  }
  cls_name, method_name = catalog_entrypoint.split(".")
  catalog_symbol_exists = method_name in actual_methods.get(cls_name, [])

  # 2. Invoke the actual verified callable under the 64 KB ThermodynamicProfiler
  elf_bytes = build_minimal_elf64_x86_64()
  summary, receipt = ThermodynamicProfiler.profile_callable(
      ElfBinaryParser.parse_bytes,
      elf_bytes,
      candidate_id="CH02_ELF_DIRECT",
      memory_ceiling_bytes=64 * 1024,
      fail_closed=True,
  )
  ```
* **Verified Execution Receipt**:
  ```json
  {
    "encounter": "1_single_channel_inspection",
    "catalog_entrypoint": "ElfBinaryParser.parse",
    "catalog_symbol_exists_in_source": false,
    "actual_class_methods": ["parse_bytes", "parse_stream"],
    "executed_entrypoint": "ElfBinaryParser.parse_bytes",
    "elf_machine": "x86-64",
    "elf_is_64_bit": true,
    "elf_entry": "0x401000",
    "peak_memory_bytes": 2860,
    "thermodynamic_passed": true
  }
  ```
* **What Remains Unknown**: Static ELF header parsing establishes the declared entry point (`0x401000`) and segment layout, but does not disassemble instruction opcodes or prove runtime behavior.

---

### Encounter 2: Multi-Channel Composition with Real Byte & Provenance Transfer (`CH 25` $\rightarrow$ `CH 26` + `CH 38` $\rightarrow$ `CH 40`)
* **What This Establishes**: Shows how to bridge four channels so the output of `CH 25` (`AsarArchiveParser`) physically slices inner `.js` payloads and feeds those exact bytes into `CH 26` (`ElectronIpcScanner`) and `CH 38` (`SecretScanner`), while `CH 40` (`ProvenanceGraph`) records the cryptographic derivation lineage.
* **Code**:
  ```python
  from kageyoni.ninshu.asar_parser import AsarArchiveParser
  from kageyoni.ninshu.electron_ipc_scanner import ElectronIpcScanner
  from kageyoni.ninshu.provenance_mapper import ArtifactNode, ProvenanceGraph
  from kageyoni.ninshu.secret_scanner import SecretScanner
  from kageyoni.ninshu.thermodynamics import ThermodynamicProfiler
  from tools.ninshu_worked_encounters import build_realistic_asar_bundle

  raw_asar = build_realistic_asar_bundle()

  # Track 1 (CH 25): Parse ASAR archive header and file table
  asar_summary, _ = ThermodynamicProfiler.profile_callable(
      AsarArchiveParser.parse_bytes, raw_asar, candidate_id="CH25_ASAR"
  )
  payload_base = 8 + asar_summary.header_size

  # Track 4 (CH 40): Record root artifact in ProvenanceGraph
  dag = ProvenanceGraph()
  dag.add_node(ArtifactNode.from_bytes("bundle.asar", raw_asar, mime_type="application/x-asar"))

  for entry in asar_summary.entries:
      if entry.is_directory:
          continue
      file_bytes = raw_asar[payload_base + entry.offset : payload_base + entry.offset + entry.size]
      dag.add_node(ArtifactNode.from_bytes(entry.path, file_bytes, mime_type="application/javascript"))
      dag.add_derivation("bundle.asar", entry.path, "AsarArchiveParser.slice_entry", timestamp=1700000000)

      # Track 2 (CH 26): Scan extracted JS payload for Electron IPC & WebPreferences risks
      ipc_summary, _ = ThermodynamicProfiler.profile_callable(
          ElectronIpcScanner.parse_bytes, file_bytes, candidate_id=f"CH26_IPC:{entry.path}"
      )
      # Track 3 (CH 38): Scan extracted JS payload for high-entropy secrets
      sec_summary, _ = ThermodynamicProfiler.profile_callable(
          SecretScanner.parse_bytes, file_bytes, candidate_id=f"CH38_SECRET:{entry.path}"
      )
  ```
* **Verified Execution Receipt**:
  ```json
  {
    "encounter": "2_multi_channel_composition",
    "patch_id": "patch:electron_audit_chain",
    "asar_files_extracted": ["main.js", "preload.js"],
    "ipc_findings": [
      {
        "file": "main.js",
        "channels": ["vault:decrypt"],
        "dynamic_sinks_count": 0,
        "node_integration": true,
        "context_isolation": false,
        "risk_level": "CRITICAL"
      },
      {
        "file": "preload.js",
        "channels": ["vault:decrypt", "ch"],
        "dynamic_sinks_count": 1,
        "node_integration": null,
        "context_isolation": null,
        "risk_level": "MEDIUM"
      }
    ],
    "secrets_detected": [
      {
        "file": "preload.js",
        "rule_id": "SEC003_GITHUB_PAT_CLASSIC",
        "masked_value": "ghp_************************q3R2",
        "entropy": 4.872
      }
    ],
    "provenance_topological_order": ["bundle.asar", "main.js", "preload.js"],
    "provenance_digests_valid": true
  }
  ```
* **What Remains Unknown**: Static regex scanning of `main.js` and `preload.js` identifies the `vault:decrypt` IPC handler, unsafe `nodeIntegration: true`, a dynamic sink (`ipcRenderer.send(ch, data)`), and a high-entropy GitHub token pattern, but does not verify whether the token is currently active against GitHub's API.

---

### Encounter 3: Contradictory Evidence & Opposing Pressures (`CH 04` vs. `CH 17` $\rightarrow$ `CH 43` + `ActiveConsole`)
* **What This Establishes**: Shows how Ninshū preserves conflicting evidence when static decompilation (`CH 04` Ghidra export) reports that `0x401000` calls `0x401100`, while a runtime trace (`CH 17` Frida Stalker) observes `0x401000` calling `0x409990`.
* **Code**:
  ```python
  from kageyoni.ninshu.console import ActiveConsole
  from kageyoni.ninshu.frida_stalker_parser import FridaStalkerParser, StalkerCallEvent, StalkerRetEvent
  from kageyoni.ninshu.ghidra_parser import GhidraParser
  from kageyoni.ninshu.patchbay import Patchbay

  # 1. Parse static Ghidra export (CH 04) -> CALL 0x401100
  ghidra_prog = GhidraParser.parse_bytes(ghidra_json_bytes)
  static_target = hex(ghidra_prog.functions["dispatch_auth"].pcode[0].inputs[0].offset)

  # 2. Parse dynamic Frida Stalker stream (CH 17) -> CALL 0x409990
  packed_stalker = FridaStalkerParser.pack_stream([
      StalkerCallEvent(source_address=0x401000, target_address=0x409990, depth=0),
      StalkerRetEvent(source_address=0x409990, target_address=0x401004, depth=0),
  ], format="tagged")
  stalker_summary = FridaStalkerParser().inspect_trace(packed_stalker)
  dynamic_target = hex(stalker_summary.call_tree_roots[0].address)

  # 3. Feed opposing pressures into ActiveConsole / EffectResolver (CH 43)
  compiled_aspects = [
      {
          "aspect_id": "ch04_static_cfg",
          "provenance": [{"source": "ghidra_export", "function": "dispatch_auth"}],
          "effects": [{"operation": "pressure", "target": "direct_call_assumption_0x401000", "direction": "activate", "strength": "derived_static"}],
      },
      {
          "aspect_id": "ch17_dynamic_stalker",
          "provenance": [{"source": "frida_stalker_trace", "site": "0x401000"}],
          "effects": [{"operation": "pressure", "target": "direct_call_assumption_0x401000", "direction": "suppress", "strength": "observed_runtime"}],
      },
  ]
  console = ActiveConsole(Patchbay().patch([4, 17, 43], daimon_name="phase_conflict_session"))
  master = console.print_master("enc3_polyphony", active_signals, compiled_aspects)
  ```
* **Verified Execution Receipt**:
  ```json
  {
    "encounter": "3_opposing_pressures",
    "static_call_target": "0x401100",
    "dynamic_call_target": "0x409990",
    "conflicts_preserved_count": 1,
    "conflicts_preserved": [
      {
        "target": "direct_call_assumption_0x401000",
        "kind": "opposing_pressures",
        "directions": ["activate", "suppress"],
        "contributors": ["ch04_static_cfg", "ch17_dynamic_stalker"]
      }
    ],
    "master_sha256": "85bd92a4c6e54afe6440aaa9ccca7688ca279ba4eb34dcdff15f9b0035164338"
  }
  ```
* **What Remains Unknown**: The preserved conflict highlights a discrepancy at `0x401000` (e.g., GOT/PLT hooking, vtable dispatch, or self-modifying code), which requires inspecting the relocation table or memory permissions at `0x401000` to explain causally.

---

### Encounter 4: Refusal, Failure-Muting Mitigation & Typed Deficit Emission (`Tier 1` + `CH 42 Compiler`)
* **What This Establishes**:
  1. How `Patchbay.patch([17, 18, 27])` flags Tier 1 operations requiring human sign-off (`requires_human_gate: true`).
  2. How passing `"confidence_score": 0.0` on a failed check causes `ActiveConsole.stream_track()` to mute the failure (`naive_zero_confidence_failure_survived: false`), whereas separating observation certainty (`"confidence_score": 1.0`) from outcome (`"passed": false`) preserves the failure record (`properly_scored_failure_survived: true`).
  3. How Kageyōni’s `Compiler` (`CH 42`) fails closed (`runnable: false`) and emits explicit typed `deficits` (`missing_state` and `invalid_binding`) when `ch04.ghidra_parser` is bound without an upstream `ghidra_headless_runner` export provider.
* **Verified Execution Receipt**:
  ```json
  {
    "encounter": "4_refusal_and_deficits",
    "tier1_requires_human_gate": true,
    "tier1_reversibility_tier": 1,
    "naive_zero_confidence_failure_survived": false,
    "properly_scored_failure_survived": true,
    "compilation_runnable": false,
    "compiler_blockers": [
      {
        "slot_id": "upstream.ghidra_jvm_export",
        "status": "UNKNOWN",
        "aspect_ids": [],
        "reason": "requires >= 1"
      },
      {
        "slot_id": "in_tree.ghidra_ast_parse",
        "status": "INVALID",
        "aspect_ids": ["ch04.ghidra_parser"],
        "reason": "dependency closure failed: ['upstream.ghidra_jvm_export']"
      }
    ],
    "compiler_emitted_deficits": [
      {
        "kind": "missing_state",
        "target": "upstream.ghidra_jvm_export",
        "reason": "requires >= 1",
        "allowed_resolution": ["acquire_or_validate_evidence", "derive_from_supported_state"],
        "auto_resolve": false
      },
      {
        "kind": "invalid_binding",
        "target": "in_tree.ghidra_ast_parse",
        "reason": "dependency closure failed: ['upstream.ghidra_jvm_export']",
        "allowed_resolution": ["derive_from_supported_state"],
        "auto_resolve": false
      }
    ]
  }
  ```

---

### Encounter 5: Cold-Process Causal Persistence & Recovery (`CH 41` + `CH 45` + `CH 48`)
* **What This Establishes**: Demonstrates recording an observation in `EpistemicFirewall` (`CH 45`), committing a state mutation to Kageyōni’s SQLite `Engine` (`CH 41`), writing a portable `SaveState` (`CH 48`), and spawning a **fresh, separate OS subprocess** (`subprocess.run([sys.executable, "-c", ...])`) with zero shared memory to reopen and verify both artifacts on disk.
* **Code**:
  ```python
  # Process A (Writer):
  firewall = EpistemicFirewall()
  firewall.record_observation(
      observation="CH26+CH38 detected unsafe nodeIntegration=True and leaked PAT in preload.js",
      source_record_id="ninshu_encounter_2",
  )
  engine = Engine.create(db_file, seed=42)
  try:
      apply_res = engine.apply({
          "api_version": 3,
          "branch": "main",
          "expected_revision": 0,
          "request_id": "ninshu:enc2:electron-audit",
          "kind": "action",
          "actor": "ninshu_auditor",
          "narrative": "Recorded verified Electron ASAR IPC and secret exposure from Encounter 2",
          "changes": [{
              "op": "create",
              "domain": "character",
              "id": "auditor_daimon",
              "data": {"name": "Ninshu Auditor", "entity_kind": "person"},
              "status": "proposed",
              "visibility": "public",
              "evidence": [{"note": "Observed via CH25+CH26+CH38 pipeline"}],
          }],
      })
  finally:
      engine.close()

  # Process B (Fresh OS Subprocess Reader):
  # Reopens db_file with Engine(db_file).verify() and SaveState.from_file(save_file)
  ```
* **Verified Execution Receipt**:
  ```json
  {
    "encounter": "5_cold_process_recovery",
    "parent_pid_differs_from_child": true,
    "writer_revision": 1,
    "writer_event_hash": "d12ee76865b80c9686a51145e4884bf2f7bf96a3b0d73c2d4823721dc760fc6f",
    "fresh_process_receipt": {
      "child_pid": 30100,
      "engine_verified_ok": true,
      "persisted_record_id": "auditor_daimon",
      "persisted_record_status": "proposed",
      "save_state_world_id": "ninshu_audit_world",
      "save_state_revision": 1,
      "save_state_claims_count": 1
    }
  }
  ```
