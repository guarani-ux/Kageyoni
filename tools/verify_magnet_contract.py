"""
tools/verify_magnet_contract.py
Gate G1 Verification: Read-Only Contract and Observable State Mapping.

Verifies:
1. Pinned read-only contract exists and is valid JSON.
2. All 6 approved requirements exist.
3. Every requirement maps to state, governing operation, permitted transitions, and observable results.
4. Asserts zero verification gaps.
"""

from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "docs" / "MAGNET-AND-STATE-CONTRACT.json"


def main():
    if not CONTRACT_PATH.exists():
        sys.exit(f"CONTRACT_ABSENT: Pinned contract file {CONTRACT_PATH} does not exist.")

    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        sys.exit(f"CONTRACT_CORRUPT: Invalid JSON in {CONTRACT_PATH}: {str(e)}")

    reqs = data.get("approved_requirements", [])
    if len(reqs) < 6:
        sys.exit(f"INCOMPLETE_REQUIREMENTS: Expected >= 6 approved requirements, found {len(reqs)}.")

    required_fields = (
        "req_id",
        "gate",
        "title",
        "specification",
        "state_representation",
        "governing_operation",
        "permitted_transitions",
        "observable_result",
    )

    gaps = []
    for r in reqs:
        req_id = r.get("req_id", "UNKNOWN_REQ")
        for field_name in required_fields:
            if not r.get(field_name):
                gaps.append(f"Requirement '{req_id}' missing field '{field_name}'")

    if gaps:
        print("[VERIFICATION GAPS FOUND]:")
        for g in gaps:
            print(f"  - {g}")
        sys.exit(1)

    print(f"[Gate G1 Contract Verified] Pinned contract: {data.get('contract_id')}")
    print(f"  Requirements Mapped: {len(reqs)}")
    print(f"  Verification Gaps: 0")
    print(f"  Candidate SHA: {data.get('pinned_candidate_sha')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
