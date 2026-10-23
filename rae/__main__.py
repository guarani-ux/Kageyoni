"""CLI: python -m rae reify --element 8 --context "CPL program promo video" --fills fills.json

The fills file is the agent's judgment: JSON mapping slot/instrument names to
{"text": "...", "provenance": "verified"|"scaffolded"}. The engine does everything else.
"""
import argparse
import json
import sys

from .reify import reify, retrieve


def main():
    p = argparse.ArgumentParser(prog="rae", description="Reify Any Element")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("reify", help="Reify an element for a context")
    r.add_argument("--element", required=True, help="knowledge id or title fragment")
    r.add_argument("--context", required=True, help="concrete context to situate in")
    r.add_argument("--fills", required=True, help="JSON file with the agent's fills")
    r.add_argument("--title", default=None, help="artifact title override")

    s = sub.add_parser("show", help="Show an element as RAE sees it")
    s.add_argument("--element", required=True)

    args = p.parse_args()
    if args.cmd == "show":
        el = retrieve(args.element)
        print(json.dumps({k: el[k] for k in
              ("id", "title", "status", "kind", "verification_source", "source_title")
              if k in el}, indent=2, ensure_ascii=False))
        print("\nContent:\n" + (el["content"] or "(empty)"))
        print("\nPattern slots:", el["pattern"]["slots"])
        print("Instruments:", el["pattern"]["instrument"])
        return
    fills_raw = json.loads(open(args.fills, encoding="utf-8").read())
    fills = {k: (v["text"], v.get("provenance", "scaffolded")) for k, v in fills_raw.items()}
    result = reify(args.element, args.context, fills, title=args.title)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
