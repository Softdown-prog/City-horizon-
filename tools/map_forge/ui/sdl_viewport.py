"""
Native SDL3 Viewport Widget for Map Forge (PySide6).
Delegates rendering and geometry projection to C++20 ch_render & ch_core via pybind11.
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QMouseEvent, QWheelEvent, QPaintEvent, QResizeEvent, QShowEvent, QHideEvent
from PySide6.QtCore import Qt, Signal, QTimer

from tools.map_forge.core.native_bridge import get_native_core

try:
    ch = get_native_core()
except Exception as e:
    ch = None
    _native_error = e


class MapForgeSDLViewport(QWidget):
    hovered_tile_changed = Signal(int, int)
    tile_clicked = Signal(int, int, int)          # tile_x, tile_y, button (1=left, 2=middle, 3=right)
    brush_stroke_started = Signal(int, int, int)  # tile_x, tile_y, button
    brush_tile_dragged = Signal(int, int, int)    # tile_x, tile_y, button
    brush_stroke_ended = Signal(int)              # button

    def __init__(self, asset_root: str, building_catalog: dict, parent=None):
        super().__init__(parent)
        if ch is None:
            raise RuntimeError("MAP FORGE NATIVE CORE UNAVAILABLE")

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)

        self.asset_root = asset_root
        self.building_catalog = building_catalog

        self.native_viewport = ch.MapForgeNativeViewport()
        self.camera = ch.CameraState()
        self.camera.pan_x = 0.0
        self.camera.pan_y = -512.0
        self.camera.zoom = 0.9

        self.map_document = None
        self._initialized = False
        self._dragging = False
        self._stroke_active = False
        self._last_mouse_pos = None
        self._press_start_pos = None
        self._active_button = None

        # Render loop authority: QTimer at 60 FPS -> _render_frame_tick() -> native_viewport.render_frame()
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._render_frame_tick)

    def paintEngine(self):
        return None

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self._ensure_initialized()
        if not self._render_timer.isActive():
            self._render_timer.start()

    def hideEvent(self, event: QHideEvent):
        super().hideEvent(event)
        if self._render_timer.isActive():
            self._render_timer.stop()

    def _render_frame_tick(self):
        if not self._initialized:
            self._ensure_initialized()
        if self._initialized:
            self.native_viewport.render_frame()

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
                self.center_camera_on_content(self.map_document)
            self._initialized = True

    def center_camera_on_content(self, map_document=None):
        doc = map_document or self.map_document
        if not doc:
            return
        min_x, max_x = 999999, -999999
        min_y, max_y = 999999, -999999

        for tile in doc.terrain_tiles():
            min_x = min(min_x, tile.tile_x)
            max_x = max(max_x, tile.tile_x)
            min_y = min(min_y, tile.tile_y)
            max_y = max(max_y, tile.tile_y)

        for b in doc.buildings():
            min_x = min(min_x, b.tile_x)
            max_x = max(max_x, b.tile_x)
            min_y = min(min_y, b.tile_y)
            max_y = max(max_y, b.tile_y)

        for r in doc.roads():
            min_x = min(min_x, r.tile_x)
            max_x = max(max_x, r.tile_x)
            min_y = min(min_y, r.tile_y)
            max_y = max(max_y, r.tile_y)

        if min_x > max_x:
            min_x, max_x, min_y, max_y = 0, 63, 0, 63

        cx = (min_x + max_x) * 0.5
        cy = (min_y + max_y) * 0.5

        # Isometric Projection Center Offset:
        # Screen point (cx, cy) is at viewport_center + (pan_x + (cx-cy)*32*zoom, pan_y + (cx+cy)*16*zoom)
        # To align (cx, cy) with screen center:
        self.camera.pan_x = - (cx - cy) * 32.0 * self.camera.zoom
        self.camera.pan_y = - (cx + cy) * 16.0 * self.camera.zoom
        if self._initialized:
            self.native_viewport.set_camera(self.camera)

    def set_map_document(self, document):
        self.map_document = document
        if self._initialized and self.map_document:
            self.native_viewport.load_map_document(self.map_document)

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

    def set_active_channels(self, channel_bitmask: int):
        if self._initialized:
            self.native_viewport.set_active_channels(channel_bitmask)

    def set_channel_opacity(self, opacity: float):
        if self._initialized:
            self.native_viewport.set_channel_opacity(opacity)

    def set_hover_brush_radius(self, radius: int):
        if self._initialized:
            self.native_viewport.set_hover_brush_radius(radius)

    def reload_catalogs(self):
        if self._initialized:
            self.native_viewport.reload_asset_catalogs()

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self._initialized:
            dpr = self.devicePixelRatio()
            pw = max(1, int(self.width() * dpr))
            ph = max(1, int(self.height() * dpr))
            self.native_viewport.resize(pw, ph)

    def paintEvent(self, event: QPaintEvent):
        if not self._initialized:
            self._ensure_initialized()
        if self._initialized:
            self.native_viewport.render_frame()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._initialized:
            self.native_viewport.set_hover_tile(0, 0, False)
        if self._stroke_active:
            self._stroke_active = False
            self.brush_stroke_ended.emit(1)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self._stroke_active:
            self._stroke_active = False
            self.brush_stroke_ended.emit(1)

    def mousePressEvent(self, event: QMouseEvent):
        self._press_start_pos = event.position()
        self._active_button = event.button()
        btn_code = 1 if event.button() == Qt.LeftButton else (3 if event.button() == Qt.RightButton else 2)

        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._dragging = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
        elif event.button() == Qt.LeftButton:
            self._stroke_active = True
            dpr = self.devicePixelRatio()
            pw = float(self.width() * dpr)
            ph = float(self.height() * dpr)
            screen_x = float(event.position().x() * dpr)
            screen_y = float(event.position().y() * dpr)
            coord = ch.screen_to_tile_coord(screen_x, screen_y, self.camera, pw, ph)
            self.brush_stroke_started.emit(coord.x, coord.y, btn_code)

    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        dpr = self.devicePixelRatio()

        if self._dragging and self._last_mouse_pos:
            delta = pos - self._last_mouse_pos
            self._last_mouse_pos = pos

            # Correct 1:1 physical screen pixel delta pan:
            self.camera.pan_x += delta.x() * dpr
            self.camera.pan_y += delta.y() * dpr

            if self._initialized:
                self.native_viewport.set_camera(self.camera)

        pw = float(self.width() * dpr)
        ph = float(self.height() * dpr)
        screen_x = float(pos.x() * dpr)
        screen_y = float(pos.y() * dpr)

        coord = ch.screen_to_tile_coord(screen_x, screen_y, self.camera, pw, ph)
        if self._initialized:
            self.native_viewport.set_hover_tile(coord.x, coord.y, True)

        self.hovered_tile_changed.emit(coord.x, coord.y)

        if self._stroke_active and self._active_button == Qt.LeftButton:
            self.brush_tile_dragged.emit(coord.x, coord.y, 1)

    def mouseReleaseEvent(self, event: QMouseEvent):
        btn_code = 1 if event.button() == Qt.LeftButton else (3 if event.button() == Qt.RightButton else 2)

        if self._dragging and event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)

        if self._stroke_active and event.button() == Qt.LeftButton:
            self._stroke_active = False
            self.brush_stroke_ended.emit(1)

        if self._press_start_pos:
            dist = (event.position() - self._press_start_pos).manhattanLength()
            if dist < 6:
                dpr = self.devicePixelRatio()
                pw = float(self.width() * dpr)
                ph = float(self.height() * dpr)
                screen_x = float(event.position().x() * dpr)
                screen_y = float(event.position().y() * dpr)
                coord = ch.screen_to_tile_coord(screen_x, screen_y, self.camera, pw, ph)
                self.tile_clicked.emit(coord.x, coord.y, btn_code)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta > 0:
            self.camera.zoom = min(2.5, self.camera.zoom * 1.15)
        else:
            self.camera.zoom = max(0.3, self.camera.zoom / 1.15)

        if self._initialized:
            self.native_viewport.set_camera(self.camera)

    def closeEvent(self, event):
        if self._render_timer.isActive():
            self._render_timer.stop()
        if self._initialized:
            self.native_viewport.shutdown()
            self._initialized = False
        super().closeEvent(event)
