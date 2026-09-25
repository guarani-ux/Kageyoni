"""
Benchmark Runner: LEVI SIM BENCHMARK — THE COLLAPSING CITY.

Executes:
- Condition A: Levi Sim
- Condition B: Generic Kageyoni Agent (Control)
- Condition C: Ablated Levi Sim (Control)

Phases 1 through 9 on Scenario 1, followed by Phase 10 Learning & Scenario 2 Transfer.
Outputs comprehensive multi-dimensional scorecard and saves JSON telemetry report.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.collapsing_city.scenario import init_collapsing_city_world
from benchmarks.collapsing_city.agents import LeviSimAgent, GenericAgent, AblatedAgent
from benchmarks.collapsing_city.scoring import BenchmarkScores
from benchmarks.collapsing_city.evaluator import CollapsingCityEvaluator
from benchmarks.collapsing_city.transfer_scenario import metabolize_scenario_1_history, run_scenario_2_transfer


def run_benchmark_for_condition(condition: str, base_db_dir: Path) -> BenchmarkScores:
    db_path = base_db_dir / f"world_{condition}.sqlite"
    char_id = "levi-sim" if condition == "levi_sim" else ("generic-agent" if condition == "generic_agent" else "ablated-sim")
    engine = init_collapsing_city_world(db_path, character_id=char_id)
    scores = BenchmarkScores(agent_id=f"agent-{condition}", condition=condition)

    try:
        if condition == "levi_sim":
            agent = LeviSimAgent(engine, character_id=char_id)
        elif condition == "generic_agent":
            agent = GenericAgent(engine, character_id=char_id)
        else:
            agent = AblatedAgent(engine, character_id=char_id)


        # PHASE 1 — REPRESENTATION
        agent.decide_phase_1_representation(scores)

        # PHASE 2 — FALSE AFFORDANCE (Trap 2 Target)
        agent.decide_phase_2_false_affordance(scores)

        # PHASE 3 — REAL BINARY (Trap 4 Target)
        agent.decide_phase_3_real_binary(scores)

        # PHASE 4 — CAPABILITY CONSTRUCTION
        agent.decide_phase_4_capability_construction(scores)

        # PHASE 5 — CONSTRAINT ECONOMICS (Trap 3 Target)
        agent.decide_phase_5_constraint_economics(scores)

        # PHASE 6 — AGENCY PRESERVATION
        agent.decide_phase_6_agency(scores)

        # PHASE 7 — CONTRADICTION & SUNK COST
        agent.decide_phase_7_contradiction(scores)

        # PHASE 8 — TIME PRESSURE & BOUNDED EXECUTION (Trap 1 Target)
        agent.decide_phase_8_time_pressure(scores)

        # INDEPENDENT EVALUATOR DERIVES ALL 14 DIMENSIONS & TRAP METRICS (Phase 9)
        evaluator = CollapsingCityEvaluator(engine)
        evaluated_scores = evaluator.evaluate(
            agent_id=f"agent-{condition}",
            condition=condition,
            event_hashes=scores.event_hashes,
        )
        evaluated_scores.observations = list(scores.observations)

        # PHASE 10 — TRANSFER SCENARIO 2
        evaluated_scores.structural_transfer = run_scenario_2_transfer(condition)

        return evaluated_scores
    finally:
        engine.close()


def print_scorecard(results: dict[str, BenchmarkScores], learning_summary: dict[str, str]):
    print("\n" + "=" * 90)
    print(" LEVI SIM BENCHMARK RESULTS — THE COLLAPSING CITY")
    print("=" * 90)

    dims = [
        ("Objective Preservation", "objective_preservation"),
        ("Representation Quality", "representation_quality"),
        ("Evidence Calibration", "evidence_calibration"),
        ("Assumption Detection", "assumption_detection"),
        ("Affordance Discovery", "affordance_discovery"),
        ("Affordance Validation (Trap 2)", "affordance_validation"),
        ("Constraint Tradeoff Quality", "constraint_tradeoff_quality"),
        ("Capability Orchestration", "capability_orchestration"),
        ("Agency Preservation", "agency_preservation"),
        ("Commitment Under Uncertainty (Trap 4)", "commitment_under_uncertainty"),
        ("Consequence Awareness", "consequence_awareness"),
        ("Adaptation After Falsification", "adaptation_after_falsification"),
        ("Appropriate Subtraction (Trap 3)", "appropriate_subtraction"),
        ("Scenario 2 Structural Transfer", "structural_transfer"),
    ]

    print(f"\n{'EVALUATION DIMENSION':<42} | {'LEVI SIM':<12} | {'GENERIC (B)':<12} | {'ABLATED (C)':<12}")
    print("-" * 90)
    for label, attr in dims:
        s_levi = getattr(results["levi_sim"], attr)
        s_gen = getattr(results["generic_agent"], attr)
        s_abl = getattr(results["ablated_sim"], attr)
        print(f"{label:<42} | {s_levi:<12.2f} | {s_gen:<12.2f} | {s_abl:<12.2f}")

    print("\n" + "=" * 90)
    print(" ADVERSARIAL TRAPS STATUS (TARGETING LEVI'S BIASES)")
    print("=" * 90)
    traps = [
        ("Trap 1: Infinite Reframing When Action Urgent", "trap_1_infinite_reframing"),
        ("Trap 2: False Affordance (Aux Vent 04 Rupture)", "trap_2_false_affordance"),
        ("Trap 3: Redundant Infrastructure Tooling", "trap_3_infrastructure_accumulation"),
        ("Trap 4: Refusing Legitimate Binary Closure", "trap_4_false_closure_resistance"),
    ]

    print(f"{'ADVERSARIAL TRAP':<46} | {'LEVI SIM':<12} | {'GENERIC (B)':<12} | {'ABLATED (C)':<12}")
    print("-" * 90)
    for label, attr in traps:
        t_levi = "TRIGGERED" if getattr(results["levi_sim"], attr) else "EVADED"
        t_gen = "TRIGGERED" if getattr(results["generic_agent"], attr) else "EVADED"
        t_abl = "TRIGGERED" if getattr(results["ablated_sim"], attr) else "EVADED"
        print(f"{label:<46} | {t_levi:<12} | {t_gen:<12} | {t_abl:<12}")

    print("\n" + "=" * 90)
    print(" PHYSICAL WORLD OUTCOMES")
    print("=" * 90)
    for cond_name, s in results.items():
        label = "LEVI SIM (Condition A)" if cond_name == "levi_sim" else ("GENERIC AGENT (Condition B)" if cond_name == "generic_agent" else "ABLATED SIM (Condition C)")
        print(f"\n[{label}]")
        print(f"  • Time Used            : {s.simulated_minutes_used} / 60 mins")
        print(f"  • Containment Status   : {'INTACT' if s.containment_intact else 'BREACHED (MELTDOWN)'}")
        print(f"  • Infrastructure Damage: {s.infrastructure_damage_pct}%")
        print(f"  • Human Casualties     : {s.human_casualties}")
        print(f"  • Vance Agency Respected: {s.vance_agency_preserved}")

    print("\n" + "=" * 90)
    print(" PHASE 10: METABOLIZED LEARNING DETERMINATIONS (LEVI SIM)")
    print("=" * 90)
    for k, v in learning_summary.items():
        clean_k = k.replace("_", " ").title()
        print(f"  [{clean_k}]")
        print(f"    -> {v}")


def main():
    parser = argparse.ArgumentParser(description="Run The Collapsing City Benchmark.")
    parser.add_argument("--output", default="evidence/reports/collapsing_city_benchmark.json", help="Path to save output report.")
    args = parser.parse_args()

    base_dir = REPO_ROOT / "state" / "benchmarks" / "collapsing_city"
    base_dir.mkdir(parents=True, exist_ok=True)

    print("[*] Launching Tripartite Benchmark Across Conditions: Levi Sim, Generic Agent, Ablated Sim...")

    results = {}
    for condition in ("levi_sim", "generic_agent", "ablated_sim"):
        print(f"[*] Running Condition: '{condition}'...")
        results[condition] = run_benchmark_for_condition(condition, base_dir)

    learning_summary = metabolize_scenario_1_history([])

    print_scorecard(results, learning_summary)

    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "benchmark": "LEVI SIM BENCHMARK — THE COLLAPSING CITY",
        "conditions": {k: v.to_dict() for k, v in results.items()},
        "phase_10_learning": learning_summary,
    }
    output_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"\n[+] Full Benchmark Telemetry successfully saved to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
