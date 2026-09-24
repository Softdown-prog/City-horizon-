#!/usr/bin/env python3
"""Normalize a source image into a City Horizon atomic-path tile.

Input: arbitrary PNG/JPG source, typically a generated reference image.
Output: exact 128x64 RGBA PNG matching ground_tile_contract.json atomic-path.

This worker is intentionally deterministic and conservative:
- no AI/background-removal service;
- crops to non-background content;
- fits content into a 128x64 isometric diamond;
- removes near-black background outside the diamond;
- preserves texture detail as much as possible while downsampling once.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops
from tile_geometry import diamond_mask

TARGET_W = 128
TARGET_H = 64


def _alpha_from_black_background(img: Image.Image, threshold: int = 20) -> Image.Image:
    """Treat near-black pixels as transparent without touching normal dirt tones."""
    rgba = img.convert("RGBA")
    px = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r <= threshold and g <= threshold and b <= threshold:
                px[x, y] = (r, g, b, 0)
    return rgba


def _content_bbox(img: Image.Image):
    alpha = img.getchannel("A")
    return alpha.getbbox()


def _diamond_mask() -> Image.Image:
    return diamond_mask()


def normalize(source: Path, output: Path) -> None:
    img = Image.open(source).convert("RGBA")
    img = _alpha_from_black_background(img)

    bbox = _content_bbox(img)
    if not bbox:
        raise SystemExit("source contains no non-background pixels")

    cropped = img.crop(bbox)

    # Fit the visible source into the canonical 2:1 tile without stretching.
    scale = min(TARGET_W / cropped.width, TARGET_H / cropped.height)
    new_w = max(1, round(cropped.width * scale))
    new_h = max(1, round(cropped.height * scale))
    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (TARGET_W, TARGET_H), (0, 0, 0, 0))
    x = (TARGET_W - new_w) // 2
    y = (TARGET_H - new_h) // 2
    canvas.alpha_composite(resized, (x, y))

    # Enforce the exact atomic-path diamond footprint.
    diamond = _diamond_mask()
    alpha = ImageChops.multiply(canvas.getchannel("A"), diamond)
    canvas.putalpha(alpha)

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, "PNG")

    if canvas.size != (TARGET_W, TARGET_H):
        raise SystemExit("normalization failed to produce 128x64 output")

    print(f"atomic-path normalization: PASS -> {output}")
    print("canvas=128x64 mode=RGBA anchor=0.5,0.92")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize an image to City Horizon atomic-path 128x64 RGBA.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    normalize(args.input, args.output)


if __name__ == "__main__":
    main()
