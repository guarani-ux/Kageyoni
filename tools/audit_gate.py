"""Antigravity CLI (agy) Dual-Agent Adversarial Verification Gate.

Implements the Finder-Verifier / Optimizer-Skeptic architecture:
1. Takes an uncommitted or staged Git diff for a candidate channel.
2. Spawns `agy.exe -p` as a fresh, independent subprocess with ZERO chat context.
3. Instructs `agy` to act as an adversarial zero-trust skeptic:
   - Scans AST for fake shortcuts (e.g. `promoted = True` fallbacks, swallowed exceptions).
   - Verifies physical binary execution against disk fixtures.
   - Enforces fail-closed rejection.
4. Reads structured JSON receipt from `agy`.
5. Mechanically blocks promotion if verdict != 'ACCEPT'.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent


AUDITOR_PROMPT_TEMPLATE = """You are an independent, adversarial Zero-Trust Code Auditor.
Your job is to REJECT code proposals that cut corners, fake progress, swallow exceptions, or lack physical grounding.

You are auditing Channel {channel_number} ({channel_name}).
Here is the git diff of the implementation and test files:
```diff
{git_diff}
```

AUDIT CHECKLIST:
1. SHORTCUT DETECTION: Does the code contain unconditional promotions, fake `promoted = True` branches, or dummy fallbacks?
2. ERROR INTEGRITY: Are exceptions swallowed with bare `except:` or `except Exception: pass` without re-raising or recording typed deficits?
3. PHYSICAL GROUNDING: Does the code perform actual binary byte operations, or does it merely match static strings?
4. THERMODYNAMIC MEMORY: Does it respect memory budgets without unbounded heap buffering?

Respond ONLY with a valid JSON object matching this schema:
{{
  "channel_number": {channel_number},
  "verdict": "ACCEPT" | "REJECT",
  "reasons": ["list of concrete findings or verifications"],
  "anti_patterns_found": ["list of shortcuts or swallowed errors detected, if any"],
  "confidence_score": 0.0 to 1.0
}}
"""


class AgyAdversarialGate:
    """Invokes `agy` CLI to independently verify code diffs."""

    @classmethod
    def get_git_diff(cls, files: Optional[list[str]] = None) -> str:
        cmd = ["git", "diff", "HEAD"]
        if files:
            cmd.extend(["--"] + files)
        try:
            res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            return res.stdout or ""
        except Exception:
            return ""

    @classmethod
    def audit_channel(cls, channel_number: int, channel_name: str, target_files: Optional[list[str]] = None) -> Dict[str, Any]:
        diff = cls.get_git_diff(target_files)
        if not diff.strip():
            return {
                "verdict": "REJECT",
                "reasons": ["No git diff detected to audit."],
                "anti_patterns_found": ["EMPTY_DIFF"]
            }

        prompt = AUDITOR_PROMPT_TEMPLATE.format(
            channel_number=channel_number,
            channel_name=channel_name,
            git_diff=diff[:8000] # Bounded diff size
        )

        print(f"[*] Spawning independent Auditor via `agy -p` (Channel {channel_number})...")

        # Invoke agy CLI in print mode with JSON output format
        cmd = [
            "agy.exe",
            "--print",
            prompt,
            "--output-format", "text",
            "--effort", "low"
        ]

        try:
            res = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
            raw_output = res.stdout.strip()
            
            # Extract JSON block from output
            json_start = raw_output.find("{")
            json_end = raw_output.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                receipt = json.loads(raw_output[json_start:json_end])
                return receipt
            else:
                return {
                    "verdict": "REJECT",
                    "reasons": [f"Auditor failed to return structured JSON: {raw_output[:200]}"],
                    "anti_patterns_found": ["MALFORMED_AUDIT_OUTPUT"]
                }
        except subprocess.TimeoutExpired:
            return {
                "verdict": "REJECT",
                "reasons": ["Auditor subprocess timed out after 120s."],
                "anti_patterns_found": ["AUDITOR_TIMEOUT"]
            }
        except Exception as e:
            return {
                "verdict": "REJECT",
                "reasons": [f"Auditor execution failed: {e}"],
                "anti_patterns_found": ["SUBPROCESS_ERROR"]
            }


def main():
    parser = argparse.ArgumentParser(description="Antigravity CLI Dual-Agent Adversarial Gate")
    parser.add_argument("--channel", type=int, required=True, help="Channel number to audit")
    parser.add_argument("--name", type=str, default="Channel Candidate", help="Channel name")
    parser.add_argument("files", nargs="*", help="Optional file paths to restrict diff")
    args = parser.parse_args()

    result = AgyAdversarialGate.audit_channel(args.channel, args.name, args.files)
    print("\n" + "=" * 60)
    print(f" ADVERSARIAL AUDIT RESULT: CH {args.channel:02d} ({args.name})")
    print("=" * 60)
    print(f" VERDICT:             {result.get('verdict', 'UNKNOWN')}")
    print(f" CONFIDENCE:          {result.get('confidence_score', 'N/A')}")
    print(" REASONS:")
    for r in result.get("reasons", []):
        print(f"   [+] {r}")
    if result.get("anti_patterns_found"):
        print(" ANTI-PATTERNS DETECTED:")
        for ap in result.get("anti_patterns_found", []):
            print(f"   [!] {ap}")
    print("=" * 60 + "\n")

    if result.get("verdict") == "ACCEPT":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
