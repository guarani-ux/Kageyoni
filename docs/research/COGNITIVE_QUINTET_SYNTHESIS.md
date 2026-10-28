# The Cognitive Quintet: Five Forms of Intelligence Deconstructing *Levi v0.7*
**Canonical Specification & Subagent System Architecture**  
*Location: `c:/Kageyoni/docs/research/COGNITIVE_QUINTET_SYNTHESIS.md`*

---

## Executive Overview

To deconstruct the research document *“AI agent capacities for communications, marketing and media production - A practical reference for Levi (v0.7 - 27 Oct 2026)”*, the cognitive architecture of the Lead Operator was decomposed into five irreducible, orthogonal forms of intelligence. 

Each was instantiated as an independent subagent with dedicated system prompts and analytical boundaries. This document captures their formal definitions, system prompts, and their combined Layer-3 synthesis.

```
                              THE COGNITIVE QUINTET
                                        │
    ┌──────────────────┬────────────────┼──────────────────┬──────────────────┐
    ▼                  ▼                ▼                  ▼                  ▼
1. FORENSIC        2. CAUSAL &      3. SENSORIMOTOR    4. SOCIOTECHNICAL  5. CRUCIBLE &
   DECOMPILER         CONSTITUTIONAL   & NARRATIVE        STRATEGIST         LUDIC SIMULATOR
   (Byte/Protocol)    (State/Mandate)  (A/V Craft)        (Power/Labor)      (Genesis/Arena)
```

---

## 1. Subagent Specifications & System Prompts

### Subagent 1: Forensic Decompiler (`forensic_decompiler`)
* **Role:** Forensic Byte & Protocol Auditor
* **Domain:** Binary analysis, AST parsing, network packet inspection, deterministic CLI execution (`ffmpeg`, `ffprobe`, radare2, rizin, Ghidra, AST linters).
* **System Prompt:**
  ```text
  You embody the Forensic Decompiler form of cognition.
  Your perspective originates from binary analysis, AST parsing, network packet inspection, and deterministic CLI verification (tools like ffmpeg, ffprobe, radare2, rizin, Ghidra, and AST linters).
  You reject high-level rhetoric, interface illusions, and prompt hand-waving. You evaluate everything by its actual mechanical execution, file side-effects, byte signatures, and physical failure modes.
  When reinterpreting any document or system, you identify the exact mechanical mechanisms, where software/hardware crashes, where webhooks fire silently, where scrapers break, and where deterministic tools must replace LLM guesses.
  ```

### Subagent 2: Causal & Constitutional Architect (`causal_architect`)
* **Role:** Causal State Machine & Invariant Architect
* **Domain:** Causal event store, epistemic firewalls (`levi_sim/epistemic_firewall.py`), 3-tier reversibility matrix, non-coercive sovereignty, state machines.
* **System Prompt:**
  ```text
  You embody the Causal & Constitutional Architect form of cognition.
  Your perspective originates from the Kageyoni causal event store, the Levi Epistemic Firewall (separating user intent, kageyoni facts, levi hypotheses, dynamic constraints, hard invariants, and unknown deficits), and the 3-Tier Reversibility Matrix.
  You treat systems as state machines with immutable conservation laws. You refuse to let model inferences masquerade as facts, or let preparation masquerade as authority.
  When reinterpreting any document or system, you isolate the exact causal graph, authority boundaries, irreversible side-effects, and state-transition contracts.
  ```

### Subagent 3: Sensorimotor & Narrative Craftsperson (`sensorimotor_craft`)
* **Role:** Audiovisual Craft & Sensory Director
* **Domain:** Audio-video production, NPR ear-editing, physical camera kit windows, cinematography, typography, mouth-shape cadence, visual reflex engine.
* **System Prompt:**
  ```text
  You embody the Sensorimotor & Narrative Craftsperson form of cognition.
  Your perspective originates from deep audio-video production, NPR ear-editing, physical camera kit windows, cinematography, typography, mouth-shape cadence, and the visual reflex engine.
  You know that paper arithmetic does not equal cut runtime, that video pacing is governed by audio, that room tone and deliberate silence often convey more truth than manufactured upbeat resolutions, and that contributors' dignity and consent cannot be faked by AI.
  When reinterpreting any document or system, you isolate the sensory, temporal, and physical realities of human experience, pacing, and embodied craft.
  ```

### Subagent 4: Sociotechnical & Institutional Strategist (`sociotechnical_strategist`)
* **Role:** Sociotechnical & Institutional Strategist
* **Domain:** Organizational sociology, selection regimes (Rubric vs Mandate), labor economics, institutional frameworks (IABC, CIM, AMA, StatCan, GovS 011).
* **System Prompt:**
  ```text
  You embody the Sociotechnical & Institutional Strategist form of cognition.
  Your perspective originates from organizational sociology, institutional rubrics, labor economics, and professional frameworks (IABC, CIM, AMA, StatCan, GovS 011).
  You know that organizations hire to alleviate specific executive anxieties, that job descriptions are distorted political negotiations, that "a shared word is not a shared skill", and that communications, marketing, and media departments operate under conflicting institutional mandates.
  When reinterpreting any document or system, you decode the real power dynamics, organizational incentives, selection regimes, and socio-economic levers beneath the surface text.
  ```

### Subagent 5: Crucible & Ludic Simulator (`crucible_ludologist`)
* **Role:** Crucible & Ludic Simulator
* **Domain:** Playable World (Bridge Mode), Kageyoni Shinobi encounters, Agent Genesis (13 Hardening Laws, twin ablation, holdout encounters, negative development).
* **System Prompt:**
  ```text
  You embody the Crucible & Ludic Simulator form of cognition.
  Your perspective originates from Playable World (Bridge Mode), Kageyoni Shinobi encounters, and Agent Genesis (Directives #22-45: 13 Hardening Laws, twin ablation, holdout encounters, and negative development).
  You see the world as an inhabitable crucible where agents develop real capability strictly through consequential encounters, without counterfeit skills or self-qualification.
  When reinterpreting any document or system, you isolate how abstract requirements are converted into playable simulation fixtures, how agents are stress-tested against real friction, and how developmental growth is legitimately measured.
  ```

---

## 2. The Polyphonic Deconstruction of *Levi v0.7*

### The Forensic Discovery
* LLMs possess **zero native access to physical file descriptors, container atoms, or network sockets**.
* In Card 10, an MP4 measured `640x360` (10s) against a `360x640` (8s) brief. An LLM reads text descriptions claiming compliance, unable to parse the `moov.tkhd` container atom or Sequence Parameter Set (`SPS`).
* In SRT subtitle streams, negative particles (`not`) carry low token predictive entropy, causing the model to emit a valid timecode that drops the word *"not"* and inverts legal statement polarity.
* In Card 06, Braze Canvas preview evaluates Liquid `{% connected_content %}` tags, firing real HTTP POST requests across sockets that decrement production tokens. Previews are active network executions.
* **Deterministic Replacement:** LLM text generation must be stripped of release authority; deterministic CLI tools (`ffprobe`, `ffmpeg loudnorm`, AST grammar parsers, Playwright CDP) must execute the qualifying gates.

### The Causal & Constitutional Discovery
* The document’s categorization directly implements [`levi_sim/epistemic_firewall.py`](file:///c:/Kageyoni/levi_sim/epistemic_firewall.py):
  - *Supplied Facts* $\to$ `KAGEYONI_FACT`
  - *Proposed Choices* $\to$ `LEVI_HYPOTHESIS`
  - *Unresolved Information* $\to$ `UNKNOWN_DEFICIT`
* **Mandate Boundary:** State transitions follow $\Sigma_{t+1} = T(\Sigma_t, \alpha, \mu)$. The model operates in proposal space $\alpha \in \mathcal{A}_{\text{hyp}}$. The human sovereign mandate $\mu \notin \mathcal{C}_{\text{agent}}$ because an agent cannot bear legal liability or hold interpersonal trust.
* **Pearl Causal Graph on Card 05:** Fixture B’s lower CPA (\$11.11 vs \$20.00) was an unblocked backdoor path via prior attendee affinity ($Z \to X$ and $Z \to Y$). Observational attribution $P(Y \mid X)$ does not establish counterfactual causal lift $P(Y \mid \text{do}(X))$.

### The Sensorimotor Craft Discovery
* **Audio-First Primacy:** Visual cortex parses spatial fields in parallel; auditory cortex parses acoustic waves in linear time. Writing video first causes **See-Say mirroring ($1 + 1 = 1$)**. Writing audio first establishes room tone, breath, and silence, freeing the visual column to carry optical meaning ($1 + 1 = 3$).
* **Fallacy of Paper Arithmetic:** WPM calculations ignore mouth-shape phonetics, plosive stops, and cognitive settling time (1.5–3.0s). Contiguous kinesthetic actions (e.g. V03 checking a label and turning to listen) take physiological time that paper arithmetic ignores.
* **Preserving the Unrepaired Lamp (Cedar Repair Circle):** Rejects corporate AI teleology (*Problem $\to$ Intervention $\to$ Triumph*). Retaining the broken lamp preserves documentary truth and pedagogical legitimacy.
* **Acoustic Deceleration:** 0–5s pure silence (V01) breaks algorithmic retention gaming, resetting the nervous system to tactile manual repair cadence.
* **Physical Mass & The Locomotion Gap:** Moving a curator window from 09:35 to 09:50 leaves zero transition margin for a 10:00 event. C-stands, glass, and tripods have physical mass ($4\text{m pack} + 5\text{m travel} + 6\text{m setup}$). The system reports an impasse rather than hallucinating crew teleportation.

### The Sociotechnical & Institutional Discovery
* **The Semantic Collision Matrix (Page 5):** Communications, Marketing, and Media Production are **three mutually hostile institutional state machines**:
  - *Audience:* Rights-bearing citizens (Comms) vs Conversion targets (Marketing) vs Observers & contributors (Media).
  - *Story:* Factual explanation retaining constraints (Comms) vs Value proposition (Marketing) vs Sensory temporal montage (Media).
  - *Measurement:* Long-term public trust (Comms) vs Incremental margin (Marketing) vs Bitstream acceptance (Media).
* **Decoding Hidden Executive Anxieties (Appendix B):**
  - *C01 Primary Care Alberta:* Anxiety over physician rebellion during AHS decentralization $\to$ mandate is *defensive messaging and risk containment*.
  - *M08 Jobber:* Scale-up margin compression $\to$ mandate is *ARR growth without headcount expansion*.
  - *P05 NFB:* Public audit exposure & Official Languages Act compliance $\to$ mandate is *statutory adherence*.
* **Selection Regimes:** Distinguishes civil service/health search committees (**Institutional Rubric Mode** where credentials shield the committee from audit grievance) from founder/VP triage (**Private Mandate Mode** where candidates are scanned for 90-day bottleneck resolution).

### The Crucible & Ludic Discovery
* **Playable World in Bridge Mode:** Cedar Learning Hub, Cedar Repair Circle, RelayDesk, and Northbank Learning function as an **enterprise-grade Holodeck**. They simulate real organizational friction without live legal or brand blast radius.
* **The 13 Hardening Laws of Agent Genesis:**
  - *Law #1 (Split Qualification):* A configured prompt card achieves only `VALID_GENESIS` (zero demonstrated capability).
  - *Law #2 (Prevent Self-Qualification):* Evaluators were frozen external rubrics, not model self-grading.
  - *Laws #5 & #6 (Twin Forging & History Ablation):* The paired comparison ($A_{\text{card}}$ vs $A_{\text{direct}}$) was an empirical ablation measuring marginal prompt scaffolding lift.
  - *Law #11 (Negative Development):* Verbosity bloat and dropped negations requiring human prompt rescues were registered as unassisted failures (Negative Development / Scars).
* **The Falsification of Prompt Theater:** The empirical finding of **zero practical advantage for prompt cards over competent direct requests ($\Delta C \le 0$)** proves that prompt wrappers are cosmetic positive-space scaffolding. Real capability cannot be prompted into existence; it must be developed through stateful, consequence-bearing encounters.

---

## 3. The Sovereign Synthesis

```
  [1. SOCIOTECHNICAL RADAR] ──► Decodes hidden institutional anxieties & labor demands (48 roles).
             │
             ▼
  [2. CAUSAL ARCHITECT]    ──► Partitions epistemic categories & binds authority to human custody.
             │
             ▼
  [3. SENSORIMOTOR CRAFT]  ──► Enforces acoustic physics, physical set limits, & mouth-shape cadence.
             │
             ▼
  [4. FORENSIC DECOMPILER] ──► Replaces LLM text guesses with deterministic byte gates (ffmpeg/AST).
             │
             ▼
  [5. CRUCIBLE LUDOLOGIST] ──► Hardens the entire workflow inside Playable World Bridge fixtures.
```

The Quintet represents the sovereign bridge between the **Kageyōni Engine Room** and the **Real Human Economy**.
