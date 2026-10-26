"""
Kageyoni Spatial Continuum - Continental World Grid & Topology Engine.

Implements the 10,000-tile Cartesian continuous grid ([0, 99] x [0, 99]),
10x10 spatial chunks, concentric radial gating zones, starter provinces,
and pass catalog footprints.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class WorldTile:
    """Represents a single tile in the 100x100 continental grid."""
    tile_index: int
    x: int
    y: int
    chunk_id: int
    zone_id: int
    zone_name: str
    province_id: int
    province_name: str
    terrain_type: str
    elevation: int
    canopy_height: int
    defense_bonus: float
    avoid_bonus: float
    blocks_los: bool
    glyph: str
    is_passable_ground: bool
    is_glassed_ruin: bool = False
    controlling_faction: Optional[str] = None
    influence_score: float = 0.0
    pass_id: Optional[str] = None
    pass_level: Optional[int] = None
    pass_unsealed: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_index": self.tile_index,
            "x": self.x,
            "y": self.y,
            "chunk_id": self.chunk_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "province_id": self.province_id,
            "province_name": self.province_name,
            "terrain_type": self.terrain_type,
            "elevation": self.elevation,
            "canopy_height": self.canopy_height,
            "defense_bonus": self.defense_bonus,
            "avoid_bonus": self.avoid_bonus,
            "blocks_los": self.blocks_los,
            "glyph": self.glyph,
            "is_passable_ground": self.is_passable_ground,
            "is_glassed_ruin": self.is_glassed_ruin,
            "controlling_faction": self.controlling_faction,
            "influence_score": self.influence_score,
            "pass_id": self.pass_id,
            "pass_level": self.pass_level,
            "pass_unsealed": self.pass_unsealed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorldTile:
        return cls(**data)


class WorldGrid:
    """
    Continuous Cartesian 100x100 Grid (10,000 tiles).
    Maps coordinates to 10x10 chunks, concentric zones, starter provinces,
    and barrier passes.
    """

    WIDTH: int = 100
    HEIGHT: int = 100
    TOTAL_TILES: int = 10000
    CHUNK_SIZE: int = 10
    CENTROID: Tuple[float, float] = (49.5, 49.5)

    def __init__(self, topology_path: Optional[str | Path] = None, seed: int = 1337):
        self.seed = seed
        self.topology_path = self._resolve_topology_path(topology_path)
        with open(self.topology_path, "r", encoding="utf-8") as f:
            self.topology = json.load(f)

        self.terrain_matrix: Dict[str, Dict[str, Any]] = {
            t["id"]: t for t in self.topology.get("terrain_matrix", [])
        }
        self.pass_catalog: List[Dict[str, Any]] = self.topology.get("pass_catalog", [])
        self.starter_provinces: List[Dict[str, Any]] = self.topology.get("starter_provinces", [])
        self.pass_lookup: Dict[str, Dict[str, Any]] = {p["pass_id"]: p for p in self.pass_catalog}

        self.tiles: List[WorldTile] = []
        self.tiles_by_coord: Dict[Tuple[int, int], WorldTile] = {}
        self.chunks: Dict[int, List[WorldTile]] = {c: [] for c in range(100)}
        self.pass_tiles: Dict[str, List[WorldTile]] = {}

        self._build_grid()

    @staticmethod
    def _resolve_topology_path(path: Optional[str | Path]) -> Path:
        if path:
            p = Path(path)
            if p.exists():
                return p
        default = Path(__file__).resolve().parent.parent.parent / "data" / "world_topology.json"
        if default.exists():
            return default
        alt = Path("data/world_topology.json").resolve()
        if alt.exists():
            return alt
        raise FileNotFoundError(f"world_topology.json not found at {path} or {default}")

    @staticmethod
    def coordinate_to_chunk_id(x: int, y: int) -> int:
        """
        Calculates chunk_id = (y // 10) * 10 + (x // 10).
        Valid chunk_id in range [0, 99].
        """
        if not (0 <= x < 100 and 0 <= y < 100):
            raise ValueError(f"Coordinates ({x}, {y}) out of continental bounds [0, 99].")
        return (y // 10) * 10 + (x // 10)

    @classmethod
    def evaluate_radial_zone(cls, x: int, y: int) -> Tuple[int, str, float]:
        """
        Concentric Radial Zone evaluation from centroid (49.5, 49.5).
        Returns: (zone_id, zone_name, radius)
          - Spire Bounds [48, 51] x [48, 51]: (30, 'WORLD_SPIRE', R)
          - Zone 1 Outer Rim (R > 37.0): (1, 'ZONE_1_OUTER_RIM', R)
          - Ring 1 Barrier (35.0 <= R <= 37.0, height 4): (10, 'RING_1_BARRIER', R)
          - Zone 2 Marches (20.0 < R < 35.0): (2, 'ZONE_2_MARCHES', R)
          - Ring 2 Barrier (18.0 <= R <= 20.0, height 4): (20, 'RING_2_BARRIER', R)
          - Zone 3 Core & World Spire (R <= 18.0): (3, 'ZONE_3_CORE', R)
        """
        cx, cy = cls.CENTROID
        dx = x - cx
        dy = y - cy
        r = math.sqrt(dx * dx + dy * dy)

        # Spire Bounds check [48, 51] x [48, 51]
        if 48 <= x <= 51 and 48 <= y <= 51:
            return 30, "WORLD_SPIRE", r

        if r > 37.0:
            return 1, "ZONE_1_OUTER_RIM", r
        elif 35.0 <= r <= 37.0:
            return 10, "RING_1_BARRIER", r
        elif 20.0 < r < 35.0:
            return 2, "ZONE_2_MARCHES", r
        elif 18.0 <= r <= 20.0:
            return 20, "RING_2_BARRIER", r
        else:
            return 3, "ZONE_3_CORE", r

    def evaluate_azimuth_province(self, x: int, y: int) -> Tuple[int, str]:
        """
        Maps (x, y) to one of the 8 starter provinces based on azimuth angle from centroid.
        Azimuth 0 deg = North (dx = 0, dy < 0), clockwise.
        """
        cx, cy = self.CENTROID
        dx = x - cx
        dy = y - cy
        # atan2(dx, -dy) gives angle from North (+y is South on 2D grid)
        deg = math.degrees(math.atan2(dx, -dy))
        deg = (deg + 360.0) % 360.0

        for prov in self.starter_provinces:
            min_deg, max_deg = prov["azimuth_range_deg"]
            if min_deg > max_deg:
                # Wraps around North (337.5 to 22.5)
                if deg >= min_deg or deg < max_deg:
                    return prov["province_id"], prov["name"]
            else:
                if min_deg <= deg < max_deg:
                    return prov["province_id"], prov["name"]

        # Default fallback
        return 1, "Frostfall Highlands"

    def _find_pass_for_coord(self, x: int, y: int) -> Optional[Dict[str, Any]]:
        """Checks if (x, y) falls within the footprint of any known pass fortress."""
        for p in self.pass_catalog:
            fp = p["footprint"]
            if fp["x_min"] <= x <= fp["x_max"] and fp["y_min"] <= y <= fp["y_max"]:
                return p
        return None

    def _build_grid(self) -> None:
        """Constructs and initializes all 10,000 tiles with topology rules."""
        self.tiles = []
        self.tiles_by_coord = {}
        for c in range(100):
            self.chunks[c] = []

        plains_spec = self.terrain_matrix.get("plains", {
            "height": 1, "defense_bonus": 0.0, "avoid_bonus": 0.0,
            "blocks_los": False, "canopy_height": 0, "glyph": "."
        })
        gate_spec = self.terrain_matrix.get("fortress_gate", {
            "height": 3, "defense_bonus": 0.4, "avoid_bonus": 0.2,
            "blocks_los": True, "canopy_height": 0, "glyph": "#"
        })
        wall_spec = self.terrain_matrix.get("citadel_walls", {
            "height": 4, "defense_bonus": 0.5, "avoid_bonus": 0.3,
            "blocks_los": True, "canopy_height": 0, "glyph": "█"
        })
        mountain_spec = self.terrain_matrix.get("high_mountain", {
            "height": 4, "defense_bonus": 0.4, "avoid_bonus": 0.2,
            "blocks_los": True, "canopy_height": 0, "glyph": "▲"
        })

        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                tile_idx = y * self.WIDTH + x
                chunk_id = self.coordinate_to_chunk_id(x, y)
                zone_id, zone_name, radius = self.evaluate_radial_zone(x, y)
                prov_id, prov_name = self.evaluate_azimuth_province(x, y)

                pass_info = self._find_pass_for_coord(x, y)

                # Default tile values
                pass_id = None
                pass_level = None
                pass_unsealed = True

                if pass_info:
                    pass_id = pass_info["pass_id"]
                    pass_level = pass_info["level"]
                    # By default Pass 1 is open, Pass 2 & Pass 3 start sealed until conquest thresholds
                    pass_unsealed = (pass_level == 1)

                    terrain_type = "fortress_gate"
                    elevation = gate_spec["height"]
                    defense_bonus = gate_spec["defense_bonus"]
                    avoid_bonus = gate_spec["avoid_bonus"]
                    blocks_los = gate_spec["blocks_los"]
                    canopy_height = gate_spec.get("canopy_height", 0)
                    glyph = gate_spec["glyph"]
                    is_passable_ground = pass_unsealed
                elif zone_id == 30:  # World Spire
                    terrain_type = "citadel_walls"
                    elevation = wall_spec["height"]
                    defense_bonus = wall_spec["defense_bonus"]
                    avoid_bonus = wall_spec["avoid_bonus"]
                    blocks_los = wall_spec["blocks_los"]
                    canopy_height = wall_spec.get("canopy_height", 0)
                    glyph = wall_spec["glyph"]
                    is_passable_ground = False
                elif zone_id in (10, 20):  # Ring 1 Barrier or Ring 2 Barrier (High Mountain)
                    terrain_type = "high_mountain"
                    elevation = mountain_spec["height"]
                    defense_bonus = mountain_spec["defense_bonus"]
                    avoid_bonus = mountain_spec["avoid_bonus"]
                    blocks_los = mountain_spec["blocks_los"]
                    canopy_height = mountain_spec.get("canopy_height", 0)
                    glyph = mountain_spec["glyph"]
                    is_passable_ground = False
                else:
                    # Procedural deterministic regional terrain
                    terrain_type, spec = self._generate_regional_terrain(x, y, prov_id, zone_id)
                    elevation = spec["height"]
                    defense_bonus = spec["defense_bonus"]
                    avoid_bonus = spec["avoid_bonus"]
                    blocks_los = spec["blocks_los"]
                    canopy_height = spec.get("canopy_height", 0)
                    glyph = spec["glyph"]
                    is_passable_ground = (elevation < 4 and terrain_type != "deep_water")

                tile = WorldTile(
                    tile_index=tile_idx,
                    x=x,
                    y=y,
                    chunk_id=chunk_id,
                    zone_id=zone_id,
                    zone_name=zone_name,
                    province_id=prov_id,
                    province_name=prov_name,
                    terrain_type=terrain_type,
                    elevation=elevation,
                    canopy_height=canopy_height,
                    defense_bonus=defense_bonus,
                    avoid_bonus=avoid_bonus,
                    blocks_los=blocks_los,
                    glyph=glyph,
                    is_passable_ground=is_passable_ground,
                    pass_id=pass_id,
                    pass_level=pass_level,
                    pass_unsealed=pass_unsealed,
                )

                self.tiles.append(tile)
                self.tiles_by_coord[(x, y)] = tile
                self.chunks[chunk_id].append(tile)
                if pass_id:
                    self.pass_tiles.setdefault(pass_id, []).append(tile)

    def _generate_regional_terrain(
        self, x: int, y: int, prov_id: int, zone_id: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates thematic deterministic terrain for regional tiles."""
        h = int(math.sin(x * 12.9898 + y * 78.233 + self.seed) * 43758.5453) % 100

        # Province flavors
        if prov_id == 2:  # Crescent Fen
            if h < 30:
                t = "swamp"
            elif h < 45:
                t = "shallow_water"
            elif h < 65:
                t = "forest"
            else:
                t = "plains"
        elif prov_id in (1, 6):  # Frostfall Highlands / Ironcliffs Mesa
            if h < 35:
                t = "hills"
            elif h < 55:
                t = "forest"
            else:
                t = "plains"
        elif prov_id == 8:  # Shadowwood Ridge
            if h < 35:
                t = "dense_forest"
            elif h < 60:
                t = "forest"
            else:
                t = "plains"
        elif prov_id in (4, 5):  # Tidecrag Reach / Verdant Delta
            if h < 20:
                t = "shallow_water"
            elif h < 45:
                t = "forest"
            else:
                t = "plains"
        else:
            if h < 20:
                t = "forest"
            elif h < 35:
                t = "hills"
            else:
                t = "plains"

        spec = self.terrain_matrix.get(t, self.terrain_matrix.get("plains", {
            "height": 1, "defense_bonus": 0.0, "avoid_bonus": 0.0,
            "blocks_los": False, "canopy_height": 0, "glyph": "."
        }))
        return t, spec

    def get_tile(self, x: int, y: int) -> WorldTile:
        """Retrieves tile by (x, y) coordinates."""
        if (x, y) not in self.tiles_by_coord:
            raise IndexError(f"Coordinates ({x}, {y}) out of world bounds [0, 99].")
        return self.tiles_by_coord[(x, y)]

    def get_tile_by_index(self, index: int) -> WorldTile:
        """Retrieves tile by its index [0, 9999]."""
        if not (0 <= index < self.TOTAL_TILES):
            raise IndexError(f"Tile index {index} out of range [0, 9999].")
        return self.tiles[index]

    def get_chunk_tiles(self, chunk_id: int) -> List[WorldTile]:
        """Retrieves all 100 tiles for the given chunk_id [0, 99]."""
        if chunk_id not in self.chunks:
            raise IndexError(f"Chunk id {chunk_id} out of range [0, 99].")
        return self.chunks[chunk_id]

    def set_tile_faction(self, x: int, y: int, faction: Optional[str]) -> None:
        """Sets the controlling faction of tile (x, y)."""
        tile = self.get_tile(x, y)
        tile.controlling_faction = faction

    def set_pass_unsealed(self, pass_id: str, unsealed: bool = True) -> None:
        """Sets the unseal state of a pass and updates all its footprint tiles."""
        if pass_id not in self.pass_tiles:
            return
        for tile in self.pass_tiles[pass_id]:
            tile.pass_unsealed = unsealed
            tile.is_passable_ground = unsealed

    def glass_tile(self, x: int, y: int) -> None:
        """Transforms tile into an Enton Ruin Void (glassed crater)."""
        tile = self.get_tile(x, y)
        ruin_spec = self.terrain_matrix.get("ruin_void", {
            "height": 0, "defense_bonus": -0.15, "avoid_bonus": -0.1,
            "blocks_los": False, "canopy_height": 0, "glyph": "x"
        })
        tile.terrain_type = "ruin_void"
        tile.is_glassed_ruin = True
        tile.elevation = ruin_spec["height"]
        tile.defense_bonus = ruin_spec["defense_bonus"]
        tile.avoid_bonus = ruin_spec["avoid_bonus"]
        tile.blocks_los = ruin_spec["blocks_los"]
        tile.glyph = ruin_spec["glyph"]
        tile.is_passable_ground = True
