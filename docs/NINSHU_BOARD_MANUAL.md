# Ninshū: The Engineer's Manual for the SSL 4000 Board
*How to Sit at the Desk, Dial the Knobs, and Mix Realities Without Clipping*

---

## 1. The Core Philosophy of the Board (The Creed)

> **"Do not wield the desk as an armory. Wield it as a resonance chamber."**

In standard engineering (Ninjutsu), an engineer tries to grab every tool at once, cramming scripts into memory until the system crashes.
In **Ninshū**, you operate like an elite recording engineer sitting in front of a 48-channel Solid State Logic desk:
1. **Never bring up all 48 faders at once.** That is pure noise and digital clipping.
2. **Every session starts in silence.** Identify the problem frequency, bring up only 2 or 3 channels, set the gain and EQ, and listen to the sub-mix stem.
3. **Preserve dynamic tension.** If two channels disagree (e.g., Static vs. Dynamic), do not flatten them. Compress the bus and preserve the chord.

---

## 2. The 4 Movements of Every Session (How to Run the Desk)

Whenever an intent or problem arrives, follow the standard **4-Movement Session Flow**:

```
[ Movement 1: LISTEN ] ──> [ Movement 2: ROUTE ] ──> [ Movement 3: TWEAK ] ──> [ Movement 4: COMMIT ]
(Assay Intent & Target)    (Patch the 3-Track Stem)   (Set the 8 Channel Knobs) (Master Bus Glue & Gate)
```

---

### Movement 1: LISTEN (The Ear & Intent)
Before touching any faders, determine:
- **What is the target material?** (Is it a PE binary, an Electron folder, a PCAP capture, an SQLite database, or a narrative brief?)
- **What is the desired output?** (An architectural report, an unpinned API stream, a decompiled C function, or a causal world mutation?)

---

### Movement 2: ROUTE (The Patchbay Query)
Never search directories manually. Ask the desk to find the minimum-sufficient sub-mix:

```sh
# Example: We have a closed Windows desktop app and need its network calls & API keys
python -m kageyoni.ninshu.cli route "extract api keys and network endpoints from electron desktop app" --subject directory --max-tier 0
```

The patchbay instantly returns your 3-track stem:
- **Track 1 (The Kick / Foundation)**: `CH 25` (Electron ASAR Archive Unpacker)
- **Track 2 (The Snare / Surface)**: `CH 26` (Electron Active Hook & IPC Boundary Scanner)
- **Track 3 (The Hi-Hat / Detail)**: `CH 38` (Fast Token & Secret Regex Radar)

---

### Movement 3: TWEAK (Setting the Channel Knobs)
On each of your active channels, calibrate the **8 Knobs** to fit the session:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        THE 8 CONSOLE DIALS                             │
│                                                                        │
│  [1. SUBSTRATE]    Set to target format (e.g., "electron", "pe")       │
│  [2. BANDWIDTH]    Wide (fast header) vs. Notch (regex) vs. Deep (CFG) │
│  [3. AUTHORITY]    Observed (raw bytes) vs. Derived (decompiled logic) │
│  [4. DAMPING]      Low (reactive to changes) vs. High (locked scars)   │
│  [5. THERMAL]      Tier 0 (Read-Only) vs. Tier 1 (Active Hook/Inject)  │
│  [6. POLARITY]     Chord (preserve conflict) vs. Mono (force consensus)│
│  [7. SIDECHAIN]    Track A failure automatically triggers Track B      │
│  [8. DEFICIT GAIN] Wet (turn blindspots into explicit typed sockets)   │
└────────────────────────────────────────────────────────────────────────┘
```

#### The Gold Standard Dial Settings:
* **For Fast Reconnaissance / Triage**:
  - Bandwidth: `Targeted` | Authority: `1.0 (Observed)` | Thermal: `Tier 0 (Cold)` | Deficit Gain: `Wet`
* **For Deep Reverse-Engineering & Decompilation**:
  - Bandwidth: `Deep (Microscopic)` | Authority: `0.5 (Derived)` | Thermal: `Tier 0 Sandbox` | Polarity: `Chord`
* **For Live Network / Memory Interception**:
  - Bandwidth: `Notch` | Authority: `1.0` | Thermal: `Tier 1 (Hot Gate)` | Sidechain: `Active Ducking`

---

### Movement 4: COMMIT (The Master Bus Compressor)
Once your tracks are balanced and the sub-mix stem sounds clean:
1. **Check the Master Reversibility Fader**:
   - If the patch contains any channel with `reversibility_tier >= 1`, the desk **fails closed** and prompts:
     `WARNING: POTENTIALLY DESTRUCTIVE ACTION`
     *(Awaiting sovereign human key-turn before injecting or writing).*
2. **Engage the Causal Bus Glue (Channels 41–44)**:
   - Run the stem through `EffectResolver` (CH 43) to balance all pressures.
   - Lock the record dependencies via `ResolutionGovernor` (CH 41/44).
   - If zero byte drift has occurred, commit the result to the permanent ledger.
3. **Close the Channels**:
   - Mute all tracks. Zero temporary files left on disk. Zero memory leakage.

---

## 3. The 3 Master Engineer Laws

1. **Law of Headroom (No In-Band Clipping)**:
   If an instrument starts throwing errors or encountering unknown code (like an obfuscated packer or indirect jump), **do not turn up the gain** by guessing or hallucinating. Back off the fader, set Deficit Gain to *Wet*, and let the missing socket summon an alternate channel (e.g., switch from static Ghidra to dynamic Frida).
2. **Law of Phase Cancellation (Opposing Pressures)**:
   When static analysis says "Class A" and dynamic memory says "Class B", they are not cancelling each other out—they are 180 degrees out of phase. Record the phase difference explicitly in the *Expression Contract*. That phase difference is usually where the secret or vulnerability is hiding.
3. **Law of Tape Hygiene (Immutable Master)**:
   The master tape is sacred. Raw commits, physical git histories, and SQLite branches are never rewritten in anger. Every change is an additive track.
