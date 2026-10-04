"""
Constellation Emergence CLI.
Implements the 6-view unified terminal interface:
1. Constellation Emergence (Preflight, Preview, Execution)
2. Technique Bank
3. Lineage Map
4. Compare and Test
5. Constellation Map
6. Runs and Receipts
"""

from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

from .models import (
    ParticipantConfig,
    EncounterConfig,
    EnvironmentAffordance,
    RunHorizon,
    EvidencePolicy,
    HorizonMode,
    AvailabilitySetting,
    QualificationStatus,
)
from .affordances import discover_affordances
from .preview import generate_configuration_preview
from .engine import EmergenceEngine
from .store import EmergenceStore


def default_preflight(full_roster: bool = True) -> Dict[str, Any]:
    """Generates the default canonical preflight configuration with the full 8-character roster."""
    participants = [
        ParticipantConfig(
            character_id="voss",
            name="Voss",
            source_state="shinobi/.state/characters/voss/kageyoni.sqlite",
            role="Adversary / Specialist Prime",
            constraints=["Must attack through workspace topologies and causal inversion"],
            bandwidth=88,
            causal_memory=94,
            antigravity_leverage=91,
            will_density=82,
        ),
        ParticipantConfig(
            character_id="sebastian",
            name="Sebastian Nelson",
            source_state="shinobi/.state/characters/sebastian/kageyoni.sqlite",
            role="Defender / Node Guardian",
            constraints=["Cannot allow root lineage token to be severed"],
            bandwidth=86,
            causal_memory=92,
            antigravity_leverage=89,
            will_density=88,
        ),
        ParticipantConfig(
            character_id="sciel",
            name="Sciel",
            source_state="shinobi/.state/characters/sciel/kageyoni.sqlite",
            role="Substrate Anchor / Master Artisan",
            constraints=["Transforms fluid narrative terrain into dense basalt"],
            bandwidth=82,
            causal_memory=89,
            antigravity_leverage=84,
            will_density=98,
        ),
        ParticipantConfig(
            character_id="alexandra",
            name="Alexandra",
            source_state="shinobi/.state/characters/alexandra/kageyoni.sqlite",
            role="Telemetry Arbiter / High Observer",
            constraints=["Verifies carrier reality contact before commitment"],
            bandwidth=85,
            causal_memory=88,
            antigravity_leverage=95,
            will_density=85,
        ),
        ParticipantConfig(
            character_id="elijah",
            name="Elijah",
            source_state="shinobi/.state/characters/elijah/kageyoni.sqlite",
            role="Strategist Prime / Revision Architect",
            constraints=["Must anchor within First Revision continuity; cannot bypass seed constraints"],
            bandwidth=87,
            causal_memory=96,
            antigravity_leverage=85,
            will_density=90,
        ),
        ParticipantConfig(
            character_id="second_queen_bleaklands",
            name="Second Queen of Bleaklands",
            source_state="shinobi/.state/characters/second_queen_bleaklands/kageyoni.sqlite",
            role="High Sovereign / Desolation Arbiter",
            constraints=["Will cannot be diluted or refracted by external narrative framing"],
            bandwidth=80,
            causal_memory=91,
            antigravity_leverage=83,
            will_density=99,
        ),
        ParticipantConfig(
            character_id="arianne",
            name="Arianne",
            source_state="shinobi/.state/characters/arianne/kageyoni.sqlite",
            role="Coordinate Sentinel / Boundary Weaver",
            constraints=["Every coordinate operation must conserve workspace energy and spatial balance"],
            bandwidth=89,
            causal_memory=87,
            antigravity_leverage=93,
            will_density=84,
        ),
        ParticipantConfig(
            character_id="maki",
            name="Maki",
            source_state="shinobi/.state/characters/maki/kageyoni.sqlite",
            role="Environmental Admiral / Kinetic Vanguard",
            constraints=["Kinetic momentum must be grounded in physical carrier mass; cannot float"],
            bandwidth=92,
            causal_memory=85,
            antigravity_leverage=88,
            will_density=94,
        ),
    ]

    if not full_roster:
        participants = participants[:4]

    encounter = EncounterConfig(
        opponents=["Voss"],
        objective="Voss attempts to extract Sebastian; expanded octet adapts by generating new constellation techniques.",
        encounter_type="Boss Encounter / Causal Topology Clash",
        starting_state="Substrate initialized; legacy techniques stripped from active memory.",
        stakes="Root lineage permanence vs. Unplaced workspace cavity extraction.",
        constraints=["Zero hardcoded legacy abilities; all moves must emerge from reachable code affordances."],
    )

    affordances = discover_affordances()

    horizon = RunHorizon(
        mode=HorizonMode.TEN_ROUND_CYCLE,
        n_cycles=1,
        current_cycle=1,
        current_round=1,
        total_rounds=10,
    )

    policy = EvidencePolicy(
        required_tests=["Direct AST verification", "Carrier availability check"],
        adversarial_tests=["Schema trigger deflection", "High-resistance stress probe"],
        pass_fail_criteria={"min_coverage": 0.8, "max_failures": 0},
        evidence_minimum=1,
        stop_conditions=["Round test blocked without remediation", "Schema invariant violation"],
    )

    return {
        "participants": participants,
        "encounter": encounter,
        "affordances": affordances,
        "horizon": horizon,
        "policy": policy,
    }


class ConstellationEmergenceCLI:
    def __init__(self, store: Optional[EmergenceStore] = None):
        self.store = store or EmergenceStore()
        self.preflight = default_preflight()

    def print_header(self, title: str) -> None:
        print("\n" + "=" * 78)
        print(f"   {title}")
        print("=" * 78)

    def view_preflight(self) -> None:
        self.print_header("EMERGENCE PREFLIGHT CONFIGURATION")
        p = self.preflight

        print("\n[PARTICIPANTS]")
        for pt in p["participants"]:
            print(f"  * {pt.name:<28} ({pt.role}) | State: {pt.source_state}")
            print(f"    Metrics: [Bandwidth: {pt.bandwidth} | Causal: {pt.causal_memory} | Antigravity: {pt.antigravity_leverage} | Will: {pt.will_density}]")

        print(f"\n[ENCOUNTER]")
        enc = p["encounter"]
        print(f"  Type:      {enc.encounter_type}")
        print(f"  Objective: {enc.objective}")
        print(f"  Stakes:    {enc.stakes}")

        print("\n[ENVIRONMENT AFFORDANCES (With Declared Intensity)]")
        for aff in p["affordances"]:
            print(f"  * {aff.name:<34} [{aff.availability.value}]")
            print(f"    Carrier:   {aff.carrier}")
            print(f"    Intensity: {aff.intensity}")

        print(f"\n[RUN HORIZON]")
        hz = p["horizon"]
        print(f"  Mode: {hz.mode.value} ({hz.total_rounds} rounds per cycle)")

        print(f"\n[EVIDENCE POLICY]")
        pol = p["policy"]
        print(f"  Required Tests:    {pol.required_tests}")
        print(f"  Adversarial Tests: {pol.adversarial_tests}")
        print(f"  Evidence Minimum:  {pol.evidence_minimum} digest(s)")

    def view_preview(self) -> Dict[str, Any]:
        self.print_header("CONFIGURATION PREVIEW & TESTABILITY AUDIT")
        preview = generate_configuration_preview(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            self.preflight["horizon"],
            self.preflight["policy"],
        )

        print("\n1. PROMISING COMBINATIONS:")
        for comb in preview["promising_combinations"]:
            print(f"  * {' + '.join(comb['actors'])}")
            print(f"    Rationale: {comb['rationale']}")

        print("\n2. CONSTRAINTS & CONFLICTS:")
        for c in preview["constraints_and_conflicts"]:
            print(f"  * [{c['type']}] {c['detail']}")

        print("\n3. ROUND TESTABILITY SCOPE:")
        for rt in preview["round_testability"]:
            print(f"  * {rt['phase_range']}: {rt['scope']}")

        print("\n4. UNREACHABLE CLAIMS (Lacking Test):")
        for uc in preview["unreachable_claims"]:
            print(f"  * Claim:  {uc['claim']}")
            print(f"    Reason: {uc['reason']}")

        print("\n5. HYPOTHESIZED DESCENDANTS:")
        for hd in preview["hypothesized_descendants"]:
            print(f"  * {hd['name']:<30} | {hd['hypothesis']}")

        return preview

    def run_emergence(self, auto_launch: bool = False) -> None:
        self.view_preflight()
        self.view_preview()

        if not auto_launch:
            choice = input("\nLaunch Constellation Emergence encounter now? [y/N/adjust]: ").strip().lower()
            if choice != "y":
                print("Emergence launch aborted by user.")
                return

        self.print_header("LAUNCHING CONSTELLATION EMERGENCE ENCOUNTER")
        engine = EmergenceEngine(
            self.preflight["participants"],
            self.preflight["encounter"],
            self.preflight["affordances"],
            self.preflight["horizon"],
            self.preflight["policy"],
        )

        run_id = f"run_{int(time.time())}"
        for r_num in range(1, self.preflight["horizon"].total_rounds + 1):
            print(f"\n--- [EXECUTING ROUND {r_num}/10] ---")
            rec = engine.execute_round(r_num)
            res = rec.round_result
            print(f"Status:   {rec.status.value}")
            print(f"Tests:    {res['passed']} Passed | {res['failed']} Failed | {res['blocked']} Blocked")
            print(f"Evidence: Digest {res['evidence_digest'][:16]}...")
            
            # Print descendant emerged
            cand = engine.technique_bank.get(f"descendant_{engine.rounds[r_num-1].round_result.get('round')}") or list(engine.technique_bank.values())[-1]
            print(f"Emergent: {cand.name} [{cand.status.value}]")
            if cand.dimensions:
                d = cand.dimensions
                print(f"Weights:  Rel={d.relevance:.2f} | Dir={d.directness:.2f} | Rep={d.repeatability:.2f} | Cov={d.test_coverage:.2f} | Res={d.resistance_encountered:.2f}")

        # Terminal Synthesis
        print("\n" + "=" * 78)
        print("   TERMINAL SYNTHESIS & JOY BOY REGROUND")
        print("=" * 78)
        synth = engine.synthesis_outcome
        if synth:
            print(f"\n[ANCESTOR PROPOSALS]")
            for ap in synth.ancestor_proposals:
                print(f"  * [{ap['ancestor']}] {ap['change']}")
                print(f"    Provenance: {ap['provenance']}")

            print(f"\n[UNRESOLVED MAP]")
            for k, v in synth.unresolved_map.items():
                print(f"  * {k}: {v}")

            print(f"\nSynthesis Hash: {synth.synthesis_hash}")

        # Persist to unified store
        self.store.save_run(run_id, {"encounter": self.preflight["encounter"].objective}, engine.rounds, engine.technique_bank, synth)
        print(f"\n[PERSISTENCE] Run and round receipts durably recorded into SQLite store ({self.store.db_path.name}).")

    def view_technique_bank(self) -> None:
        self.print_header("VIEW 2: TECHNIQUE BANK (Descendants & Candidate Applications)")
        bank = self.store.get_technique_bank()
        if not bank:
            print("Technique bank is currently empty. Run an emergence encounter to seed descendants.")
            return

        for t in bank:
            dims = json.loads(t["dimensions_json"]) if t.get("dimensions_json") else {}
            print(f"\n* {t['name']} [{t['status']}] (ID: {t['descendant_id']})")
            print(f"  Carrier:  {t['carrier']}")
            print(f"  Ancestor: {t['ancestor']}")
            print(f"  Weights:  {dims}")
            print(f"  Evidence: {t['evidence_ref'][:20]}...")

    def view_lineage_map(self) -> None:
        self.print_header("VIEW 3: LINEAGE MAP (Parentage & Evidence Paths)")
        links = self.store.get_lineage_map()
        if not links:
            print("No lineage links recorded yet.")
            return

        for l in links:
            print(f"  {l['parent_id']}  ──[{l['relation']}]──>  {l['name']} ({l['status']})")
            print(f"    Attribution: {l['attribution']} | Evidence: {l['evidence_ref'][:16]}...")

    def view_compare_and_test(self) -> None:
        self.print_header("VIEW 4: COMPARE AND TEST (Shared Test Matrix & Dimensional Scores)")
        candidates = self.store.get_compare_and_test()
        if not candidates:
            print("No candidate techniques to compare.")
            return

        print(f"{'Name':<32} | {'Status':<16} | {'Relevance':<9} | {'Directness':<10} | {'Coverage':<8} | {'Resistance':<10}")
        print("-" * 96)
        for c in candidates:
            d = c.get("dimensions", {})
            rel = d.get("relevance", 0.0)
            dir_ = d.get("directness", 0.0)
            cov = d.get("test_coverage", 0.0)
            res = d.get("resistance_encountered", 0.0)
            print(f"{c['name']:<32} | {c['status']:<16} | {rel:<9.2f} | {dir_:<10.2f} | {cov:<8.2f} | {res:<10.2f}")

    def view_constellation_map(self) -> None:
        self.print_header("VIEW 5: CONSTELLATION MAP (Active Points, Relations & Transformations)")
        cmap = self.store.get_constellation_map()
        print("\n[ACTIVE CONSTELLATION POINTS]")
        for pt in cmap["active_points"]:
            print(f"  * {pt['name']:<30} [{pt['status']}] (Carrier: {pt['carrier']})")

        print("\n[CONSEQUENTIAL MANIPULATIONS]")
        for m in cmap["transformations"]:
            print(f"  * [{m['type']}] on {m['target']}")
            print(f"    Gain: {m['gain']} | Loss: {m['loss']}")
            print(f"    Reachability: +({m['new_reachability']}) / -({m['closed_reachability']})")
            print(f"    Attribution: {m['attribution']}")

    def view_runs_and_receipts(self) -> None:
        self.print_header("VIEW 6: RUNS AND RECEIPTS (Historical Configurations & Round Evidence)")
        runs = self.store.get_runs_and_receipts()
        if not runs:
            print("No prior emergence runs recorded.")
            return

        for r in runs:
            print(f"\nRun ID: {r['run_id']} | Status: {r['status']} | Date: {time.ctime(r['timestamp'])}")
            print(f"Synthesis Hash: {r['synthesis_hash']}")
            print(f"Total Rounds Recorded: {len(r.get('rounds', []))}")
            for rd in r.get("rounds", []):
                print(f"  - Round {rd['round_num']}: {rd['status']} | Digest: {rd['evidence_digest'][:16]}...")

    def main_menu(self) -> None:
        while True:
            self.print_header("CONSTELLATION EMERGENCE CLI — MAIN MENU")
            print("1. Constellation Emergence — configure and run an encounter")
            print("2. Technique Bank — browse descendants and candidate applications")
            print("3. Lineage Map — inspect parentage, revisions and evidence paths")
            print("4. Compare and Test — compare candidates against shared tests")
            print("5. Constellation Map — inspect active points, relations and transformations")
            print("6. Runs and Receipts — review configurations, round evidence and outcomes")
            print("0. Exit")

            choice = input("\nSelect view (0-6): ").strip()
            if choice == "1":
                self.run_emergence()
            elif choice == "2":
                self.view_technique_bank()
            elif choice == "3":
                self.view_lineage_map()
            elif choice == "4":
                self.view_compare_and_test()
            elif choice == "5":
                self.view_constellation_map()
            elif choice == "6":
                self.view_runs_and_receipts()
            elif choice == "0":
                print("Exiting Constellation Emergence CLI.")
                break
            else:
                print("Invalid option. Please choose between 0 and 6.")


def main():
    parser = argparse.ArgumentParser(description="Constellation Emergence CLI")
    parser.add_argument("--run", action="store_true", help="Launch emergence encounter directly")
    parser.add_argument("--auto", action="store_true", help="Auto-confirm emergence launch")
    parser.add_argument("--bank", action="store_true", help="View Technique Bank")
    parser.add_argument("--lineage", action="store_true", help="View Lineage Map")
    parser.add_argument("--compare", action="store_true", help="View Compare and Test Matrix")
    parser.add_argument("--map", action="store_true", help="View Constellation Map")
    parser.add_argument("--runs", action="store_true", help="View Runs and Receipts")
    parser.add_argument("--preview", action="store_true", help="View Preflight and Configuration Preview only")
    parser.add_argument("--core4", action="store_true", help="Limit to original core 4 participants")
    args = parser.parse_args()

    cli = ConstellationEmergenceCLI()
    if args.core4:
        cli.preflight = default_preflight(full_roster=False)

    if args.run:
        cli.run_emergence(auto_launch=args.auto)
    elif args.preview:
        cli.view_preflight()
        cli.view_preview()
    elif args.bank:
        cli.view_technique_bank()
    elif args.lineage:
        cli.view_lineage_map()
    elif args.compare:
        cli.view_compare_and_test()
    elif args.map:
        cli.view_constellation_map()
    elif args.runs:
        cli.view_runs_and_receipts()
    else:
        cli.main_menu()


if __name__ == "__main__":
    main()
