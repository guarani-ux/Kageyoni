#!/usr/bin/env python3
"""
Entry point for Constellation Emergence CLI.
"""
import sys
from pathlib import Path

# Ensure root directory is always on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from kageyoni.emergence.cli import main

if __name__ == "__main__":
    main()
