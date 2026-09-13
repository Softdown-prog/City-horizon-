#!/usr/bin/env python3
"""Forensic alpha-edge inspection for the approved Water V2 master.

This script does not render, recolour, or overwrite the master. In
--create-bleed-diagnostic mode it writes a separate diagnostic PNG whose
alpha is byte-for-byte identical but whose transparent texels inherit nearby
water RGB, isolating linear-filter alpha bleed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def inspect(path: Path) -> dict:
    image = Image.open(path).convert("RGBA")
    w, h = image.size
    edge_pixels = {edge: [] for edge in ("north_east", "south_east", "south_west", "north_west")}
    midpoint = h / 2
    for y in range(h):
        occupied = [x for x in range(w) if image.getpixel((x, y))[3] > 0]
        if not occupied:
            continue
        left, right = occupied[0], occupied[-1]
        vertical = "north" if y < midpoint else "south"
        if left > 0:
            edge_pixels[f"{vertical}_west"].extend([image.getpixel((left, y)), image.getpixel((left - 1, y))])
        if right + 1 < w:
            edge_pixels[f"{vertical}_east"].extend([image.getpixel((right, y)), image.getpixel((right + 1, y))])

    rows = {}
    for edge, pixels in edge_pixels.items():
        alpha_values = [p[3] for p in pixels]
        rgb_transparent = [p[:3] for p in pixels if p[3] == 0]
        rgb_semi = [p[:3] for p in pixels if 0 < p[3] < 255]
        rows[edge] = {
            "alphaMin": min(alpha_values),
            "alphaMax": max(alpha_values),
            "semiTransparentCount": sum(1 for alpha in alpha_values if 0 < alpha < 255),
            "transparentRgbSamples": rgb_transparent[:8],
            "semiTransparentRgbSamples": rgb_semi[:8],
            "transparentNearBlack": sum(1 for rgb in rgb_transparent if max(rgb) <= 16),
        }
    return {"path": str(path), "size": [w, h], "edges": rows}


def create_bleed_diagnostic(source: Path, output: Path) -> None:
    image = Image.open(source).convert("RGBA")
    alpha = image.getchannel("A")
    source_pixels = image.load()
    output_image = image.copy()
    output_pixels = output_image.load()
    for y in range(image.height):
        for x in range(image.width):
            if source_pixels[x, y][3] != 0:
                continue
            candidates = []
            for radius in range(1, 5):
                for oy in range(-radius, radius + 1):
                    for ox in range(-radius, radius + 1):
                        px, py = x + ox, y + oy
                        if 0 <= px < image.width and 0 <= py < image.height and source_pixels[px, py][3] > 0:
                            candidates.append(source_pixels[px, py][:3])
                if candidates:
                    break
            if candidates:
                r = sum(pixel[0] for pixel in candidates) // len(candidates)
                g = sum(pixel[1] for pixel in candidates) // len(candidates)
                b = sum(pixel[2] for pixel in candidates) // len(candidates)
                output_pixels[x, y] = (r, g, b, 0)
    if output_image.getchannel("A").tobytes() != alpha.tobytes():
        raise RuntimeError("diagnostic must not change alpha")
    output.parent.mkdir(parents=True, exist_ok=True)
    output_image.save(output, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--create-bleed-diagnostic", type=Path)
    args = parser.parse_args()
    report = inspect(args.master)
    if args.create_bleed_diagnostic:
        create_bleed_diagnostic(args.master, args.create_bleed_diagnostic)
        report["bleedDiagnostic"] = str(args.create_bleed_diagnostic)
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
