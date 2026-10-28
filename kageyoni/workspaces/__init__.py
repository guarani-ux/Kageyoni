"""Kageyōni Workspaces Subsystem.

Sandboxed subagent execution pipelines, workspace repositories, documents,
transitions, and shared world encounters.
"""

from .contracts import KINDS, checkpoint
from .documents import Documents
from .pipeline import Pipelines, verify_pipelines
from .registry import Registry, verify_workspaces
from .repository import Repository, tree_digest
from .transitions import Transitions
from .world import Encounters, verify_encounters

__all__ = [
    "checkpoint",
    "Documents",
    "Encounters",
    "KINDS",
    "Pipelines",
    "Registry",
    "Repository",
    "Transitions",
    "tree_digest",
    "verify_encounters",
    "verify_pipelines",
    "verify_workspaces",
]
