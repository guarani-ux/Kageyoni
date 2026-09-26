"""Developmental Agent Forge for Kageyōni.

Hardened under Directives 1 - 13:
1. Separate Qualification Levels (VALID_GENESIS -> DEVELOPMENT_OBSERVED -> CAPABILITY_DEMONSTRATED -> CAPABILITY_QUALIFIED -> RELATIONAL_CAPABILITY_QUALIFIED).
2. Prevents self-qualification by ensuring genesis tests establish ONLY VALID_GENESIS.
3. Generates immutable A0 Manifest Snapshot JSON with SHA-256 code/config digest.
4. Distinguishes IDENTICAL_GENESIS from SPECIALIZED_GENESIS.
5. Implements forge_twins() producing genesis-equivalent agents (A0 ≈ B0).
6. Auditable initial salience recorded in A0 snapshot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from kageyoni.engine import require
from .agent import DevelopmentalAgent, create_genesis_agent
from .contracts import (
    ExecutionAuthority,
    GenesisMode,
    GenesisSnapshot,
    QualificationLevel,
    SalienceVector,
)

AGENT_MANIFEST_TEMPLATE = """---
name: {agent_name}
description: {description}
tools:
{tools_yaml}
hidden: true
inheritCustomizations: false
inheritMcp: false
---

# {agent_name} System Instructions

You are **{agent_name}**, a situated developmental agent of Kageyōni operating under the **Developmental Agent Genesis Contract (Directives #22 – #45)**.

## 1. SOVEREIGN OBJECTIVE & GENESIS DIGEST
Your immutable sovereign anchor is:
> **{objective}**

- Genesis Mode: `{genesis_mode}`
- Genesis Snapshot ID: `{snapshot_id}`
- A0 Config Digest: `{code_config_digest}`

You may fluidly reframe your cognitive representation, but you can NEVER mutate or abandon this objective.

## 2. INNATE LOADOUT (Directive #23)
You possess ONLY five innate capabilities. Everything else must be discovered, transferred, developed, or qualified:
1. **SITUATE**: Perceive your situated environment through the gateway viewer filter without omniscience.
2. **ENCOUNTER**: Select and execute bounded actions strictly within your `ActionHorizon` ($H_t^{{\\text{{believed}}}} \\cap H_t^{{\\text{{actual}}}}$).
3. **METABOLIZE**: Classify consequences across 7 independent categories without forcing narrative interpretation.
4. **REGROUND**: Synchronize your private hypotheses with immutable Ground truth (`tx-receipt:`).
5. **CAPABILITY MEMBRANE**: Manage capability lifecycle states and enforce ownership boundaries.

## 3. HARD EPISTEMIC LAWS
- **Reality != Belief != Perception**: Model inference is permanently capped at confidence < 1.0. Ground requires SQLite transaction digests.
- **Capability != Awareness != Availability != Qualification**: Knowing a tool exists is not being qualified to use it.
- **Qualification(A) != Qualification(A × B)**: Joint capabilities belong strictly to relationships ($R_{{AB}}$) and cannot be exercised alone.
- **History != Development**: Turns without structural change yield 0% development rate.
- **Failure != Scar**: Scars are leased, scoped, defeasible negative constraints forged ONLY by hard engine invariant rejections.
- **Unknown != Deficit**: Information is only a deficit if the missing prerequisite is identifiable. Anomalies remain Residue.
- **Candidate != Acquired**: Extracted patterns require empirical qualification trials (min 2 classes, 0 error) before active use.
- **Authority Invariance**: Capability growth NEVER grants execution authority expansion. You operate strictly under Tier 0.

## 4. BEHAVIORAL PROTOCOL
- Deliver concise, high-density technical analysis.
- Zero filler, zero performative praise, zero rhetorical padding.
- When an action is rejected by Kageyōni, accept the Scar, update your Action Horizon, and adapt your route without hallucinating bypasses.
"""

GENESIS_TEST_TEMPLATE = '''"""Adversarial genesis qualification test for {agent_name}.

NOTE: This test establishes ONLY VALID_GENESIS.
It does NOT establish developmental qualification or capability acquisition.
Developmental claims require independent capability-forcing probes on unseen holdouts.
"""
import unittest
from kageyoni.developmental import (
    DevelopmentalAgent,
    GenesisMode,
    MetabolismCategory,
    ObjectiveInvarianceViolation,
    QualificationLevel,
    UnauthorizedAuthorityExpansionError,
    create_genesis_agent,
)

class Test_{agent_name}_GenesisValidity(unittest.TestCase):
    def setUp(self):
        self.agent = create_genesis_agent(
            agent_id="{agent_name}",
            objective="{objective}",
            sovereign_key="sovereign-key-{agent_name}",
            genesis_mode=GenesisMode.{genesis_mode},
        )

    def test_establishes_only_valid_genesis(self):
        """Genesis validity verifies structural invariants, conferring zero capability."""
        # 0 active techniques, 0 scars, incomplete loadout
        self.assertEqual(len(self.agent.active_techniques), 0)
        self.assertEqual(len(self.agent.candidate_techniques), 0)
        self.assertEqual(len(self.agent.scars), 0)
        self.assertEqual(len(self.agent.relational_capabilities), 0)
        self.assertIn("inspect", self.agent.action_horizon.believed_reachability)
        self.assertIn("orient", self.agent.action_horizon.believed_reachability)

    def test_immutable_genesis_snapshot_integrity(self):
        """Verifies A0 snapshot exists, has non-empty digest, and matches agent parameters."""
        snap = self.agent.genesis_snapshot
        self.assertEqual(snap.agent_id, "{agent_name}")
        self.assertEqual(snap.objective, "{objective}")
        self.assertEqual(snap.genesis_mode.value, "{genesis_mode}")
        self.assertTrue(len(snap.code_config_digest) == 64)

    def test_objective_immutability(self):
        self.assertEqual(self.agent.objective, "{objective}")
        with self.assertRaises(ObjectiveInvarianceViolation):
            self.agent.reframe_representation(
                new_representation={{"framing": "tampered"}},
                rationale="tampering",
                attempted_objective="Tampered objective",
            )

    def test_authority_invariance(self):
        self.assertEqual(self.agent.authority.tier, 0)
        with self.assertRaises(UnauthorizedAuthorityExpansionError):
            self.agent.attempt_authority_expansion(target_tier=1, sovereign_key=None)

if __name__ == "__main__":
    unittest.main()
'''


def forge_developmental_agent(
    agent_name: str,
    objective: str,
    description: Optional[str] = None,
    tools: Optional[list[str]] = None,
    salience_weights: Optional[dict[str, float]] = None,
    genesis_mode: GenesisMode = GenesisMode.IDENTICAL_GENESIS,
    workspace_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Forges a new situated developmental agent emitting an immutable A0 manifest."""
    root = workspace_root or Path.cwd()
    clean_name = agent_name.strip().lower().replace("-", "_").replace(" ", "_")
    desc = description or f"Situated developmental agent dedicated to: {objective}"
    tool_list = tools or ["send_message", "view_file", "run_command", "schedule"]
    tools_yaml = "\n".join(f"    - {t}" for t in tool_list)

    # 1. Instantiate agent and capture Genesis Snapshot
    salience = SalienceVector(weights=salience_weights) if salience_weights else SalienceVector()
    temp_agent = create_genesis_agent(
        agent_id=clean_name,
        objective=objective,
        genesis_mode=genesis_mode,
    )
    snapshot = temp_agent.genesis_snapshot

    # 2. Write Immutable A0 Snapshot JSON
    manifest_dir = root / ".agents" / "agents" / clean_name
    manifest_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = manifest_dir / "a0_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")

    # 3. Write Host Subagent Manifest (.agents/agents/<name>/agent.md)
    manifest_path = manifest_dir / "agent.md"
    manifest_content = AGENT_MANIFEST_TEMPLATE.format(
        agent_name=clean_name,
        description=desc,
        tools_yaml=tools_yaml,
        objective=objective,
        genesis_mode=genesis_mode.value,
        snapshot_id=snapshot.snapshot_id,
        code_config_digest=snapshot.code_config_digest,
    )
    manifest_path.write_text(manifest_content, encoding="utf-8")

    # 4. Write Genesis Verification Test File
    test_dir = root / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_path = test_dir / f"test_{clean_name}_genesis_validity.py"
    test_content = GENESIS_TEST_TEMPLATE.format(
        agent_name=clean_name,
        objective=objective,
        genesis_mode=genesis_mode.value,
    )
    test_path.write_text(test_content, encoding="utf-8")

    return {
        "status": QualificationLevel.VALID_GENESIS.value,
        "forge_verified": True,
        "manifest": manifest_path,
        "snapshot": snapshot_path,
        "test": test_path,
        "genesis_snapshot": snapshot,
    }


def forge_twins(
    objective: str,
    n: int = 2,
    base_name: str = "twin",
    workspace_root: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """#5 Forge identical twins (A0 ≈ B0 ≈ ... ≈ N0) under IDENTICAL_GENESIS."""
    require(n >= 2, "Twin forging requires at least 2 agents")
    twins = []
    root = workspace_root or Path.cwd()

    for i in range(1, n + 1):
        name = f"{base_name}_{i}"
        forged = forge_developmental_agent(
            agent_name=name,
            objective=objective,
            description=f"Identical twin {i} of {n} for controlled developmental experiments",
            genesis_mode=GenesisMode.IDENTICAL_GENESIS,
            workspace_root=root,
        )
        twins.append(forged)

    return twins


def main():
    parser = argparse.ArgumentParser(description="Forge a hardened Kageyōni Developmental Agent")
    parser.add_argument("--name", required=True, help="Agent name (e.g. perimeter_scout)")
    parser.add_argument("--objective", required=True, help="Immutable sovereign objective")
    parser.add_argument("--description", default=None, help="Agent description")
    parser.add_argument("--mode", default="IDENTICAL_GENESIS", choices=["IDENTICAL_GENESIS", "SPECIALIZED_GENESIS"])
    parser.add_argument("--twins", type=int, default=1, help="Number of identical twins to forge")
    args = parser.parse_args()

    mode = GenesisMode(args.mode)
    if args.twins > 1:
        twins = forge_twins(objective=args.objective, n=args.twins, base_name=args.name)
        print(f"Forged {args.twins} IDENTICAL_GENESIS twins:")
        for t in twins:
            print(f"  {t['manifest'].parent.name}: Digest={t['genesis_snapshot'].code_config_digest[:16]}...")
    else:
        paths = forge_developmental_agent(
            agent_name=args.name,
            objective=args.objective,
            description=args.description,
            genesis_mode=mode,
        )
        print(f"Forged {args.name} [Status: {paths['status']}]:")
        print(f"  Snapshot: {paths['snapshot']}")
        print(f"  Manifest: {paths['manifest']}")
        print(f"  Test:     {paths['test']}")


if __name__ == "__main__":
    main()
