"""Unit tests for the Portable Play Kernel (playable-world/0.1).

Validates:
1. Canonical Save loading from data/SAVE.json.
2. Turn execution lifecycle & monotonic revision advance.
3. Adapter Contract validation (rejection of stale base_revision).
4. Cross-host portability: world travels, permissions do not.
5. Real action boundary: missing tools leave actions pending.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kageyoni.playable_world.kernel import (
    PlayableWorldKernel,
    SaveState,
    TurnRequest,
    TurnResponse,
)


class TestPlayableWorldKernel(unittest.TestCase):

    def setUp(self):
        self.save_path = Path("c:/Kageyoni/data/SAVE.json")
        self.assertTrue(self.save_path.is_file(), "Canonical SAVE.json must exist")

    def test_1_load_canonical_save(self):
        """Kernel cleanly boots from canonical data/SAVE.json."""
        kernel = PlayableWorldKernel()
        kernel.load_save(self.save_path)

        self.assertEqual(kernel.state.kernel, "playable-world/0.1")
        self.assertEqual(kernel.state.world_id, "levi-world-001")
        self.assertEqual(kernel.state.revision, 0)
        self.assertEqual(kernel.state.player["id"], "levi")
        self.assertEqual(kernel.state.scene["title"], "The Threshold")

    def test_2_turn_execution_advances_revision(self):
        """Executing a turn advances revision and produces valid TurnResponse."""
        kernel = PlayableWorldKernel()
        kernel.load_save(self.save_path)

        req = TurnRequest(
            request_id="turn-001",
            operation="continue",
            input="I observe the boundary between worlds and test the air.",
            presentation="json",
            base_revision=0,
        )

        res = kernel.execute_turn(req)

        self.assertEqual(res.request_id, "turn-001")
        self.assertEqual(res.base_revision, 0)
        self.assertEqual(kernel.state.revision, 1)
        self.assertEqual(kernel.state.parent_revision, 0)
        self.assertEqual(len(kernel.state.events), 1)
        self.assertEqual(kernel.state.events[0]["revision"], 1)
        self.assertIn("turn-001", kernel.state.processed_requests)

    def test_3_stale_base_revision_fails_closed(self):
        """Adapter contract: submitting a stale base_revision is rejected."""
        kernel = PlayableWorldKernel()
        kernel.load_save(self.save_path)

        # Advance to revision 1
        req1 = TurnRequest(request_id="turn-001", operation="continue", input="First action", base_revision=0)
        kernel.execute_turn(req1)
        self.assertEqual(kernel.state.revision, 1)

        # Now submit a stale request expecting base_revision 0
        stale_req = TurnRequest(request_id="turn-002", operation="continue", input="Stale action", base_revision=0)
        res = kernel.execute_turn(stale_req)

        self.assertIn("Revision conflict", res.scene)
        self.assertEqual(kernel.state.revision, 1, "State must not advance on conflict")
        self.assertEqual(res.save_status, "not_written")

    def test_4_cross_host_portable_handoff(self):
        """The world travels between hosts; host permissions do not."""
        # Host A (Antigravity): Has storage sink and file tools
        host_a_kernel = PlayableWorldKernel()
        host_a_kernel.load_save(self.save_path)

        def mock_storage(state: SaveState) -> bool:
            return True

        req_a = TurnRequest(
            request_id="turn-a",
            operation="continue",
            input="Record observation of the threshold stone",
            host={"name": "antigravity", "available_actions": ["write_file", "execute_command"]},
            base_revision=0,
        )
        res_a = host_a_kernel.execute_turn(req_a, storage_sink=mock_storage)
        self.assertEqual(res_a.save_status, "written")

        # Export state from Host A
        exported_json = host_a_kernel.state.to_json()

        # Host B (iOS Shortcuts / Mobile): Read-only, no file tool, no execution commands
        host_b_kernel = PlayableWorldKernel()
        host_b_kernel.load_save(json.loads(exported_json))

        self.assertEqual(host_b_kernel.state.revision, 1)
        self.assertEqual(host_b_kernel.state.world_id, "levi-world-001")

        req_b = TurnRequest(
            request_id="turn-b",
            operation="continue",
            input="Speak into the void",
            host={"name": "shortcuts", "available_actions": ["render", "export_save"]},
            base_revision=1,
        )
        res_b = host_b_kernel.execute_turn(req_b)
        self.assertEqual(res_b.save_status, "exported")
        self.assertEqual(host_b_kernel.state.revision, 2)

    def test_5_real_action_boundary_leaves_missing_tools_pending(self):
        """Missing external tool permissions leave actions in pending_actions."""
        kernel = PlayableWorldKernel()
        kernel.load_save(self.save_path)

        def adjudicate_with_external_request(state: SaveState, req: TurnRequest):
            return {
                "scene": "A draft for the video script was composed in the world.",
                "changes": "Draft generated.",
                "choices": [],
                "pending_actions": [
                    {
                        "action_id": "act-pub-01",
                        "type": "external_file_write",
                        "target": "scripts/opening.md",
                        "status": "pending_host_authorization",
                    }
                ],
            }

        req = TurnRequest(request_id="turn-bridge-1", operation="continue", input="Write opening script draft", base_revision=0)
        res = kernel.execute_turn(req, adjudicator=adjudicate_with_external_request)

        self.assertEqual(len(res.pending_actions), 1)
        self.assertEqual(res.pending_actions[0]["status"], "pending_host_authorization")
        self.assertEqual(len(kernel.state.pending_actions), 1)
