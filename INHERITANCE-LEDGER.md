# Kageyoni v10 inheritance ledger

Inheritance is permitted only when a prior implementation hardens a causal workflow Kageyoni already performs. This release does not import project names or architecture wholesale.

## Qualified and integrated

### Nelson → exact basis binding
**Existing Kageyoni workflow:** compile state → propose transition → commit consequence.  
**Weakness:** a proposal could otherwise outlive the exact records that justified it.  
**Inherited mechanism:** dependency binding to specific inputs.  
**v10 implementation:** `EngineAspectAdapter.basis_manifest()` + `ResolutionGovernor` rebind exact record IDs, versions, source events, branch revision, and exact command before commit.  
**Preserved semantics:** canonical mutation still goes through `Engine.apply`.

### Outer Sanctum → fail-closed verification registry
**Existing workflow:** Frame admission already names verification requirements.  
**Weakness:** named checks could become decorative metadata.  
**Inherited mechanism:** registered gates reject unknown/broken gate implementations.  
**v10 implementation:** `composition/gates.py`; compiler executes every declared Frame verifier.

### 10 Shadows → first-class deficits
**Existing workflow:** incomplete scenes/tasks already wait or fail on missing state.  
**Weakness:** missing knowledge, state, or capability was not represented as a reusable resolution object.  
**Inherited mechanism:** typed deficit declaration and bounded resolution routes.  
**v10 implementation:** compilation blockers emit typed deficits.  
**Rejected donor behavior:** dictionary provisioning is never relabeled automatically as `verified_evidence`.

### Espada → metamorphic checks
**Existing workflow:** compilation and serialization should preserve semantic state under irrelevant representation changes.  
**Weakness:** example tests alone can pass while hidden order dependence survives.  
**Inherited mechanism:** independently declared transformations that should preserve behavior; non-applicability is not success.  
**v10 implementation:** order invariance, JSON roundtrip, and valid optional-pressure tests.

### v9.5 challenge → recovery/current-output hardening
**Existing workflow:** pipeline writes, reconciliation, and completion verification.  
**Weakness:** conflicting partial writes could dead-end; historical completion could mask later external divergence.  
**v10 implementation:** recoverable state + present-tense output verification.  
**Evidence:** original frozen challenge now passes 9/9.

## Inspected but not inherited as-is

- Ten Shadows Control role separation: valuable, but rc1 does not claim an independent external verifier identity for every simulation action. Existing explicit preview/authorize/verify boundaries were hardened without inventing independence.
- Hidden Booder Village profile scoring: real persistence/routing exists, but caller-supplied success and fixed increments are too weak for v10 development qualification.
- Mugen critic/retry loops: useful producer→checker→repair shape, but some checks are structural/phrase-based and are not sufficient correctness authorities.
- Outer Sanctum memory rules: durable failure retrieval is useful, but a stored warning is not automatically a valid general rule.
- JobHunter truth set: the principle informs Expression Contracts, but rc1 does not yet implement a generic semantic checker capable of proving generated prose contains no unsupported implication.
