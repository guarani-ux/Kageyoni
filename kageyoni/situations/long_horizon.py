from __future__ import annotations
from dataclasses import dataclass
from .memory import SituationMemory, SituationMemoryStore

@dataclass(frozen=True)
class HorizonObservation:
    trajectory: str
    stored_history: bool
    first_retrieval: tuple[str, ...]
    later_retrieval: tuple[str, ...]
    first_decision: str
    later_decision: str
    changed_reasoning: bool
    changed_capability: bool
    changed_outcome: bool

def _decision(memories, default_action, learned_action):
    relevant = any(m.outcome_refs for m in memories)
    return learned_action if relevant else default_action

def run_horizon_trial(store: SituationMemoryStore, trajectory: str, template_id: str, dependency_key: str,
                      default_action: str = "baseline", learned_action: str = "apply-qualified-lesson"):
    before_memories = store.retrieve(template_id=template_id, dependency_keys=(dependency_key,))
    before = tuple(m.memory_id for m in before_memories)
    first_decision = _decision(before_memories, default_action, learned_action)

    lesson = SituationMemory(
        f"{trajectory}:lesson", f"{trajectory}:1", template_id, f"{trajectory} objective",
        decisions=("retain consequential lesson",),
        outcome_refs=(f"{trajectory}:outcome",),
        dependency_keys=(dependency_key,),
    )
    store.remember(lesson)

    after_memories = store.retrieve(template_id=template_id, dependency_keys=(dependency_key,))
    after = tuple(m.memory_id for m in after_memories)
    later_decision = _decision(after_memories, default_action, learned_action)

    return HorizonObservation(
        trajectory=trajectory,
        stored_history=lesson.memory_id in {m.memory_id for m in store.store.values("memory")},
        first_retrieval=before,
        later_retrieval=after,
        first_decision=first_decision,
        later_decision=later_decision,
        changed_reasoning=first_decision != later_decision,
        changed_capability=False,
        changed_outcome=first_decision != later_decision,
    )
