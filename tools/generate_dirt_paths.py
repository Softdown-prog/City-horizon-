"""Generate the 16 connected dirt-path variants from the approved dirt tile.

Topology matches RoadManager/SidewalkManager exactly:
N=1, E=2, S=4 and W=8.

The approved visual source is assets/terrain/dirt_isometric_01.png. This
script never invents a replacement soil material; it only prepares shared
edges, makes the approved texture periodic across the isometric tile lattice,
adds subtle topology-aware wear and writes the canonical 16-mask set.
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


def uv_to_xy(u: float, v: float) -> tuple[float, float]:
    """Map logical square coordinates to the exact raster diamond vertices."""
    u = min(1.0, max(0.0, u))
    v = min(1.0, max(0.0, v))
    top = (W // 2, 0)
    right = (W - 1, H // 2)
    bottom = (W // 2, H - 1)
    left = (0, H // 2)
    weights = (
        ((1.0 - u) * (1.0 - v), top),
        (u * (1.0 - v), right),
        (u * v, bottom),
        ((1.0 - u) * v, left),
    )
    return (
        sum(weight * point[0] for weight, point in weights),
        sum(weight * point[1] for weight, point in weights),
    )


def bilinear_rgb(image: Image.Image, u: float, v: float) -> tuple[float, float, float]:
    x, y = uv_to_xy(u, v)
    x = min(W - 1.0, max(0.0, x))
    y = min(H - 1.0, max(0.0, y))
    x0, y0 = int(x), int(y)
    x1, y1 = min(W - 1, x0 + 1), min(H - 1, y0 + 1)
    tx, ty = x - x0, y - y0
    px = image.load()

    def rgb(ix: int, iy: int) -> tuple[float, float, float]:
        r, g, b, _ = px[ix, iy]
        return float(r), float(g), float(b)

    a, b = rgb(x0, y0), rgb(x1, y0)
    c, d = rgb(x0, y1), rgb(x1, y1)
    return tuple(
        ((a[i] * (1.0 - tx) + b[i] * tx) * (1.0 - ty) +
         (c[i] * (1.0 - tx) + d[i] * tx) * ty)
        for i in range(3)
    )


def smoothstep(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


def mean_rgb(*colors: tuple[float, float, float]) -> tuple[float, float, float]:
    count = float(len(colors))
    return tuple(sum(color[i] for color in colors) / count for i in range(3))


def harmonize_shared_edges(source: Image.Image, band: float = 0.18) -> Image.Image:
    """Force opposite isometric borders to share the same texture samples.

    The logical diamond is a square in (u,v). For each texel near a u seam we
    blend toward the mean of u=0 and u=1 at the same v. The same is done for v.
    Where both bands overlap we blend toward the mean of all four corners, so
    correcting one seam cannot re-open the other. The centre stays untouched.
    """
    result = source.copy()
    src = source.load()
    dst = result.load()

    corner_mean = mean_rgb(
        bilinear_rgb(source, 0.0, 0.0),
        bilinear_rgb(source, 1.0, 0.0),
        bilinear_rgb(source, 0.0, 1.0),
        bilinear_rgb(source, 1.0, 1.0),
    )

    for y in range(H):
        for x in range(W):
            if source.getpixel((x, y))[3] == 0:
                continue

            # Stable inverse for the logical 2:1 grid. The exact raster diamond
            # differs by at most one pixel at right/bottom, which is intentional.
            s = y / (H * 0.5)
            d = (x - W * 0.5) / (W * 0.5)
            u = min(1.0, max(0.0, (s + d) * 0.5))
            v = min(1.0, max(0.0, (s - d) * 0.5))

            base = tuple(float(channel) for channel in src[x, y][:3])
            du = min(u, 1.0 - u)
            dv = min(v, 1.0 - v)
            wu = 1.0 - smoothstep(du / band) if du < band else 0.0
            wv = 1.0 - smoothstep(dv / band) if dv < band else 0.0

            seam_u = mean_rgb(
                bilinear_rgb(source, 0.0, v),
                bilinear_rgb(source, 1.0, v),
            )
            seam_v = mean_rgb(
                bilinear_rgb(source, u, 0.0),
                bilinear_rgb(source, u, 1.0),
            )

            # Bilinear blend of four targets. At u=0/1 this resolves to the same
            # seam_u value; at v=0/1 it resolves to the same seam_v value.
            color = tuple(
                base[i] * (1.0 - wu) * (1.0 - wv)
                + seam_u[i] * wu * (1.0 - wv)
                + seam_v[i] * (1.0 - wu) * wv
                + corner_mean[i] * wu * wv
                for i in range(3)
            )
            dst[x, y] = tuple(int(round(min(255.0, max(0.0, c)))) for c in color) + (255,)

    result.putalpha(display_diamond())
    return result


def load_source(path: Path) -> Image.Image:
    source = Image.open(path).convert("RGBA")
    if source.size != (W, H):
        raise ValueError(f"Approved dirt source must be exactly {W}x{H}; got {source.size[0]}x{source.size[1]}")

    # The normalized source intentionally contains anti-aliased transparent
    # edge pixels. For connected ground those pixels reveal the grass below.
    # Fill them from the nearest interior texel before applying the canonical
    # hard diamond alpha. This changes only the technical edge, not the art.
    src = source.load()
    filled = Image.new("RGBA", source.size, (0, 0, 0, 0))
    dst = filled.load()

    opaque = []
    for y in range(H):
        for x in range(W):
            if src[x, y][3] >= 240:
                opaque.append((x, y))

    if not opaque:
        raise ValueError("Approved dirt source has no opaque pixels")

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
    return harmonize_shared_edges(filled)


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


def edge_error(tile: Image.Image) -> float:
    """Mean RGB mismatch of opposite logical edges; lower is better."""
    samples = []
    for i in range(1, 32):
        t = i / 32.0
        for a, b in (((0.0, t), (1.0, t)), ((t, 0.0), (t, 1.0))):
            ca = bilinear_rgb(tile, *a)
            cb = bilinear_rgb(tile, *b)
            samples.append(sum(abs(ca[j] - cb[j]) for j in range(3)) / 3.0)
    return sum(samples) / len(samples)


def preview(tiles: dict[int, Image.Image], path: Path) -> None:
    # Deliberately no grid overlay: this preview is a seam gate, not a map
    # topology debug view. A connected patch makes block repetition obvious.
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

    base_error = edge_error(source)
    if base_error > 3.0:
        raise SystemExit(f"shared-edge harmonization failed: mean RGB mismatch {base_error:.2f} > 3.00")
    print(f"PASS source={args.source} masks=16 edge_error={base_error:.2f} output={args.output_dir}")


if __name__ == "__main__":
    main()
