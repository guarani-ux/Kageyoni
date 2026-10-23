"""Reification patterns: how each kind of abstract element becomes wieldable.

A pattern is not the reified artifact — it's the scaffold the agent fills
with judgment. The engine enforces the shape; the agent supplies the substance.
Every filled slot the agent invents is marked scaffolded (candidate).
"""

PATTERNS = {
    "framework": {
        "description": "A named multi-step structure (PAS, AIDA, Freytag). Reifies to a slot template.",
        "slots": ["steps", "slot_prompts", "transitions"],
        "instrument": ["worked_example", "checklist", "failure_modes", "success_criteria"],
    },
    "principle": {
        "description": "A rule or heuristic (e.g. 'mind for having ideas'). Reifies to a checklist + test.",
        "slots": ["statement", "when_it_applies", "when_it_doesnt"],
        "instrument": ["checklist", "worked_example", "failure_modes", "success_criteria"],
    },
    "mechanism": {
        "description": "A cause-effect process (e.g. algorithm ranking). Reifies to a procedure.",
        "slots": ["inputs", "process", "outputs", "levers"],
        "instrument": ["procedure", "worked_example", "failure_modes", "success_criteria"],
    },
}


def detect_kind(element):
    """Rough kind detection from the element's title/content. Agent overrides as needed."""
    text = (element.get("title", "") + " " + (element.get("content") or "")).lower()
    if any(w in text for w in ["framework", "structure", "steps", "formula", "acronym"]):
        return "framework"
    if any(w in text for w in ["mechanism", "algorithm", "process", "how it works"]):
        return "mechanism"
    return "principle"


def joint_mark(status):
    """Label provenance for a filled slot."""
    return {
        "verified": "[verified]",
        "scaffolded": "[scaffolded — candidate]",
        "candidate": "[scaffolded — candidate]",
        "failed": "[failed — do not use]",
    }[status]
