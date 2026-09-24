#!/usr/bin/env python3
"""Reusable City Horizon ground-tile preparation worker.

One command takes a source image and produces a canonical 128x64 RGBA
isometric ground tile plus a seam preview/report. It is intentionally generic
so future dirt, sand, mud, snow, stone and similar ground materials can reuse
the same intake instead of rebuilding one-off cleanup scripts.

Pipeline:
1. normalize arbitrary PNG/JPG input to the canonical 128x64 diamond;
2. fill transparent texels from nearby interior texture before sampling the edge;
3. optionally replace a baked visual border/bevel with nearby interior texture;
4. optionally decontaminate obvious dark/saturated edge outliers using nearby valid material samples;
5. harden the diamond alpha so connected tiles cannot reveal grass hairlines;
6. match only the exact opposite-edge samples needed for seamless repetition;
7. render a grid-free repeated preview and write JSON metrics.

The seam stage deliberately does not diffuse border colours into the interior.
That keeps authored texture/style intact and avoids radial streaks or stains.
This worker does not invent topology/autotile art. A topology-specific generator
can consume its prepared PNG afterwards.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import tempfile
from pathlib import Path

from PIL import Image

from normalize_atomic_path_tile import normalize
from tile_geometry import diamond_mask

W, H = 128, 64
DEFAULT_MAX_EDGE_ERROR = 6.0


def strip_edge_band(source: Image.Image, band_pixels: int) -> Image.Image:
    """Replace a baked rim/bevel with nearby interior texture.

    Samples move inward along the local edge normal instead of toward the tile
    centre. That removes a raised rim without stretching the material into a
    radial/star pattern at the four diamond corners.
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

            dx = x - cx
            dy = y - cy
            d = abs(dx) / (W / 2.0) + abs(dy) / (H / 2.0)
            edge_depth = (1.0 - d) * (H / 2.0)
            if edge_depth >= band_pixels:
                continue

            sign_x = -1.0 if dx < 0 else 1.0
            sign_y = -1.0 if dy < 0 else 1.0
            nx = -sign_x / (W / 2.0)
            ny = -sign_y / (H / 2.0)
            length = max(1e-6, (nx * nx + ny * ny) ** 0.5)
            nx /= length
            ny /= length

            pull = max(1.0, band_pixels - edge_depth + 1.0)
            sx = round(x + nx * pull)
            sy = round(y + ny * pull)
            sx = min(W - 1, max(0, sx))
            sy = min(H - 1, max(0, sy))

            for step in range(0, band_pixels + 3):
                tx = round(sx + nx * step)
                ty = round(sy + ny * step)
                if 0 <= tx < W and 0 <= ty < H and mp[tx, ty] != 0:
                    sx, sy = tx, ty
                    break

            dst[x, y] = src[sx, sy]

    result.putalpha(mask)
    return result


def decontaminate_edge_outliers(source: Image.Image, band_pixels: int) -> tuple[Image.Image, int]:
    """Replace obvious non-material pixels near the diamond perimeter.

    This is intentionally conservative and only touches the outer band. A pixel
    is considered contaminated when it is very dark, or when it is strongly
    saturated red/blue/green compared with the warm sand/soil family. Replacement
    samples are taken from valid pixels farther inward along the local edge normal.
    The tile centre is never modified by this stage.
    """
    if band_pixels <= 0:
        return source.convert("RGBA"), 0

    source = source.convert("RGBA")
    src = source.load()
    result = source.copy()
    dst = result.load()
    mask = diamond_mask()
    mp = mask.load()
    cx, cy = W / 2.0, H / 2.0
    replaced = 0

    def contaminated(r: int, g: int, b: int, a: int) -> bool:
        if a < 240:
            return False
        value = max(r, g, b)
        if value < 70:
            return True
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        if v < 0.42 and s > 0.45:
            return True
        # Reject vivid red/magenta/green/blue specks but keep warm yellow/orange sand.
        hue_deg = h * 360.0
        non_sand_hue = hue_deg < 18.0 or 95.0 < hue_deg < 330.0
        return s > 0.68 and v > 0.28 and non_sand_hue

    for y in range(H):
        for x in range(W):
            if mp[x, y] == 0:
                continue
            dx = x - cx
            dy = y - cy
            d = abs(dx) / (W / 2.0) + abs(dy) / (H / 2.0)
            edge_depth = (1.0 - d) * (H / 2.0)
            if edge_depth >= band_pixels:
                continue
            r, g, b, a = src[x, y]
            if not contaminated(r, g, b, a):
                continue

            sign_x = -1.0 if dx < 0 else 1.0
            sign_y = -1.0 if dy < 0 else 1.0
            nx = (-sign_x / (W / 2.0))
            ny = (-sign_y / (H / 2.0))
            length = max(1e-6, (nx * nx + ny * ny) ** 0.5)
            nx /= length
            ny /= length

            replacement = None
            for step in range(band_pixels + 2, band_pixels + 28):
                tx = round(x + nx * step)
                ty = round(y + ny * step)
                if not (0 <= tx < W and 0 <= ty < H) or mp[tx, ty] == 0:
                    continue
                tr, tg, tb, ta = src[tx, ty]
                if ta >= 240 and not contaminated(tr, tg, tb, ta):
                    replacement = (tr, tg, tb, 255)
                    break
            if replacement is not None:
                dst[x, y] = replacement
                replaced += 1

    result.putalpha(mask)
    return result, replaced


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


def harmonize_edges(source: Image.Image, band_pixels: int = 0) -> Image.Image:
    """Match exact opposite border samples without touching interior texels."""
    del band_pixels
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


def count_near_black_pixels(tile: Image.Image) -> int:
    """Count opaque black residue inside the tile, independent of edge averages."""
    image = tile.convert("RGBA")
    pixels = image.load()
    return sum(
        pixels[x, y][3] >= 240 and max(pixels[x, y][:3]) < 48
        for y in range(image.height) for x in range(image.width)
    )


def prepare(source_path: Path, output_path: Path, preview_path: Path, report_path: Path, max_edge_error: float, strip_edge_pixels: int = 0, decontaminate_edge_pixels: int = 0, max_dark_pixels: int | None = None) -> dict:
    if max_dark_pixels is not None and max_dark_pixels < 0:
        raise ValueError("max_dark_pixels must be non-negative")
    with tempfile.TemporaryDirectory() as tmp:
        normalized_path = Path(tmp) / "normalized.png"
        with Image.open(source_path) as original:
            already_canonical = original.size == (W, H) and original.mode == "RGBA"
        if already_canonical:
            Image.open(source_path).convert("RGBA").save(normalized_path)
        else:
            normalize(source_path, normalized_path)

        normalized = Image.open(normalized_path).convert("RGBA")
        # The reference can have transparent gaps inside the canonical diamond.
        # Fill them while source alpha still tells us which texels are valid;
        # stripping first would copy invisible black RGB and make it opaque.
        filled = fill_transparent_edge(normalized)
        flattened = strip_edge_band(filled, strip_edge_pixels)
        decontaminated, replaced = decontaminate_edge_outliers(flattened, decontaminate_edge_pixels)
        prepared = harmonize_edges(decontaminated)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(output_path)
    repeated_preview(prepared, preview_path)
    error = edge_error(prepared)
    dark_pixels = count_near_black_pixels(prepared)
    report = {
        "schema": "CITY_HORIZON_GROUND_TILE_WORKER_V1",
        "ok": error <= max_edge_error and (max_dark_pixels is None or dark_pixels <= max_dark_pixels),
        "source": str(source_path),
        "output": str(output_path),
        "preview": str(preview_path),
        "width": W,
        "height": H,
        "mode": "RGBA",
        "stripEdgePixels": strip_edge_pixels,
        "decontaminateEdgePixels": decontaminate_edge_pixels,
        "decontaminatedPixels": replaced,
        "edgeHarmonization": "exact-border-only",
        "edgeError": round(error, 4),
        "maxEdgeError": max_edge_error,
        "nearBlackPixels": dark_pixels,
        "maxNearBlackPixels": max_dark_pixels,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["ok"]:
        raise SystemExit(
            f"ground tile gate failed: edge_error={error:.2f} (max {max_edge_error:.2f}), "
            f"near_black_pixels={dark_pixels} (max {max_dark_pixels})"
        )
    print(
        f"PASS ground tile prepared: {output_path} edge_error={error:.2f} "
        f"strip_edge={strip_edge_pixels} decontaminated={replaced}"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and seam-check a City Horizon 128x64 isometric ground tile.")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preview", type=Path, default=Path("out/ground_tile_preview.png"))
    parser.add_argument("--report", type=Path, default=Path("out/ground_tile_report.json"))
    parser.add_argument("--max-edge-error", type=float, default=DEFAULT_MAX_EDGE_ERROR)
    parser.add_argument("--strip-edge-band", type=int, default=0, help="Replace this many boundary pixels with interior texture to remove a baked rim/bevel.")
    parser.add_argument("--decontaminate-edge-band", type=int, default=0, help="Replace obvious dark/saturated outlier pixels within this many boundary pixels using valid interior material samples.")
    parser.add_argument("--max-dark-pixels", type=int, default=None, help="Optional maximum opaque near-black pixels; use 0 for light materials such as sand.")
    args = parser.parse_args()
    prepare(
        args.source,
        args.output,
        args.preview,
        args.report,
        args.max_edge_error,
        args.strip_edge_band,
        args.decontaminate_edge_band,
        args.max_dark_pixels,
    )


if __name__ == "__main__":
    main()
