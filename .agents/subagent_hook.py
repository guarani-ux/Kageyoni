#!/usr/bin/env python3
"""PreToolUse hook entrypoint for Subagent Forge in Kageyoni."""
import sys
from pathlib import Path

# Ensure repo root is on sys.path
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from tools.subagent import main

if __name__ == "__main__":
    sys.exit(main(["hook", "pre"]))
