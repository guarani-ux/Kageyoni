#!/usr/bin/env python3
"""
Entry point for Vantage: Organizational Video Development & Production System.
"""
import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from kageyoni.vantage.cli import main

if __name__ == "__main__":
    main()
