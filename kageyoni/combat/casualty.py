"""Casualty Economics and Convalescent Triage System.

Implements:
- 3-tier casualty ledger: 60% Slight Wounded, 35% Hospital Severe, 5% KIA
  (driven by data/combat_rules.json casualty_economics).
- Anti-overflow hospital invariant:
  - Hospital has a bounded bed capacity (bed_capacity).
  - When severe wounded arrive and hospital capacity is exceeded, overflow wounded enter
    `Stagnant Convalescence`:
    - HP floor: 1 HP (prevents instant death upon overflow).
    - 2.0x ration consumption multiplier.
    - 0.02 daily tension penalty per convalescent patient / day.
    - Deployment lockout (cannot be deployed in battle while convalescent).
    - Starvation death rate: 10% (only if rations are exhausted, strictly NOT instant upon overflow).
- CasualtyLedger: records total casualties, slight wounded, hospital severe, stagnant convalescence, and KIA.
- Hospital: handles admission, capacity checks, and daily tick with ration consumption.
"""
from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Union

from .resolver import load_combat_rules


@dataclass
class CasualtyBreakdown:
    """Triage division of battle casualties into 3 canonical tiers."""
    slight_wounded: int
    hospital_severe: int
    kia: int
    total: int

    @classmethod
    def calculate(
        cls,
        total_casualties: int,
        rules_config: Optional[dict[str, Any]] = None,
    ) -> CasualtyBreakdown:
        """Divide total casualties into 60% slight, 35% severe, 5% KIA with exact sum conservation."""
        if total_casualties <= 0:
            return cls(slight_wounded=0, hospital_severe=0, kia=0, total=0)

        cfg = rules_config or load_combat_rules()
        econ_cfg = cfg.get("casualty_economics", {})
        dist_cfg = econ_cfg.get("distribution", {})

        slight_pct = float(dist_cfg.get("slight_wound_pct", 60))
        severe_pct = float(dist_cfg.get("hospital_severe_pct", 35))
        kia_pct = float(dist_cfg.get("kia_pct", 5))
        total_pct = slight_pct + severe_pct + kia_pct
        if total_pct <= 0:
            total_pct = 100.0

        # Exact conservation rounding
        slight = int(round(total_casualties * (slight_pct / total_pct)))
        severe = int(round(total_casualties * (severe_pct / total_pct)))
        kia = total_casualties - slight - severe

        # Ensure no negative counts due to rounding on small totals
        if kia < 0:
            severe += kia
            kia = 0
        if severe < 0:
            slight += severe
            severe = 0

        return cls(
            slight_wounded=slight,
            hospital_severe=severe,
            kia=kia,
            total=total_casualties,
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "slight_wounded": self.slight_wounded,
            "hospital_severe": self.hospital_severe,
            "kia": self.kia,
            "total": self.total,
        }


@dataclass
class ConvalescencePatient:
    """Represents a soldier or cohort in hospital care or stagnant convalescence."""
    patient_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Wounded Combatant"
    hp: int = 1
    max_hp: int = 100
    is_convalescent: bool = False
    in_hospital_bed: bool = True
    deployment_locked: bool = True
    ration_multiplier: float = 1.0
    daily_tension_penalty: float = 0.0
    days_in_care: int = 0
    days_to_recover: int = 5
    is_alive: bool = True

    def can_deploy(self) -> bool:
        """Evaluate if patient is cleared for active military deployment."""
        return (
            self.is_alive
            and not self.deployment_locked
            and not self.is_convalescent
            and self.hp > 1
        )


@dataclass
class AdmissionResult:
    """Detailed summary of a hospital admission transaction."""
    admitted_beds: int
    overflow_convalescent: int
    total_admitted: int
    patients: list[ConvalescencePatient] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted_beds": self.admitted_beds,
            "overflow_convalescent": self.overflow_convalescent,
            "total_admitted": self.total_admitted,
            "patient_count": len(self.patients),
            "message": self.message,
        }


@dataclass
class DailyTickResult:
    """Telemetry report produced by one daily cycle of hospital care and rations."""
    day: int
    rations_demanded: float
    rations_supplied: float
    rations_consumed: float
    ration_deficit: float
    tension_penalty_generated: float
    starvation_deaths: int
    recovered_discharges: int
    active_bed_occupancy: int
    active_convalescence: int
    dead_total: int


class Hospital:
    """Field hospital managing bed allocation, stagnant overflow, rations, and recovery."""

    def __init__(
        self,
        bed_capacity: int = 100,
        daily_ration_per_patient: float = 1.0,
        rules_config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.bed_capacity = max(1, bed_capacity)
        self.daily_ration_per_patient = daily_ration_per_patient
        self.rules_config = rules_config or load_combat_rules()

        econ_cfg = self.rules_config.get("casualty_economics", {})
        stag_cfg = econ_cfg.get("stagnant_convalescence", {})

        self.convalescent_ration_multiplier: float = float(
            stag_cfg.get("ration_consumption_multiplier", 2.0)
        )
        self.daily_tension_penalty: float = float(
            stag_cfg.get("daily_tension_penalty", 0.02)
        )
        self.starvation_death_rate_pct: float = float(
            stag_cfg.get("starvation_death_rate_pct", 10.0)
        )
        self.hp_floor: int = int(stag_cfg.get("hp_floor", 1))

        self.bed_patients: list[ConvalescencePatient] = []
        self.convalescent_patients: list[ConvalescencePatient] = []
        self.graveyard: list[ConvalescencePatient] = []
        self.discharged: list[ConvalescencePatient] = []

        self.total_tension_accumulated: float = 0.0
        self.current_day: int = 0

    @property
    def available_beds(self) -> int:
        return max(0, self.bed_capacity - len(self.bed_patients))

    @property
    def bed_occupancy(self) -> int:
        return len(self.bed_patients)

    @property
    def stagnant_convalescence_count(self) -> int:
        return len(self.convalescent_patients)

    @property
    def total_active_patients(self) -> int:
        return len(self.bed_patients) + len(self.convalescent_patients)

    def admit_patient(self, patient: ConvalescencePatient) -> bool:
        """Admit a single patient into a bed if available, or into Stagnant Convalescence if full."""
        if not patient.is_alive:
            self.graveyard.append(patient)
            return False

        if self.available_beds > 0:
            patient.in_hospital_bed = True
            patient.is_convalescent = False
            patient.deployment_locked = True
            patient.ration_multiplier = 1.0
            patient.daily_tension_penalty = 0.0
            patient.hp = max(self.hp_floor, patient.hp)
            self.bed_patients.append(patient)
            return True
        else:
            # Enforce Anti-Overflow Hospital Invariant
            # HP floor: 1 HP prevents instant death upon overflow
            patient.in_hospital_bed = False
            patient.is_convalescent = True
            patient.deployment_locked = True
            patient.hp = max(self.hp_floor, patient.hp)
            patient.ration_multiplier = self.convalescent_ration_multiplier
            patient.daily_tension_penalty = self.daily_tension_penalty
            self.convalescent_patients.append(patient)
            return False

    def admit_severe(
        self,
        count: int,
        names: Optional[list[str]] = None,
    ) -> AdmissionResult:
        """Admit a cohort of severe casualties.
        
        Beds receive patients first. Any overflow strictly enters Stagnant Convalescence
        with 1 HP floor, deployment locked, 2.0x ration consumption, and 0.02 tension penalty.
        Instant death is completely barred upon overflow.
        """
        if count <= 0:
            return AdmissionResult(
                admitted_beds=0,
                overflow_convalescent=0,
                total_admitted=0,
                patients=[],
                message="No casualties to admit.",
            )

        new_patients: list[ConvalescencePatient] = []
        admitted_beds = 0
        overflow_convalescent = 0

        for i in range(count):
            name = names[i] if names and i < len(names) else f"Severe Casualty #{len(self.bed_patients) + len(self.convalescent_patients) + 1}"
            patient = ConvalescencePatient(
                name=name,
                hp=self.hp_floor,
                max_hp=100,
                days_to_recover=5,
            )
            was_bed = self.admit_patient(patient)
            if was_bed:
                admitted_beds += 1
            else:
                overflow_convalescent += 1
            new_patients.append(patient)

        msg = (
            f"Admitted {count} severe casualties: {admitted_beds} assigned to hospital beds, "
            f"{overflow_convalescent} placed into Stagnant Convalescence."
        )
        return AdmissionResult(
            admitted_beds=admitted_beds,
            overflow_convalescent=overflow_convalescent,
            total_admitted=count,
            patients=new_patients,
            message=msg,
        )

    def calculate_daily_rations_needed(self) -> float:
        """Calculate total ration consumption for all admitted patients.
        
        Normal bed patients consume 1.0x baseline.
        Stagnant convalescence patients consume 2.0x baseline rations.
        """
        bed_demands = len(self.bed_patients) * self.daily_ration_per_patient * 1.0
        convalescent_demands = (
            len(self.convalescent_patients)
            * self.daily_ration_per_patient
            * self.convalescent_ration_multiplier
        )
        return round(bed_demands + convalescent_demands, 4)

    def triage_rebalance(self) -> int:
        """Promote stagnant convalescent patients into free hospital beds if available."""
        promoted = 0
        while self.available_beds > 0 and self.convalescent_patients:
            patient = self.convalescent_patients.pop(0)
            patient.in_hospital_bed = True
            patient.is_convalescent = False
            patient.ration_multiplier = 1.0
            patient.daily_tension_penalty = 0.0
            self.bed_patients.append(patient)
            promoted += 1
        return promoted

    def daily_tick(
        self,
        available_rations: float,
        rng: Optional[random.Random] = None,
    ) -> DailyTickResult:
        """Execute one daily hospital cycle.
        
        Consumes rations, advances recovery, checks starvation on ration exhaustion,
        and generates daily tension penalty from stagnant convalescence.
        """
        self.current_day += 1
        r = rng or random.Random()

        # Step 1: Promote convalescents if beds freed up
        self.triage_rebalance()

        # Step 2: Demand calculation
        rations_demanded = self.calculate_daily_rations_needed()
        rations_consumed = min(available_rations, rations_demanded)
        deficit = max(0.0, rations_demanded - available_rations)

        # Step 3: Tension penalty calculation from stagnant convalescence
        # 0.02 daily tension penalty per convalescent patient
        daily_tension = len(self.convalescent_patients) * self.daily_tension_penalty
        self.total_tension_accumulated += daily_tension

        # Step 4: Starvation check (ONLY if rations are exhausted/in deficit, NEVER upon overflow)
        starvation_deaths = 0
        if deficit > 0 and self.convalescent_patients:
            # If rations are completely exhausted, 10% base starvation death rate applies
            is_complete_exhaustion = (available_rations <= 0)
            starve_rate = (self.starvation_death_rate_pct / 100.0) if is_complete_exhaustion else (
                (self.starvation_death_rate_pct / 100.0) * (deficit / max(0.0001, rations_demanded))
            )

            surviving_convalescents: list[ConvalescencePatient] = []
            for patient in self.convalescent_patients:
                roll = r.random()
                if roll < starve_rate:
                    patient.is_alive = False
                    patient.hp = 0
                    patient.deployment_locked = True
                    self.graveyard.append(patient)
                    starvation_deaths += 1
                else:
                    surviving_convalescents.append(patient)
            self.convalescent_patients = surviving_convalescents

        # Step 5: Healing & Recovery for bed patients
        recovered_discharges = 0
        still_in_bed: list[ConvalescencePatient] = []
        for patient in self.bed_patients:
            if not patient.is_alive:
                self.graveyard.append(patient)
                continue

            patient.days_in_care += 1
            # Heal HP gradually if fed
            if deficit == 0:
                patient.hp = min(patient.max_hp, patient.hp + 20)

            if patient.days_in_care >= patient.days_to_recover and patient.hp >= 80:
                # Discharged back to active duty
                patient.is_convalescent = False
                patient.in_hospital_bed = False
                patient.deployment_locked = False
                self.discharged.append(patient)
                recovered_discharges += 1
            else:
                still_in_bed.append(patient)

        self.bed_patients = still_in_bed

        # Step 6: Post-discharge rebalance: pull remaining convalescents into newly opened beds
        self.triage_rebalance()

        return DailyTickResult(
            day=self.current_day,
            rations_demanded=rations_demanded,
            rations_supplied=available_rations,
            rations_consumed=rations_consumed,
            ration_deficit=deficit,
            tension_penalty_generated=round(daily_tension, 4),
            starvation_deaths=starvation_deaths,
            recovered_discharges=recovered_discharges,
            active_bed_occupancy=len(self.bed_patients),
            active_convalescence=len(self.convalescent_patients),
            dead_total=len(self.graveyard),
        )


class CasualtyLedger:
    """Historical and strategic ledger recording all military casualties across tiers."""

    def __init__(self, rules_config: Optional[dict[str, Any]] = None) -> None:
        self.rules_config = rules_config or load_combat_rules()
        self.total_casualties: int = 0
        self.slight_wounded: int = 0
        self.hospital_severe: int = 0
        self.stagnant_convalescence: int = 0
        self.kia: int = 0

    def record_casualties(
        self,
        total_casualties: int,
        hospital: Optional[Hospital] = None,
    ) -> CasualtyBreakdown:
        """Divide total casualties into tiers, log them, and optionally admit severe into hospital."""
        breakdown = CasualtyBreakdown.calculate(total_casualties, self.rules_config)
        self.record_breakdown(breakdown, hospital=hospital)
        return breakdown

    def record_breakdown(
        self,
        breakdown: CasualtyBreakdown,
        hospital: Optional[Hospital] = None,
    ) -> Optional[AdmissionResult]:
        """Record an explicit casualty breakdown into ledger tallies."""
        self.total_casualties += breakdown.total
        self.slight_wounded += breakdown.slight_wounded
        self.kia += breakdown.kia

        admission_result: Optional[AdmissionResult] = None
        if hospital is not None:
            admission_result = hospital.admit_severe(breakdown.hospital_severe)
            self.hospital_severe += admission_result.admitted_beds
            self.stagnant_convalescence += admission_result.overflow_convalescent
        else:
            self.hospital_severe += breakdown.hospital_severe

        return admission_result

    def sync_with_hospital(self, hospital: Hospital) -> None:
        """Synchronize active ledger counters with live hospital state."""
        self.hospital_severe = hospital.bed_occupancy
        self.stagnant_convalescence = hospital.stagnant_convalescence_count
        self.kia += len(hospital.graveyard)

    def summary(self) -> dict[str, Any]:
        """Return a structured summary of the casualty ledger."""
        return {
            "total_casualties": self.total_casualties,
            "slight_wounded": self.slight_wounded,
            "hospital_severe": self.hospital_severe,
            "stagnant_convalescence": self.stagnant_convalescence,
            "kia": self.kia,
        }
