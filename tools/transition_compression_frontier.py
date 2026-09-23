"""
tools/transition_compression_frontier.py

Transitions a Frontier in state/compression_situation.sqlite through the mandatory lifecycle:
  open -> investigating -> observe(refs, payload) -> resolved(resolution_observation_ids)
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kageyoni.engine import Engine
from kageyoni.v11.frontier import FrontierManager


def transition_frontier(
    frontier_id: str,
    reason: str,
    refs: list[str],
    payload: dict,
    db_path: Path | None = None,
) -> str:
    db_path = db_path or (ROOT / "state" / "compression_situation.sqlite")
    if not db_path.exists():
        raise FileNotFoundError(f"Compression situation database not found: {db_path}")

    engine = Engine(str(db_path))
    fm = FrontierManager(engine)

    cur = fm.read(frontier_id)
    if cur["state"] == "resolved":
        print(f"Frontier {frontier_id} already resolved.")
        return "ALREADY_RESOLVED"

    if cur["state"] == "open":
        fm.transition(frontier_id, "investigating", patch={"investigation_note": reason})

    obs = fm.observe(frontier_id, refs=refs, payload=payload)
    oid = obs["observation_id"]

    fm.transition(
        frontier_id,
        "resolved",
        patch={
            "resolution_observation_ids": [oid],
            "resolution_reason": reason,
            "remaining_unknowns": [],
        },
    )
    engine.close()
    print(f"[Compression Situation OS] Resolved {frontier_id} -> observation {oid}")
    return oid


def main():
    parser = argparse.ArgumentParser(description="Transition a compression frontier to resolved")
    parser.add_argument("frontier_id", help="Frontier ID (e.g. frontier:cp00-baseline)")
    parser.add_argument("--reason", required=True, help="Resolution rationale")
    parser.add_argument("--refs", nargs="+", default=[], help="Evidence refs")
    parser.add_argument("--payload", default="{}", help="JSON observation payload")
    args = parser.parse_args()

    payload = json.loads(args.payload)
    transition_frontier(args.frontier_id, args.reason, args.refs, payload)


if __name__ == "__main__":
    main()
