"""Tests for the Ninshū 8-Knob Power System & Revision 167 Painteress Encounter."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kageyoni.engine import Engine
from kageyoni.ninshu.power_system import (
    CANONICAL_WILL_CARRIERS,
    NinshuKnobVector,
    NinshuPowerConsole,
    execute_revision_167_painteress_encounter,
)
from kageyoni.will import validate_contract


class TestNinshuPowerSystem(unittest.TestCase):
    def test_chidori_shape_transformation_across_8_knobs(self) -> None:
        """Turning Knob 2 (bandwidth_shape) reshapes a single WillCarrier from needle to domain."""
        console = NinshuPowerConsole()
        sciel = CANONICAL_WILL_CARRIERS["sciel_painteress"]

        senbon_pkg = console.modulate(
            sciel,
            NinshuKnobVector(substrate="stone", bandwidth_shape="senbon", damping_density=0.98),
            technique_id="tech_sciel_pigment_needle",
            technique_name="Twilight Pigment Senbon",
            effect_operation="alter",
            pressure_target="ringbolt_seam",
            pressure_direction="suppress",
        )
        domain_pkg = console.modulate(
            sciel,
            NinshuKnobVector(
                substrate="stone",
                bandwidth_shape="domain",
                damping_density=0.98,
                sidechain_from="tech_sciel_pigment_needle",
            ),
            technique_id="tech_sciel_full_domain",
            technique_name="Domain of the Painteress",
            effect_operation="preserve",
            pressure_target="chamber_space",
            pressure_direction="increase",
        )

        self.assertEqual(
            senbon_pkg.will_technique_contract["effects"][0]["scope"]["area"],
            {"value": 0.1, "unit": "meter"},
        )
        self.assertEqual(senbon_pkg.will_technique_contract["activation"], "deliberate")

        self.assertEqual(
            domain_pkg.will_technique_contract["effects"][0]["scope"]["area"],
            {"value": 15.0, "unit": "meter"},
        )
        self.assertEqual(domain_pkg.will_technique_contract["activation"], "sustained")
        self.assertEqual(
            console.provenance.topological_sort(),
            ["tech_sciel_pigment_needle", "tech_sciel_full_domain"],
        )

    def test_all_9_canonical_carriers_compile_valid_will_contracts(self) -> None:
        """All 9 canonical Kageyōni Will/Ability carriers compile into valid Will contracts."""
        console = NinshuPowerConsole()
        for cid, carrier in CANONICAL_WILL_CARRIERS.items():
            pkg = console.modulate(
                carrier,
                NinshuKnobVector(
                    substrate="stone",
                    bandwidth_shape="spear",
                    damping_density=carrier.default_damping,
                ),
                technique_id=f"tech_{cid}_test",
                technique_name=f"{carrier.name} Spear",
                effect_operation="alter",
                pressure_target="target_node",
                pressure_direction="increase",
            )
            validate_contract("will_definition", pkg.will_definition_contract, f"wdef_{cid}", 1)
            validate_contract("will_expression", pkg.will_expression_contract, f"wexp_{cid}", 1)
            validate_contract("will_technique", pkg.will_technique_contract, f"tech_{cid}_test", 1)

    def test_invalid_knob_settings_fail_closed(self) -> None:
        """Out-of-bounds damping, authority, or unknown shapes fail closed."""
        with self.assertRaises(ValueError):
            NinshuKnobVector(bandwidth_shape="invalid_shape").validate()
        with self.assertRaises(ValueError):
            NinshuKnobVector(damping_density=1.5).validate()
        with self.assertRaises(ValueError):
            NinshuKnobVector(authority_gain=-0.1).validate()

    def test_revision_167_painteress_encounter_on_canonical_campaign_copy(self) -> None:
        """Executes Revision 167 on an isolated copy of build/kageyoni.sqlite and verifies cold reopen."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            canonical_db = Path("c:/Kageyoni/build/kageyoni.sqlite")
            db_path = tmp_path / "rev167_campaign.sqlite"
            if canonical_db.exists():
                shutil.copy2(canonical_db, db_path)
                engine = Engine(db_path)
            else:
                engine = Engine(db_path)
                engine.init()

            try:
                result = execute_revision_167_painteress_encounter(engine, branch="main")
                clash = result["clash_report"]

                # 1. Verify gaia-balance polyphonic clash preservation
                self.assertTrue(clash["gaia_balance_preserved"])
                conflicts = clash["effect_resolution"]["conflicts"]
                self.assertEqual(len(conflicts), 1)
                self.assertEqual(conflicts[0]["target"], "voss_conduit_link")
                self.assertEqual(conflicts[0]["kind"], "opposing_pressures")

                # 2. Verify Voss grab gate is contested/blocked and Lucretia is uninjured
                gates = {g["action"]: g["state"] for g in clash["effect_resolution"]["action_gates"]}
                self.assertEqual(gates.get("voss_avatar_grab"), "CONFLICTED")
                self.assertEqual(clash["outcomes_by_technique"]["tech_voss_grab_and_sever"], "partial")
                self.assertEqual(clash["outcomes_by_technique"]["tech_sciel_painteress_domain"], "success")

                # 3. Verify Voss avatar is slack in earth with prior damage remaining
                avatar = result["avatar_final_state"]
                self.assertEqual(
                    avatar["data"]["condition"],
                    "slack_in_earth_prior_damage_remains",
                )
                self.assertEqual(
                    avatar["data"]["effects"],
                    "live_link_severed_impressions_calcified_on_stone",
                )

                # 4. Verify the 3 stone impressions are preserved as 'proposed' (unverified location/authenticity)
                impressions = result["stone_impressions"]
                self.assertEqual(len(impressions), 3)
                for imp in impressions:
                    self.assertEqual(imp["status"], "proposed")
                    self.assertEqual(
                        imp["data"]["condition"],
                        "painted_on_stone_authenticity_unknown",
                    )

                # 5. Verify zero d20 rolls were used and Engine.verify() passes
                rolls_count = engine.db.execute("SELECT COUNT(*) FROM rolls WHERE branch='main'").fetchone()[0]
                self.assertEqual(rolls_count, 0)
                verify_res = engine.verify()
                self.assertTrue(verify_res["ok"])
            finally:
                engine.db.close()

            # 6. Cold-process reopen check in a separate OS subprocess
            probe = (
                "import json, sys; "
                "from kageyoni.engine import Engine; "
                "e = Engine(sys.argv[1]); "
                "v = e.verify(); "
                "weff = e.get('main', 'weff_rev167_painteress_residue'); "
                "avatar = e.get('main', 'voss_avatar_vessel'); "
                "e.db.close(); "
                "print(json.dumps({'ok': v['ok'], 'phase': weff['data']['contract']['phase'], "
                "'residues': weff['data']['contract']['residue_records'], "
                "'avatar_cond': avatar['data']['condition']}))"
            )
            proc = subprocess.run(
                [sys.executable, "-c", probe, str(db_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            reopened = json.loads(proc.stdout.strip())
            self.assertTrue(reopened["ok"])
            self.assertEqual(reopened["phase"], "active")
            self.assertEqual(reopened["avatar_cond"], "slack_in_earth_prior_damage_remains")
            self.assertIn("impression_g7_chamber", reopened["residues"])


if __name__ == "__main__":
    unittest.main()
