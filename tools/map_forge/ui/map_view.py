"""
Interactive Map Canvas for Map Forge (PySide6).
Supports mouse drag panning, wheel zooming, and coordinate inspection in READ-ONLY mode.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QMouseEvent, QWheelEvent, QPaintEvent
from PySide6.QtCore import Qt, Signal

from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.projection import Camera, screen_to_tile
from tools.map_forge.render.iso_renderer import IsoRendererPySide


class MapViewCanvas(QWidget):
    hovered_tile_changed = Signal(int, int)

    def __init__(self, asset_root: str, building_catalog: dict, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.asset_root = asset_root
        self.building_catalog = building_catalog
        self.renderer = IsoRendererPySide(asset_root, building_catalog)
        self.camera = Camera(world_x=-2.0, world_y=12.0, zoom=0.9)

        self.map_model: MapModel = None
        self._dragging = False
        self._last_mouse_pos = None

    def set_map_model(self, map_model: MapModel):
        self.map_model = map_model
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.map_model:
            self.renderer.render(painter, self.map_model, self.camera, float(self.width()), float(self.height()))
        else:
            painter.fillRect(self.rect(), Qt.darkGray)
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "No scenario loaded.")

        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton:
            self._dragging = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        if self._dragging and self._last_mouse_pos:
            delta = pos - self._last_mouse_pos
            self._last_mouse_pos = pos

            # Pan camera matching zoom scale
            dx = delta.x() / (64.0 * self.camera.zoom)
            dy = delta.y() / (64.0 * self.camera.zoom)
            self.camera.world_x -= dx
            self.camera.world_y -= dy
            self.update()

        # Update hovered logical tile coordinates
        tile_x, tile_y = screen_to_tile(pos.x(), pos.y(), self.camera, float(self.width()), float(self.height()))
        self.hovered_tile_changed.emit(tile_x, tile_y)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton or event.button() == Qt.MiddleButton:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.camera.zoom = min(2.5, self.camera.zoom * 1.15)
        else:
            self.camera.zoom = max(0.3, self.camera.zoom / 1.15)
        self.update()
