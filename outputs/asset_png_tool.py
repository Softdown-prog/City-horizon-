"""Asset PNG Tool — clean city-builder assets and export PNG RGBA + JSON.

Run the interface:
    python asset_png_tool.py

Run without a UI:
    python asset_png_tool.py --batch input.jpg --out exported --id cafe_001
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import sys

from PIL import Image, ImageFilter, ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


DEFAULT_CATEGORY = "commerce"
CATEGORIES = (
    "residential", "commerce", "industry", "civic", "infrastructure",
    "decoration", "terrain", "other",
)


@dataclass(frozen=True)
class ProcessingOptions:
    tolerance: int = 52
    feather: int = 2
    shrink: int = 1
    trim: bool = False


def sanitize_asset_id(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    return value.strip("_") or "asset"


def _border_points(width: int, height: int, band: int = 12) -> Iterable[tuple[int, int]]:
    step = max(1, min(width, height) // 600)
    for x in range(0, width, step):
        for y in range(min(band, height)):
            yield x, y
            yield x, height - 1 - y
    for y in range(0, height, step):
        for x in range(min(band, width)):
            yield x, y
            yield width - 1 - x, y


def detect_background_palette(image: Image.Image, colors: int = 8) -> list[tuple[int, int, int]]:
    """Find dominant colors around the image border.

    Checkerboards generally produce two large border clusters; JPEG compression adds
    nearby variants, so colors are quantized before selecting representative means.
    """
    rgb = image.convert("RGB")
    pixels = rgb.load()
    buckets: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for x, y in _border_points(rgb.width, rgb.height):
        color = pixels[x, y]
        key = tuple(channel // 16 for channel in color)
        buckets.setdefault(key, []).append(color)
    ranked = sorted(buckets.values(), key=len, reverse=True)[:colors]
    palette = []
    for group in ranked:
        palette.append(tuple(sum(c[i] for c in group) // len(group) for i in range(3)))
    return palette or [(255, 255, 255)]


def nearest_background(color: tuple[int, int, int], palette: list[tuple[int, int, int]]) -> tuple[int, tuple[int, int, int]]:
    best = min(palette, key=lambda bg: sum((color[i] - bg[i]) ** 2 for i in range(3)))
    distance = int(sum((color[i] - best[i]) ** 2 for i in range(3)) ** 0.5)
    return distance, best


def edge_connected_background(image: Image.Image, palette: list[tuple[int, int, int]], tolerance: int) -> Image.Image:
    """Return a binary foreground mask by flood-filling only border-connected background.

    This avoids removing light architectural surfaces contained within the asset.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size
    source = rgb.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def candidate(x: int, y: int) -> bool:
        distance, _ = nearest_background(source[x, y], palette)
        # The detected checkerboard is neutral gray. Requiring low chroma keeps
        # cream walls and awnings (which are bright but noticeably warm) from
        # becoming connected to the outside background.
        chroma = max(source[x, y]) - min(source[x, y])
        return distance <= tolerance and chroma <= 32

    for x in range(width):
        for y in (0, height - 1):
            index = y * width + x
            if not visited[index] and candidate(x, y):
                visited[index] = 1
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            index = y * width + x
            if not visited[index] and candidate(x, y):
                visited[index] = 1
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                index = ny * width + nx
                if not visited[index] and candidate(nx, ny):
                    visited[index] = 1
                    queue.append((nx, ny))

    mask = Image.new("L", (width, height), 255)
    mask_bytes = bytearray(mask.tobytes())
    for index, is_background in enumerate(visited):
        if is_background:
            mask_bytes[index] = 0
    return Image.frombytes("L", (width, height), bytes(mask_bytes))


def soften_and_shrink(mask: Image.Image, options: ProcessingOptions) -> Image.Image:
    if options.shrink:
        mask = mask.filter(ImageFilter.MinFilter(options.shrink * 2 + 1))
    if options.feather:
        mask = mask.filter(ImageFilter.GaussianBlur(options.feather))
    return mask


def decontaminate_edges(image: Image.Image, alpha: Image.Image, palette: list[tuple[int, int, int]]) -> Image.Image:
    """Unmix known border color from anti-aliased pixels to suppress pale halos."""
    rgb = image.convert("RGB")
    out = Image.new("RGBA", rgb.size)
    source, alpha_pixels, result = rgb.load(), alpha.load(), out.load()
    width, height = rgb.size
    for y in range(height):
        for x in range(width):
            a = alpha_pixels[x, y]
            if a <= 2:
                result[x, y] = (0, 0, 0, 0)
                continue
            color = source[x, y]
            # Only unmix neutral pixels that are close to a detected background
            # color. Applying this calculation to a genuinely orange/green edge
            # amplifies saturation and creates a colored fringe instead of fixing
            # the pale JPEG/checkerboard halo.
            distance, background = nearest_background(color, palette)
            saturation = max(color) - min(color)
            if a < 252 and saturation < 34 and distance < 46:
                coverage = max(a / 255.0, 0.18)
                corrected = tuple(
                    max(0, min(255, round((color[i] - (1 - coverage) * background[i]) / coverage)))
                    for i in range(3)
                )
                result[x, y] = (*corrected, a)
            else:
                result[x, y] = (*color, a)
    return out


def process_image(image: Image.Image, options: ProcessingOptions) -> tuple[Image.Image, list[tuple[int, int, int]]]:
    source = ImageOps.exif_transpose(image).convert("RGBA")
    if source.getextrema()[3][0] < 250:
        # Existing alpha is already meaningful; retain it while lightly shrinking halos.
        alpha = source.getchannel("A")
        palette = []
        if options.shrink or options.feather:
            alpha = soften_and_shrink(alpha, options)
        output = source.copy()
        output.putalpha(alpha)
    else:
        palette = detect_background_palette(source)
        hard_mask = edge_connected_background(source, palette, options.tolerance)
        alpha = soften_and_shrink(hard_mask, options)
        output = decontaminate_edges(source, alpha, palette)
    if options.trim:
        bounds = output.getchannel("A").getbbox()
        if bounds:
            output = output.crop(bounds)
    return output, palette


def alpha_bounds(image: Image.Image) -> dict[str, int] | None:
    box = image.getchannel("A").getbbox()
    if not box:
        return None
    left, top, right, bottom = box
    return {"left": left, "top": top, "right": right, "bottom": bottom, "width": right - left, "height": bottom - top}


def make_metadata(asset_id: str, source_name: str, output_name: str, image: Image.Image, fields: dict[str, str], options: ProcessingOptions, palette: list[tuple[int, int, int]]) -> dict:
    tags = [tag.strip() for tag in fields["tags"].split(",") if tag.strip()]
    return {
        "schemaVersion": 1,
        "id": asset_id,
        "source": source_name,
        "image": output_name,
        "category": fields["category"],
        "subtype": fields["subtype"],
        "displayName": fields["display_name"],
        "gridFootprint": {"width": int(fields["grid_width"]), "height": int(fields["grid_height"])},
        "tier": fields["tier"],
        "tags": tags,
        "author": fields["author"],
        "notes": fields["notes"],
        "imageSize": {"width": image.width, "height": image.height},
        "opaqueBounds": alpha_bounds(image),
        "anchor": {"x": float(fields["anchor_x"]), "y": float(fields["anchor_y"])},
        "processing": {
            "backgroundMode": "border-connected auto palette",
            "tolerance": options.tolerance,
            "featherPixels": options.feather,
            "shrinkPixels": options.shrink,
            "trimTransparentBounds": options.trim,
            "detectedBackgroundPalette": ["#{:02X}{:02X}{:02X}".format(*color) for color in palette],
        },
    }


def checkerboard_preview(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    preview = image.convert("RGBA")
    preview.thumbnail(size, Image.Resampling.LANCZOS)
    background = Image.new("RGBA", preview.size, (222, 222, 222, 255))
    tile = max(8, preview.width // 32)
    pixels = background.load()
    for y in range(preview.height):
        for x in range(preview.width):
            if (x // tile + y // tile) % 2:
                pixels[x, y] = (244, 244, 244, 255)
    background.alpha_composite(preview)
    return background


class AssetPngTool(QMainWindow):
    """PySide6 desktop interface; image processing remains UI-independent."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Asset PNG Tool — PNG RGBA + JSON")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.processed_image: Image.Image | None = None
        self.palette: list[tuple[int, int, int]] = []
        self.values: dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_previews())
        splitter.setSizes([330, 960])

    def _build_sidebar(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        panel = QWidget()
        scroll.setWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 10, 6)

        open_button = QPushButton("Abrir imagem")
        open_button.clicked.connect(self.open_image)
        layout.addWidget(open_button)
        self.file_label = QLabel("Nenhuma imagem carregada")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.file_label)

        metadata = QGroupBox("Classificação do asset")
        form = QFormLayout(metadata)
        self._add_line_edit(form, "ID do asset", "asset_id")
        self._add_line_edit(form, "Nome exibido", "display_name")
        self._add_line_edit(form, "Subtipo", "subtype", "cafe")
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.setCurrentText(DEFAULT_CATEGORY)
        form.addRow("Categoria", self.category)
        self.grid_width = self._spin_box(1, 64, 2)
        self.grid_height = self._spin_box(1, 64, 2)
        grid = QWidget(); grid_layout = QHBoxLayout(grid); grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.addWidget(QLabel("X")); grid_layout.addWidget(self.grid_width)
        grid_layout.addWidget(QLabel("Y")); grid_layout.addWidget(self.grid_height)
        form.addRow("Grade", grid)
        self.tier = self._spin_box(1, 99, 1)
        form.addRow("Tier", self.tier)
        self._add_line_edit(form, "Tags (vírgulas)", "tags", "cafe, commerce")
        self._add_line_edit(form, "Autor", "author")
        self.anchor_x = QLineEdit("0.5")
        self.anchor_y = QLineEdit("1.0")
        anchor = QWidget(); anchor_layout = QHBoxLayout(anchor); anchor_layout.setContentsMargins(0, 0, 0, 0)
        anchor_layout.addWidget(QLabel("X")); anchor_layout.addWidget(self.anchor_x)
        anchor_layout.addWidget(QLabel("Y")); anchor_layout.addWidget(self.anchor_y)
        form.addRow("Âncora", anchor)
        layout.addWidget(metadata)

        processing = QGroupBox("Tratamento")
        process_form = QFormLayout(processing)
        self.tolerance = self._spin_box(8, 110, 52)
        self.feather = self._spin_box(0, 8, 2)
        self.shrink = self._spin_box(0, 4, 1)
        self.trim = QCheckBox("Recortar área transparente")
        process_form.addRow("Tolerância de fundo", self.tolerance)
        process_form.addRow("Suavização de borda", self.feather)
        process_form.addRow("Redução de halo", self.shrink)
        process_form.addRow(self.trim)
        layout.addWidget(processing)

        preview_button = QPushButton("Processar / atualizar prévia")
        preview_button.clicked.connect(self.process)
        export_button = QPushButton("Exportar PNG + JSON")
        export_button.clicked.connect(self.export)
        layout.addWidget(preview_button)
        layout.addWidget(export_button)

        layout.addWidget(QLabel("Notas"))
        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Observações para o catálogo do jogo")
        self.notes.setFixedHeight(100)
        layout.addWidget(self.notes)
        self.status = QLabel("Abra uma PNG ou JPG para começar.")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.status)
        layout.addStretch(1)
        return scroll

    def _build_previews(self) -> QWidget:
        area = QWidget()
        layout = QGridLayout(area)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(1, 1)
        layout.addWidget(QLabel("Original"), 0, 0)
        layout.addWidget(QLabel("Tratado (RGBA)"), 0, 1)
        self.original_label = self._preview_label()
        self.processed_label = self._preview_label()
        layout.addWidget(self.original_label, 1, 0)
        layout.addWidget(self.processed_label, 1, 1)
        return area

    @staticmethod
    def _preview_label() -> QLabel:
        label = QLabel("Carregue uma imagem")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(320, 380)
        label.setFrameShape(QFrame.Shape.StyledPanel)
        label.setStyleSheet("QLabel { background: #202225; color: #b6bdc9; }")
        return label

    @staticmethod
    def _spin_box(lower: int, upper: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(lower, upper)
        box.setValue(value)
        return box

    def _add_line_edit(self, form: QFormLayout, label: str, key: str, value: str = "") -> None:
        field = QLineEdit(value)
        self.values[key] = field
        form.addRow(label, field)

    def options(self) -> ProcessingOptions:
        return ProcessingOptions(
            tolerance=self.tolerance.value(),
            feather=self.feather.value(),
            shrink=self.shrink.value(),
            trim=self.trim.isChecked(),
        )

    def open_image(self) -> None:
        chosen, _ = QFileDialog.getOpenFileName(
            self,
            "Escolha a imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.webp);;Todos os arquivos (*.*)",
        )
        if not chosen:
            return
        try:
            self.source_path = Path(chosen)
            with Image.open(self.source_path) as opened:
                self.source_image = opened.copy()
            stem = sanitize_asset_id(self.source_path.stem)
            self.values["asset_id"].setText(stem)
            self.values["display_name"].setText(stem.replace("_", " ").title())
            self.file_label.setText(str(self.source_path))
            self._show_preview(self.original_label, self.source_image)
            self.process()
        except Exception as error:
            self.status.setText(f"Erro ao abrir imagem: {error}")
            QMessageBox.critical(self, "Erro ao abrir", str(error))

    @staticmethod
    def _pixmap_for(image: Image.Image, bounds: tuple[int, int]) -> QPixmap:
        preview = checkerboard_preview(image, bounds)
        return QPixmap.fromImage(ImageQt(preview.convert("RGBA")))

    def _show_preview(self, widget: QLabel, image: Image.Image) -> None:
        pixmap = self._pixmap_for(image, (640, 720))
        widget.setPixmap(pixmap)
        widget.setText("")

    def process(self) -> None:
        if self.source_image is None:
            self.status.setText("Abra uma imagem antes de processar.")
            return
        try:
            self.processed_image, self.palette = process_image(self.source_image, self.options())
            self._show_preview(self.processed_label, self.processed_image)
            colors = ", ".join("#{:02X}{:02X}{:02X}".format(*color) for color in self.palette[:4]) or "alpha existente"
            self.status.setText(f"Pronto. Fundo detectado: {colors}")
        except Exception as error:
            self.status.setText(f"Erro: {error}")
            QMessageBox.critical(self, "Erro no tratamento", str(error))

    def fields(self) -> dict[str, str]:
        return {
            **{key: field.text().strip() for key, field in self.values.items()},
            "category": self.category.currentText(),
            "grid_width": str(self.grid_width.value()),
            "grid_height": str(self.grid_height.value()),
            "tier": str(self.tier.value()),
            "anchor_x": self.anchor_x.text().strip(),
            "anchor_y": self.anchor_y.text().strip(),
            "notes": self.notes.toPlainText().strip(),
        }

    def export(self) -> None:
        if self.source_path is None or self.processed_image is None:
            QMessageBox.warning(self, "Sem imagem", "Abra e processe uma imagem antes de exportar.")
            return
        try:
            fields = self.fields()
            asset_id = sanitize_asset_id(fields["asset_id"])
            int(fields["grid_width"]); int(fields["grid_height"]); float(fields["anchor_x"]); float(fields["anchor_y"])
            destination = QFileDialog.getExistingDirectory(self, "Escolha a pasta de exportação")
            if not destination:
                return
            output_dir = Path(destination)
            png_path = output_dir / f"{asset_id}.png"
            json_path = output_dir / f"{asset_id}.json"
            self.processed_image.save(png_path, "PNG")
            metadata = make_metadata(asset_id, self.source_path.name, png_path.name, self.processed_image, fields, self.options(), self.palette)
            json_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
            self.status.setText(f"Exportado: {png_path.name} + {json_path.name}")
            QMessageBox.information(self, "Exportação concluída", f"Criados:\n{png_path}\n{json_path}")
        except ValueError:
            QMessageBox.critical(self, "Campos inválidos", "Grade e âncoras devem conter números válidos.")
        except Exception as error:
            QMessageBox.critical(self, "Erro ao exportar", str(error))


def run_batch(source_path: Path, output_dir: Path, asset_id: str, options: ProcessingOptions) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(source_path)
    processed, palette = process_image(source, options)
    asset_id = sanitize_asset_id(asset_id)
    png_path = output_dir / f"{asset_id}.png"
    processed.save(png_path, "PNG")
    fields = {"category": DEFAULT_CATEGORY, "subtype": "", "display_name": asset_id, "grid_width": "1", "grid_height": "1", "tier": "1", "tags": "", "author": "", "notes": "", "anchor_x": "0.5", "anchor_y": "1.0"}
    metadata = make_metadata(asset_id, source_path.name, png_path.name, processed, fields, options, palette)
    (output_dir / f"{asset_id}.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported {png_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove city-builder PNG backgrounds and export metadata.")
    parser.add_argument("--batch", type=Path, help="Source image for non-interactive processing")
    parser.add_argument("--out", type=Path, help="Output folder for --batch")
    parser.add_argument("--id", default="asset", help="Asset id for --batch")
    parser.add_argument("--tolerance", type=int, default=52, help="Background tolerance for --batch (8-110)")
    parser.add_argument("--feather", type=int, default=2, help="Edge feather pixels for --batch (0-8)")
    parser.add_argument("--shrink", type=int, default=1, help="Halo shrink pixels for --batch (0-4)")
    parser.add_argument("--trim", action="store_true", help="Trim transparent bounds for --batch")
    args = parser.parse_args()
    if args.batch:
        if args.out is None:
            parser.error("--out is required with --batch")
        if not 8 <= args.tolerance <= 110 or not 0 <= args.feather <= 8 or not 0 <= args.shrink <= 4:
            parser.error("--tolerance must be 8-110, --feather 0-8, and --shrink 0-4")
        run_batch(args.batch, args.out, args.id, ProcessingOptions(
            tolerance=args.tolerance,
            feather=args.feather,
            shrink=args.shrink,
            trim=args.trim,
        ))
    else:
        app = QApplication(sys.argv)
        window = AssetPngTool()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
