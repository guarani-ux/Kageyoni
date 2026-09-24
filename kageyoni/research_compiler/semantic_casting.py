"""
kageyoni/research_compiler/semantic_casting.py
Semantic Casting & Epistemic Gate (Gate G3).

Enforces mathematical invariants across linguistic transformations:
1. Modality Preserving: 'may' / 'might' cannot become 'does' / 'proves'.
2. Quantifier Preserving: 'some' / 'partially' cannot expand to 'all' / 'every'.
3. Epistemic Status Preserving: ASSUMPTION or HEURISTIC cannot be laundered into SOURCE_SUPPLIED_FACT.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Set, Tuple

from .claims import ClaimNode, EpistemicStatus


class SemanticCastingError(ValueError):
    """Raised when an assertion illegally changes modality, quantifier scope, or epistemic status."""
    pass


MODALITY_RANKS: Dict[str, int] = {
    "UNSPECIFIED": 0,
    "POSSIBLE": 1,
    "PROBABLE": 2,
    "CERTAIN": 3,
}

QUANTIFIER_RANKS: Dict[str, int] = {
    "UNSPECIFIED": 0,
    "SOME": 1,
    "MANY": 2,
    "MOST": 3,
    "ALL": 4,
}

# Regex patterns for detecting linguistic indicators
MODALITY_PATTERNS = [
    (re.compile(r"\b(may|might|could|possibly|potential|can)\b", re.IGNORECASE), "POSSIBLE"),
    (re.compile(r"\b(likely|probable|probably|should|expected)\b", re.IGNORECASE), "PROBABLE"),
    (re.compile(r"\b(is|are|does|do|proves|proves that|demonstrates|will|must|causes)\b", re.IGNORECASE), "CERTAIN"),
]

QUANTIFIER_PATTERNS = [
    (re.compile(r"\b(some|a subset|certain|a few|partially)\b", re.IGNORECASE), "SOME"),
    (re.compile(r"\b(many|numerous|multiple|a significant portion)\b", re.IGNORECASE), "MANY"),
    (re.compile(r"\b(most|majority|largely|predominantly)\b", re.IGNORECASE), "MOST"),
    (re.compile(r"\b(all|every|always|universally|entirely|in all cases)\b", re.IGNORECASE), "ALL"),
]


def infer_modality(text: str, default: str = "UNSPECIFIED") -> str:
    """Infers the modality tier from statement text."""
    # Check lowest rank first to be conservative
    for pattern, tier in MODALITY_PATTERNS:
        if pattern.search(text):
            return tier
    return default


def infer_quantifier(text: str, default: str = "UNSPECIFIED") -> str:
    """Infers the quantifier tier from statement text."""
    for pattern, tier in QUANTIFIER_PATTERNS:
        if pattern.search(text):
            return tier
    return default


def validate_semantic_transition(
    source_statement: str,
    target_statement: str,
    source_status: EpistemicStatus,
    target_status: EpistemicStatus,
    source_modality: Optional[str] = None,
    target_modality: Optional[str] = None,
    source_quantifier: Optional[str] = None,
    target_quantifier: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validates that a statement transformation does not violate semantic casting invariants.
    Returns (True, None) if valid, or (False, reason) if invalid.
    """
    s_mod = source_modality or infer_modality(source_statement)
    t_mod = target_modality or infer_modality(target_statement)

    s_quant = source_quantifier or infer_quantifier(source_statement)
    t_quant = target_quantifier or infer_quantifier(target_statement)

    # 1. Modality Shift Gate
    s_mod_rank = MODALITY_RANKS.get(s_mod, 3)
    t_mod_rank = MODALITY_RANKS.get(t_mod, 3)
    if t_mod_rank > s_mod_rank:
        return False, f"ILLEGAL_MODALITY_PROMOTION: Source modality '{s_mod}' promoted to target modality '{t_mod}' in transformation."

    # 2. Quantifier Expansion Gate
    s_quant_rank = QUANTIFIER_RANKS.get(s_quant, 4)
    t_quant_rank = QUANTIFIER_RANKS.get(t_quant, 4)
    if t_quant_rank > s_quant_rank:
        return False, f"ILLEGAL_QUANTIFIER_EXPANSION: Source scope '{s_quant}' expanded to target scope '{t_quant}' in transformation."

    # 3. Epistemic Status Laundering Gate
    unwarranted_statuses = {
        EpistemicStatus.ASSUMPTION.value,
        EpistemicStatus.HEURISTIC.value,
        EpistemicStatus.INTERPRETATION.value,
        EpistemicStatus.CREATIVE_DECISION.value,
        EpistemicStatus.PREFERENCE.value,
        EpistemicStatus.UNKNOWN.value,
    }
    warranted_statuses = {
        EpistemicStatus.SOURCE_SUPPLIED_FACT.value,
        EpistemicStatus.EVIDENCE_SUPPORTED_CLAIM.value,
    }

    if source_status.value in unwarranted_statuses and target_status.value in warranted_statuses:
        return False, f"EPISTEMIC_STATUS_LAUNDERING: Cannot promote '{source_status.value}' to warranted status '{target_status.value}' without empirical evidence."

    return True, None


def cast_claim_safely(
    source_claim: ClaimNode,
    new_claim_id: str,
    target_statement: str,
    target_status: EpistemicStatus,
    target_modality: Optional[str] = None,
    target_quantifier: Optional[str] = None,
) -> ClaimNode:
    """
    Attempts to cast an existing claim into a child claim, raising SemanticCastingError if invariants are violated.
    """
    valid, reason = validate_semantic_transition(
        source_statement=source_claim.statement,
        target_statement=target_statement,
        source_status=source_claim.epistemic_status,
        target_status=target_status,
        source_modality=source_claim.modality,
        target_modality=target_modality,
        source_quantifier=source_claim.quantifier,
        target_quantifier=target_quantifier,
    )
    if not valid:
        raise SemanticCastingError(reason)

    t_mod = target_modality or infer_modality(target_statement, default=source_claim.modality)
    t_quant = target_quantifier or infer_quantifier(target_statement, default=source_claim.quantifier)

    child = ClaimNode(
        claim_id=new_claim_id,
        statement=target_statement,
        epistemic_status=target_status,
        provenance_sources=list(source_claim.provenance_sources),
        confidence_level=source_claim.confidence_level,
        falsification_condition=source_claim.falsification_condition,
        parent_claim_ids=[source_claim.claim_id],
        evidence_establishes_claim=target_statement,
        modality=t_mod,
        quantifier=t_quant,
        uncertainties=list(source_claim.uncertainties),
    )
    return child
