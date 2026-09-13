"""
Canonical Isometric Projection Engine (CH_GRID_V1).
Delegates all projection, rotation, and depth key calculation to C++ city_horizon_native.
"""

from dataclasses import dataclass
from typing import Tuple
from tools.map_forge.core.native_bridge import get_native_core

_ch = get_native_core()

TILE_WIDTH = float(_ch.kTileWidth) if _ch else 128.0
TILE_HEIGHT = float(_ch.kTileHeight) if _ch else 64.0
MAP_MIN = int(_ch.kMapMin) if _ch else -24
MAP_MAX = int(_ch.kMapMax) if _ch else 23


@dataclass
class Camera:
    world_x: float = 0.0
    world_y: float = 0.0
    zoom: float = 1.0
    rotation: int = 0  # 0: 0°, 1: 90°, 2: 180°, 3: 270°


def tile_visual_top_world(tile_x: float, tile_y: float) -> Tuple[float, float]:
    """Calculates top vertex of tile in world coordinates using C++ native core."""
    ch = get_native_core()
    pt = ch.tile_visual_top_world(int(tile_x), int(tile_y), ch.CameraRotation(0))
    return pt.x, pt.y


def world_to_screen(world_x: float, world_y: float, camera: Camera, viewport_w: float, viewport_h: float) -> Tuple[float, float]:
    """Converts world coordinates to screen pixel coordinates using C++ native core."""
    ch = get_native_core()
    cs = ch.CameraState()
    cs.pan_x = camera.world_x
    cs.pan_y = camera.world_y
    cs.zoom = camera.zoom
    cs.rotation = ch.CameraRotation(camera.rotation)
    sp = ch.world_to_screen_point(world_x, world_y, cs, viewport_w, viewport_h)
    return sp.x, sp.y


def screen_to_tile(screen_x: float, screen_y: float, camera: Camera, viewport_w: float, viewport_h: float) -> Tuple[int, int]:
    """Converts screen pixel coordinates back to logical integer tile using C++ native core."""
    ch = get_native_core()
    cs = ch.CameraState()
    cs.pan_x = camera.world_x
    cs.pan_y = camera.world_y
    cs.zoom = camera.zoom
    cs.rotation = ch.CameraRotation(camera.rotation)
    gc = ch.screen_to_tile_coord(screen_x, screen_y, cs, viewport_w, viewport_h)
    return gc.x, gc.y


def camera_depth_key(tile_x: float, tile_y: float) -> float:
    """Calculates depth key for isometric depth sorting using C++ native core."""
    ch = get_native_core()
    cs = ch.CameraState()
    return ch.camera_depth_key(float(tile_x), float(tile_y), cs)
