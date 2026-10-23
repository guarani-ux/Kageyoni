# RAE — Reify Any Element

A Kageyoni subsystem. Takes an abstract element (framework, principle, mechanism)
from the knowledge store and reifies it: converts it from a description into a
wieldable operational artifact (template, checklist, procedure).

## The six stages

1. **retrieve** — pull the element with its verification status attached
2. **de-abstract** — extract the actionable structure (slots, steps, decisions)
3. **situate** — bind the structure to a concrete context
4. **instrument** — add checklists, worked examples, failure modes, success criteria
5. **mark-joints** — label every part `[verified]` vs `[scaffolded — candidate]`;
   the reified form is a new combination, and combinations don't inherit certainty
6. **store** — write the artifact, register it as a work product linked to the source

## Division of labor

The engine handles retrieval, provenance, assembly, and registration.
The agent supplies judgment in the fills. The machine never invents substance;
the agent never does bookkeeping.

## Usage

```bash
python -m rae reify --element 8 --context "CPL program promo video" --fills fills.json
python -m rae show --element "PAS (Problem-Agitate-Solve)"
```

## Epistemic discipline

Mirrors the engine's own: evidence-not-truth. Verified parts of the source stay
verified; everything added to make the artifact wieldable is scaffolded
(candidate) until tested in use.
