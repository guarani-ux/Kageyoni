"""
Kageyoni Spatial Continuum - Tactical Micro-Grid Viewport & ASCII Visualization.

Provides dynamic 16x16 tactical combat arenas extracted from the continuous 100x100
world, Line-Of-Sight (LOS) obstruction tracing, cover bonus calculations, and
dual-tier ASCII renderers (10x10 Macro Sector Map and 16x16 Micro Tactical Zoom).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from kageyoni.spatial.grid import WorldGrid, WorldTile


@dataclass
class TacticalUnit:
    """Represents a unit entity placed on the tactical micro-grid."""
    unit_id: str
    faction: str
    glyph: str
    name: str = ""
    elevation: int = 1


class TacticalMicroGrid:
    """
    16x16 Tactical Combat Sub-Grid extracted from the WorldGrid.
    Provides local-to-world coordinate translation, line-of-sight analysis,
    and cover bonus queries.
    """

    WIDTH: int = 16
    HEIGHT: int = 16

    def __init__(self, world_grid: WorldGrid, center_x: int, center_y: int):
        self.world_grid = world_grid
        self.center_x = center_x
        self.center_y = center_y

        # Clamp origin [x0, y0] so the 16x16 window stays strictly within [0, 99]
        self.origin_x = max(0, min(center_x - (self.WIDTH // 2), world_grid.WIDTH - self.WIDTH))
        self.origin_y = max(0, min(center_y - (self.HEIGHT // 2), world_grid.HEIGHT - self.HEIGHT))

        self.tiles: List[List[WorldTile]] = []
        self._extract_tiles()

        self.units: Dict[Tuple[int, int], TacticalUnit] = {}

    def _extract_tiles(self) -> None:
        """Extracts the 16x16 grid of WorldTile references."""
        self.tiles = []
        for ly in range(self.HEIGHT):
            row: List[WorldTile] = []
            for lx in range(self.WIDTH):
                wx = self.origin_x + lx
                wy = self.origin_y + ly
                row.append(self.world_grid.get_tile(wx, wy))
            self.tiles.append(row)

    def get_local_tile(self, lx: int, ly: int) -> WorldTile:
        """Gets tile at local viewport coordinate (lx, ly) in [0, 15] x [0, 15]."""
        if not (0 <= lx < self.WIDTH and 0 <= ly < self.HEIGHT):
            raise IndexError(f"Local coordinates ({lx}, {ly}) outside 16x16 viewport.")
        return self.tiles[ly][lx]

    def to_world_coords(self, lx: int, ly: int) -> Tuple[int, int]:
        """Translates local viewport (lx, ly) to world coordinates (wx, wy)."""
        return self.origin_x + lx, self.origin_y + ly

    def to_local_coords(self, wx: int, wy: int) -> Optional[Tuple[int, int]]:
        """Translates world coordinates (wx, wy) to local (lx, ly) if inside viewport."""
        lx = wx - self.origin_x
        ly = wy - self.origin_y
        if 0 <= lx < self.WIDTH and 0 <= ly < self.HEIGHT:
            return lx, ly
        return None

    def place_unit(self, lx: int, ly: int, unit: TacticalUnit) -> None:
        """Places a tactical unit at local coordinate (lx, ly)."""
        if not (0 <= lx < self.WIDTH and 0 <= ly < self.HEIGHT):
            raise IndexError(f"Local coordinate ({lx}, {ly}) out of bounds.")
        self.units[(lx, ly)] = unit

    def remove_unit(self, lx: int, ly: int) -> Optional[TacticalUnit]:
        """Removes and returns a unit at local coordinate (lx, ly)."""
        return self.units.pop((lx, ly), None)

    def get_cover_bonus(self, lx: int, ly: int) -> Tuple[float, float]:
        """Returns (defense_bonus, avoid_bonus) for tile at local (lx, ly)."""
        tile = self.get_local_tile(lx, ly)
        return tile.defense_bonus, tile.avoid_bonus

    def has_line_of_sight(self, from_local: Tuple[int, int], to_local: Tuple[int, int]) -> bool:
        """
        Calculates unobstructed Line of Sight using Bresenham Raycast.
        Ray is blocked if any intermediate tile has blocks_los == True,
        or if intervening terrain elevation exceeds max(elevation_start, elevation_end).
        """
        x0, y0 = from_local
        x1, y1 = to_local

        if not (0 <= x0 < self.WIDTH and 0 <= y0 < self.HEIGHT):
            raise IndexError(f"Start coordinate ({x0}, {y0}) out of viewport bounds.")
        if not (0 <= x1 < self.WIDTH and 0 <= y1 < self.HEIGHT):
            raise IndexError(f"Target coordinate ({x1}, {y1}) out of viewport bounds.")

        if (x0, y0) == (x1, y1):
            return True

        start_tile = self.get_local_tile(x0, y0)
        target_tile = self.get_local_tile(x1, y1)
        max_vantage_elevation = max(start_tile.elevation, target_tile.elevation)

        # Bresenham's line algorithm
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        curr_x, curr_y = x0, y0

        while True:
            # Advance ray
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy

            if (curr_x, curr_y) == (x1, y1):
                # Target reached without intermediate obstruction
                break

            # Intermediate tile check
            inter_tile = self.get_local_tile(curr_x, curr_y)
            if inter_tile.blocks_los:
                return False
            if inter_tile.elevation > max_vantage_elevation:
                return False

        return True


class ViewportRenderer:
    """
    Renders formatted ASCII maps for macro sector overview (10x10 chunks)
    and micro tactical viewports (16x16 tiles).
    """

    @staticmethod
    def render_macro_ascii(world_grid: WorldGrid) -> str:
        """
        Renders a 10x10 Macro Sector Map representing the 100 chunks.
        Displays concentric zones, barriers, and faction fortresses.
        """
        lines: List[str] = []
        lines.append("=== KAGEYŌNI CONTINENTAL SECTOR MAP (10x10 CHUNKS) ===")
        lines.append("    " + " ".join(f"{c:1d}" for c in range(10)))
        lines.append("   +" + "-" * 20 + "+")

        for cy in range(10):
            row_chars: List[str] = []
            for cx in range(10):
                chunk_id = cy * 10 + cx
                chunk_tiles = world_grid.get_chunk_tiles(chunk_id)

                # Check if chunk contains Spire, Barrier, Pass, or faction stronghold
                has_spire = any(t.zone_id == 30 for t in chunk_tiles)
                has_ring2 = any(t.zone_id == 20 for t in chunk_tiles)
                has_ring1 = any(t.zone_id == 10 for t in chunk_tiles)
                has_pass = any(t.pass_id is not None for t in chunk_tiles)

                factions = [t.controlling_faction for t in chunk_tiles if t.controlling_faction]

                if has_spire:
                    char = "S"  # World Spire
                elif has_pass:
                    char = "P"  # Pass Fortress
                elif has_ring2:
                    char = "2"  # Ring 2 Barrier
                elif has_ring1:
                    char = "1"  # Ring 1 Barrier
                elif factions:
                    # Most frequent faction's initial
                    char = factions[0][0].upper()
                else:
                    avg_zone = chunk_tiles[len(chunk_tiles) // 2].zone_id
                    if avg_zone == 3:
                        char = "C"  # Core
                    elif avg_zone == 2:
                        char = "M"  # Marches
                    else:
                        char = "O"  # Outer Rim
                row_chars.append(char)

            lines.append(f"{cy:2d} |" + " ".join(row_chars) + "|")

        lines.append("   +" + "-" * 20 + "+")
        lines.append("LEGEND: S: Spire | 1: Ring 1 Barrier | 2: Ring 2 Barrier | P: Pass Gate")
        lines.append("        O: Outer Rim | M: Marches | C: Core | [A-Z]: Faction Grip")
        return "\n".join(lines)

    @staticmethod
    def render_micro_ascii(viewport: TacticalMicroGrid) -> str:
        """
        Renders a 16x16 Tactical Zoom arena with coordinate axes, terrain glyphs,
        placed unit markers, and cover / defense bonuses.
        """
        lines: List[str] = []
        wx0, wy0 = viewport.origin_x, viewport.origin_y
        wx1, wy1 = wx0 + viewport.WIDTH - 1, wy0 + viewport.HEIGHT - 1

        lines.append(f"=== TACTICAL COMBAT VIEWPORT (16x16) World Bounds: [{wx0:02d}..{wx1:02d}, {wy0:02d}..{wy1:02d}] ===")

        # Column header
        header = "    " + " ".join(f"{x:2d}" for x in range(viewport.WIDTH))
        lines.append(header)
        lines.append("   +" + "-" * (viewport.WIDTH * 3) + "+")

        for ly in range(viewport.HEIGHT):
            row_symbols: List[str] = []
            for lx in range(viewport.WIDTH):
                if (lx, ly) in viewport.units:
                    u = viewport.units[(lx, ly)]
                    symbol = f"[{u.glyph}]"
                else:
                    tile = viewport.get_local_tile(lx, ly)
                    symbol = f" {tile.glyph} "
                row_symbols.append(symbol)
            lines.append(f"{ly:2d} |" + "".join(row_symbols) + f"| {wy0 + ly:02d}")

        lines.append("   +" + "-" * (viewport.WIDTH * 3) + "+")
        lines.append("TERRAIN GLYPHS:")
        lines.append(" . : Plains (+0% Def, +0% Avo)       | ▲ : High Mountain (+40% Def, Impassable)")
        lines.append(" ♣ : Forest (+20% Def, +15% Avo)     | # : Fortress Gate (+40% Def, Chokepoint)")
        lines.append(" ♠ : Dense Canopy (+30% Def, BlkLOS) | █ : Citadel Wall (+50% Def, Impassable)")
        lines.append(" ∩ : Rolling Hills (+15% Def)        | x : Enton Glassed Ruin (-15% Def)")
        return "\n".join(lines)
