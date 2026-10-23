#!/usr/bin/env python3
"""Root forwarder shim to cognitive-os/scripts/cos_cli.py."""
import subprocess
import sys
from pathlib import Path

target = Path(__file__).resolve().parent.parent / "cognitive-os" / "scripts" / "cos_cli.py"
if not target.exists():
    print(f"Error: Cognitive OS CLI not found at {target}", file=sys.stderr)
    sys.exit(1)

proc = subprocess.run([sys.executable, str(target)] + sys.argv[1:], cwd=str(target.parent.parent))
sys.exit(proc.returncode)
