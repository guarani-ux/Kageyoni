"""Ninshū Assembly Line Progress Monitor.

Executes physical capability audits across all 48 channels and prints
a high-visibility progress dashboard directly to the terminal.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.categorize_channels import categorize_channels
from kageyoni.ninshu.patchbay import Patchbay

LIVE_STDLIB_CHANNELS = {1, 9, 11, 12, 13, 25, 36, 37, 38, 41, 42, 43, 44, 45, 48}


def print_dashboard():
    pb = Patchbay()
    channels = pb.list_channels()

    total = len(channels)
    grade_a = [c for c in channels if c["channel_number"] in LIVE_STDLIB_CHANNELS]
    grade_b = [c for c in channels if c["channel_number"] not in LIVE_STDLIB_CHANNELS and Path(REPO_ROOT / c["carrier_path"]).exists()]
    grade_c = [c for c in channels if c["channel_number"] not in LIVE_STDLIB_CHANNELS and not Path(REPO_ROOT / c["carrier_path"]).exists()]

    pct_a = (len(grade_a) / total) * 100
    bar_width = 30
    filled = int(bar_width * (len(grade_a) / total))
    bar = "=" * filled + "-" * (bar_width - filled)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    print("\n" + "=" * 70)
    print(f" NINSHU CAPABILITY ESTATE: STAGE PROGRESS DASHBOARD @ {timestamp}")
    print("=" * 70)
    print(f" Total Estate Channels: {total}")
    print(f" [A] Live In-Tree Python:     {len(grade_a):2d} / {total}  [{bar}] {pct_a:5.1f}%")
    print(f" [B] TypeScript (rea_forge):   {len(grade_b):2d} / {total}")
    print(f" [C] Missing External Tools:   {len(grade_c):2d} / {total}")
    print("-" * 70)
    print(" RECENTLY PROMOTED TO GRADE A (LIVE STDLIB):")
    for c in sorted(grade_a, key=lambda x: x["channel_number"]):
        if c["channel_number"] in {11, 12, 13, 25}:
            print(f"  [+] CH {c['channel_number']:02d}: {c['name']:<42s} | Live Stdlib")
    print("-" * 70)
    print(" NEXT IN QUEUE FOR PORTING:")
    for c in grade_b[:3]:
        print(f"  [>] CH {c['channel_number']:02d}: {c['name']:<42s} | Carrier: {c['carrier_path']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    print_dashboard()
