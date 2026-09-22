#!/usr/bin/env python3
"""Reusable City Horizon ground-tile preparation worker.

One command takes a source image and produces a canonical 128x64 RGBA
isometric ground tile plus a seam preview/report. It is intentionally generic
so future dirt, sand, mud, snow, stone and similar ground materials can reuse
the same intake instead of rebuilding one-off cleanup scripts.

Pipeline:
1. normalize arbitrary PNG/JPG input to the canonical 128x64 diamond;
2. optionally replace a baked visual border/bevel with nearby interior texture;
3. fill anti-aliased transparent edge texels from nearby interior texture;
4. harden the diamond alpha so connected tiles cannot reveal grass hairlines;
5. soften opposite-edge colour mismatch in a narrow border band;
6. render a grid-free repeated preview and write JSON metrics.

This worker does not invent topology/autotile art. A topology-specific generator
can consume its prepared PNG afterwards.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from normalize_atomic_path_tile import normalize

W, H = 128, 64
DEFAULT_MAX_EDGE_ERROR = 6.0


def diamond_mask() -> Image.Image:
    alpha = Image.new("L", (W, H), 0)
    ImageDraw.Draw(alpha).polygon(((W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)), fill=255)
    return alpha


def strip_edge_band(source: Image.Image, band_pixels: int) -> Image.Image:
    """Replace a baked rim/bevel with samples pulled from the interior texture.

    Generated source art sometimes arrives as a raised diamond with a visible
    side wall. Ground tiles must be a flat surface. For pixels near the diamond
    boundary this function samples farther toward the centre, preserving the
    material while discarding the decorative thickness/rim.
    """
    if band_pixels <= 0:
        return source.convert("RGBA")
    source = source.convert("RGBA")
    src = source.load()
    result = source.copy()
    dst = result.load()
    cx, cy = W / 2.0, H / 2.0
    mask = diamond_mask()
    mp = mask.load()

    for y in range(H):
        for x in range(W):
            if mp[x, y] == 0:
                continue
            # 2:1 diamond distance: boundary is |x-cx|/64 + |y-cy|/32 = 1.
            d = abs(x - cx) / (W / 2.0) + abs(y - cy) / (H / 2.0)
            edge_depth = (1.0 - d) * (H / 2.0)
            if edge_depth >= band_pixels:
                continue
            # Pull the sample inward by the missing depth plus one pixel.
            pull = max(1.0, band_pixels - edge_depth + 1.0)
            vx, vy = cx - x, cy - y
            length = max(1.0, (vx * vx + vy * vy) ** 0.5)
            sx = round(x + vx / length * pull)
            sy = round(y + vy / length * pull)
            sx = min(W - 1, max(0, sx))
            sy = min(H - 1, max(0, sy))
            dst[x, y] = src[sx, sy]
    result.putalpha(mask)
    return result


def fill_transparent_edge(source: Image.Image) -> Image.Image:
    source = source.convert("RGBA")
    src = source.load()
    opaque = [(x, y) for y in range(H) for x in range(W) if src[x, y][3] >= 240]
    if not opaque:
        raise ValueError("source has no opaque pixels")

    result = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dst = result.load()
    for y in range(H):
        for x in range(W):
            if src[x, y][3] >= 240:
                dst[x, y] = src[x, y]
                continue
            nx, ny = min(opaque, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
            r, g, b, _ = src[nx, ny]
            dst[x, y] = (r, g, b, 255)
    result.putalpha(diamond_mask())
    return result


def edge_points(a: tuple[int, int], b: tuple[int, int], count: int = 33) -> list[tuple[int, int]]:
    points = []
    for i in range(count):
        t = i / (count - 1)
        x = round(a[0] * (1.0 - t) + b[0] * t)
        y = round(a[1] * (1.0 - t) + b[1] * t)
        points.append((x, y))
    return points


def edge_error(tile: Image.Image) -> float:
    """Mean RGB mismatch between opposite raster edges of the 2:1 diamond."""
    top, right, bottom, left = (W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)
    pairs = (
        (edge_points(top, left), edge_points(right, bottom)),
        (edge_points(top, right), edge_points(left, bottom)),
    )
    px = tile.convert("RGBA").load()
    values: list[float] = []
    for first, second in pairs:
        for a, b in zip(first, second):
            ca, cb = px[a[0], a[1]], px[b[0], b[1]]
            values.append(sum(abs(ca[i] - cb[i]) for i in range(3)) / 3.0)
    return sum(values) / len(values)


def harmonize_edges(source: Image.Image, band_pixels: int = 8) -> Image.Image:
    """Blend opposite raster borders toward their shared mean, inward gradually."""
    result = source.copy().convert("RGBA")
    px = result.load()
    top, right, bottom, left = (W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)
    edge_pairs = (
        (edge_points(top, left, 65), edge_points(right, bottom, 65)),
        (edge_points(top, right, 65), edge_points(left, bottom, 65)),
    )

    for first, second in edge_pairs:
        for a, b in zip(first, second):
            ca, cb = px[a[0], a[1]], px[b[0], b[1]]
            mean = tuple(round((ca[i] + cb[i]) / 2) for i in range(3)) + (255,)
            px[a[0], a[1]] = mean
            px[b[0], b[1]] = mean

    centre = (W // 2, H // 2)
    border_samples = []
    for first, second in edge_pairs:
        border_samples.extend(first)
        border_samples.extend(second)
    for bx, by in border_samples:
        br, bg, bb, _ = px[bx, by]
        for depth in range(1, band_pixels + 1):
            t = depth / (band_pixels + 1)
            x = round(bx * (1.0 - t) + centre[0] * t)
            y = round(by * (1.0 - t) + centre[1] * t)
            if not (0 <= x < W and 0 <= y < H) or px[x, y][3] == 0:
                continue
            strength = (1.0 - t) * 0.22
            r, g, b, a = px[x, y]
            px[x, y] = (
                round(r * (1.0 - strength) + br * strength),
                round(g * (1.0 - strength) + bg * strength),
                round(b * (1.0 - strength) + bb * strength),
                a,
            )

    result.putalpha(diamond_mask())
    return result


def repeated_preview(tile: Image.Image, path: Path) -> None:
    canvas = Image.new("RGBA", (768, 384), (87, 126, 62, 255))
    origin_x, origin_y = 384, 48
    for y in range(-2, 4):
        for x in range(-3, 4):
            sx = origin_x + (x - y) * 64 - 64
            sy = origin_y + (x + y) * 32
            canvas.alpha_composite(tile, (sx, sy))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def prepare(source_path: Path, output_path: Path, preview_path: Path, report_path: Path, max_edge_error: float, strip_edge_pixels: int = 0) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        normalized_path = Path(tmp) / "normalized.png"
        with Image.open(source_path) as original:
            already_canonical = original.size == (W, H) and original.mode == "RGBA"
        if already_canonical:
            Image.open(source_path).convert("RGBA").save(normalized_path)
        else:
            normalize(source_path, normalized_path)

        normalized = Image.open(normalized_path).convert("RGBA")
        flattened = strip_edge_band(normalized, strip_edge_pixels)
        prepared = harmonize_edges(fill_transparent_edge(flattened))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(output_path)
    repeated_preview(prepared, preview_path)
    error = edge_error(prepared)
    report = {
        "schema": "CITY_HORIZON_GROUND_TILE_WORKER_V1",
        "ok": error <= max_edge_error,
        "source": str(source_path),
        "output": str(output_path),
        "preview": str(preview_path),
        "width": W,
        "height": H,
        "mode": "RGBA",
        "stripEdgePixels": strip_edge_pixels,
        "edgeError": round(error, 4),
        "maxEdgeError": max_edge_error,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(f"ground tile seam gate failed: edge_error={error:.2f} > {max_edge_error:.2f}")
    print(f"PASS ground tile prepared: {output_path} edge_error={error:.2f} strip_edge={strip_edge_pixels}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and seam-check a City Horizon 128x64 isometric ground tile.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preview", type=Path, default=Path("out/ground_tile_preview.png"))
    parser.add_argument("--report", type=Path, default=Path("out/ground_tile_report.json"))
    parser.add_argument("--max-edge-error", type=float, default=DEFAULT_MAX_EDGE_ERROR)
    parser.add_argument("--strip-edge-band", type=int, default=0, help="Replace this many boundary pixels with interior texture to remove a baked rim/bevel.")
    args = parser.parse_args()
    prepare(args.source, args.output, args.preview, args.report, args.max_edge_error, args.strip_edge_band)


if __name__ == "__main__":
    main()
