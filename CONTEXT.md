# KAGEYONI DOMAIN CONTEXT & CAUSAL ONTOLOGY

**Version:** `v11.0.0-audited`  
**Repository:** `guarani-ux/Kageyoni`  
**Standard:** Software 3.0 Contract & Domain-Driven Grounding (Matt Pocock / Deep Modules)

---

## 1. Architectural Mission

Kageyoni is a deterministically audited narrative engine, state machine, and multi-agent coordination layer. It executes operations across narrative, technical, and analytical domains under strict cryptographic, relational, and behavioral invariants.

System claims must reflect physical reality in code and database state. Synthetic self-certification, hardcoded evaluators, and semantic inflation are strictly prohibited.

---

## 2. The 19-Layer Causal Stack

Information propagates through nineteen causal layers from human expression to system evolution. Every interface transition must preserve semantic resolution without loss, leakage, or unearned inflation:

```
 0. HUMAN INTENT / LANGUAGE
        ↓
 1. SEMANTIC INTERPRETATION
        ↓
 2. REPRESENTATION / SITUATION GENESIS
        ↓
 3. CONTEXT / UNKNOWN / CONTRADICTION
        ↓
 4. CLAIM / WARRANT / EVIDENCE
        ↓
 5. OBJECTIVE / REQUIREMENT
        ↓
 6. WORKFLOW / PLAN
        ↓
 7. AUTHORITY / ADMISSION
        ↓
 8. EXECUTION
        ↓
 9. OBSERVATION / VERIFICATION
        ↓
10. STATE CHANGE
        ↓
11. CONSEQUENCE / INVALIDATION FRONTIER
        ↓
12. ARTIFACT / DELIVERY
        ↓
13. MEMORY (Session Scratchpad)
        ↓
14. LEARNING / METHOD (Durable Engine Memory)
        ↓
15. TRANSFER / GENERALIZATION
        ↓
16. FUTURE RETRIEVAL
        ↓
17. FUTURE DECISION / BEHAVIOR
        ↓
18. SYSTEM DEVELOPMENT
```

### Layer Responsibilities & Invariants

1. **Layer 0–1 (Intent → Interpretation):** Human language modality, negation, quantification, temporality, scope, causality, and attribution must be represented explicitly without relying on host-model inference.
2. **Layer 4–5 (Evidence → Claim via Warrant):** The existence of an event receipt or database row does NOT establish a factual claim. Evidence requires an explicit **Warrant** binding it to a scope, revision epoch, and limit.
3. **Layer 7–8 (Authority → Execution):** Ring-fenced execution. No protected operation executes without an engine-held qualification and valid custody chain.
4. **Layer 10–11 (State Change → Invalidation Frontier):** When an engine revision advances, downstream dependent assessments bound to older revisions are marked stale.
5. **Layer 13–14 (Memory → Learning):** Two-tiered boundary. `SituationMemory` is strictly an ephemeral session scratchpad. Durable cross-session learning requires formal promotion into the Foundation `Learning` ledger (`v11_methods`, `v11_learning_cases`).
6. **Layer 15–16 (Transfer → Retrieval):** Lexical relevance does NOT equal current validity. Retrieval must distinguish between relevant history, valid history, and capability-exercising precedent.

---

## 3. Core Physical Primitives

| Primitive | Module Seam | Physical Implementation |
| :--- | :--- | :--- |
| **`Engine`** | `kageyoni.engine.Engine` | Cryptographically hashed event store, revision tracking, branch isolation, and migration custody. |
| **`ProtectedOperations`** | `kageyoni.v11.ProtectedOperations` | State machine governing lifecycle transitions (`DECLARED` $\to$ `PREPARED` $\to$ `ASSESSED` $\to$ `AUTHORIZED` $\to$ `COMPLETED`). |
| **`EnforcerRegistry`** | `kageyoni.v11.EnforcerRegistry` | Engine-evaluated qualification authority requiring multi-case discrimination before granting authority. |
| **`AssessmentLedger`** | `kageyoni.v11.AssessmentLedger` | Records enforcer dispositions against protected requirements with strict revision epoch freshness checks. |
| **`SituationService`** | `kageyoni.situations.service.SituationService` | Domain-agnostic situation lifecycle manager managing templates, frontiers, and state projections. |
| **`Warrant`** | `kageyoni.v11.enforcement.Warrant` | Immutable epistemic bridge connecting raw observed receipts to verified assertions under explicit scope and limits. |
| **`Learning`** | `kageyoni.intelligence.learning` | Empirical parameter and method derivation ledger requiring observed context and counter-outcome checks. |

---

## 4. Prohibited Terminology & Semantic Invariants

To eliminate cognitive drift and prevent agents from hallucinating unearned capabilities:

1. **No Anime Power-Scaling in Engineering Scope:**  
   Terms like *"Mid-Yonko"*, *"Admiral"*, or *"Sannin"* belong strictly to the fictional world bible (`docs/WORLD.md`, narrative character cards). They must NEVER be used to describe engine capability, test maturity, or release tiers. Standard SemVer (`v11.0.0-audited`) is mandatory.

2. **No Cognitive Anthropomorphism:**  
   Relational SQLite rows and parameter overrides must not be titled *"Autonomous Consciousness"*, *"Sentient Substrate"*, or *"Self-Awareness"*. Modules must be named according to their physical function: `parameter_overrides.py`, `assessment_ledger.py`, `learning_ledger.py`.

3. **No Synthetic Self-Certification:**  
   Scripts generating deterministic mock outputs and claiming benchmark wins are forbidden. In the absence of an external empirical verifier, the system must declare `VERIFIER_DEFICIT` and qualify strictly at the mechanical protocol level.

4. **The 5-Fold Long-Horizon Distinction:**  
   Any evaluation of long-horizon development MUST physically distinguish:
   $$\text{Stored History} \neq \text{Retrieved History} \neq \text{Changed Reasoning} \neq \text{Changed Capability} \neq \text{Changed Outcome}$$
   Storage of memory alone does NOT establish developmental progress.
