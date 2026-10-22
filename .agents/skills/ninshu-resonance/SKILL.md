---
name: ninshu-resonance
description: Ninshū Harmonic Modulation & Sub-Mix Console. Modulates the 6-Axis capability tensor into reactive Daimons, multi-track sub-mixes, and dynamic sidechain networks across REA and Kageyōni without duplicating code.
---

# Ninshū: The Harmonic Modulation & Sub-Mix Console (忍宗)

You operate **Ninshū**—the harmonic modulation console and reactive daimon runtime. Where the Multi-Dimensional Forge provides the raw smelting furnace, **Ninshū provides the mixing desk, the faders, the knobs, and the sidechain patchbays**.

Instead of static one-off scripts, Ninshū treats capabilities as **tracks on a multi-track console**, grouped into **sub-mixes (Daimons)** that react dynamically to inputs, sidechain off each other's tensions, and preserve opposing pressures without collapsing into monolithic clutter.

---

## 1. The Ninshū Mixing Console: The 8 Master Knobs (Modulation Dimensions)

To move beyond a "console with no knobs," Ninshū exposes **8 continuous modulation knobs** that can be turned on any instrument, sub-mix, or daimon:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE NINSHŪ CONSOLE SURFACE                      │
│                                                                        │
│   [KNOB 1]     [KNOB 2]     [KNOB 3]     [KNOB 4]     [KNOB 5]         │
│   SUBSTRATE    BANDWIDTH    ACOUSTIC      DAMPING     THERMAL          │
│   SELECT       (DEPTH)      AUTHORITY     (DEFEAT)    CEILING          │
│                                                                        │
│   [KNOB 6]     [KNOB 7]     [KNOB 8]     [FADER M]                     │
│   POLARITY     SIDECHAIN    TOPOLOGICAL  MASTER CONFORM                │
│   TENSION      COUPLING     DEFICIT GAIN DRY/WET (TIER)                │
└────────────────────────────────────────────────────────────────────────┘
```

### Knob 1: Substrate Select ($S_{\text{dial}}$ — The Input Channel)
- **Setting 0-3 (Binary Native)**: PE, ELF, Mach-O, Raw Bytes (x86, ARM, MIPS, RISC-V).
- **Setting 4-6 (Application Bundles)**: Electron, ASAR, Node.js, APK, DEX, IPA.
- **Setting 7-8 (Network & Memory Streams)**: PCAP packet flows, Mitmproxy websockets, Memory dumps, GDB traces.
- **Setting 9-10 (Causal World State)**: Kageyōni SQLite branches, Agent transcripts, Intent contracts.

### Knob 2: Inspection Bandwidth / Resolution ($B_{\text{dial}}$ — The EQ Q-Factor)
- **Wide Open (Broad/Fast)**: Static header identification, magic bytes, top-level symbol tokens (sub-millisecond, low token cost).
- **Notch Filter (Targeted Slice)**: Scans specifically for Protobuf signatures, IPC channel strings, or memory offsets.
- **Microscopic (Deep/Surgical)**: Full recursive AST parsing, Control-Flow Graph (CFG) generation, decompiler intermediate representation (IL/Ghidra P-Code).

### Knob 3: Acoustic Authority ($A_{\text{dial}}$ — Confidence / Gain)
- **0.0 — Pure Inferred**: Hypotheses, speculative model framing, creative interpretation (marked untrusted).
- **0.5 — Derived Fact**: Deterministic parser outputs, CFG reconstructions, symbol table extracts.
- **1.0 — Cryptographic Ground**: Exact SHA-256 byte receipts, live process memory registers, ACID committed SQLite rows.

### Knob 4: Dynamic Damping / Defeat ($D_{\text{dial}}$ — The Gate Threshold)
- Controls how easily a Daimon **drops obsolete constraints** when the underlying world state shifts.
- **High Damping**: Conservative; holds onto past rejections and scars indefinitely.
- **Low Damping (Reactive)**: Defeats dynamic constraints the instant the target binary or revision changes.

### Knob 5: Thermal / Energy Ceiling ($\Phi_{\text{dial}}$ — Thermodynamic Cost)
- **Cold (Tier 0)**: Completely read-only, idempotent, zero process spawn, zero disk writes.
- **Warm (Tier 0 Sandbox)**: Spawns isolated local decompiler subprocess (Ghidra, Hopper, Node), writes only to ephemeral `/tmp`.
- **Hot (Tier 1 Gate)**: Modifies target binary bytes, hooks active process memory (Frida stalker), mutates live SQLite state. Requires human key-turn.

### Knob 6: Polarity Tension ($T_{\text{dial}}$ — Opposing Pressure Tolerance)
- Configures how the sub-mix handles contradictory findings (via Kageyōni's `EffectResolver`):
  - **Monophonic (Force Consensus)**: Blocks if two aspects disagree; demands further evidence.
  - **Polyphonic (Chord Preservation)**: Preserves opposing findings side-by-side (e.g., Static says `x86_64`, Dynamic trace reveals `ARM64 emulation`) and projects both into the Expression Contract.

### Knob 7: Sidechain Coupling Ratio ($R_{\text{dial}}$ — Inter-Daimon Reaction)
- Sets how strongly Track A reacts when Track B encounters resistance:
  - *Example*: When Track 1 (Static Decompiler) hits a wall (`status: UNRESOLVED`), Track 2 (Dynamic Hook) automatically un-mutes and ducks the static track's volume.

### Knob 8: Topological Deficit Gain ($G_{\text{dial}}$ — Blindspot Amplification)
- **Dry**: Suppresses unknown areas; reports only what was positively observed.
- **Wet (Maximum Signal)**: Amplifies and maps every missing jump table, unplaced dependency, and dark caller into a first-class `Deficit` socket for downstream resolution.

---

## 2. The 3 Standard Sub-Mix Stems (The Rhythm Section)

In any investigation, software repair, or gameplay encounter, assemble the instruments into these **3 standard Daimon Sub-Mixes**:

```
                       [ INPUT STIMULUS / BINARY TARGET ]
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
   ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
   │  DAIMON 1:     │         │  DAIMON 2:     │         │  DAIMON 3:     │
   │  THE PERCUSSION│         │  THE BASSLINE  │         │  THE HARMONY   │
   │  (SENSORY BUS) │         │  (CAUSAL BUS)  │         │  (INTENT BUS)  │
   └───────┬────────┘         └───────┬────────┘         └───────┬────────┘
           │ (Stem 1: Facts)          │ (Stem 2: Laws)           │ (Stem 3: Aim)
           └──────────────────────────┼──────────────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │    NINSHŪ RESONANCE BUS   │
                        │ (EffectResolver Polyphony)│
                        └─────────────┬─────────────┘
                                      ▼
                        [ BALANCED EXPRESSION CONFORM ]
```

### Stem 1: The Percussion Daimon (Sensory / REA Engine)
- **Instruments**:
  - *Kick*: PE/ELF/Mach-O Binary Header Parsers (`DotNetPEParser`, `binaryTargetTypes.ts`).
  - *Snare*: Decompiler bridges (Ghidra, Hopper, Cutter, .NET BSJB streams).
  - *Hi-Hats*: Fast regex scanners (`scan`, `extract_strings`, `find_tokens`).
  - *Overheads*: Live telemetry (Electron IPC hooks, Frida stalkers, PCAP capture).
- **Sub-Mix Output**: A clean, deduplicated `EvidenceBundle` with explicit caller/callee `RelationshipCoverage`.

### Stem 2: The Bassline Daimon (Physics / Kageyōni Governance)
- **Instruments**:
  - *Sub-Bass*: SQLite ACID ledger (`kageyoni.engine.Engine`), CAS revision locks (`branch.revision`).
  - *Root Note*: 3-Tier Reversibility Matrix (`council-reversibility-agent`).
  - *Harmonics*: V11 10-state `ProtectedOperations` machine (`DECLARED` $\rightarrow$ `VERIFIED`).
- **Sub-Mix Output**: Hard thermodynamic constraints, authority boundary assertions, and rollback receipts.

### Stem 3: The Harmony Daimon (Cognition / Intent)
- **Instruments**:
  - *Lead*: Levi Sim `IntentCompiler` & `EpistemicFirewall` (separating intent, observation, and scar).
  - *Pad*: Shinobi `HorizonScout` & Dōjutsu perspective lenses.
  - *Counter-Melody*: `SymbiogenesisAgent` (recomposing ecology when stuck).
- **Sub-Mix Output**: Action proposals, prioritized hypotheses, and verified user dialogue.

---

## 3. The Ninshū DSL: How to Define a Reactive Daimon (Zero Code Cloning)

To instantiate a multi-track Ninshū daimon, write a lightweight declarative resonance file:

```yaml
ninshu_manifest:
  name: "binary-decomp-submix"
  version: "1.0.0"
  daimon:
    role: "Automated binary triage and vulnerability sensor"
    thermal_ceiling: 0  # Tier 0 only
    
  console_dials:
    substrate: "pe | dotnet"
    bandwidth: "targeted"
    authority: 1.0
    polarity: "polyphonic"
    deficit_gain: "wet"
    
  tracks:
    - track_id: "t1_header"
      carrier: "c:/Kageyoni/tools/reverse_engineer.py#DotNetPEParser"
      role: "kick"
      dials: { bandwidth: "fast" }

    - track_id: "t2_strings"
      carrier: "c:/Kageyoni/tools/reverse_engineer.py#extract_strings"
      role: "hihat"
      dials: { filter: "protobuf|rpc|secret" }

    - track_id: "t3_bsjb"
      carrier: "c:/Kageyoni/rea_forge/src/contracts/managedToolContracts.ts"
      role: "snare"
      dials: { bandwidth: "deep" }

  sidechain_bus:
    - trigger: "t1_header.clr_runtime.present == true"
      action: "unmute(t3_bsjb)"
      duck: "t2_strings.gain(-3dB)"

    - trigger: "t3_bsjb.status == UNRESOLVED"
      action: "emit_deficit('MISSING_METHOD_BODY')"
      duck: "t1_header.freeze()"

  master_out:
    format: "kageyoni_aspect_bundle"
    governor: "kageyoni.composition.effects.EffectResolver"
```

---

## 4. Operating Laws of Ninshū

1. **No In-Band Clipping (Zero Monolithic Hacks)**: An instrument must never bypass its sub-mix bus to force a mutation directly on the world state. Everything flows through the sub-mix fader.
2. **Sidechains Must Be Visible**: Any reaction between tracks (e.g. Track A ducking Track B) must be explicitly declared in the sidechain bus, never buried in hidden Python callbacks.
3. **Keep the Master Fader Clean**: The final conform into the world engine must strip all intermediate track chatter and emit only the pure, hash-verified Result.
