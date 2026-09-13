"""
Native SDL3 Viewport Widget for Map Forge (PySide6).
Delegates rendering and geometry projection to C++20 ch_render & ch_core via pybind11.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent, QPaintEvent, QResizeEvent, QShowEvent
from PySide6.QtCore import Qt, Signal

from tools.map_forge.core.native_bridge import get_native_core

try:
    ch = get_native_core()
except Exception as e:
    ch = None
    _native_error = e


class MapForgeSDLViewport(QWidget):
    hovered_tile_changed = Signal(int, int)
    tile_clicked = Signal(int, int, int)  # tile_x, tile_y, button (1=left, 2=middle, 3=right)

    def __init__(self, asset_root: str, building_catalog: dict, parent=None):
        super().__init__(parent)
        if ch is None:
            raise RuntimeError("MAP FORGE NATIVE CORE UNAVAILABLE")

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_PaintOnScreen, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.asset_root = asset_root
        self.building_catalog = building_catalog

        self.native_viewport = ch.MapForgeNativeViewport()
        self.camera = ch.CameraState()
        self.camera.pan_x = -2.0
        self.camera.pan_y = 12.0
        self.camera.zoom = 0.9

        self.map_document = None
        self._initialized = False
        self._dragging = False
        self._last_mouse_pos = None
        self._press_start_pos = None
        self._active_button = None

    def paintEngine(self):
        return None

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._ensure_initialized()

    def _ensure_initialized(self):
        if not self._initialized:
            hwnd = int(self.winId())
            dpr = self.devicePixelRatio()
            pw = max(1, int(self.width() * dpr))
            ph = max(1, int(self.height() * dpr))

            ok = self.native_viewport.initialize(hwnd, pw, ph, self.asset_root)
            if not ok:
                raise RuntimeError("Failed to initialize native SDL3 viewport window handle.")
            self.native_viewport.set_camera(self.camera)
            if self.map_document:
                self.native_viewport.load_map_document(self.map_document)
            self._initialized = True

    def set_map_document(self, document):
        self.map_document = document
        if self._initialized and self.map_document:
            self.native_viewport.load_map_document(self.map_document)
        self.update()

    def set_map_model(self, map_model):
        """Adapter for MapModel: creates a native MapDocument from raw json."""
        if hasattr(map_model, 'raw_json') and map_model.raw_json:
            doc = ch.MapDocument(map_model.raw_json)
        elif hasattr(map_model, 'raw_content') and map_model.raw_content:
            doc = ch.MapDocument(map_model.raw_content)
        elif hasattr(map_model, '_raw_json') and map_model._raw_json:
            doc = ch.MapDocument(map_model._raw_json)
        else:
            raise ValueError("MapModel does not contain raw json content.")
        self.set_map_document(doc)

    def set_view_mode(self, mode: int):
        if self._initialized:
            self.native_viewport.set_view_mode(mode)
            self.update()

    def set_active_channels(self, channel_bitmask: int):
        if self._initialized:
            self.native_viewport.set_active_channels(channel_bitmask)
            self.update()

    def set_channel_opacity(self, opacity: float):
        if self._initialized:
            self.native_viewport.set_channel_opacity(opacity)
            self.update()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._initialized:
            dpr = self.devicePixelRatio()
            pw = max(1, int(self.width() * dpr))
            ph = max(1, int(self.height() * dpr))
            self.native_viewport.resize(pw, ph)
            self.update()

    def paintEvent(self, event: QPaintEvent):
        if not self._initialized:
            self._ensure_initialized()
        if self._initialized:
            self.native_viewport.render_frame()

    def mousePressEvent(self, event: QMouseEvent):
        self._press_start_pos = event.position()
        self._active_button = event.button()
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._dragging = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        if self._dragging and self._last_mouse_pos:
            delta = pos - self._last_mouse_pos
            self._last_mouse_pos = pos

            dx = delta.x() / (64.0 * self.camera.zoom)
            dy = delta.y() / (64.0 * self.camera.zoom)
            self.camera.pan_x -= dx
            self.camera.pan_y -= dy

            if self._initialized:
                self.native_viewport.set_camera(self.camera)
            self.update()

        dpr = self.devicePixelRatio()
        pw = float(self.width() * dpr)
        ph = float(self.height() * dpr)
        screen_x = float(pos.x() * dpr)
        screen_y = float(pos.y() * dpr)

        coord = ch.screen_to_tile_coord(screen_x, screen_y, self.camera, pw, ph)
        self.hovered_tile_changed.emit(coord.x, coord.y)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)

        if self._press_start_pos:
            dist = (event.position() - self._press_start_pos).manhattanLength()
            if dist < 6:
                dpr = self.devicePixelRatio()
                pw = float(self.width() * dpr)
                ph = float(self.height() * dpr)
                screen_x = float(event.position().x() * dpr)
                screen_y = float(event.position().y() * dpr)
                coord = ch.screen_to_tile_coord(screen_x, screen_y, self.camera, pw, ph)
                btn_code = 1 if event.button() == Qt.LeftButton else (3 if event.button() == Qt.RightButton else 2)
                self.tile_clicked.emit(coord.x, coord.y, btn_code)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.camera.zoom = min(2.5, self.camera.zoom * 1.15)
        else:
            self.camera.zoom = max(0.3, self.camera.zoom / 1.15)

        if self._initialized:
            self.native_viewport.set_camera(self.camera)
        self.update()

    def closeEvent(self, event):
        if self._initialized:
            self.native_viewport.shutdown()
            self._initialized = False
        super().closeEvent(event)
