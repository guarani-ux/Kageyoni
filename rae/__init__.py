"""RAE — Reify Any Element.

Takes an abstract element (framework, principle, mechanism) from the
knowledge database and reifies it: converts it from a description into
a wieldable operational artifact (template, checklist, procedure).

The six stages:
  1. retrieve  — pull the element with its verification status attached
  2. de-abstract — extract the actionable structure (slots, steps, decisions)
  3. situate   — bind the structure to a concrete context (CPL, production, ...)
  4. instrument — add checklists, worked examples, failure modes, success criteria
  5. mark-joints — label every part verified / scaffolded(candidate); the reified
                   form is a new combination, and combinations don't inherit certainty
  6. store      — write the artifact, register it as a work product linked to the source

Usage:
  python -m rae reify --element 8 --context "CPL program promo video"
  python -m rae reify --element "PAS (Problem-Agitate-Solve)" --context "Instagram reel"
"""
