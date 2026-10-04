"""
Unit tests for kageyoni.celestial: Unified Celestial Kernel.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kageyoni.celestial import CelestialKernel
from kageyoni.gate import GateRule, GateOperator


def test_celestial_initialization(tmp_path):
    db_file = tmp_path / "celestial_sciel.db"
    kernel = CelestialKernel(
        character_id="sciel",
        name="Sciel",
        db_path=db_file,
        role="operative",
    )
    assert kernel.character_id == "sciel"
    assert kernel.name == "Sciel"
    assert kernel.role == "operative"
    assert kernel.dag is not None
    assert kernel.ledger is not None
    assert db_file.exists()
    kernel.close()


def test_perspective_observation():
    kernel = CelestialKernel("sciel", "Sciel")
    mock_world = MagicMock()
    mock_world.inspect.return_value = {"encounter": "boss_fight", "terrain": "mist"}

    obs = kernel.observe(mock_world, "enc_001")
    assert obs == {"encounter": "boss_fight", "terrain": "mist"}
    mock_world.inspect.assert_called_once_with("main", "enc_001", viewer="sciel")
    kernel.close()


def test_prerequisite_gate_evaluation():
    kernel = CelestialKernel("sciel", "Sciel")
    
    # Establish a factual node in local DAG
    kernel.dag.add_node("intel_route_clear", "intel", {"verified": True})

    obs = {
        "stamina": 80,
        "required_route": "intel_route_clear",
    }

    rules = [
        GateRule(field="stamina", op=">=", expected=50, error_message="Stamina low"),
        GateRule(field="required_route", op="valid_in_dag", error_message="Route intel invalid"),
    ]

    # Preconditions pass initially
    res = kernel.evaluate_action_prerequisites(rules, obs)
    assert res.passed is True

    # Invalidate DAG node -> fail-closed precondition check
    kernel.dag.invalidate("intel_route_clear", reason="Enemy patrol entered route")
    res_failed = kernel.evaluate_action_prerequisites(rules, obs)
    assert res_failed.passed is False
    assert len(res_failed.violations) == 1
    assert "Route intel invalid" in res_failed.violations[0]
    kernel.close()


def test_propose_action_contract():
    kernel = CelestialKernel("sciel", "Sciel")
    proposal = kernel.propose_action(
        encounter_id="enc_001",
        action_id="shadow_strike",
        rationale="Flank exposed",
        payload={"target": "commander", "power": 90},
    )

    assert proposal["encounter_id"] == "enc_001"
    assert proposal["host"] == "CelestialKernel:sciel"
    assert proposal["message"] == "[Sciel] Proposes shadow_strike: Flank exposed"
    assert proposal["interpretation"] == "Flank exposed"
    assert proposal["action"] == {
        "kind": "propose_action",
        "action_id": "shadow_strike",
        "payload": {"target": "commander", "power": 90},
    }
    kernel.close()


def test_record_experience(tmp_path):
    db_file = tmp_path / "experience.db"
    kernel = CelestialKernel("sciel", "Sciel", db_path=db_file)

    rec1 = kernel.record_experience(
        kind="scar",
        topic="kinetic_impact",
        payload={"damage": 35},
    )
    assert rec1.actor_id == "sciel"
    assert rec1.sequence == 1

    rec2 = kernel.record_experience(
        kind="learning",
        topic="kinetic_impact",
        payload={"mitigation": "raise_barrier_earlier"},
    )
    assert rec2.sequence == 2
    assert rec2.prev_hash == rec1.event_hash

    # Query records
    events = kernel.ledger.query(actor_id="sciel")
    assert len(events) == 2

    # Integrity verification
    valid, err = kernel.ledger.verify_integrity()
    assert valid is True
    assert err is None
    kernel.close()
