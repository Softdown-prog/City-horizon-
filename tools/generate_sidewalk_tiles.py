#!/usr/bin/env python3
"""Generate the 16 connected, flat isometric sidewalk tiles used by the map."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


DISPLAY_WIDTH, DISPLAY_HEIGHT, SCALE = 128, 64, 4
WIDTH, HEIGHT = DISPLAY_WIDTH * SCALE, DISPLAY_HEIGHT * SCALE
NORTH, EAST, SOUTH, WEST = 1, 2, 4, 8


def tile_for_connections(connections: int) -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    top, right, bottom, left = (WIDTH // 2, 0), (WIDTH, HEIGHT // 2), (WIDTH // 2, HEIGHT), (0, HEIGHT // 2)
    diamond = (top, right, bottom, left)
    # A quiet, warm-grey paving surface sits beside the dark asphalt without
    # reading as a bright white diamond dropped onto the grass.
    draw.polygon(diamond, fill=(181, 187, 181, 255))

    # Quiet paver seams give scale without creating a heavy checkerboard.
    seam = (137, 147, 141, 255)
    for offset in (-96, -32, 32, 96):
        draw.line(((WIDTH // 2 + offset, 0), (WIDTH + offset, HEIGHT // 2)), fill=seam, width=2)
        draw.line(((WIDTH // 2 + offset, 0), (offset, HEIGHT // 2)), fill=seam, width=2)
    for y in (HEIGHT // 4, HEIGHT // 2, HEIGHT * 3 // 4):
        span = min(y, HEIGHT - y) * 2
        draw.line(((WIDTH // 2 - span, y), (WIDTH // 2 + span, y)), fill=seam, width=2)

    # Shared sides have no border: adjacent sidewalks form one continuous path.
    sides = {NORTH: (top, right), EAST: (right, bottom), SOUTH: (bottom, left), WEST: (left, top)}
    for bit, segment in sides.items():
        if not connections & bit:
            # A thin curb on exposed sides provides a readable edge against
            # grass. Shared sides intentionally have no curb at all.
            draw.line(segment, fill=(109, 123, 115, 255), width=5)
            draw.line(segment, fill=(205, 211, 204, 255), width=2)

    alpha = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(alpha).polygon(diamond, fill=255)
    image.putalpha(alpha)
    return image.resize((DISPLAY_WIDTH, DISPLAY_HEIGHT), Image.Resampling.LANCZOS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_dir", type=Path)
    args = parser.parse_args()
    args.asset_dir.mkdir(parents=True, exist_ok=True)
    for connections in range(16):
        tile_for_connections(connections).save(args.asset_dir / f"sidewalk_concrete_{connections:02d}.png", "PNG", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
