"""Kageyōni Spatial Continuum Subsystem (Phase 2 Core Mechanical Engine).

Synthesizes:
- 100x100 Continental Cartesian World Grid & Concentric Zones (Outer Rim, Barriers, Core, Spire).
- 16x16 Tactical Micro-Grid Viewport, Line-Of-Sight Raycasting, & ASCII Visualization.
- A* Tactical Pathfinder with Strict Anti-Corner-Cutting Law.
- Corridor Supply Logistics & Garrison Attrition Engine.
- Kalpa Revision Engine & Samsara Molt Milestones (50% Pass 2, 80% Pass 3, 100% Kalpa Molt).
"""

from .grid import (
    WorldGrid,
    WorldTile,
)
from .viewport import (
    TacticalMicroGrid,
    TacticalUnit,
    ViewportRenderer,
)
from .pathfinding import (
    AStarPathfinder,
    BASE_TERRAIN_COSTS,
)
from .supply import (
    CorridorSupplyEngine,
    CorridorState,
    CorridorTickResult,
)
from .kalpa import (
    KalpaRevisionEngine,
    KalpaStatus,
    KalpaRevisionReport,
)

# Canonical Architectural Aliases
ContinentalGrid = WorldGrid
TacticalViewport = TacticalMicroGrid

__all__ = [
    # Grid & Topology
    "ContinentalGrid",
    "WorldGrid",
    "WorldTile",
    # Viewport & ASCII
    "TacticalViewport",
    "TacticalMicroGrid",
    "TacticalUnit",
    "ViewportRenderer",
    # Pathfinding
    "AStarPathfinder",
    "BASE_TERRAIN_COSTS",
    # Supply
    "CorridorSupplyEngine",
    "CorridorState",
    "CorridorTickResult",
    # Kalpa
    "KalpaRevisionEngine",
    "KalpaStatus",
    "KalpaRevisionReport",
]
