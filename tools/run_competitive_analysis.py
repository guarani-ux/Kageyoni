"""
Competitive Media Strategy Analysis Runner (Sovereign Media Engine)

Executes Workflow 1 across Canadian Public Libraries, benchmarking Calgary Public Library
against Toronto, Edmonton, and Vancouver Public Libraries.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kageyoni.engine import Engine
from kageyoni.workflows import Workflows


def run_analysis(
    target: str = "Calgary Public Library",
    peers: list = None,
    focus_area: str = "YouTube & Digital Media Strategy",
    db_path: str = "state/agency_workspace.sqlite",
    output_path: str = "evidence/reports/competitive_analysis_cpl.json",
):
    if peers is None:
        peers = ["Toronto Public Library", "Edmonton Public Library", "Vancouver Public Library"]

    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    engine = Engine(db_path)
    workflows = Workflows(engine)

    report = workflows.agency.run_competitive_analysis(
        target_name=target,
        peer_names=peers,
        focus_area=focus_area,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(description="Run Public Library Competitive Media Analysis")
    parser.add_argument("--target", type=str, default="Calgary Public Library", help="Target library")
    parser.add_argument("--peers", type=str, default="Toronto Public Library,Edmonton Public Library,Vancouver Public Library", help="Comma-separated peer libraries")
    parser.add_argument("--focus", type=str, default="YouTube & Digital Media Strategy", help="Content / channel focus area")
    parser.add_argument("--db", type=str, default="state/agency_workspace.sqlite", help="SQLite database path")
    parser.add_argument("--out", type=str, default="evidence/reports/competitive_analysis_cpl.json", help="Output JSON path")
    args = parser.parse_args()

    peers_list = [p.strip() for p in args.peers.split(",") if p.strip()]
    report = run_analysis(args.target, peers_list, args.focus, args.db, args.out)

    print("\n=======================================================")
    print(f"COMPETITIVE MEDIA STRATEGY REPORT: {report['target']}")
    print(f"Analysis ID: {report['analysis_id']}")
    print("=======================================================\n")
    print(f"Target: {report['target']}")
    print(f"Peers: {', '.join(report['peers'])}\n")
    print("1. RADAR TELEMETRY SUMMARY:")
    for lib, data in report["telemetry"].items():
        print(f"  * {lib}: {data['subscribers']:,} subs | {data['total_videos']} videos | {data['subs_per_video']:.1f} subs/vid")
        print(f"    Archetype: {data['archetype']}")
    print("\n2. ORACLE RHETORICAL AUDIT:")
    for k, v in report["rhetorical_audit"].items():
        print(f"  * {k}: {v}")
    print("\n3. DEFICIT SCANNER (MISSINGNESS LEDGER):")
    for d in report["deficits"]:
        print(f"  * [{d['code']}]: {d['detail']}")
    print("\n4. /TRIBUNAL ADJUDICATION:")
    print(f"  * Verdict: {report['tribunal']['final_verdict']}")
    print(f"  * Concession: {report['tribunal']['concession_made']}")
    print(f"  * Flip Condition: {report['tribunal']['mandatory_flip_condition']}")
    print(f"\n[DURABLE STATE COMMITTED TO SQLITE: {args.db}]")
    print(f"[REPORT EXPORTED TO: {args.out}]")


if __name__ == "__main__":
    main()
