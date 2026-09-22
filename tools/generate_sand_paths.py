"""Generate the 16 connected sand-path variants from the prepared sand tile.

Topology matches RoadManager/SidewalkManager exactly:
N=1, E=2, S=4 and W=8.

The source material is prepared first by ground_tile_worker.py. This script
keeps the approved sand texture and adds only subtle topology-aware wear so the
16-mask family is deterministic and visually consistent with the dirt path
pipeline.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ground_tile_worker import DEFAULT_MAX_EDGE_ERROR, edge_error, fill_transparent_edge, harmonize_edges

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
    "sand_path_00_isolated.png", "sand_path_01_end_n.png", "sand_path_02_end_e.png", "sand_path_03_curve_ne.png",
    "sand_path_04_end_s.png", "sand_path_05_straight_ns.png", "sand_path_06_curve_es.png", "sand_path_07_tee_no_w.png",
    "sand_path_08_end_w.png", "sand_path_09_curve_nw.png", "sand_path_10_straight_ew.png", "sand_path_11_tee_no_s.png",
    "sand_path_12_curve_sw.png", "sand_path_13_tee_no_e.png", "sand_path_14_tee_no_n.png", "sand_path_15_cross.png",
)


def display_diamond() -> Image.Image:
    alpha = Image.new("L", (W, H), 0)
    ImageDraw.Draw(alpha).polygon(((W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)), fill=255)
    return alpha


def load_source(path: Path) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    if source.size != (W, H):
        raise ValueError(f"Prepared sand source must be exactly {W}x{H}; got {source.size[0]}x{source.size[1]}")
    return harmonize_edges(fill_transparent_edge(source))


def wear_overlay(mask: int) -> Image.Image:
    """Subtle compressed-sand wear indicates active N/E/S/W connections."""
    wear = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    active = [bit for bit in (N, E, S, WEST) if mask & bit]

    if not active:
        radius = 16 * SS
        draw.ellipse(
            (CENTER[0] - radius, CENTER[1] - radius // 2, CENTER[0] + radius, CENTER[1] + radius // 2),
            fill=(120, 92, 56, 12),
        )
    else:
        for bit in active:
            px, py = PORTS[bit]
            draw.line((CENTER, (px, py)), fill=(112, 84, 49, 24), width=12 * SS)
            draw.line((CENTER, (px, py)), fill=(236, 211, 156, 12), width=5 * SS)

    return wear.filter(ImageFilter.GaussianBlur(SS * 2.0)).resize((W, H), Image.Resampling.LANCZOS)


def render(mask: int, source: Image.Image) -> Image.Image:
    result = Image.alpha_composite(source, wear_overlay(mask))
    result.putalpha(display_diamond())
    return result


def preview(tiles: dict[int, Image.Image], path: Path) -> None:
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
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("assets/terrain/sand_isometric_01.png"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terrain/paths/sand_01"))
    parser.add_argument("--preview", type=Path, default=Path("out/sand_path_autotile_preview.png"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.preview.parent.mkdir(parents=True, exist_ok=True)

    source = load_source(args.source)
    base_error = edge_error(source)
    if base_error > DEFAULT_MAX_EDGE_ERROR:
        raise SystemExit(
            f"shared-edge preparation failed: mean RGB mismatch {base_error:.2f} > {DEFAULT_MAX_EDGE_ERROR:.2f}"
        )

    tiles = {mask: render(mask, source) for mask in range(16)}
    for mask, tile in tiles.items():
        tile.save(args.output_dir / NAMES[mask])
    preview(tiles, args.preview)

    print(
        f"PASS source={args.source} masks=16 edge_error={base_error:.2f} "
        f"max={DEFAULT_MAX_EDGE_ERROR:.2f} output={args.output_dir}"
    )


if __name__ == "__main__":
    main()
