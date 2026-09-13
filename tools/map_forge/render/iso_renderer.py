"""
PySide6 QPainter Isometric Renderer for Map Forge.
Matches main.cpp C++ engine projection, artScale, anchors, depth key sorting, and asset paths.
"""

import os
from typing import Dict, Any, Optional
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtCore import QPointF, QRectF

from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.projection import (
    Camera, MAP_MIN, MAP_MAX, TILE_WIDTH, TILE_HEIGHT,
    world_to_screen, camera_depth_key
)


class TextureCachePySide:
    """Caches PySide6 QPixmaps loaded from build/assets/."""
    def __init__(self, asset_root: str):
        self.asset_root = asset_root
        self._cache: Dict[str, QPixmap] = {}

    def get(self, rel_path: str) -> Optional[QPixmap]:
        if not rel_path:
            return None
        if rel_path in self._cache:
            return self._cache[rel_path]

        full_path = os.path.join(self.asset_root, rel_path)
        if not os.path.exists(full_path):
            # Try path as given if relative to asset_root or build
            full_path = os.path.join(self.asset_root, rel_path.lstrip("/\\"))

        if os.path.exists(full_path):
            pixmap = QPixmap(full_path)
            self._cache[rel_path] = pixmap
            return pixmap
        return None


class IsoRendererPySide:
    def __init__(self, asset_root: str, building_catalog: Dict[str, Dict[str, Any]]):
        self.asset_root = asset_root
        self.building_catalog = building_catalog
        self.textures = TextureCachePySide(asset_root)

    def render(self, painter: QPainter, map_model: MapModel, camera: Camera, viewport_w: float, viewport_h: float):
        # 1. Fill background matching main.cpp (RGB: 74, 104, 83)
        painter.fillRect(0, 0, int(viewport_w), int(viewport_h), QColor(74, 104, 83))

        # Load grass base texture
        grass_pixmap = self.textures.get("assets/terrain/grass_isometric_01.png")

        # Create quick lookup map for custom scenario terrain tiles
        terrain_map: Dict[tuple, str] = {}
        for t in map_model.terrain_tiles:
            tx, ty = t.get("tileX", 0), t.get("tileY", 0)
            tex = t.get("texture", "")
            if tex:
                terrain_map[(tx, ty)] = tex

        # 2. Render Ground Terrain (depth loop matching main.cpp render_map)
        for depth in range(MAP_MIN * 2, MAP_MAX * 2 + 1):
            first_x = max(MAP_MIN, depth - MAP_MAX)
            last_x = min(MAP_MAX, depth - MAP_MIN)
            for x in range(first_x, last_x + 1):
                y = depth - x
                world_x = float(x - y)
                world_y = float(x + y) * 0.5

                screen_x, screen_y = world_to_screen(world_x, world_y, camera, viewport_w, viewport_h)

                custom_tex_path = terrain_map.get((x, y))
                pixmap = self.textures.get(custom_tex_path) if custom_tex_path else grass_pixmap

                if pixmap and not pixmap.isNull():
                    pw = pixmap.width() * camera.zoom
                    ph = pixmap.height() * camera.zoom
                    dest_x = screen_x - (pw * 0.5)
                    dest_y = screen_y
                    painter.drawPixmap(QRectF(dest_x, dest_y, pw, ph), pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))

        # 3. Render Buildings & Preplaced Infrastructure (depth sorted)
        buildings_to_draw = []
        for instance in map_model.buildings:
            def_id = instance.get("definitionId", "")
            definition = self.building_catalog.get(def_id)
            if not definition:
                continue

            tile_x = instance.get("tileX", 0)
            tile_y = instance.get("tileY", 0)
            world_x = float(tile_x - tile_y)
            world_y = float(tile_x + tile_y) * 0.5
            depth_key = camera_depth_key(world_x, world_y)

            buildings_to_draw.append({
                "depth": depth_key,
                "instance": instance,
                "definition": definition
            })

        # Depth sorting matching main.cpp
        buildings_to_draw.sort(key=lambda b: (b["depth"], b["instance"].get("instanceId", 0)))

        for item in buildings_to_draw:
            instance = item["instance"]
            definition = item["definition"]
            tile_x = instance.get("tileX", 0)
            tile_y = instance.get("tileY", 0)

            texture_path = definition.get("texture", "")
            pixmap = self.textures.get(texture_path)
            if not pixmap or pixmap.isNull():
                continue

            art_scale = definition.get("artScale", 0.3)
            anchor = definition.get("anchor", {"x": 0.5, "y": 0.85})
            anchor_x = anchor.get("x", 0.5)
            anchor_y = anchor.get("y", 0.85)

            world_x = float(tile_x - tile_y)
            world_y = float(tile_x + tile_y) * 0.5
            screen_x, screen_y = world_to_screen(world_x, world_y, camera, viewport_w, viewport_h)

            sprite_w = pixmap.width() * art_scale * camera.zoom
            sprite_h = pixmap.height() * art_scale * camera.zoom

            # Position building using ground anchor
            dest_x = screen_x - (sprite_w * anchor_x)
            dest_y = screen_y - (sprite_h * anchor_y) + (TILE_HEIGHT * 0.5 * camera.zoom)

            painter.drawPixmap(QRectF(dest_x, dest_y, sprite_w, sprite_h), pixmap, QRectF(0, 0, pixmap.width(), pixmap.height()))
