"""
Canonical Isometric Projection Engine (CH_GRID_V1)
Matches City Horizon C++ engine projection, anchor math, and camera depth keys.
"""

from dataclasses import dataclass
from typing import Tuple

TILE_WIDTH = 128.0
TILE_HEIGHT = 64.0
MAP_MIN = -24
MAP_MAX = 23


@dataclass
class Camera:
    world_x: float = 0.0
    world_y: float = 0.0
    zoom: float = 1.0
    rotation: int = 0  # 0: 0°, 1: 90°, 2: 180°, 3: 270°


def tile_visual_top_world(tile_x: float, tile_y: float) -> Tuple[float, float]:
    """
    Calculates top vertex of tile in world coordinates matching main.cpp.
    """
    world_x = float(tile_x - tile_y)
    world_y = float(tile_x + tile_y) * 0.5
    return world_x, world_y


def world_to_screen(world_x: float, world_y: float, camera: Camera, viewport_w: float, viewport_h: float) -> Tuple[float, float]:
    """
    Converts world coordinates to screen pixel coordinates matching main.cpp.
    """
    screen_x = (viewport_w * 0.5) + (world_x - camera.world_x) * (64.0 * camera.zoom)
    screen_y = (viewport_h * 0.5) + (world_y - camera.world_y) * (64.0 * camera.zoom)
    return screen_x, screen_y


def screen_to_tile(screen_x: float, screen_y: float, camera: Camera, viewport_w: float, viewport_h: float) -> Tuple[int, int]:
    """
    Converts screen pixel coordinates back to logical integer tile (gridX, gridY).
    """
    world_x = camera.world_x + (screen_x - viewport_w * 0.5) / (64.0 * camera.zoom)
    world_y = camera.world_y + (screen_y - viewport_h * 0.5) / (64.0 * camera.zoom)
    
    # Linear equation system:
    # world_x = tile_x - tile_y
    # 2 * world_y = tile_x + tile_y
    # => tile_x = (2 * world_y + world_x) / 2
    # => tile_y = (2 * world_y - world_x) / 2
    tile_x = int((2.0 * world_y + world_x) // 2)
    tile_y = int((2.0 * world_y - world_x) // 2)
    return tile_x, tile_y


def camera_depth_key(tile_x: float, tile_y: float) -> float:
    """
    Calculates depth key for isometric depth sorting matching main.cpp.
    """
    return float(tile_x + tile_y)
