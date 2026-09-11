#!/usr/bin/env python3
"""Extract a 4x2 black-background UI icon sheet into trimmed RGBA PNG assets."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


BACKGROUND_MAX_CHANNEL = 48


def remove_exterior_black(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    mask = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if mask[index]:
            return
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or max(red, green, blue) <= BACKGROUND_MAX_CHANNEL:
            mask[index] = 1
            pending.append((x, y))

    for x in range(width):
        enqueue(x, 0); enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y); enqueue(width - 1, y)
    while pending:
        x, y = pending.popleft()
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                enqueue(next_x, next_y)
    for y in range(height):
        for x in range(width):
            if mask[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("names", nargs=8, help="four top-row names followed by four bottom-row names")
    args = parser.parse_args()
    image = Image.open(args.source).convert("RGBA")
    width, height = image.size
    if width % 4 != 0 or height % 2 != 0:
        raise SystemExit("icon sheet must use an exact 4x2 grid")
    cell_width, cell_height = width // 4, height // 2
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(args.names):
        column, row = index % 4, index // 4
        cell = image.crop((column * cell_width, row * cell_height, (column + 1) * cell_width, (row + 1) * cell_height))
        icon = remove_exterior_black(cell)
        bounds = icon.getbbox()
        if bounds is None:
            raise SystemExit(f"empty icon cell: {name}")
        padding = 4
        left = max(0, bounds[0] - padding); top = max(0, bounds[1] - padding)
        right = min(icon.width, bounds[2] + padding); bottom = min(icon.height, bounds[3] + padding)
        icon.crop((left, top, right, bottom)).save(args.output_dir / f"{name}.png", "PNG", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
