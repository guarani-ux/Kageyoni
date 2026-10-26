"""Anti-Slop AST Gate & Austere Prose Verifier for Kageyōni.

Enforces zero-trust narrative discipline:
1. Scans text for 50 banned stems/phrases from data/narrative_rules.json.
2. Calculates adjective density: adjective_count / total_words, enforcing
   mode-specific ceilings (default <= 0.18, tactical <= 0.12, camp <= 0.20).
3. Enforces the Mandatory Physical Anchor Law: every narrative paragraph must
   contain at least 2 registered physical nouns from the active scene table.
4. Generates austere fallback rewrite prompts or rejects non-compliant prose.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


# Default 50 banned stems and phrases if narrative_rules.json is absent
DEFAULT_BANNED_STEMS: List[str] = [
    "destin",
    "fate",
    "darkness",
    "beacon",
    "hope",
    "echoes of",
    "testament",
    "delve",
    "intertwin",
    "shiver down",
    "unspoken",
    "symphon",
    "dance of",
    "profound",
    "tapestr",
    "mosaic",
    "threaded",
    "converg",
    "inevitab",
    "weight of",
    "valid",
    "process",
    "heal",
    "holding space",
    "vulnerab",
    "journey",
    "safe space",
    "unpack",
    "closure",
    "toxic",
    "boundar",
    "trigger",
    "emotional labor",
    "trauma response",
    "resonant",
    "deep breath",
    "whisper",
    "caress",
    "ethereal",
    "palpab",
    "tangible",
    "kaleidoscop",
    "cacophon",
    "poignant",
    "intricate",
    "myriad",
    "luminous",
    "resplendent",
    "shattered soul",
    "sacred",
]

DEFAULT_FALLBACK_REWRITE_PROMPT: str = (
    "Rewrite in austere Anglo-Saxon prose under 40 words. "
    "Use active physical verbs. Zero emotional adjectives. "
    "Name at least two registered physical objects from the scene."
)

DEFAULT_ADJECTIVE_CEILINGS: Dict[str, float] = {
    "default": 0.18,
    "tactical": 0.12,
    "camp": 0.20,
}

# Extensive set of root adjectives common in literary/fantasy prose
COMMON_ROOT_ADJECTIVES: Set[str] = {
    # Colors
    "red", "crimson", "scarlet", "blue", "azure", "green", "emerald",
    "yellow", "amber", "black", "charcoal", "white", "pale", "gray", "grey",
    "brown", "gold", "golden", "silver", "violet", "purple", "bronze", "copper",
    # Physical & Somatic
    "cold", "hot", "warm", "cool", "chill", "chilly", "dry", "wet", "damp",
    "hard", "soft", "rough", "smooth", "sharp", "blunt", "keen", "dull",
    "heavy", "light", "dark", "bright", "dim", "faint", "harsh", "stark",
    "thick", "thin", "broad", "narrow", "wide", "deep", "shallow", "steep",
    "flat", "hollow", "dense", "taut", "slack", "tight", "loose", "crisp",
    "fresh", "stale", "sour", "bitter", "sweet", "salty", "raw", "numb",
    "sore", "frail", "stout", "lean", "gaunt", "chubby", "brawny", "battered",
    "tall", "short", "grand", "vast", "tiny", "small", "huge", "great",
    "brisk", "swift", "slow", "fast", "quick", "still", "calm", "wild",
    "fierce", "bare", "bald", "sheer", "pure", "clean", "foul", "vile",
    "loud", "quiet", "silent", "hoarse", "shrill", "hushed", "muffled",
    # Emotional, Evaluative & Mental
    "cruel", "proud", "vain", "smug", "stern", "grave", "dour", "grim",
    "bleak", "weary", "tired", "spent", "sad", "glad", "angry", "mad",
    "sick", "ill", "fond", "bold", "shy", "coy", "rash", "terse", "curt",
    "gruff", "sly", "cunning", "wicked", "fair", "right", "wrong", "true",
    "false", "strange", "odd", "weird", "ancient", "new", "old", "young",
    "mature", "dire", "rich", "poor", "dead", "alive", "alone", "sole",
    # Participle-form descriptors
    "broken", "shattered", "severed", "twisted", "fractured", "dented",
    "notched", "cracked", "bruised", "bloodied", "scarred", "calloused",
    "weathered", "rusted", "burned", "charred", "blackened", "torn",
    "frayed", "stitched", "soaked", "drenched", "frozen", "chilled",
    "carved", "forged", "tempered", "honed", "drawn", "poised", "crouched",
    "slouched", "planted", "pinned", "unlaced", "unbuttoned", "unarmored",
    "armored", "hooded", "booted", "cloaked", "veiled", "bandaged",
}

# Words ending in adjective-like suffixes that are actually nouns or non-adjectives
SUFFIX_EXCLUSION_NOUNS: Set[str] = {
    # -al nouns
    "animal", "canal", "pedal", "metal", "signal", "portal", "crystal",
    "hospital", "rival", "trial", "burial", "council", "vessel", "pupil",
    "level", "model", "festival", "denial", "refusal", "survival", "corral",
    "corridor", "capital", "memorial", "individual", "substance",
    # -ic nouns
    "music", "relic", "magic", "traffic", "panic", "fabric", "clinic",
    "logic", "topic", "critic", "tactic", "epic", "mechanic", "mosaic",
    # -ive nouns
    "motive", "archive", "initiative", "objective", "narrative", "executive",
    "fugitive", "relative", "representative", "captive", "derivative",
    # -ary / -ory nouns
    "memory", "story", "theory", "category", "boundary", "territory",
    "history", "sanctuary", "inventory", "century", "victory", "glory",
    "salary", "factory", "dictionary", "military", "adversary", "commentary",
    # -able / -ible nouns
    "table", "cable", "bible", "stable",
}


class AntiSlopViolationError(ValueError):
    """Raised when prose violates the Anti-Slop Zero-Trust Gate."""

    def __init__(self, message: str, result: AntiSlopResult) -> None:
        super().__init__(message)
        self.result = result


@dataclass
class BannedStemMatch:
    """Record of a banned stem or phrase found in text."""

    stem: str
    matched_text: str
    char_index: int


@dataclass
class ParagraphAnchorReport:
    """Audit of physical anchors within a single paragraph."""

    paragraph_index: int
    text_snippet: str
    anchors_found: List[str]
    required_count: int
    passed: bool


@dataclass
class AntiSlopResult:
    """Comprehensive result of anti-slop inspection."""

    passed: bool
    mode: str
    total_words: int
    adjective_count: int
    adjective_density: float
    adjective_density_ceiling: float
    adjectives_found: List[str] = field(default_factory=list)
    banned_stems_found: List[BannedStemMatch] = field(default_factory=list)
    paragraph_anchors: List[ParagraphAnchorReport] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    fallback_rewrite_prompt: str = ""

    def summary(self) -> str:
        """Render human-readable summary of the inspection result."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"Anti-Slop Gate [{status}] (mode={self.mode})",
            f"  - Words: {self.total_words}, Adjectives: {self.adjective_count}",
            f"  - Density: {self.adjective_density:.4f} (Ceiling: {self.adjective_density_ceiling:.4f})",
            f"  - Banned Stem Hits: {len(self.banned_stems_found)}",
            f"  - Paragraphs Evaluated: {len(self.paragraph_anchors)}",
        ]
        if self.violations:
            lines.append("  - Violations:")
            for v in self.violations:
                lines.append(f"      * {v}")
        if not self.passed and self.fallback_rewrite_prompt:
            lines.append(f"  - Fallback Prompt: {self.fallback_rewrite_prompt}")
        return "\n".join(lines)


class AntiSlopGate:
    """Zero-Trust Anti-Slop AST Gate."""

    def __init__(
        self,
        rules_path: Optional[str | Path] = None,
        custom_banned_stems: Optional[Sequence[str]] = None,
    ) -> None:
        self.banned_stems: List[str] = list(DEFAULT_BANNED_STEMS)
        self.ceilings: Dict[str, float] = dict(DEFAULT_ADJECTIVE_CEILINGS)
        self.required_anchors_per_paragraph: int = 2
        self.fallback_prompt: str = DEFAULT_FALLBACK_REWRITE_PROMPT

        self._load_rules(rules_path)
        if custom_banned_stems:
            self.banned_stems = list(custom_banned_stems)

        self._compile_patterns()

    def _load_rules(self, rules_path: Optional[str | Path]) -> None:
        path = self._resolve_rules_path(rules_path)
        if not path or not path.is_file():
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            gate = data.get("anti_slop_gate", {})
            if "banned_stems" in gate:
                self.banned_stems = [str(s).strip() for s in gate["banned_stems"] if str(s).strip()]
            if "adjective_density_ceiling_default" in gate:
                self.ceilings["default"] = float(gate["adjective_density_ceiling_default"])
            if "adjective_density_ceiling_tactical" in gate:
                self.ceilings["tactical"] = float(gate["adjective_density_ceiling_tactical"])
            if "adjective_density_ceiling_camp" in gate:
                self.ceilings["camp"] = float(gate["adjective_density_ceiling_camp"])
            if "required_physical_nouns_per_paragraph" in gate:
                self.required_anchors_per_paragraph = int(gate["required_physical_nouns_per_paragraph"])
            if "fallback_rewrite_prompt" in gate:
                self.fallback_prompt = str(gate["fallback_rewrite_prompt"])
        except Exception:
            # Fall back to hardcoded defaults if rules file cannot be loaded
            pass

    @staticmethod
    def _resolve_rules_path(rules_path: Optional[str | Path]) -> Optional[Path]:
        if rules_path:
            p = Path(rules_path)
            return p if p.is_file() else None

        candidates = [
            Path("data/narrative_rules.json"),
            Path(__file__).resolve().parent.parent.parent / "data" / "narrative_rules.json",
            Path(__file__).resolve().parents[2] / "data" / "narrative_rules.json",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None

    def _compile_patterns(self) -> None:
        """Compile regex matchers for banned stems and phrases."""
        self._phrase_matchers: List[Tuple[str, re.Pattern[str]]] = []
        self._stem_matchers: List[Tuple[str, re.Pattern[str]]] = []

        for item in self.banned_stems:
            stem = item.strip()
            if not stem:
                continue
            if " " in stem:
                # Multi-word phrase: match with flexible whitespace between words
                escaped = r"\s+".join(re.escape(w) for w in stem.split())
                pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
                self._phrase_matchers.append((stem, pattern))
            else:
                # Single-word stem: matches at word start
                pattern = re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE)
                self._stem_matchers.append((stem, pattern))

    def is_adjective(self, word: str, registered_scene_nouns: Optional[Set[str]] = None) -> bool:
        """Heuristic zero-dependency morphological adjective classifier."""
        w = word.lower().strip()
        if not w or len(w) <= 2:
            return False

        # Physical scene nouns are NEVER adjectives, even when placed attributively
        if registered_scene_nouns and w in registered_scene_nouns:
            return False

        if w in SUFFIX_EXCLUSION_NOUNS:
            return False

        if w in COMMON_ROOT_ADJECTIVES:
            return True

        # Suffix rules for English adjectives
        if w.endswith(("ous", "ious", "eous")) and len(w) > 4:
            return True
        if w.endswith("ful") and len(w) > 4:
            return True
        if w.endswith("less") and len(w) > 5:
            return True
        if w.endswith(("able", "ible")) and len(w) > 5:
            return True
        if w.endswith("esque") and len(w) > 6:
            return True
        if w.endswith("ive") and len(w) > 4:
            return True
        if w.endswith(("ic", "ical")) and len(w) > 4:
            return True
        if w.endswith("ish") and len(w) > 4:
            return True
        if w.endswith("al") and len(w) > 4:
            return True
        if w.endswith(("ary", "ory")) and len(w) > 5:
            return True

        return False

    def scan_banned_stems(self, text: str) -> List[BannedStemMatch]:
        """Scan text for all configured banned stems and phrases."""
        matches: List[BannedStemMatch] = []
        seen_positions: Set[int] = set()

        for stem, pattern in self._phrase_matchers:
            for m in pattern.finditer(text):
                if m.start() not in seen_positions:
                    seen_positions.add(m.start())
                    matches.append(BannedStemMatch(stem=stem, matched_text=m.group(), char_index=m.start()))

        for stem, pattern in self._stem_matchers:
            for m in pattern.finditer(text):
                if m.start() not in seen_positions:
                    seen_positions.add(m.start())
                    matches.append(BannedStemMatch(stem=stem, matched_text=m.group(), char_index=m.start()))

        matches.sort(key=lambda x: x.char_index)
        return matches

    def calculate_adjective_density(
        self,
        text: str,
        registered_scene_nouns: Optional[Set[str]] = None,
    ) -> Tuple[float, int, int, List[str]]:
        """Calculate adjective density: adjective_count / total_words."""
        tokens = re.findall(r"\b[a-zA-Z0-9'-]+\b", text)
        total_words = len(tokens)
        if total_words == 0:
            return 0.0, 0, 0, []

        adjectives: List[str] = []
        for token in tokens:
            cleaned = token.strip("'-")
            if self.is_adjective(cleaned, registered_scene_nouns):
                adjectives.append(cleaned.lower())

        density = len(adjectives) / total_words
        return density, len(adjectives), total_words, adjectives

    def verify_physical_anchors(
        self,
        text: str,
        scene_nouns: Sequence[str],
    ) -> Tuple[bool, List[ParagraphAnchorReport]]:
        """Assert that every narrative paragraph contains at least 2 registered physical nouns."""
        cleaned_scene_nouns = {n.lower().strip() for n in scene_nouns if n.strip()}
        if not cleaned_scene_nouns:
            # If no scene table registered, paragraph cannot satisfy the anchor law
            pass

        # Split into non-empty paragraphs
        raw_paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", text) if p.strip()]
        if not raw_paragraphs and text.strip():
            raw_paragraphs = [text.strip()]

        reports: List[ParagraphAnchorReport] = []
        all_passed = True

        for idx, para in enumerate(raw_paragraphs):
            para_tokens = set(re.findall(r"\b[a-zA-Z0-9'-]+\b", para.lower()))
            found_anchors: List[str] = [noun for noun in cleaned_scene_nouns if noun in para_tokens]

            passed = len(found_anchors) >= self.required_anchors_per_paragraph
            if not passed:
                all_passed = False

            snippet = (para[:60] + "...") if len(para) > 60 else para
            reports.append(
                ParagraphAnchorReport(
                    paragraph_index=idx,
                    text_snippet=snippet,
                    anchors_found=sorted(found_anchors),
                    required_count=self.required_anchors_per_paragraph,
                    passed=passed,
                )
            )

        return all_passed, reports

    def inspect_text(
        self,
        text: str,
        scene_nouns: Optional[Sequence[str]] = None,
        mode: str = "default",
    ) -> AntiSlopResult:
        """Comprehensive zero-trust audit of prose."""
        scene_noun_set = {n.lower().strip() for n in (scene_nouns or []) if n.strip()}
        ceiling = self.ceilings.get(mode, self.ceilings["default"])

        banned_matches = self.scan_banned_stems(text)
        density, adj_count, total_words, adjs_found = self.calculate_adjective_density(
            text, registered_scene_nouns=scene_noun_set
        )
        anchors_passed, anchor_reports = self.verify_physical_anchors(
            text, scene_nouns or []
        )

        violations: List[str] = []
        if banned_matches:
            stems_list = ", ".join(f"'{m.matched_text}' (stem: {m.stem})" for m in banned_matches)
            violations.append(f"Found {len(banned_matches)} banned stem violation(s): {stems_list}")

        if density > ceiling:
            violations.append(
                f"Adjective density {density:.4f} exceeds ceiling {ceiling:.4f} for mode '{mode}' "
                f"({adj_count} adjectives / {total_words} words: {', '.join(adjs_found[:8])})"
            )

        if not anchors_passed:
            failed_paras = [r.paragraph_index + 1 for r in anchor_reports if not r.passed]
            violations.append(
                f"Mandatory Physical Anchor Law violated: paragraph(s) {failed_paras} "
                f"contain fewer than {self.required_anchors_per_paragraph} registered scene nouns."
            )

        passed = len(violations) == 0
        fallback_prompt = ""
        if not passed:
            fallback_prompt = (
                f"{self.fallback_prompt}\n"
                f"[Violations: {'; '.join(violations)}]"
            )

        return AntiSlopResult(
            passed=passed,
            mode=mode,
            total_words=total_words,
            adjective_count=adj_count,
            adjective_density=density,
            adjective_density_ceiling=ceiling,
            adjectives_found=adjs_found,
            banned_stems_found=banned_matches,
            paragraph_anchors=anchor_reports,
            violations=violations,
            fallback_rewrite_prompt=fallback_prompt,
        )

    def assert_prose_clean(
        self,
        text: str,
        scene_nouns: Optional[Sequence[str]] = None,
        mode: str = "default",
    ) -> None:
        """Assert that prose passes all anti-slop rules; raise AntiSlopViolationError if not."""
        result = self.inspect_text(text, scene_nouns=scene_nouns, mode=mode)
        if not result.passed:
            err_msg = f"Anti-Slop Gate rejected prose:\n{result.summary()}"
            raise AntiSlopViolationError(err_msg, result)

    def reject_or_rewrite(
        self,
        text: str,
        scene_nouns: Optional[Sequence[str]] = None,
        mode: str = "default",
    ) -> Tuple[bool, str]:
        """Returns (True, text) if clean, or (False, fallback_rewrite_prompt) if rejected."""
        result = self.inspect_text(text, scene_nouns=scene_nouns, mode=mode)
        if result.passed:
            return True, text
        return False, result.fallback_rewrite_prompt


# Module-level convenience functions
_DEFAULT_GATE = AntiSlopGate()


def inspect_prose(
    text: str,
    scene_nouns: Optional[Sequence[str]] = None,
    mode: str = "default",
) -> AntiSlopResult:
    """Audit text against the default AntiSlopGate."""
    return _DEFAULT_GATE.inspect_text(text, scene_nouns=scene_nouns, mode=mode)


def assert_prose_clean(
    text: str,
    scene_nouns: Optional[Sequence[str]] = None,
    mode: str = "default",
) -> None:
    """Raise AntiSlopViolationError if text fails the default AntiSlopGate."""
    _DEFAULT_GATE.assert_prose_clean(text, scene_nouns=scene_nouns, mode=mode)
