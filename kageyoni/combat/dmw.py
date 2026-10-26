"""Crisis Core style Digital Mind Wave (DMW) Token Pool & Reel Resonance.

Implements:
- DMWTokenType: FOCUS, ECHO, SURGE, CATHARSIS.
- DMWTokenPool:
  - Bounded pool (max 5 tokens).
  - 1 decay tick per turn.
  - Reel spin matching evaluation:
    - 2-match: 0.25 base probability -> awards FOCUS, ECHO, or SURGE.
    - 3-match: 0.05 base probability -> awards CATHARSIS.
    - Primed companion + affection (>=75) boosts match probabilities.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Sequence, Tuple


class DMWTokenType(str, Enum):
    FOCUS = "FOCUS"
    ECHO = "ECHO"
    SURGE = "SURGE"
    CATHARSIS = "CATHARSIS"


@dataclass
class DMWSpinResult:
    """Outcome of spinning the 3-reel DMW slot system."""
    reels: Tuple[str, str, str]
    match_count: int
    matched_character: Optional[str] = None
    token_awarded: Optional[DMWTokenType] = None
    is_primed: bool = False
    details: str = ""


class DMWTokenPool:
    """Manages active DMW resonance tokens, spin resolution, and turn decay."""

    MAX_CAPACITY: int = 5
    DECAY_PER_TURN: int = 1

    def __init__(self, max_capacity: int = 5) -> None:
        self.max_capacity = max_capacity
        self.tokens: List[DMWTokenType] = []

    @property
    def is_full(self) -> bool:
        return len(self.tokens) >= self.max_capacity

    @property
    def count_total(self) -> int:
        return len(self.tokens)

    def count(self, token_type: DMWTokenType) -> int:
        """Count tokens of a specific type in the pool."""
        return self.tokens.count(token_type)

    def add_token(self, token_type: DMWTokenType) -> bool:
        """Add a token to the pool if under max capacity (5). Returns True if added."""
        if len(self.tokens) >= self.max_capacity:
            return False
        self.tokens.append(token_type)
        return True

    def spend_token(self, token_type: DMWTokenType) -> bool:
        """Spend a single token of the specified type. Returns True if spent successfully."""
        if token_type in self.tokens:
            self.tokens.remove(token_type)
            return True
        return False

    def turn_decay_tick(self) -> Optional[DMWTokenType]:
        """Apply 1 decay per turn, dropping the oldest token in the pool."""
        if self.tokens:
            return self.tokens.pop(0)
        return None

    def spin_reels(
        self,
        roster_names: Sequence[str],
        primed_companion: Optional[str] = None,
        affection_level: int = 50,
        rng_seed: Optional[int] = None,
        auto_add: bool = True,
    ) -> DMWSpinResult:
        """Spin 3 reels and resolve match probabilities.

        Base probabilities:
        - 3-match: 0.05 base -> CATHARSIS
        - 2-match: 0.25 base -> FOCUS, ECHO, or SURGE

        Primed companion + affection (>= 75):
        - 3-match probability +0.10 (total 0.15)
        - 2-match probability +0.20 (total 0.45)
        """
        if not roster_names:
            names = ["Zack", "Sephiroth", "Genesis", "Angeal", "Cloud", "Aerith", "Tifa"]
        else:
            names = list(roster_names)

        r = random.Random(rng_seed) if rng_seed is not None else random.Random()

        # Affection & Priming Boost
        is_primed = bool(primed_companion and primed_companion in names and affection_level >= 75)
        bonus_3 = 0.10 if is_primed else 0.0
        bonus_2 = 0.20 if is_primed else 0.0

        p_3_match = 0.05 + bonus_3
        p_2_match = 0.25 + bonus_2

        roll = r.random()
        match_count = 1
        matched_character: Optional[str] = None
        awarded_token: Optional[DMWTokenType] = None
        reels: Tuple[str, str, str]

        if roll < p_3_match:
            # 3-Match: Catharsis
            match_count = 3
            matched_character = primed_companion if is_primed else r.choice(names)
            reels = (matched_character, matched_character, matched_character)
            awarded_token = DMWTokenType.CATHARSIS
            details = f"JACKPOT 3-MATCH [{matched_character}]: Unlocked CATHARSIS token!"
        elif roll < (p_3_match + p_2_match):
            # 2-Match: FOCUS, ECHO, or SURGE
            match_count = 2
            matched_character = primed_companion if is_primed else r.choice(names)
            # Pick a distinct third reel
            remaining = [n for n in names if n != matched_character]
            third = r.choice(remaining) if remaining else "Echo"

            # Randomize position of distinct reel
            pos = r.randint(0, 2)
            if pos == 0:
                reels = (third, matched_character, matched_character)
            elif pos == 1:
                reels = (matched_character, third, matched_character)
            else:
                reels = (matched_character, matched_character, third)

            token_choices = [DMWTokenType.FOCUS, DMWTokenType.ECHO, DMWTokenType.SURGE]
            awarded_token = r.choice(token_choices)
            details = f"2-MATCH [{matched_character}]: Awarded {awarded_token.value} token!"
        else:
            # No match
            match_count = 1
            if len(names) >= 3:
                sample = r.sample(names, 3)
                reels = (sample[0], sample[1], sample[2])
            else:
                reels = (names[0], names[-1], names[0])
            awarded_token = None
            details = "Reels spun with no resonance match."

        if awarded_token is not None and auto_add:
            self.add_token(awarded_token)

        return DMWSpinResult(
            reels=reels,
            match_count=match_count,
            matched_character=matched_character,
            token_awarded=awarded_token,
            is_primed=is_primed,
            details=details,
        )

    def to_dict(self) -> dict:
        return {
            "tokens": [t.value for t in self.tokens],
            "count": len(self.tokens),
            "max_capacity": self.max_capacity,
        }
