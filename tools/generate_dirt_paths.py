"""Generate the 16 connected dirt-path variants from the approved dirt tile.

Topology matches RoadManager/SidewalkManager exactly:
N=1, E=2, S=4 and W=8.

The approved visual source is assets/terrain/dirt_isometric_01.png.  This
script never invents a replacement soil material; it only prepares shared
edges, adds subtle topology-aware wear and writes the canonical 16-mask set.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

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
    "dirt_path_00_isolated.png", "dirt_path_01_end_n.png", "dirt_path_02_end_e.png", "dirt_path_03_curve_ne.png",
    "dirt_path_04_end_s.png", "dirt_path_05_straight_ns.png", "dirt_path_06_curve_es.png", "dirt_path_07_tee_no_w.png",
    "dirt_path_08_end_w.png", "dirt_path_09_curve_nw.png", "dirt_path_10_straight_ew.png", "dirt_path_11_tee_no_s.png",
    "dirt_path_12_curve_sw.png", "dirt_path_13_tee_no_e.png", "dirt_path_14_tee_no_n.png", "dirt_path_15_cross.png",
)


def display_diamond() -> Image.Image:
    """Hard shared edge so adjacent tiles never reveal grass hairlines."""
    alpha = Image.new("L", (W, H), 0)
    ImageDraw.Draw(alpha).polygon(((W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)), fill=255)
    return alpha


def load_source(path: Path) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    if source.size != (W, H):
        raise ValueError(f"Approved dirt source must be exactly {W}x{H}; got {source.size[0]}x{source.size[1]}")

    # The normalized source intentionally contains anti-aliased transparent
    # edge pixels.  For connected ground those pixels reveal the grass below.
    # Fill them from the nearest interior texel before applying the canonical
    # hard diamond alpha.  This changes only the technical edge, not the art.
    src = source.load()
    filled = Image.new("RGBA", source.size, (0, 0, 0, 0))
    dst = filled.load()
    cx, cy = W // 2, H // 2

    opaque = []
    for y in range(H):
        for x in range(W):
            if src[x, y][3] >= 240:
                opaque.append((x, y))

    if not opaque:
        raise ValueError("Approved dirt source has no opaque pixels")

    # 128x64 is tiny; the explicit nearest search keeps this dependency-free
    # and deterministic on every agent/runner.
    for y in range(H):
        for x in range(W):
            pixel = src[x, y]
            if pixel[3] >= 240:
                dst[x, y] = pixel
                continue
            nx, ny = min(opaque, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
            r, g, b, _ = src[nx, ny]
            dst[x, y] = (r, g, b, 255)

    filled.putalpha(display_diamond())
    return filled


def wear_overlay(mask: int) -> Image.Image:
    """Very subtle compacted wear indicates active N/E/S/W connections."""
    wear = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    active = [bit for bit in (N, E, S, WEST) if mask & bit]

    if not active:
        radius = 16 * SS
        draw.ellipse(
            (CENTER[0] - radius, CENTER[1] - radius // 2, CENTER[0] + radius, CENTER[1] + radius // 2),
            fill=(76, 48, 28, 18),
        )
    else:
        for bit in active:
            px, py = PORTS[bit]
            draw.line((CENTER, (px, py)), fill=(65, 40, 24, 38), width=13 * SS)
            draw.line((CENTER, (px, py)), fill=(196, 145, 85, 16), width=5 * SS)

    return wear.filter(ImageFilter.GaussianBlur(SS * 2.0)).resize((W, H), Image.Resampling.LANCZOS)


def render(mask: int, source: Image.Image) -> Image.Image:
    result = Image.alpha_composite(source, wear_overlay(mask))
    result.putalpha(display_diamond())
    return result


def preview(tiles: dict[int, Image.Image], path: Path) -> None:
    canvas = Image.new("RGBA", (896, 448), (87, 126, 62, 255))
    origin = (224, 54)

    def at(x: int, y: int) -> tuple[int, int]:
        return origin[0] + (x - y) * 64 - 64, origin[1] + (x + y) * 32

    layout = [
        (0, 0, 5), (0, -1, 5), (0, -2, 5),
        (3, 0, 10), (4, 0, 10), (5, 0, 10),
        (2, 3, 3), (4, 3, 7), (6, 3, 15),
        (2, 5, 1), (4, 5, 6), (6, 5, 14),
    ]
    for x, y, mask in layout:
        canvas.alpha_composite(tiles[mask], at(x, y))
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("assets/terrain/dirt_isometric_01.png"))
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terrain/paths/dirt_01"))
    parser.add_argument("--preview", type=Path, default=Path("work/dirt_path_autotile_preview.png"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.preview.parent.mkdir(parents=True, exist_ok=True)

    source = load_source(args.source)
    tiles = {mask: render(mask, source) for mask in range(16)}
    for mask, tile in tiles.items():
        tile.save(args.output_dir / NAMES[mask])
    preview(tiles, args.preview)

    print(f"PASS source={args.source} masks=16 output={args.output_dir}")


if __name__ == "__main__":
    main()
