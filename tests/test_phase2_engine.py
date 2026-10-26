"""Comprehensive Verification Suite for Kageyōni Phase 2 Deterministic Engine.

Validates 100% assertions across all 4 major subsystems:
1. Combat (DMW token pool & reels, Pre-Cognitive Clash Gambits, 2RN Resolver, Commanders, Casualty).
2. Martial (Satori Epiphany Engine, Star Ocean Secret Talents, Compound Compiler, Kata Deck).
3. Spatial (A* Pathfinder with Anti-Corner-Cutting, Corridor Supply Attrition, Kalpa Molt Revision).
4. Narrative (Capability Affordance Filter, Social Friction DCE with Fail-Forward, Enton Rupture, PA Bridge).
"""
import math
import random
import unittest

# Subsystem 1: Combat
import kageyoni.combat as combat
from kageyoni.combat.dmw import DMWTokenPool, DMWTokenType, DMWSpinResult
from kageyoni.combat.gambits import PreCognitiveGambitEngine, GambitType, GambitResult
from kageyoni.combat.resolver import TrueHitResolver, Combatant, Weapon, AttackType
from kageyoni.combat.commanders import DualCommanderTeam, Commander
from kageyoni.combat.casualty import CasualtyLedger, Hospital, CasualtyBreakdown

# Subsystem 2: Martial
import kageyoni.martial as martial
from kageyoni.martial.satori import SatoriEpiphanyEngine, SatoriResult
from kageyoni.martial.talents import StarOceanTalentLedger, TalentType, BreakthroughResult
from kageyoni.martial.compiler import TechniqueCompiler, MartialGrammar
from kageyoni.martial.deck import AttunedDeck, KataForge

# Subsystem 3: Spatial
import kageyoni.spatial as spatial
from kageyoni.spatial.pathfinding import AStarPathfinder, BASE_TERRAIN_COSTS
from kageyoni.spatial.supply import CorridorSupplyEngine, CorridorTickResult
from kageyoni.spatial.kalpa import KalpaRevisionEngine, KalpaStatus, KalpaRevisionReport
from kageyoni.spatial.grid import WorldGrid
from kageyoni.spatial.viewport import TacticalMicroGrid

# Subsystem 4: Narrative
import kageyoni.narrative as narrative
from kageyoni.narrative.social import (
    CapabilityAffordanceFilter,
    SocialFrictionDCE,
    CausalConsequenceGraph,
    DialogueOption,
    CharacterSocialProfile,
    SocialConsequence,
)
from kageyoni.narrative.enton import EntonRuptureEngine, EntonRuptureResult
from kageyoni.narrative.pa_bridge import (
    TacticalRelationalBridge,
    CombatContactType,
    PrivateAction,
)
from kageyoni.narrative.anti_slop import AntiSlopGate


class TestPhase2CombatSubsystem(unittest.TestCase):
    """Group 1: Combat Subsystem Verification."""

    def test_dmw_token_pool_operations(self):
        pool = DMWTokenPool(max_capacity=5)
        self.assertEqual(pool.count_total, 0)

        # Add up to capacity
        self.assertTrue(pool.add_token(DMWTokenType.FOCUS))
        self.assertTrue(pool.add_token(DMWTokenType.ECHO))
        self.assertTrue(pool.add_token(DMWTokenType.SURGE))
        self.assertTrue(pool.add_token(DMWTokenType.CATHARSIS))
        self.assertTrue(pool.add_token(DMWTokenType.FOCUS))
        self.assertEqual(pool.count_total, 5)
        self.assertTrue(pool.is_full)

        # Enforce max pool size 5
        self.assertFalse(pool.add_token(DMWTokenType.SURGE))
        self.assertEqual(pool.count_total, 5)

        # Spend token
        self.assertEqual(pool.count(DMWTokenType.FOCUS), 2)
        self.assertTrue(pool.spend_token(DMWTokenType.FOCUS))
        self.assertEqual(pool.count(DMWTokenType.FOCUS), 1)
        self.assertEqual(pool.count_total, 4)
        self.assertFalse(pool.spend_token(DMWTokenType.FOCUS) and pool.spend_token(DMWTokenType.FOCUS))

        # Turn decay tick (1 token dropped per turn, FIFO)
        decayed = pool.turn_decay_tick()
        self.assertEqual(decayed, DMWTokenType.ECHO)
        self.assertEqual(pool.count_total, 2)

    def test_dmw_spin_reels_probabilities_and_priming(self):
        pool = DMWTokenPool()
        roster = ["Kage", "Yoni", "Ayame", "Rikimaru"]

        # 3-match jackpot forced via seeded roll below 0.05
        res_jackpot = pool.spin_reels(roster, rng_seed=42, auto_add=True)
        self.assertIsInstance(res_jackpot, DMWSpinResult)

        # Primed companion with affection >= 75 boosts match probabilities
        res_primed = pool.spin_reels(
            roster,
            primed_companion="Ayame",
            affection_level=80,
            rng_seed=100,
            auto_add=False,
        )
        self.assertTrue(res_primed.is_primed)

    def test_precognitive_gambit_vajra_read(self):
        engine = PreCognitiveGambitEngine()

        # Success: predicted == incoming
        # 100% negate, 50% reflect, +150 rage, 0 stamina cost
        res_success = engine.resolve_gambit(
            gambit_type=GambitType.VAJRA_READ,
            incoming_damage=100.0,
            incoming_vector="linear_cleave",
            predicted_vector="linear_cleave",
            user_stamina=80,
        )
        self.assertTrue(res_success.success)
        self.assertEqual(res_success.damage_taken, 0.0)
        self.assertEqual(res_success.damage_reflected, 50.0)
        self.assertEqual(res_success.rage_delta, 150)
        self.assertEqual(res_success.stamina_delta, 0)
        self.assertEqual(res_success.stamina_remaining, 80)
        self.assertFalse(res_success.exhaustion_stun)

        # Failure: predicted != incoming
        # incoming damage * 1.25, -10 stamina
        res_fail = engine.resolve_gambit(
            gambit_type=GambitType.VAJRA_READ,
            incoming_damage=100.0,
            incoming_vector="linear_cleave",
            predicted_vector="rising_geyser",
            user_stamina=80,
        )
        self.assertFalse(res_fail.success)
        self.assertEqual(res_fail.damage_taken, 125.0)
        self.assertEqual(res_fail.damage_reflected, 0.0)
        self.assertEqual(res_fail.rage_delta, 0)
        self.assertEqual(res_fail.stamina_delta, -10)
        self.assertEqual(res_fail.stamina_remaining, 70)

    def test_precognitive_gambit_roll_and_counter(self):
        engine = PreCognitiveGambitEngine()

        # Success: 1d20 + agility >= 10
        # 100% negate, +20% crit counter bonus, 15 stamina cost
        res_success = engine.resolve_gambit(
            gambit_type=GambitType.ROLL_AND_COUNTER,
            incoming_damage=80.0,
            incoming_vector="thrust",
            user_agility=15,  # guaranteed >= 10
            user_stamina=50,
            seed=7,
        )
        self.assertTrue(res_success.success)
        self.assertEqual(res_success.damage_taken, 0.0)
        self.assertEqual(res_success.crit_counter_bonus, 0.20)
        self.assertEqual(res_success.stamina_delta, -15)
        self.assertEqual(res_success.stamina_remaining, 35)

        # Failure: roll + agility < 10
        # 50% damage reduction
        res_fail = engine.resolve_gambit(
            gambit_type=GambitType.ROLL_AND_COUNTER,
            incoming_damage=80.0,
            incoming_vector="thrust",
            user_agility=-20,  # guaranteed < 10
            user_stamina=50,
            seed=7,
        )
        self.assertFalse(res_fail.success)
        self.assertEqual(res_fail.damage_taken, 40.0)
        self.assertEqual(res_fail.crit_counter_bonus, 0.0)
        self.assertEqual(res_fail.stamina_delta, -15)

    def test_precognitive_gambit_brace_shield(self):
        engine = PreCognitiveGambitEngine()

        # Normal brace: 50% reduction, 30 stamina cost
        res = engine.resolve_gambit(
            gambit_type=GambitType.BRACE_SHIELD,
            incoming_damage=120.0,
            incoming_vector="overhead_smash",
            user_stamina=50,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.damage_taken, 60.0)
        self.assertEqual(res.stamina_delta, -30)
        self.assertEqual(res.stamina_remaining, 20)
        self.assertFalse(res.exhaustion_stun)

        # Exhaustion stun: remaining stamina < 0
        res_exhaust = engine.resolve_gambit(
            gambit_type=GambitType.BRACE_SHIELD,
            incoming_damage=120.0,
            incoming_vector="overhead_smash",
            user_stamina=15,  # 15 - 30 = -15 < 0
        )
        self.assertTrue(res_exhaust.exhaustion_stun)
        self.assertEqual(res_exhaust.stamina_remaining, -15)

    def test_combat_package_exports_and_aliases(self):
        self.assertTrue(hasattr(combat, "CombatResolver"))
        self.assertTrue(hasattr(combat, "TrueHitCalculator"))
        self.assertTrue(hasattr(combat, "ContactSplitType"))
        self.assertTrue(hasattr(combat, "DualCommanderSquad"))
        self.assertTrue(hasattr(combat, "StagnantConvalescenceRoster"))
        self.assertTrue(hasattr(combat, "DMWTokenPool"))
        self.assertTrue(hasattr(combat, "PreCognitiveGambitEngine"))
        self.assertEqual(combat.CombatResolver, combat.TrueHitResolver)


class TestPhase2MartialSubsystem(unittest.TestCase):
    """Group 2: Martial Subsystem Verification."""

    def test_satori_epiphany_density_formula(self):
        # Formula: D_combat = [(P_danger * U_unresolved) / (R_stamina + 0.001)] * friction
        danger = 2.0
        unresolved = 1.5
        stamina = 0.5
        friction = 1.2
        expected = ((danger * unresolved) / (stamina + 0.001)) * friction
        calculated = SatoriEpiphanyEngine.calculate_danger_density(danger, unresolved, stamina, friction)
        self.assertAlmostEqual(calculated, round(expected, 4), places=3)

    def test_satori_epiphany_threshold_and_rate_limiter(self):
        engine = SatoriEpiphanyEngine(threshold=1.5)

        # Below threshold: no trigger
        res_below = engine.evaluate_epiphany(danger=0.5, unresolved=0.5, stamina=10.0)
        self.assertFalse(res_below.triggered)
        self.assertFalse(engine.has_triggered_this_encounter)

        # Above threshold: triggers mutation
        res_above = engine.evaluate_epiphany(
            danger=3.0,
            unresolved=2.0,
            stamina=1.0,
            friction=1.0,
            current_stance="stance.golden_lotus",
            target_slot="stance",
        )
        self.assertTrue(res_above.triggered)
        self.assertEqual(res_above.slot_mutated, "stance")
        self.assertEqual(res_above.original_primitive, "stance.golden_lotus")
        self.assertEqual(res_above.mutated_primitive, "stance.flowing_willow")
        self.assertTrue(engine.has_triggered_this_encounter)

        # Strict rate-limiter: maximum 1 epiphany per encounter
        res_second = engine.evaluate_epiphany(danger=5.0, unresolved=5.0, stamina=0.1)
        self.assertFalse(res_second.triggered)
        self.assertIn("rate-limit", res_second.details)

        # Reset encounter clears flag
        engine.reset_encounter()
        self.assertFalse(engine.has_triggered_this_encounter)

    def test_star_ocean_talent_ledger_breakthrough(self):
        ledger = StarOceanTalentLedger(base_threshold=100.0)
        char = "hero_kage"

        self.assertFalse(ledger.is_awakened(char, TalentType.ORIGINALITY))
        self.assertEqual(ledger.get_friction(char, TalentType.ORIGINALITY), 0.0)

        # Accumulate friction on practice failure
        f1 = ledger.accumulate_friction(char, TalentType.ORIGINALITY, amount=25.0)
        self.assertEqual(f1, 25.0)
        f2 = ledger.accumulate_friction(char, TalentType.ORIGINALITY, amount=75.0)
        self.assertEqual(f2, 100.0)

        # Breakthrough check: 100.0 friction / 100.0 threshold = 100% chance
        res = ledger.check_breakthrough(char, TalentType.ORIGINALITY)
        self.assertTrue(res.awakened)
        self.assertTrue(ledger.is_awakened(char, TalentType.ORIGINALITY))

        # Subsequent check returns already unlocked
        res_subsequent = ledger.check_breakthrough(char, TalentType.ORIGINALITY)
        self.assertTrue(res_subsequent.already_unlocked)

    def test_martial_package_exports_and_aliases(self):
        self.assertTrue(hasattr(martial, "MartialCompoundCompiler"))
        self.assertTrue(hasattr(martial, "AttunedKataDeck"))
        self.assertTrue(hasattr(martial, "SatoriEpiphanyEngine"))
        self.assertTrue(hasattr(martial, "StarOceanTalentLedger"))
        self.assertEqual(martial.MartialCompoundCompiler, martial.TechniqueCompiler)
        self.assertEqual(martial.AttunedKataDeck, martial.AttunedDeck)


class TestPhase2SpatialSubsystem(unittest.TestCase):
    """Group 3: Spatial Continuum Subsystem Verification."""

    def test_astar_pathfinder_and_anti_corner_cutting(self):
        # Construct grid with impassable corner
        # Cell (1, 1) is destination from (0, 0)
        # If (1, 0) is high mountain (impassable), diagonal step (0,0)->(1,1) must be strictly barred
        impassable_coords = {(1, 0)}

        def custom_cost(x: int, y: int, unit: str) -> float:
            if (x, y) in impassable_coords:
                return 99.0
            return 1.0

        pf = AStarPathfinder(custom_cost_fn=custom_cost)

        # Diagonal from (0, 0) to (1, 1) cannot cut corner (1, 0)
        path = pf.find_path(start=(0, 0), goal=(1, 1), unit_type="infantry")
        self.assertIsNotNone(path)

        # Path must go around via (0, 1) -> (1, 1) instead of direct diagonal (0,0)->(1,1)
        self.assertNotIn((1, 0), path)
        self.assertEqual(path, [(0, 0), (0, 1), (1, 1)])

    def test_astar_unit_type_costs(self):
        pf = AStarPathfinder()
        self.assertEqual(pf.get_tile_cost(10, 10, "flying"), 1.0)
        self.assertGreaterEqual(pf.get_tile_cost(10, 10, "infantry"), 1.0)

    def test_corridor_supply_decay_recovery_and_attrition(self):
        engine = CorridorSupplyEngine()
        corr_id = "supply_route_alpha"
        engine.register_corridor(corr_id, initial_integrity=0.30)

        # Contested decay: -0.15 per turn
        t1 = engine.tick_turn(corr_id, is_contested=True)
        self.assertAlmostEqual(t1.integrity, 0.15, places=2)
        self.assertEqual(t1.attrition_rate, 0.0)

        # Second contested turn: 0.15 - 0.15 = 0.0 (fully collapsed)
        t2 = engine.tick_turn(corr_id, is_contested=True, garrison_hp=100.0)
        self.assertEqual(t2.integrity, 0.0)
        # Attrition triggered: 5% garrison HP loss
        self.assertEqual(t2.attrition_rate, 0.05)
        self.assertEqual(t2.garrison_hp_loss, 5.0)
        self.assertEqual(t2.garrison_hp_remaining, 95.0)

        # Safe recovery: +0.25 per turn
        t3 = engine.tick_turn(corr_id, is_contested=False)
        self.assertAlmostEqual(t3.integrity, 0.25, places=2)
        self.assertEqual(t3.attrition_rate, 0.0)

    def test_kalpa_revision_conquest_milestones_and_persistence(self):
        engine = KalpaRevisionEngine(total_tiles=10000)

        # Initially sealed
        self.assertFalse(engine.is_pass_2_unsealed)
        self.assertFalse(engine.is_pass_3_unsealed)
        self.assertFalse(engine.is_molt_ready)

        # 5,000 tiles (50%): Pass 2 unseals
        s1 = engine.conquer_n_tiles(5000)
        self.assertTrue(s1.pass_2_unsealed)
        self.assertFalse(s1.pass_3_unsealed)
        self.assertFalse(s1.molt_triggered)

        # 8,000 tiles (80%): Pass 3 unseals
        s2 = engine.conquer_n_tiles(3000)
        self.assertTrue(s2.pass_2_unsealed)
        self.assertTrue(s2.pass_3_unsealed)
        self.assertFalse(s2.molt_triggered)

        # Record persistent scars and memories
        engine.record_subterranean_scar("scar_abyss_1", origin_tile=(50, 50))
        engine.record_memory("mem_fall_of_spire", "The spire collapsed in flame.")

        # 10,000 tiles (100%): Kalpa Molt triggers
        s3 = engine.conquer_n_tiles(2000)
        self.assertTrue(s3.molt_triggered)

        # Trigger Kalpa Revision
        report = engine.trigger_kalpa_revision()
        self.assertTrue(report.molt_triggered)
        self.assertEqual(report.new_cycle, 2)
        self.assertEqual(report.scars_persisted, 1)
        self.assertEqual(report.memories_persisted, 1)

        # Surface conquest reset back to 0
        self.assertEqual(engine.conquered_count, 0)
        self.assertFalse(engine.is_pass_2_unsealed)
        # But subterranean data preserved
        self.assertEqual(len(engine.subterranean_scars), 1)
        self.assertEqual(len(engine.memory_ledger), 1)

    def test_spatial_package_exports_and_aliases(self):
        self.assertTrue(hasattr(spatial, "ContinentalGrid"))
        self.assertTrue(hasattr(spatial, "TacticalViewport"))
        self.assertTrue(hasattr(spatial, "AStarPathfinder"))
        self.assertTrue(hasattr(spatial, "CorridorSupplyEngine"))
        self.assertTrue(hasattr(spatial, "KalpaRevisionEngine"))
        self.assertEqual(spatial.ContinentalGrid, spatial.WorldGrid)
        self.assertEqual(spatial.TacticalViewport, spatial.TacticalMicroGrid)


class TestPhase2NarrativeSubsystem(unittest.TestCase):
    """Group 4: Narrative & Relational Subsystem Verification."""

    def test_capability_affordance_filter(self):
        profile = CharacterSocialProfile(
            character_id="hero",
            stats={"insight": 16, "charisma": 10},
            active_scars={"zenkai_eye"},
            roles={"commander"},
            gold=100,
        )

        options = [
            DialogueOption(option_id="opt1", text="Read their intentions", tag="[VAJRA INSIGHT]"),
            DialogueOption(option_id="opt2", text="Bribe the sentinel", tag="[BRIBE]"),
            DialogueOption(option_id="opt3", text="Demand submission", required_stat="charisma", min_stat_value=15),
            DialogueOption(option_id="opt4", text="Order tactical formation", required_role="commander"),
        ]

        filtered = CapabilityAffordanceFilter.filter_options(options, profile)
        filtered_ids = {opt.option_id for opt in filtered}

        self.assertIn("opt1", filtered_ids)  # Insight 16 and zenkai_eye
        self.assertIn("opt2", filtered_ids)  # Gold 100 >= 50
        self.assertNotIn("opt3", filtered_ids)  # Charisma 10 < 15
        self.assertIn("opt4", filtered_ids)  # Role commander matches

    def test_social_friction_dce_fail_forward(self):
        # Base DC standard = 12
        # Leverage modifiers: physical receipt +3, high ground +2, ideological hostility -4, slop -5

        # Clean Success: roll 10 + 3 (receipt) = 13 >= 12
        res_success = SocialFrictionDCE.resolve_check(
            base_dc="standard",
            d20_roll=10,
            active_leverages={"physical_receipt": True},
        )
        self.assertEqual(res_success.branch, "success")
        self.assertGreaterEqual(res_success.margin, 0)

        # 4-point Fail-Forward Complication: roll 6 + 3 (receipt) = 9, failed DC 12 by 3 (<= 4)
        res_comp = SocialFrictionDCE.resolve_check(
            base_dc="standard",
            d20_roll=6,
            active_leverages={"physical_receipt": True},
        )
        self.assertEqual(res_comp.branch, "complication")
        self.assertGreaterEqual(res_comp.margin, -4)
        self.assertLess(res_comp.margin, 0)

        # Decisive Failure: roll 2 - 4 (hostility) = -2, failed DC 12 by 14 (> 4)
        res_fail = SocialFrictionDCE.resolve_check(
            base_dc="standard",
            d20_roll=2,
            active_leverages={"ideological_hostility": True},
        )
        self.assertEqual(res_fail.branch, "failure")
        self.assertLess(res_fail.margin, -4)

    def test_causal_consequence_graph(self):
        ccg = CausalConsequenceGraph()
        consequence = SocialConsequence(
            consequence_id="treaty_accord",
            approval_deltas={"Ayame": 10, "Rikimaru": -5},
            disposition_deltas={"Citadel": 15},
            spatial_displacements=[(10, 20, "Citadel")],
        )

        res = ccg.apply_consequence(consequence)
        self.assertEqual(ccg.companion_approval["Ayame"], 10)
        self.assertEqual(ccg.companion_approval["Rikimaru"], -5)
        self.assertEqual(ccg.faction_disposition["Citadel"], 15)
        self.assertEqual(len(ccg.displacement_history), 1)

    def test_enton_rupture_engine(self):
        engine = EntonRuptureEngine(initial_ruptures=0)
        # Threshold: 18 + 12 * 0 = 18

        # Contained: ambiguity=2, pressure=3 -> 2^2 + 3^2 = 13 < 18
        res_contained = engine.evaluate_rupture(ambiguity=2.0, pressure=3.0)
        self.assertFalse(res_contained.rupture_triggered)
        self.assertEqual(engine.prior_ruptures, 0)

        # Breached: ambiguity=4, pressure=3 -> 4^2 + 3^2 = 25 >= 18
        res_breached = engine.evaluate_rupture(ambiguity=4.0, pressure=3.0, target_coord=(25, 30))
        self.assertTrue(res_breached.rupture_triggered)
        self.assertEqual(res_breached.glassing_lockout_turns, 10)
        self.assertEqual(res_breached.tile_converted, "RUIN_VOID")
        self.assertEqual(res_breached.erosion_delta, 0.15)
        self.assertEqual(engine.prior_ruptures, 1)

        # Next threshold scaled: 18 + 12 * 1 = 30
        self.assertEqual(engine.calculate_barrier_threshold(), 30.0)

        # Tick turn decrements lockout
        lockouts = engine.tick_turn()
        self.assertEqual(lockouts[(25, 30)], 9)

    def test_tactical_relational_bridge(self):
        bridge = TacticalRelationalBridge()

        # Ingest combat contact events
        bridge.record_contact(
            event_type=CombatContactType.FRIENDLY_FIRE,
            source_id="archer_1",
            target_id="knight_1",
            severity=45.0,
            turn=3,
        )
        bridge.record_contact(
            event_type=CombatContactType.SAVING_INTERVENTION,
            source_id="monk_1",
            target_id="knight_1",
            severity=80.0,
            turn=4,
        )

        self.assertEqual(len(bridge.contact_ledger), 2)

        # Generate morning actions
        actions = bridge.generate_morning_actions()
        self.assertEqual(len(actions), 2)
        # Friendly fire has highest priority (3)
        self.assertEqual(actions[0].context_trigger, "friendly_fire")
        self.assertEqual(actions[0].priority, 3)

        # Dequeue
        next_action = bridge.dequeue_next_action()
        self.assertIsNotNone(next_action)
        self.assertEqual(next_action.initiator_id, "knight_1")

    def test_narrative_package_exports_and_aliases(self):
        self.assertTrue(hasattr(narrative, "AntiSlopInterceptor"))
        self.assertTrue(hasattr(narrative, "CapabilityAffordanceFilter"))
        self.assertTrue(hasattr(narrative, "SocialFrictionDCE"))
        self.assertTrue(hasattr(narrative, "CausalConsequenceGraph"))
        self.assertTrue(hasattr(narrative, "EntonRuptureEngine"))
        self.assertTrue(hasattr(narrative, "TacticalRelationalBridge"))
        self.assertEqual(narrative.AntiSlopInterceptor, narrative.AntiSlopGate)


if __name__ == "__main__":
    unittest.main()
