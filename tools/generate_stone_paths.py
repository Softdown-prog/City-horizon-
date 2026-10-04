"""Generate a City Horizon stone-path candidate family from an authored source PNG.

This tool follows the canonical tile pipeline:
- preprocess only the flat near-white canvas around the authored diamond;
- use ground_tile_worker.prepare() for canonical 128x64 normalization/seam work;
- generate the 16 N/E/S/W path masks with subtle topology-aware wear;
- write technical report and visual previews under out/ for human approval.

It intentionally does not publish to runtime assets. Promotion happens only after
visual approval, per tools/tiles/README.md.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ground_tile_worker import prepare
from tile_geometry import diamond_mask

W, H, SS = 128, 64, 4
NW, NH = W * SS, H * SS
N, E, S, WEST = 1, 2, 4, 8
PORTS = {
    N: (96 * SS, 16 * SS),
    E: (96 * SS, 48 * SS),
    S: (32 * SS, 48 * SS),
    WEST: (32 * SS, 16 * SS),
}
CENTER = (64 * SS, 32 * SS)
NAMES = (
    "stone_path_00_isolated.png", "stone_path_01_end_n.png", "stone_path_02_end_e.png", "stone_path_03_curve_ne.png",
    "stone_path_04_end_s.png", "stone_path_05_straight_ns.png", "stone_path_06_curve_es.png", "stone_path_07_tee_no_w.png",
    "stone_path_08_end_w.png", "stone_path_09_curve_nw.png", "stone_path_10_straight_ew.png", "stone_path_11_tee_no_s.png",
    "stone_path_12_curve_sw.png", "stone_path_13_tee_no_e.png", "stone_path_14_tee_no_n.png", "stone_path_15_cross.png",
)


def remove_flat_white_canvas(source: Path, output: Path, threshold: int = 245) -> None:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha and red >= threshold and green >= threshold and blue >= threshold:
                pixels[x, y] = (red, green, blue, 0)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, "PNG")


def wear_overlay(mask: int) -> Image.Image:
    wear = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    active = [bit for bit in (N, E, S, WEST) if mask & bit]

    if not active:
        rx, ry = 16 * SS, 8 * SS
        draw.ellipse(
            (CENTER[0] - rx, CENTER[1] - ry, CENTER[0] + rx, CENTER[1] + ry),
            fill=(70, 64, 58, 10),
        )
    else:
        for bit in active:
            port = PORTS[bit]
            draw.line((CENTER, port), fill=(62, 58, 54, 18), width=10 * SS)
            draw.line((CENTER, port), fill=(220, 215, 205, 7), width=4 * SS)

    return wear.filter(ImageFilter.GaussianBlur(SS * 1.8)).resize((W, H), Image.Resampling.LANCZOS)


def render(mask: int, source: Image.Image) -> Image.Image:
    result = Image.alpha_composite(source, wear_overlay(mask))
    result.putalpha(diamond_mask())
    return result


def autotile_preview(tiles: dict[int, Image.Image], path: Path) -> None:
    canvas = Image.new("RGBA", (896, 448), (87, 126, 62, 255))
    origin = (320, 54)

    def at(x: int, y: int) -> tuple[int, int]:
        return origin[0] + (x - y) * 64 - 64, origin[1] + (x + y) * 32

    layout = [
        (0, 0, 2), (1, 0, 10), (2, 0, 10), (3, 0, 8),
        (2, -2, 4), (2, -1, 5), (2, 0, 15), (2, 1, 5), (2, 2, 1),
        (-1, 3, 6), (0, 3, 9), (4, 3, 3), (5, 3, 12),
    ]
    for x, y, mask in layout:
        canvas.alpha_composite(tiles[mask], at(x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("Converter/file_000000002c5c820ea492fb76b85d5fb1.png"),
    )
    parser.add_argument("--output-root", type=Path, default=Path("out/stone_path_01"))
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    base = args.output_root / "stone_path_base_128x64.png"
    repeat_preview = args.output_root / "stone_path_repeat_preview.png"
    worker_report = args.output_root / "stone_path_worker_report.json"
    family_dir = args.output_root / "stone_01"
    family_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        transparent_source = Path(tmp) / "stone_source_transparent.png"
        remove_flat_white_canvas(args.source, transparent_source)
        report = prepare(
            transparent_source,
            base,
            repeat_preview,
            worker_report,
            max_edge_error=6.0,
            strip_edge_pixels=2,
            decontaminate_edge_pixels=2,
            max_dark_pixels=None,
        )

    prepared = Image.open(base).convert("RGBA")
    tiles = {mask: render(mask, prepared) for mask in range(16)}
    for mask, tile in tiles.items():
        tile.save(family_dir / NAMES[mask], "PNG")

    preview_path = args.output_root / "stone_path_autotile_preview.png"
    autotile_preview(tiles, preview_path)

    manifest = {
        "contract": "CH_ATOMIC_PATH_FAMILY_V1",
        "id": "stone_path_01",
        "displayName": "Caminho de Pedras",
        "tileCanvas": {"width": W, "height": H, "projection": "isometric_2_to_1"},
        "connectivity": {"bits": {"N": 1, "E": 2, "S": 4, "W": 8}, "variantCount": 16},
        "source": str(args.source),
        "base": base.name,
        "variants": list(NAMES),
        "workerReport": report,
        "promotionState": "candidate-awaiting-visual-approval",
    }
    (args.output_root / "stone_path_01.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"PASS stone path candidate: source={args.source} masks=16 "
        f"edge_error={report['edgeError']} preview={preview_path}"
    )


if __name__ == "__main__":
    main()
