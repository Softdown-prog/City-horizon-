#!/usr/bin/env python3
"""Validate the actual 16-mask path family, including compatible neighbors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops

from ground_tile_worker import count_near_black_pixels, edge_points
from tile_geometry import TILE_HEIGHT, TILE_WIDTH, diamond_mask

TOP, RIGHT = (TILE_WIDTH // 2, 0), (TILE_WIDTH - 1, TILE_HEIGHT // 2)
BOTTOM, LEFT = (TILE_WIDTH // 2, TILE_HEIGHT - 1), (0, TILE_HEIGHT // 2)
# Each pair follows the same sample ordering as ground_tile_worker.harmonize_edges.
SIDES = (
    ("W-E", 8, 2, edge_points(TOP, LEFT), edge_points(RIGHT, BOTTOM)),
    ("N-S", 1, 4, edge_points(TOP, RIGHT), edge_points(LEFT, BOTTOM)),
)


def inspect_family(directory: Path, prefix: str, *, max_pair_error: float = 6.0,
                   max_pixel_error: float = 48.0, max_dark_pixels: int | None = None) -> dict:
    errors = []
    images = {}
    expected_alpha = diamond_mask()
    for mask in range(16):
        paths = list(directory.glob(f"{prefix}_{mask:02d}_*.png"))
        if len(paths) != 1:
            errors.append(f"mask {mask:02d}: expected one PNG, found {len(paths)}")
            continue
        path = paths[0]
        with Image.open(path) as source:
            if source.mode != "RGBA" or source.size != (TILE_WIDTH, TILE_HEIGHT):
                errors.append(f"{path.name}: expected {TILE_WIDTH}x{TILE_HEIGHT} RGBA")
                continue
            image = source.copy()
        if ImageChops.difference(image.getchannel("A"), expected_alpha).getbbox():
            errors.append(f"{path.name}: alpha differs from the canonical diamond")
        dark = count_near_black_pixels(image)
        if max_dark_pixels is not None and dark > max_dark_pixels:
            errors.append(f"{path.name}: {dark} near-black pixels (max {max_dark_pixels})")
        images[mask] = image

    worst = {"mean": 0.0, "pixel": 0.0, "side": None, "masks": None}
    worst_pixel = 0.0
    if len(images) == 16:
        pixels = {mask: image.load() for mask, image in images.items()}
        for side, bit_a, bit_b, points_a, points_b in SIDES:
            for a in range(16):
                for b in range(16):
                    if bool(a & bit_a) != bool(b & bit_b):
                        continue
                    # Rasterized 2:1 edges have a one-pixel alpha stagger. A
                    # transparent texel has arbitrary RGB and cannot form a seam.
                    differences = [
                        sum(abs(pixels[a][x, y][channel] - pixels[b][u, v][channel])
                            for channel in range(3)) / 3.0
                        for (x, y), (u, v) in zip(points_a, points_b)
                        if pixels[a][x, y][3] >= 240 and pixels[b][u, v][3] >= 240
                    ]
                    if not differences:
                        errors.append(f"{side} masks {a:02d}/{b:02d}: no shared opaque edge samples")
                        continue
                    mean, peak = sum(differences) / len(differences), max(differences)
                    worst_pixel = max(worst_pixel, peak)
                    if mean > worst["mean"]:
                        worst = {"mean": round(mean, 4), "pixel": round(peak, 4),
                                 "side": side, "masks": [a, b]}
                    if mean > max_pair_error or peak > max_pixel_error:
                        errors.append(f"{side} masks {a:02d}/{b:02d}: mean {mean:.2f}, peak {peak:.2f}")

    return {"contract": "CH_PATH_FAMILY_GATE_V1", "ok": not errors,
            "directory": str(directory), "prefix": prefix, "tileCount": len(images),
            "maxPairError": max_pair_error, "maxPixelError": max_pixel_error,
            "maxDarkPixels": max_dark_pixels, "worstPair": worst,
            "worstPixelError": round(worst_pixel, 4),
            "errors": errors[:20], "errorCount": len(errors)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--prefix", choices=("dirt_path", "sand_path"), required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--max-pair-error", type=float, default=6.0)
    parser.add_argument("--max-pixel-error", type=float, default=48.0)
    parser.add_argument("--max-dark-pixels", type=int, default=None)
    args = parser.parse_args()
    result = inspect_family(args.directory, args.prefix,
                            max_pair_error=args.max_pair_error,
                            max_pixel_error=args.max_pixel_error,
                            max_dark_pixels=args.max_dark_pixels)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Path family: {result['tileCount']}/16 tiles, {result['errorCount']} defects; {args.report}")
    if not result["ok"]:
        for error in result["errors"][:5]:
            print(f" - {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
