"""Ninshū CLI Interface.

Allows users, agents, and daimons to query the desk, route intents,
and inspect the 48-channel SSL console directly from the command line.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .patchbay import Patchbay


def main() -> None:
    parser = argparse.ArgumentParser(description="Ninshū: The 48-Channel SSL Capability Console & Patchbay")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Busses
    subparsers.add_parser("busses", help="List the 6 Master Busses")

    # 2. Channels
    ch_cmd = subparsers.add_parser("channels", help="List channels on the desk")
    ch_cmd.add_argument("--bus", help="Filter by bus ID (BUS_A to BUS_F)")

    # 3. Channel Strip
    strip_cmd = subparsers.add_parser("channel", help="Inspect a specific channel strip")
    strip_cmd.add_argument("number", type=int, help="Channel number (1 to 48)")

    # 4. Route Intent
    route_cmd = subparsers.add_parser("route", help="Route a problem intent to the optimal channel sub-mix")
    route_cmd.add_argument("intent", help="Natural language intent or technical keywords")
    route_cmd.add_argument("--subject", help="Filter by subject format (e.g. pe, elf, dotnet, pcap, electron)")
    route_cmd.add_argument("--max-tier", type=int, default=2, help="Maximum allowed Reversibility Tier (0, 1, or 2)")
    route_cmd.add_argument("--limit", type=int, default=5, help="Max channels to return")

    # 5. Patch Sub-Mix
    patch_cmd = subparsers.add_parser("patch", help="Build a multi-track sub-mix patch")
    patch_cmd.add_argument("channels", help="Comma-separated channel numbers (e.g. 1,26,38)")
    patch_cmd.add_argument("--name", default="session_submix", help="Sub-mix Daimon name")

    args = parser.parse_args()
    patchbay = Patchbay()

    if args.command == "busses":
        print("=== NINSHU 4000: 6 MASTER BUSSES ===")
        for b in patchbay.get_busses():
            print(f"[{b['bus_id']}] {b['name']} ({b['channel_range']})")
            print(f"       {b['description']}")

    elif args.command == "channels":
        print(f"=== NINSHU CHANNELS ({args.bus or 'ALL'}) ===")
        for c in patchbay.list_channels(bus_id=args.bus):
            print(f"CH {c['channel_number']:02d} | [{c['bus_id']}] {c['name']} (Tier {c['reversibility_tier']})")
            print(f"      Carrier: {c['carrier_path']} -> {c['entrypoint']}")

    elif args.command == "channel":
        strip = patchbay.get_channel(args.number)
        if not strip:
            print(f"Channel {args.number} not found.", file=sys.stderr)
            sys.exit(1)
        print(f"=== CHANNEL STRIP: CH {strip['channel_number']:02d} - {strip['name']} ===")
        print(json.dumps(strip, indent=2))

    elif args.command == "route":
        matches = patchbay.route(args.intent, subject=args.subject, max_tier=args.max_tier, limit=args.limit)
        print(f"=== ROUTED NINSHU SUB-MIX FOR: '{args.intent}' ===")
        if not matches:
            print("No matching channels found.")
            return
        for m in matches:
            print(f"-> CH {m['channel_number']:02d}: {m['name']} (Bus: {m['bus_id']}, Tier {m['reversibility_tier']})")
            print(f"   Role: {m['description']}")
            print(f"   Carrier: {m['carrier_path']} -> {m['entrypoint']}")

    elif args.command == "patch":
        try:
            nums = [int(x.strip()) for x in args.channels.split(",") if x.strip()]
        except ValueError:
            print("Invalid channel numbers format.", file=sys.stderr)
            sys.exit(1)
        res = patchbay.patch(nums, daimon_name=args.name)
        print(f"=== NINSHU SUB-MIX PATCH: {res['patch_id']} ===")
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
