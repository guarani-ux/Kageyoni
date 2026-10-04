#!/usr/bin/env python3
"""
Root Entrypoint for Constellation Emergence All-in-One Workflow.
Runs all steps end-to-end:
1. Substrate & Carrier Inventorying
2. Character Provisioning (8 Characters: Voss, Sebastian, Sciel, Alexandra, Elijah, Second Queen, Arianne, Maki)
3. Preflight & Testability Audit
4. 10-Round Live Encounter Execution
5. Post-Run Multi-View Matrix Comparison
6. Direct Observational Reality Report
"""

import os
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from kageyoni.emergence.workflow import EmergenceFullWorkflow


def main():
    workflow = EmergenceFullWorkflow(repo_root=REPO_ROOT)
    workflow.run_all()


if __name__ == "__main__":
    main()
