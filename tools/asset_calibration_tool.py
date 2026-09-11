#!/usr/bin/env python3
"""HUI Asset Calibration Tool v1 — City Horizon Golden Standard

Ferramenta visual de diagnóstico para verificar se um sprite de building
cumpre o contrato geométrico HUI antes de entrar no catálogo do jogo.

Esta ferramenta INSPECIONA. Ela nunca modifica arquivos-fonte, código do
engine ou dados do jogo. Ela nunca gera rotações, aplica flips ou tenta
corrigir perspectivas.

Uso:
    python tools/asset_calibration_tool.py
    python tools/asset_calibration_tool.py <definition.json>
    python tools/asset_calibration_tool.py <rot0_image.png>

Controles:
    Z / ←           Rotação anterior
    X / →           Próxima rotação
    1-4             Ir direto para R0/R90/R180/R270
    Scroll          Zoom
    Botão do meio   Pan (ou botão direito)
    R               Resetar vista
    F               Ajustar vista ao conteúdo
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image as PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QAction, QBrush, QColor, QFont, QKeyEvent, QMouseEvent,
    QPainter, QPen, QPixmap, QPolygonF, QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDoubleSpinBox, QFileDialog,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSizePolicy, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)


# ---------------------------------------------------------------------------
# Constants — match the engine's tile reference exactly
# ---------------------------------------------------------------------------
TILE_W: float = 128.0
TILE_H: float = 64.0

ROT_LABELS: Tuple[str, ...] = (
    "R0 — Norte (0°)",
    "R90 — Leste (90°)",
    "R180 — Sul (180°)",
    "R270 — Oeste (270°)",
)
ROT_SHORT: Tuple[str, ...] = ("R0", "R90", "R180", "R270")

DEFAULT_ART_SCALE: float = 0.24
DEFAULT_FP_W: int = 2
DEFAULT_FP_H: int = 2
DEFAULT_ANCHOR_X: float = 0.5
DEFAULT_ANCHOR_Y: float = 1.0

# --- Viewport palette ---
C_BG = QColor(38, 38, 44)
C_BG2 = QColor(46, 46, 52)
C_FOOTPRINT = QColor(255, 208, 92, 210)
C_TILE_GRID = QColor(54, 134, 164, 140)
C_ANCHOR = QColor(72, 236, 255)         # Current JSON/Engine Anchor (Ciano)
C_HUI_TARGET = QColor(255, 60, 180)     # HUI Target Anchor (0.5, 1.0) (Magenta)
C_PIVOT = QColor(255, 255, 255, 200)
C_CANVAS = QColor(238, 94, 224, 140)
C_ALPHA_BBOX = QColor(140, 255, 140, 100)
C_FRONT_EDGE = QColor(255, 120, 80, 220)
C_TEXT = QColor(220, 220, 230)
C_DIM = QColor(140, 140, 160)
C_NO_IMAGE = QColor(100, 100, 120)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------
@dataclass
class RotationData:
    """Per-rotation image data and its geometric anchor."""
    pixmap: Optional[QPixmap] = None
    path: str = ""
    canvas_w: int = 0
    canvas_h: int = 0
    alpha_bbox: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
    anchor_x: float = DEFAULT_ANCHOR_X
    anchor_y: float = DEFAULT_ANCHOR_Y


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def world_to_scene(wx: float, wy: float, fp_w: int, fp_h: int) -> Tuple[float, float]:
    """World grid coordinates → scene coordinates with ground anchor at (0, 0).

    The ground anchor is the isometric screen position of world point
    (fp_w, fp_h), which is the front-bottom vertex of the footprint diamond.
    All scene coordinates are relative to that fixed point.
    """
    return (
        ((wx - wy) - (fp_w - fp_h)) * TILE_W / 2.0,
        ((wx + wy) - (fp_w + fp_h)) * TILE_H / 2.0,
    )


def footprint_diamond(fp_w: int, fp_h: int) -> List[Tuple[float, float]]:
    """Return the 4 vertices of the footprint diamond: [top, right, bottom, left].

    'bottom' coincides with the ground anchor at (0, 0).
    """
    return [
        world_to_scene(0, 0, fp_w, fp_h),           # top
        world_to_scene(fp_w, 0, fp_w, fp_h),         # right
        world_to_scene(fp_w, fp_h, fp_w, fp_h),      # bottom / anchor
        world_to_scene(0, fp_h, fp_w, fp_h),          # left
    ]


def diamond_center(diamond: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Geometric center of the diamond."""
    cx = sum(v[0] for v in diamond) / len(diamond)
    cy = sum(v[1] for v in diamond) / len(diamond)
    return (cx, cy)


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------
def discover_rotation_files(r0_path: Path) -> List[Optional[Path]]:
    """Given an R0 image path, try to find R1/R2/R3 by filename pattern.

    Handles both patterns:
      house_suburban_01_rot0.png  → _rot1, _rot2, _rot3
      cafe_moderno_01.png        → _rot1, _rot2, _rot3 (R0 has no suffix)
    """
    stem = r0_path.stem
    parent = r0_path.parent
    ext = r0_path.suffix
    paths: List[Optional[Path]] = [r0_path, None, None, None]

    base = stem[:-5] if stem.endswith("_rot0") else stem

    for i in range(1, 4):
        candidate = parent / f"{base}_rot{i}{ext}"
        if candidate.exists():
            paths[i] = candidate

    return paths


def load_alpha_bbox(path: str) -> Optional[Tuple[int, int, int, int]]:
    """Compute opaque bounding box using PIL.  Returns (x, y, w, h) or None."""
    if not _HAS_PIL:
        return None
    try:
        bbox = PILImage.open(path).convert("RGBA").getbbox()
        if bbox is None:
            return None
        return (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# JSON definition parsing  (read-only, never writes)
# ---------------------------------------------------------------------------
def load_definition_json(json_path: Path):
    """Parse a building definition JSON.

    Returns a tuple:
        (sprites_dict, art_scale, fp_w, fp_h, per_rot_anchors,
         global_anchor_x, global_anchor_y, front_edge)
    or None on failure.
    """
    try:
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return None

    sprites: Dict[int, str] = {}
    if "sprites" in data:
        for k, v in data["sprites"].items():
            sprites[int(k)] = v

    art_scale = float(data.get("artScale", DEFAULT_ART_SCALE))
    fp = data.get("footprint", {})
    fp_w = int(fp.get("width", DEFAULT_FP_W))
    fp_h = int(fp.get("height", DEFAULT_FP_H))

    global_anc = data.get("anchor", {})
    gax = float(global_anc.get("x", DEFAULT_ANCHOR_X))
    gay = float(global_anc.get("y", DEFAULT_ANCHOR_Y))

    per_rot_anchors: Dict[int, Tuple[float, float]] = {}
    if "spriteAnchors" in data:
        for k, v in data["spriteAnchors"].items():
            per_rot_anchors[int(k)] = (
                float(v.get("x", gax)),
                float(v.get("y", gay)),
            )

    front_edge = data.get("frontEdge", None)

    return (sprites, art_scale, fp_w, fp_h, per_rot_anchors,
            gax, gay, front_edge)


# ---------------------------------------------------------------------------
# CalibrationViewport — the main drawing area
# ---------------------------------------------------------------------------
class CalibrationViewport(QWidget):
    """Renders the building sprite over the HUI geometric reference.

    The ground anchor (front-bottom vertex of the footprint diamond) is
    fixed at scene-space origin (0, 0).  Switching rotations changes only
    the image; the reference geometry never moves.
    """

    rotation_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Expanding)

        # Per-rotation image data
        self.rotations: List[RotationData] = [RotationData() for _ in range(4)]
        self.current_rot: int = 0

        # Geometry parameters
        self.art_scale: float = DEFAULT_ART_SCALE
        self.fp_w: int = DEFAULT_FP_W
        self.fp_h: int = DEFAULT_FP_H
        self.front_edge: Optional[str] = None

        # Viewport transform
        self.view_zoom: float = 2.0
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0

        # Drag state
        self._dragging: bool = False
        self._drag_start: QPointF = QPointF()
        self._pan_start: Tuple[float, float] = (0.0, 0.0)

        # Overlay toggles (controlled by InfoPanel)
        self.show_footprint: bool = True
        self.show_tile_grid: bool = True
        self.show_anchor: bool = True
        self.show_hui_target: bool = True
        self.show_pivot: bool = True
        self.show_canvas: bool = True
        self.show_alpha_bbox: bool = True
        self.show_front_edge: bool = True

        # Checkerboard pattern for transparency inspection
        self._checker = QPixmap(20, 20)
        self._checker.fill(C_BG)
        p = QPainter(self._checker)
        p.fillRect(0, 0, 10, 10, C_BG2)
        p.fillRect(10, 10, 10, 10, C_BG2)
        p.end()

    # --- Public API ---

    def set_rotation(self, rot: int) -> None:
        self.current_rot = rot % 4
        self.rotation_changed.emit(self.current_rot)
        self.update()

    def reset_view(self) -> None:
        self.view_zoom = 2.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.update()

    def fit_view(self) -> None:
        """Auto-fit zoom and pan to show the building + footprint."""
        rd = self.rotations[self.current_rot]
        diamond = footprint_diamond(self.fp_w, self.fp_h)

        # Scene bounding box
        scene_top = min(v[1] for v in diamond)
        scene_bottom = max(v[1] for v in diamond)
        scene_left = min(v[0] for v in diamond)
        scene_right = max(v[0] for v in diamond)

        if rd.pixmap is not None:
            img_w = rd.canvas_w * self.art_scale
            img_h = rd.canvas_h * self.art_scale
            img_x = -img_w * rd.anchor_x
            img_y = -img_h * rd.anchor_y
            scene_top = min(scene_top, img_y)
            scene_bottom = max(scene_bottom, img_y + img_h)
            scene_left = min(scene_left, img_x)
            scene_right = max(scene_right, img_x + img_w)

        padding = 30.0
        scene_h = (scene_bottom - scene_top) + padding * 2
        scene_w = (scene_right - scene_left) + padding * 2
        center_y = (scene_top + scene_bottom) / 2.0

        vp_w = max(1.0, float(self.width()))
        vp_h = max(1.0, float(self.height()))

        zoom_h = vp_h / scene_h if scene_h > 0 else 2.0
        zoom_w = vp_w / scene_w if scene_w > 0 else 2.0
        self.view_zoom = min(zoom_h, zoom_w) * 0.90
        self.pan_x = 0.0
        self.pan_y = -center_y * self.view_zoom
        self.update()

    # --- Painting ---

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Checkerboard background
        painter.fillRect(self.rect(), QBrush(self._checker))

        vp_cx = self.width() / 2.0
        vp_cy = self.height() / 2.0
        rd = self.rotations[self.current_rot]
        diamond = footprint_diamond(self.fp_w, self.fp_h)
        inv_zoom = 1.0 / max(self.view_zoom, 0.001)

        # Apply view transform: scene (0, 0) maps to viewport center + pan
        painter.save()
        painter.translate(vp_cx + self.pan_x, vp_cy + self.pan_y)
        painter.scale(self.view_zoom, self.view_zoom)

        # --- 1. Building sprite ---
        if rd.pixmap is not None:
            img_w = rd.canvas_w * self.art_scale
            img_h = rd.canvas_h * self.art_scale
            img_x = -img_w * rd.anchor_x
            img_y = -img_h * rd.anchor_y
            target = QRectF(img_x, img_y, img_w, img_h)
            painter.drawPixmap(target, rd.pixmap, QRectF(rd.pixmap.rect()))

            # --- 2. Canvas outline ---
            if self.show_canvas:
                pen = QPen(C_CANVAS, 1.5 * inv_zoom)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(target)

            # --- 3. Alpha bounding box ---
            if self.show_alpha_bbox and rd.alpha_bbox is not None:
                bx, by, bw, bh = rd.alpha_bbox
                alpha_rect = QRectF(
                    img_x + bx * self.art_scale,
                    img_y + by * self.art_scale,
                    bw * self.art_scale,
                    bh * self.art_scale,
                )
                pen = QPen(C_ALPHA_BBOX, 1.5 * inv_zoom)
                pen.setStyle(Qt.PenStyle.DotLine)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(alpha_rect)

        # --- 4. Tile grid inside footprint ---
        if self.show_tile_grid:
            painter.setPen(QPen(C_TILE_GRID, 1.0 * inv_zoom))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for ty in range(self.fp_h):
                for tx in range(self.fp_w):
                    corners = [
                        world_to_scene(tx, ty, self.fp_w, self.fp_h),
                        world_to_scene(tx + 1, ty, self.fp_w, self.fp_h),
                        world_to_scene(tx + 1, ty + 1, self.fp_w, self.fp_h),
                        world_to_scene(tx, ty + 1, self.fp_w, self.fp_h),
                    ]
                    painter.drawPolygon(
                        QPolygonF([QPointF(*c) for c in corners]))

        # --- 5. Footprint outer boundary ---
        if self.show_footprint:
            painter.setPen(QPen(C_FOOTPRINT, 2.5 * inv_zoom))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(
                QPolygonF([QPointF(*v) for v in diamond]))

        # --- 6. Front edge highlight ---
        if self.show_front_edge and self.front_edge is not None:
            edge_map = {
                "south": (diamond[3], diamond[2]),  # left → bottom
                "north": (diamond[0], diamond[1]),  # top  → right
                "east":  (diamond[1], diamond[2]),  # right → bottom
                "west":  (diamond[0], diamond[3]),  # top  → left
            }
            edge = edge_map.get(self.front_edge)
            if edge is not None:
                painter.setPen(QPen(C_FRONT_EDGE, 3.5 * inv_zoom))
                painter.drawLine(QPointF(*edge[0]), QPointF(*edge[1]))
                # Label
                mid_x = (edge[0][0] + edge[1][0]) / 2.0
                mid_y = (edge[0][1] + edge[1][1]) / 2.0
                font = painter.font()
                font.setPixelSize(max(1, int(9 * inv_zoom)))
                painter.setFont(font)
                painter.setPen(C_FRONT_EDGE)
                painter.drawText(
                    QPointF(mid_x + 6 * inv_zoom, mid_y),
                    f"FRONT ({self.front_edge.upper()})")

        # --- 7. Current JSON Anchor marker (Ciano at scene 0,0) ---
        if self.show_anchor:
            r = 7.0 * inv_zoom
            pen = QPen(C_ANCHOR, 2.0 * inv_zoom)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(-r, 0), QPointF(r, 0))
            painter.drawLine(QPointF(0, -r), QPointF(0, r))
            painter.drawEllipse(QPointF(0, 0), r * 0.5, r * 0.5)
            font = painter.font()
            font.setPixelSize(max(1, int(11 * inv_zoom)))
            painter.setFont(font)
            painter.setPen(C_ANCHOR)
            painter.drawText(
                QPointF(r + 4 * inv_zoom, -4 * inv_zoom), "CURRENT JSON ANCHOR")

        # --- 7b. HUI Target Anchor marker (Magenta at sprite canvas 0.5, 1.0) ---
        if self.show_hui_target and rd.pixmap is not None:
            img_w = rd.canvas_w * self.art_scale
            img_h = rd.canvas_h * self.art_scale
            img_x = -img_w * rd.anchor_x
            img_y = -img_h * rd.anchor_y
            hui_x = img_x + img_w * 0.5
            hui_y = img_y + img_h * 1.0

            r = 8.0 * inv_zoom
            pen = QPen(C_HUI_TARGET, 2.0 * inv_zoom)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            # Square target box
            painter.drawRect(QRectF(hui_x - r * 0.5, hui_y - r * 0.5, r, r))
            painter.drawLine(QPointF(hui_x - r, hui_y), QPointF(hui_x + r, hui_y))
            painter.drawLine(QPointF(hui_x, hui_y - r), QPointF(hui_x, hui_y + r))

            # Draw dashed offset vector line if current anchor != target anchor
            if abs(hui_x) > 0.1 or abs(hui_y) > 0.1:
                dash_pen = QPen(C_HUI_TARGET, 1.5 * inv_zoom)
                dash_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(QPointF(0, 0), QPointF(hui_x, hui_y))

            font = painter.font()
            font.setPixelSize(max(1, int(11 * inv_zoom)))
            painter.setFont(font)
            painter.setPen(C_HUI_TARGET)
            painter.drawText(
                QPointF(hui_x + r + 4 * inv_zoom, hui_y + 12 * inv_zoom),
                "HUI TARGET (0.5, 1.0)")

        # --- 8. Center / pivot marker ---
        if self.show_pivot:
            cx, cy = diamond_center(diamond)
            r = 5.0 * inv_zoom
            painter.setPen(QPen(C_PIVOT, 1.5 * inv_zoom))
            painter.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
            painter.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
            font = painter.font()
            font.setPixelSize(max(1, int(10 * inv_zoom)))
            painter.setFont(font)
            painter.setPen(C_PIVOT)
            painter.drawText(
                QPointF(cx + r + 3 * inv_zoom, cy - 3 * inv_zoom), "PIVOT")

        painter.restore()

        # --- 9. HUD overlay (screen-space, not zoomed) ---
        self._draw_hud(painter, rd)

        painter.end()

    def _draw_hud(self, painter: QPainter, rd: RotationData) -> None:
        """Draw rotation label and info text over the viewport."""
        # Rotation label
        font = QFont("Consolas", 14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(C_TEXT)
        label = ROT_LABELS[self.current_rot]
        suffix = "" if rd.pixmap is not None else "  [SEM IMAGEM]"
        painter.drawText(12, 28, label + suffix)

        # Image info
        if rd.pixmap is not None:
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(C_DIM)
            info = (f"PNG: {rd.canvas_w}×{rd.canvas_h}  |  "
                    f"Escala: {self.art_scale:.3f}  |  "
                    f"Anchor: ({rd.anchor_x:.4f}, {rd.anchor_y:.4f})")
            painter.drawText(12, 48, info)
        elif rd.path == "":
            # No image loaded at all — show hint
            font.setPointSize(11)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(C_NO_IMAGE)
            cx = self.width() // 2
            cy = self.height() // 2
            painter.drawText(
                cx - 180, cy - 10,
                "Ctrl+O  Abrir imagem R0")
            painter.drawText(
                cx - 180, cy + 14,
                "Ctrl+J  Abrir definição JSON")

        # Controls hint at bottom
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(C_DIM)
        painter.drawText(
            12, self.height() - 10,
            "Z/← Ant.  |  X/→ Próx.  |  Scroll: Zoom  |  "
            "Meio/Dir.: Pan  |  R: Reset  |  F: Fit")

    # --- Input handling ---

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Z, Qt.Key.Key_Left):
            self.set_rotation(self.current_rot - 1)
        elif key in (Qt.Key.Key_X, Qt.Key.Key_Right):
            self.set_rotation(self.current_rot + 1)
        elif key == Qt.Key.Key_1:
            self.set_rotation(0)
        elif key == Qt.Key.Key_2:
            self.set_rotation(1)
        elif key == Qt.Key.Key_3:
            self.set_rotation(2)
        elif key == Qt.Key.Key_4:
            self.set_rotation(3)
        elif key == Qt.Key.Key_R:
            self.reset_view()
        elif key == Qt.Key.Key_F:
            self.fit_view()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1.0 / 1.15
        self.view_zoom = max(0.1, min(50.0, self.view_zoom * factor))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (Qt.MouseButton.MiddleButton,
                               Qt.MouseButton.RightButton):
            self._dragging = True
            self._drag_start = event.position()
            self._pan_start = (self.pan_x, self.pan_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging:
            delta = event.position() - self._drag_start
            self.pan_x = self._pan_start[0] + delta.x()
            self.pan_y = self._pan_start[1] + delta.y()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() in (Qt.MouseButton.MiddleButton,
                               Qt.MouseButton.RightButton):
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            super().mouseReleaseEvent(event)


# ---------------------------------------------------------------------------
# InfoPanel — right-hand parameter and checklist panel
# ---------------------------------------------------------------------------
class InfoPanel(QWidget):
    """Displays image info, geometry controls, overlay toggles and the
    HUI approval checklist."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(310)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # --- Rotation navigation ---
        rot_box = QGroupBox("Rotação")
        rot_layout = QHBoxLayout(rot_box)
        self.btn_prev = QPushButton("◄ Z")
        self.rot_label = QLabel(ROT_LABELS[0])
        self.rot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rot_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_next = QPushButton("X ►")
        rot_layout.addWidget(self.btn_prev)
        rot_layout.addWidget(self.rot_label, 1)
        rot_layout.addWidget(self.btn_next)
        layout.addWidget(rot_box)

        # --- PNG info ---
        info_box = QGroupBox("Informações do PNG")
        info_grid = QGridLayout(info_box)
        info_grid.setColumnStretch(1, 1)

        self.lbl_file = QLabel("—")
        self.lbl_file.setWordWrap(True)
        self.lbl_file.setStyleSheet("color: #999; font-size: 10px;")
        self.lbl_size = QLabel("—")
        self.lbl_alpha = QLabel("—")

        info_grid.addWidget(QLabel("Arquivo:"), 0, 0)
        info_grid.addWidget(self.lbl_file, 0, 1)
        info_grid.addWidget(QLabel("Canvas:"), 1, 0)
        info_grid.addWidget(self.lbl_size, 1, 1)
        info_grid.addWidget(QLabel("BBox Alfa:"), 2, 0)
        info_grid.addWidget(self.lbl_alpha, 2, 1)
        layout.addWidget(info_box)

        # --- Geometry controls ---
        geom_box = QGroupBox("Geometria")
        geom_grid = QGridLayout(geom_box)

        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.01, 2.0)
        self.spin_scale.setSingleStep(0.01)
        self.spin_scale.setDecimals(3)
        self.spin_scale.setValue(DEFAULT_ART_SCALE)

        self.spin_fp_w = QSpinBox()
        self.spin_fp_w.setRange(1, 10)
        self.spin_fp_w.setValue(DEFAULT_FP_W)

        self.spin_fp_h = QSpinBox()
        self.spin_fp_h.setRange(1, 10)
        self.spin_fp_h.setValue(DEFAULT_FP_H)

        self.spin_ax = QDoubleSpinBox()
        self.spin_ax.setRange(0.0, 1.0)
        self.spin_ax.setSingleStep(0.001)
        self.spin_ax.setDecimals(4)
        self.spin_ax.setValue(DEFAULT_ANCHOR_X)

        self.spin_ay = QDoubleSpinBox()
        self.spin_ay.setRange(0.0, 1.5)
        self.spin_ay.setSingleStep(0.001)
        self.spin_ay.setDecimals(4)
        self.spin_ay.setValue(DEFAULT_ANCHOR_Y)

        geom_grid.addWidget(QLabel("Art Scale:"), 0, 0)
        geom_grid.addWidget(self.spin_scale, 0, 1)

        geom_grid.addWidget(QLabel("Footprint:"), 1, 0)
        fp_row = QHBoxLayout()
        fp_row.addWidget(self.spin_fp_w)
        fp_row.addWidget(QLabel("×"))
        fp_row.addWidget(self.spin_fp_h)
        geom_grid.addLayout(fp_row, 1, 1)

        geom_grid.addWidget(QLabel("Anchor X:"), 2, 0)
        geom_grid.addWidget(self.spin_ax, 2, 1)
        geom_grid.addWidget(QLabel("Anchor Y:"), 3, 0)
        geom_grid.addWidget(self.spin_ay, 3, 1)
        layout.addWidget(geom_box)

        # --- Overlay toggles ---
        overlay_box = QGroupBox("Overlays")
        overlay_layout = QVBoxLayout(overlay_box)

        self.chk_footprint = QCheckBox("Footprint 2:1")
        self.chk_footprint.setChecked(True)
        self.chk_tile_grid = QCheckBox("Grade de Tiles")
        self.chk_tile_grid.setChecked(True)
        self.chk_anchor = QCheckBox("Current JSON Anchor (Ciano)")
        self.chk_anchor.setChecked(True)
        self.chk_hui_target = QCheckBox("HUI Target Anchor (0.5, 1.0) (Magenta)")
        self.chk_hui_target.setChecked(True)
        self.chk_pivot = QCheckBox("Centro / Pivô")
        self.chk_pivot.setChecked(True)
        self.chk_canvas = QCheckBox("Canvas do PNG")
        self.chk_canvas.setChecked(True)
        self.chk_alpha_bbox = QCheckBox("BBox Alfa (diagnóstico)")
        self.chk_alpha_bbox.setChecked(True)
        self.chk_front_edge = QCheckBox("Front Edge")
        self.chk_front_edge.setChecked(True)

        for chk in (self.chk_footprint, self.chk_tile_grid, self.chk_anchor,
                     self.chk_hui_target, self.chk_pivot, self.chk_canvas,
                     self.chk_alpha_bbox, self.chk_front_edge):
            overlay_layout.addWidget(chk)
        layout.addWidget(overlay_box)

        # --- HUI Checklist ---
        checklist_box = QGroupBox("HUI Checklist")
        checklist_layout = QVBoxLayout(checklist_box)

        self.checks: Dict[str, QCheckBox] = {}
        for item in ("CAMERA", "FOOTPRINT", "GROUND ANCHOR", "SCALE",
                      "ROTATION", "PUBLIC OVERLAYS", "ALPHA"):
            chk = QCheckBox(item)
            self.checks[item] = chk
            checklist_layout.addWidget(chk)
            chk.stateChanged.connect(self._update_status)

        self.status_label = QLabel("STATUS: PENDENTE")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_status_pending()
        checklist_layout.addWidget(self.status_label)
        layout.addWidget(checklist_box)

        layout.addStretch()

    # --- Public helpers ---

    def update_info(self, rd: RotationData, rot_index: int) -> None:
        """Refresh the info panel for the given rotation."""
        self.rot_label.setText(ROT_LABELS[rot_index])
        if rd.pixmap is not None:
            self.lbl_file.setText(Path(rd.path).name)
            self.lbl_size.setText(f"{rd.canvas_w} × {rd.canvas_h}")
            if rd.alpha_bbox is not None:
                bx, by, bw, bh = rd.alpha_bbox
                self.lbl_alpha.setText(f"[{bx}, {by}]  {bw}×{bh}")
            else:
                self.lbl_alpha.setText("—")
            # Update anchor spinboxes without triggering valueChanged
            self.spin_ax.blockSignals(True)
            self.spin_ay.blockSignals(True)
            self.spin_ax.setValue(rd.anchor_x)
            self.spin_ay.setValue(rd.anchor_y)
            self.spin_ax.blockSignals(False)
            self.spin_ay.blockSignals(False)
        else:
            self.lbl_file.setText("Sem imagem")
            self.lbl_size.setText("—")
            self.lbl_alpha.setText("—")

    # --- Private ---

    def _update_status(self) -> None:
        if all(chk.isChecked() for chk in self.checks.values()):
            self.status_label.setText("STATUS: HUI APPROVED ✓")
            self.status_label.setStyleSheet(
                "font-weight: bold; font-size: 12px; color: #50FF78; "
                "padding: 6px; background: #1a3a1a; border-radius: 4px;")
        else:
            self._set_status_pending()

    def _set_status_pending(self) -> None:
        self.status_label.setText("STATUS: PENDENTE")
        self.status_label.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: #FF9944; "
            "padding: 6px;")


# ---------------------------------------------------------------------------
# CalibrationWindow — main window wiring
# ---------------------------------------------------------------------------
class CalibrationWindow(QMainWindow):
    """Top-level window connecting the viewport with the info panel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HUI Asset Calibration Tool — City Horizon")
        self.resize(1200, 800)

        self.viewport = CalibrationViewport()
        self.info_panel = InfoPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.viewport)
        splitter.addWidget(self.info_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self.setCentralWidget(splitter)

        self._build_menu()
        self._connect_signals()

    # --- Menu ---

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("Arquivo")

        open_json = QAction("Abrir Definição JSON...", self)
        open_json.setShortcut("Ctrl+J")
        open_json.triggered.connect(self._open_definition_dialog)
        file_menu.addAction(open_json)

        open_r0 = QAction("Abrir Imagem R0...", self)
        open_r0.setShortcut("Ctrl+O")
        open_r0.triggered.connect(self._open_r0_dialog)
        file_menu.addAction(open_r0)

        file_menu.addSeparator()

        quit_action = QAction("Sair", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    # --- Signal wiring ---

    def _connect_signals(self) -> None:
        vp = self.viewport
        ip = self.info_panel

        # Rotation
        vp.rotation_changed.connect(self._on_rotation_changed)
        ip.btn_prev.clicked.connect(lambda: vp.set_rotation(vp.current_rot - 1))
        ip.btn_next.clicked.connect(lambda: vp.set_rotation(vp.current_rot + 1))

        # Geometry spinboxes
        ip.spin_scale.valueChanged.connect(self._on_geometry_changed)
        ip.spin_fp_w.valueChanged.connect(self._on_geometry_changed)
        ip.spin_fp_h.valueChanged.connect(self._on_geometry_changed)
        ip.spin_ax.valueChanged.connect(self._on_anchor_changed)
        ip.spin_ay.valueChanged.connect(self._on_anchor_changed)

        # Overlay toggles
        self._bind_overlay(ip.chk_footprint,  "show_footprint")
        self._bind_overlay(ip.chk_tile_grid,  "show_tile_grid")
        self._bind_overlay(ip.chk_anchor,     "show_anchor")
        self._bind_overlay(ip.chk_hui_target, "show_hui_target")
        self._bind_overlay(ip.chk_pivot,      "show_pivot")
        self._bind_overlay(ip.chk_canvas,     "show_canvas")
        self._bind_overlay(ip.chk_alpha_bbox, "show_alpha_bbox")
        self._bind_overlay(ip.chk_front_edge, "show_front_edge")

    def _bind_overlay(self, checkbox: QCheckBox, attr: str) -> None:
        def toggle(checked: bool) -> None:
            setattr(self.viewport, attr, checked)
            self.viewport.update()
        checkbox.toggled.connect(toggle)

    # --- Slots ---

    def _on_rotation_changed(self, rot: int) -> None:
        rd = self.viewport.rotations[rot]
        self.info_panel.update_info(rd, rot)

    def _on_geometry_changed(self) -> None:
        self.viewport.art_scale = self.info_panel.spin_scale.value()
        self.viewport.fp_w = self.info_panel.spin_fp_w.value()
        self.viewport.fp_h = self.info_panel.spin_fp_h.value()
        self.viewport.update()

    def _on_anchor_changed(self) -> None:
        rot = self.viewport.current_rot
        self.viewport.rotations[rot].anchor_x = self.info_panel.spin_ax.value()
        self.viewport.rotations[rot].anchor_y = self.info_panel.spin_ay.value()
        self.viewport.update()

    # --- Loading ---

    def _load_rotation(self, rot_index: int, path: Path,
                       anchor_x: float = DEFAULT_ANCHOR_X,
                       anchor_y: float = DEFAULT_ANCHOR_Y) -> None:
        rd = self.viewport.rotations[rot_index]
        rd.path = str(path)
        rd.pixmap = QPixmap(str(path))
        if rd.pixmap.isNull():
            rd.pixmap = None
            rd.canvas_w = 0
            rd.canvas_h = 0
            return
        rd.canvas_w = rd.pixmap.width()
        rd.canvas_h = rd.pixmap.height()
        rd.alpha_bbox = load_alpha_bbox(str(path))
        rd.anchor_x = anchor_x
        rd.anchor_y = anchor_y

    def _open_definition_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Definição JSON", "", "JSON (*.json)")
        if path:
            self._load_from_definition(Path(path))

    def _open_r0_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Imagem R0", "", "PNG (*.png)")
        if path:
            self._load_from_r0(Path(path))

    def _load_from_definition(self, json_path: Path) -> None:
        result = load_definition_json(json_path)
        if result is None:
            return

        (sprites, art_scale, fp_w, fp_h,
         per_rot_anchors, gax, gay, front_edge) = result

        # Derive project root: definition JSONs live in assets/definitions/
        project_root = json_path.parent.parent.parent

        self.info_panel.spin_scale.setValue(art_scale)
        self.info_panel.spin_fp_w.setValue(fp_w)
        self.info_panel.spin_fp_h.setValue(fp_h)
        self.viewport.art_scale = art_scale
        self.viewport.fp_w = fp_w
        self.viewport.fp_h = fp_h
        self.viewport.front_edge = front_edge

        for rot in range(4):
            ax = per_rot_anchors.get(rot, (gax, gay))[0]
            ay = per_rot_anchors.get(rot, (gax, gay))[1]
            if rot in sprites and sprites[rot]:
                sprite_path = project_root / sprites[rot]
                # Fallback: try relative to CWD
                if not sprite_path.exists():
                    sprite_path = Path(sprites[rot])
                if sprite_path.exists():
                    self._load_rotation(rot, sprite_path, ax, ay)
                else:
                    self.viewport.rotations[rot] = RotationData(
                        anchor_x=ax, anchor_y=ay)
            else:
                self.viewport.rotations[rot] = RotationData(
                    anchor_x=ax, anchor_y=ay)

        self.viewport.set_rotation(0)
        self._on_rotation_changed(0)
        self.viewport.fit_view()
        self.setWindowTitle(f"HUI Calibration — {json_path.stem}")

    def _load_from_r0(self, r0_path: Path) -> None:
        files = discover_rotation_files(r0_path)

        for rot in range(4):
            if files[rot] is not None:
                self._load_rotation(rot, files[rot])
            else:
                self.viewport.rotations[rot] = RotationData()

        # Try to find a matching definition JSON for metadata
        stem = r0_path.stem
        building_id = stem[:-5] if stem.endswith("_rot0") else stem

        for json_dir in (r0_path.parent.parent / "definitions",
                         r0_path.parent):
            json_path = json_dir / f"{building_id}.json"
            if json_path.exists():
                result = load_definition_json(json_path)
                if result is not None:
                    (_, art_scale, fp_w, fp_h,
                     per_rot_anchors, gax, gay, front_edge) = result

                    self.info_panel.spin_scale.setValue(art_scale)
                    self.info_panel.spin_fp_w.setValue(fp_w)
                    self.info_panel.spin_fp_h.setValue(fp_h)
                    self.viewport.art_scale = art_scale
                    self.viewport.fp_w = fp_w
                    self.viewport.fp_h = fp_h
                    self.viewport.front_edge = front_edge

                    for rot in range(4):
                        ax = per_rot_anchors.get(rot, (gax, gay))[0]
                        ay = per_rot_anchors.get(rot, (gax, gay))[1]
                        self.viewport.rotations[rot].anchor_x = ax
                        self.viewport.rotations[rot].anchor_y = ay
                    break

        self.viewport.set_rotation(0)
        self._on_rotation_changed(0)
        self.viewport.fit_view()
        self.setWindowTitle(f"HUI Calibration — {building_id}")

    def load_from_args(self, path_str: str) -> None:
        """Load from a command-line argument (JSON or PNG)."""
        p = Path(path_str)
        if p.suffix.lower() == ".json":
            self._load_from_definition(p)
        elif p.suffix.lower() == ".png":
            self._load_from_r0(p)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    app = QApplication(sys.argv)

    # Dark Fusion palette
    app.setStyle("Fusion")
    palette = app.palette()
    palette.setColor(palette.ColorRole.Window, QColor(53, 53, 60))
    palette.setColor(palette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Base, QColor(42, 42, 48))
    palette.setColor(palette.ColorRole.AlternateBase, QColor(53, 53, 60))
    palette.setColor(palette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Button, QColor(60, 60, 68))
    palette.setColor(palette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(palette.ColorRole.Highlight, QColor(72, 180, 220))
    palette.setColor(palette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = CalibrationWindow()

    if len(sys.argv) > 1:
        window.load_from_args(sys.argv[1])

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
