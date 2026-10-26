"""A* Continental & Tactical Pathfinder with Strict Anti-Corner-Cutting.

Implements:
- 100x100 grid Cartesian pathfinding supporting orthogonal and diagonal movement.
- Strict Anti-Corner-Cutting Law:
  A diagonal step from (x1, y1) to (x2, y2) is strictly barred if either
  intermediate cardinal neighbor (x1, y2) OR (x2, y1) is impassable
  (height == 4, cost >= 99.0, or not passable ground).
- Movement costs by unit type: infantry, cavalry, armored, flying.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# Canonical terrain movement cost table
BASE_TERRAIN_COSTS: Dict[str, Dict[str, float]] = {
    "plains": {"infantry": 1.0, "cavalry": 0.8, "armored": 1.2, "flying": 1.0},
    "forest": {"infantry": 1.5, "cavalry": 2.5, "armored": 2.0, "flying": 1.0},
    "dense_forest": {"infantry": 2.0, "cavalry": 3.5, "armored": 2.5, "flying": 1.0},
    "hills": {"infantry": 2.0, "cavalry": 3.0, "armored": 2.5, "flying": 1.0},
    "swamp": {"infantry": 2.5, "cavalry": 4.0, "armored": 3.0, "flying": 1.0},
    "shallow_water": {"infantry": 2.0, "cavalry": 3.0, "armored": 3.5, "flying": 1.0},
    "deep_water": {"infantry": 99.0, "cavalry": 99.0, "armored": 99.0, "flying": 1.0},
    "high_mountain": {"infantry": 99.0, "cavalry": 99.0, "armored": 99.0, "flying": 1.0},
    "citadel_walls": {"infantry": 99.0, "cavalry": 99.0, "armored": 99.0, "flying": 99.0},
    "fortress_gate": {"infantry": 1.5, "cavalry": 1.5, "armored": 1.5, "flying": 1.0},
    "ruin_void": {"infantry": 1.5, "cavalry": 2.0, "armored": 2.0, "flying": 1.0},
}


class AStarPathfinder:
    """A* Pathfinder on 100x100 grid enforcing strict anti-corner-cutting geometry."""

    WIDTH: int = 100
    HEIGHT: int = 100

    def __init__(
        self,
        world_grid: Optional[Any] = None,
        custom_cost_fn: Optional[Callable[[int, int, str], float]] = None,
    ) -> None:
        self.world_grid = world_grid
        self.custom_cost_fn = custom_cost_fn

    def get_tile_cost(self, x: int, y: int, unit_type: str = "infantry") -> float:
        """Evaluate movement cost for a specific tile and unit type."""
        if not (0 <= x < self.WIDTH and 0 <= y < self.HEIGHT):
            return 99.0

        if self.custom_cost_fn:
            return self.custom_cost_fn(x, y, unit_type)

        if self.world_grid is not None:
            try:
                tile = self.world_grid.get_tile(x, y)
                if not tile.is_passable_ground and unit_type != "flying":
                    return 99.0
                if tile.elevation >= 4 and unit_type != "flying":
                    return 99.0
                terrain_costs = BASE_TERRAIN_COSTS.get(tile.terrain_type, BASE_TERRAIN_COSTS["plains"])
                return terrain_costs.get(unit_type, 1.0)
            except Exception:
                pass

        # Default open plains
        return BASE_TERRAIN_COSTS["plains"].get(unit_type, 1.0)

    def is_tile_impassable(self, x: int, y: int, unit_type: str = "infantry") -> bool:
        """Check if a tile is impassable (cost >= 99.0)."""
        return self.get_tile_cost(x, y, unit_type) >= 99.0

    @staticmethod
    def _heuristic(x1: int, y1: int, x2: int, y2: int) -> float:
        """Octile distance heuristic for 8-directional movement."""
        dx = abs(x1 - x2)
        dy = abs(y1 - y2)
        return max(dx, dy) + (math.sqrt(2.0) - 1.0) * min(dx, dy)

    def find_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        unit_type: str = "infantry",
    ) -> Optional[List[Tuple[int, int]]]:
        """Find lowest-cost path from start to goal.

        Enforces the Strict Anti-Corner-Cutting Law:
        A diagonal move from (x, y) to (x+dx, y+dy) is blocked if (x+dx, y) OR (x, y+dy)
        is impassable.
        """
        sx, sy = start
        gx, gy = goal

        if not (0 <= sx < self.WIDTH and 0 <= sy < self.HEIGHT):
            return None
        if not (0 <= gx < self.WIDTH and 0 <= gy < self.HEIGHT):
            return None

        if start == goal:
            return [start]

        if self.is_tile_impassable(gx, gy, unit_type):
            return None

        # Priority queue entries: (f_score, counter, (x, y))
        counter = 0
        open_set: List[Tuple[float, int, Tuple[int, int]]] = []
        heapq.heappush(open_set, (self._heuristic(sx, sy, gx, gy), counter, start))

        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0.0}

        # 8 directions
        directions = [
            (1, 0), (-1, 0), (0, 1), (0, -1),      # Orthogonal
            (1, 1), (1, -1), (-1, 1), (-1, -1),    # Diagonal
        ]

        while open_set:
            _, _, current = heapq.heappop(open_set)
            cx, cy = current

            if current == goal:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy

                # Bounds check
                if not (0 <= nx < self.WIDTH and 0 <= ny < self.HEIGHT):
                    continue

                # Diagonal move check: Anti-Corner-Cutting Law
                if dx != 0 and dy != 0:
                    # Intermediate cardinal tiles: (cx + dx, cy) and (cx, cy + dy)
                    cardinal_1_impassable = self.is_tile_impassable(cx + dx, cy, unit_type)
                    cardinal_2_impassable = self.is_tile_impassable(cx, cy + dy, unit_type)

                    if cardinal_1_impassable or cardinal_2_impassable:
                        # STRICT LAW: Diagonal move completely barred
                        continue

                # Target tile cost
                tile_cost = self.get_tile_cost(nx, ny, unit_type)
                if tile_cost >= 99.0:
                    continue

                # Step cost: diagonal is sqrt(2) * tile_cost
                step_mult = math.sqrt(2.0) if (dx != 0 and dy != 0) else 1.0
                tentative_g = g_score[current] + (tile_cost * step_mult)

                neighbor = (nx, ny)
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score = tentative_g + self._heuristic(nx, ny, gx, gy)
                    counter += 1
                    heapq.heappush(open_set, (f_score, counter, neighbor))

        return None
