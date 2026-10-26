"""
Modular Martial Grammar & Compound Compiler for Kageyōni.

Synthesizes 4-part compound techniques from the fundamental martial grammar:
    Technique = Stance (12) + Vector (16) + Infusion (16) + Intent (20) = 61,440 combinations.

Computes closed-form deterministic physics metrics:
    - Will Stamina Cost: C_stamina = base_cost * (1 - mastery_discount) * stance_stability
    - Emotional Erosion Ticks: E_erosion = infusion_density * thermal_tier * intent_complexity
    - Kinetic Backlash Damage: B_backlash = kinetic_impulse * (1 - kinetic_stability)
    - Recovery frames based on stance recovery and vector reach.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class MartialGrammarError(Exception):
    """Base exception for martial grammar errors."""


class InvalidPrimitiveError(MartialGrammarError):
    """Raised when an unknown primitive ID is referenced."""


class IncompatibleCompoundError(MartialGrammarError):
    """Raised when an invalid or contradictory combination of primitives is rejected."""


@dataclass(frozen=True)
class StancePrimitive:
    id: str
    name: str
    name_jp: str
    kinetic_stability: float
    recovery_mod_frames: int
    primary_substrates: List[str]
    description: str


@dataclass(frozen=True)
class VectorPrimitive:
    id: str
    name: str
    name_jp: str
    shape_envelope: str
    base_reach_meters: float
    penetration_multiplier: float
    kinetic_impulse_multiplier: float
    description: str


@dataclass(frozen=True)
class InfusionPrimitive:
    id: str
    origin_carrier: str
    thermal_tier: int
    base_density: float
    polarity: str
    description: str


@dataclass(frozen=True)
class IntentPrimitive:
    id: str
    name: str
    name_jp: str
    trigger_rule: str
    branch_operation: str
    complexity_weight: float
    description: str


@dataclass(frozen=True)
class TalentPrimitive:
    id: str
    name: str
    name_jp: str
    martial_focus: str
    threshold_base: float
    awakening_perk: str
    description: str


@dataclass
class CompiledTechnique:
    technique_id: str
    character_id: str
    name: str
    stance_id: str
    vector_id: str
    infusion_id: str
    intent_id: str
    practice_status: str  # proposed, experimental, demonstrated, retained, unavailable
    mastery_discount: float
    stamina_cost: float
    erosion_ticks: float
    backlash_damage: float
    effective_backlash: float
    recovery_frames: int
    times_executed: int = 0
    times_hit: int = 0
    discovery_engine: str = "forge"  # forge, satori, camp_sparring, quarried
    lineage_donor_id: Optional[str] = None
    created_turn: int = 1
    compound_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CompiledTechnique:
        # Default effective_backlash if omitted
        if "effective_backlash" not in data:
            data["effective_backlash"] = max(0.0, data.get("backlash_damage", 0.0))
        return cls(**data)

    def to_db_row(self) -> Dict[str, Any]:
        """Convert to SQLite character_techniques record row."""
        return {
            "technique_id": self.technique_id,
            "character_id": self.character_id,
            "name": self.name,
            "stance_id": self.stance_id,
            "vector_id": self.vector_id,
            "infusion_id": self.infusion_id,
            "intent_id": self.intent_id,
            "practice_status": self.practice_status,
            "mastery_discount": self.mastery_discount,
            "stamina_cost": self.stamina_cost,
            "erosion_ticks": self.erosion_ticks,
            "backlash_damage": self.backlash_damage,
            "recovery_frames": self.recovery_frames,
            "times_executed": self.times_executed,
            "times_hit": self.times_hit,
            "discovery_engine": self.discovery_engine,
            "lineage_donor_id": self.lineage_donor_id,
            "created_turn": self.created_turn,
        }


class MartialGrammar:
    """Loaded repository of martial grammar primitives."""

    DEFAULT_GRAMMAR_PATH = Path(__file__).resolve().parents[2] / "data" / "martial_grammar.json"

    def __init__(
        self,
        stances: Dict[str, StancePrimitive],
        vectors: Dict[str, VectorPrimitive],
        infusions: Dict[str, InfusionPrimitive],
        intents: Dict[str, IntentPrimitive],
        talents: Dict[str, TalentPrimitive],
    ) -> None:
        self.stances = stances
        self.vectors = vectors
        self.infusions = infusions
        self.intents = intents
        self.talents = talents

    @property
    def total_combinations(self) -> int:
        return len(self.stances) * len(self.vectors) * len(self.infusions) * len(self.intents)

    @classmethod
    def load(cls, grammar_path: Optional[Path | str] = None) -> MartialGrammar:
        path = Path(grammar_path) if grammar_path else cls.DEFAULT_GRAMMAR_PATH
        if not path.is_file():
            raise FileNotFoundError(f"Martial grammar file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        stances = {
            s["id"]: StancePrimitive(
                id=s["id"],
                name=s["name"],
                name_jp=s["name_jp"],
                kinetic_stability=float(s["kinetic_stability"]),
                recovery_mod_frames=int(s["recovery_mod_frames"]),
                primary_substrates=list(s.get("primary_substrates", [])),
                description=s["description"],
            )
            for s in raw.get("stances", [])
        }

        vectors = {
            v["id"]: VectorPrimitive(
                id=v["id"],
                name=v["name"],
                name_jp=v["name_jp"],
                shape_envelope=v["shape_envelope"],
                base_reach_meters=float(v["base_reach_meters"]),
                penetration_multiplier=float(v["penetration_multiplier"]),
                kinetic_impulse_multiplier=float(v["kinetic_impulse_multiplier"]),
                description=v["description"],
            )
            for v in raw.get("vectors", [])
        }

        infusions = {
            i["id"]: InfusionPrimitive(
                id=i["id"],
                origin_carrier=i["origin_carrier"],
                thermal_tier=int(i["thermal_tier"]),
                base_density=float(i["base_density"]),
                polarity=i["polarity"],
                description=i["description"],
            )
            for i in raw.get("infusions", [])
        }

        intents = {
            it["id"]: IntentPrimitive(
                id=it["id"],
                name=it["name"],
                name_jp=it["name_jp"],
                trigger_rule=it["trigger_rule"],
                branch_operation=it["branch_operation"],
                complexity_weight=float(it["complexity_weight"]),
                description=it["description"],
            )
            for it in raw.get("intents", [])
        }

        talents = {
            t["id"]: TalentPrimitive(
                id=t["id"],
                name=t["name"],
                name_jp=t["name_jp"],
                martial_focus=t["martial_focus"],
                threshold_base=float(t["threshold_base"]),
                awakening_perk=t["awakening_perk"],
                description=t["description"],
            )
            for t in raw.get("talents", [])
        }

        return cls(stances, vectors, infusions, intents, talents)

    def get_stance(self, stance_id: str) -> StancePrimitive:
        if stance_id in self.stances:
            return self.stances[stance_id]
        prefixed = f"stance.{stance_id}"
        if prefixed in self.stances:
            return self.stances[prefixed]
        raise InvalidPrimitiveError(f"Unknown stance: {stance_id}")

    def get_vector(self, vector_id: str) -> VectorPrimitive:
        if vector_id in self.vectors:
            return self.vectors[vector_id]
        prefixed = f"vector.{vector_id}"
        if prefixed in self.vectors:
            return self.vectors[prefixed]
        raise InvalidPrimitiveError(f"Unknown vector: {vector_id}")

    def get_infusion(self, infusion_id: str) -> InfusionPrimitive:
        if infusion_id in self.infusions:
            return self.infusions[infusion_id]
        prefixed = f"infusion.{infusion_id}"
        if prefixed in self.infusions:
            return self.infusions[prefixed]
        raise InvalidPrimitiveError(f"Unknown infusion: {infusion_id}")

    def get_intent(self, intent_id: str) -> IntentPrimitive:
        if intent_id in self.intents:
            return self.intents[intent_id]
        prefixed = f"intent.{intent_id}"
        if prefixed in self.intents:
            return self.intents[prefixed]
        raise InvalidPrimitiveError(f"Unknown intent: {intent_id}")

    def get_talent(self, talent_id: str) -> TalentPrimitive:
        if talent_id in self.talents:
            return self.talents[talent_id]
        prefixed = f"talent.{talent_id}"
        if prefixed in self.talents:
            return self.talents[prefixed]
        raise InvalidPrimitiveError(f"Unknown talent: {talent_id}")


class TechniqueCompiler:
    """Synthesizes and validates 4-part compound martial techniques."""

    def __init__(self, grammar: Optional[MartialGrammar] = None) -> None:
        self.grammar = grammar or MartialGrammar.load()

    @staticmethod
    def calculate_stamina_cost(
        stance: StancePrimitive,
        mastery_discount: float = 0.0,
        base_cost: float = 20.0,
    ) -> float:
        """
        Will Stamina Cost:
        C_stamina = base_cost * (1 - mastery_discount) * stance_stability
        """
        clamped_discount = max(0.0, min(0.35, float(mastery_discount)))
        return round(base_cost * (1.0 - clamped_discount) * stance.kinetic_stability, 4)

    @staticmethod
    def calculate_emotional_erosion(
        infusion: InfusionPrimitive,
        intent: IntentPrimitive,
    ) -> float:
        """
        Emotional Erosion Ticks:
        E_erosion = infusion_density * thermal_tier * intent_complexity
        """
        return round(infusion.base_density * float(infusion.thermal_tier) * intent.complexity_weight, 4)

    @staticmethod
    def calculate_kinetic_backlash(
        stance: StancePrimitive,
        vector: VectorPrimitive,
        kinetic_impulse: Optional[float] = None,
    ) -> float:
        """
        Kinetic Backlash Damage:
        B_backlash = kinetic_impulse * (1 - kinetic_stability)
        """
        impulse = kinetic_impulse if kinetic_impulse is not None else round(vector.kinetic_impulse_multiplier * 10.0, 4)
        return round(impulse * (1.0 - stance.kinetic_stability), 4)

    @staticmethod
    def calculate_recovery_frames(
        stance: StancePrimitive,
        vector: VectorPrimitive,
        base_recovery_frames: int = 10,
        reach_factor: float = 1.0,
    ) -> int:
        """
        Recovery frames based on stance recovery mod and vector reach:
        F_recovery = max(1, int(round(base_recovery_frames + recovery_mod_frames + base_reach_meters * reach_factor)))
        """
        raw_frames = base_recovery_frames + stance.recovery_mod_frames + (vector.base_reach_meters * reach_factor)
        return max(1, int(round(raw_frames)))

    def validate_combination(
        self,
        stance: StancePrimitive,
        vector: VectorPrimitive,
        infusion: InfusionPrimitive,
        intent: IntentPrimitive,
        strict: bool = True,
    ) -> Tuple[bool, List[str]]:
        """
        Validates against physical and doctrinal contradictions in martial grammar:
        1. Immovable Stance vs Leaping / Aerial Vectors:
           Adamantine Bastion (locked brace) cannot execute high aerial launch (rising_geyser)
           or displaced coordinate folding (spatial_fold).
        2. Absolute Void Silence vs Thermal Detonation:
           Void Silence (tier 0 stillness) zeroing signatures cannot drive residue/memory ignition.
        3. Polar Resonance Contradiction:
           Strictly monophonic infusions cannot sustain polyphonic resonant counter (gaia_balance_recoil).
        4. Substrate Clash:
           Air-locked de-weighted mist step cannot deliver seismic ground shockwave (quake_stomp).
        """
        incompatibilities: List[str] = []

        # 1. Immovable / zero mobility restrictions
        if stance.id == "stance.adamantine_bastion":
            if vector.id in ("vector.rising_geyser", "vector.spatial_fold"):
                incompatibilities.append(
                    f"Locked brace stance '{stance.id}' cannot launch dynamic displacement vector '{vector.id}'"
                )

        # 2. Void Silence incompatibility with ignition/detonation intents
        if infusion.id == "infusion.void_silence":
            if intent.id in ("intent.residue_detonation", "intent.memory_burn_ignition"):
                incompatibilities.append(
                    f"Informational void infusion '{infusion.id}' directly contradicts explosive thermal intent '{intent.id}'"
                )

        # 3. Monophonic vs Polyphonic intent
        if infusion.polarity == "monophonic" and intent.id == "intent.gaia_balance_recoil":
            incompatibilities.append(
                f"Monophonic carrier '{infusion.id}' cannot resonate with polyphonic harmonic intent '{intent.id}'"
            )

        # 4. Air stance vs Ground seismic stomp
        if stance.id == "stance.mist_step" and vector.id in ("vector.quake_stomp", "vector.falling_meteor"):
            incompatibilities.append(
                f"De-weighted aerial stance '{stance.id}' cannot anchor crushing downward vector '{vector.id}'"
            )

        is_valid = len(incompatibilities) == 0
        if strict and not is_valid:
            raise IncompatibleCompoundError(f"Invalid primitive combination: {'; '.join(incompatibilities)}")
        return is_valid, incompatibilities

    @staticmethod
    def generate_compound_hash(stance_id: str, vector_id: str, infusion_id: str, intent_id: str) -> str:
        key = f"{stance_id}:{vector_id}:{infusion_id}:{intent_id}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()

    def compile(
        self,
        stance: str | StancePrimitive,
        vector: str | VectorPrimitive,
        infusion: str | InfusionPrimitive,
        intent: str | IntentPrimitive,
        character_id: str = "char.hero",
        custom_name: Optional[str] = None,
        mastery_discount: float = 0.0,
        base_cost: float = 20.0,
        kinetic_impulse: Optional[float] = None,
        base_recovery_frames: int = 10,
        reach_factor: float = 1.0,
        practice_status: str = "experimental",
        discovery_engine: str = "forge",
        lineage_donor_id: Optional[str] = None,
        created_turn: int = 1,
        validate: bool = True,
    ) -> CompiledTechnique:
        """Compile a 4-part martial compound technique with closed physics calculations."""
        # Resolve primitives
        s = stance if isinstance(stance, StancePrimitive) else self.grammar.get_stance(stance)
        v = vector if isinstance(vector, VectorPrimitive) else self.grammar.get_vector(vector)
        i = infusion if isinstance(infusion, InfusionPrimitive) else self.grammar.get_infusion(infusion)
        it = intent if isinstance(intent, IntentPrimitive) else self.grammar.get_intent(intent)

        # Validate
        if validate:
            self.validate_combination(s, v, i, it, strict=True)

        # Physics formulas
        stamina_cost = self.calculate_stamina_cost(s, mastery_discount, base_cost)
        erosion_ticks = self.calculate_emotional_erosion(i, it)
        backlash_damage = self.calculate_kinetic_backlash(s, v, kinetic_impulse)
        effective_backlash = max(0.0, backlash_damage)
        recovery_frames = self.calculate_recovery_frames(s, v, base_recovery_frames, reach_factor)

        # Compound hash and deterministic ID
        c_hash = self.generate_compound_hash(s.id, v.id, i.id, it.id)
        tech_id = f"tech_{character_id}_{c_hash[:12]}"

        # Name synthesis
        if custom_name:
            name = custom_name
        else:
            name = f"{s.name} · {v.name} [{it.name}]"

        return CompiledTechnique(
            technique_id=tech_id,
            character_id=character_id,
            name=name,
            stance_id=s.id,
            vector_id=v.id,
            infusion_id=i.id,
            intent_id=it.id,
            practice_status=practice_status,
            mastery_discount=round(mastery_discount, 4),
            stamina_cost=stamina_cost,
            erosion_ticks=erosion_ticks,
            backlash_damage=backlash_damage,
            effective_backlash=effective_backlash,
            recovery_frames=recovery_frames,
            times_executed=0,
            times_hit=0,
            discovery_engine=discovery_engine,
            lineage_donor_id=lineage_donor_id,
            created_turn=created_turn,
            compound_hash=c_hash,
        )
