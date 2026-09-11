#!/usr/bin/env python3
"""Turn a black-background building reference into a transparent PNG deterministically.

The tool removes only near-black pixels connected to the outer canvas.  Dark details
inside the building (roofs, outlines and shadows) remain intact because they are not
part of that exterior connected component.  It is deliberately not an AI image tool:
the input canvas, pixels and scale are otherwise unchanged.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


BACKGROUND_MAX_CHANNEL = 48


def is_background_candidate(red: int, green: int, blue: int) -> bool:
    return max(red, green, blue) <= BACKGROUND_MAX_CHANNEL


def exterior_black_mask(image: Image.Image) -> bytearray:
    width, height = image.size
    pixels = image.load()
    mask = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()

    def enqueue_if_background(x: int, y: int) -> None:
        index = y * width + x
        if mask[index]:
            return
        red, green, blue = pixels[x, y]
        if is_background_candidate(red, green, blue):
            mask[index] = 1
            pending.append((x, y))

    for x in range(width):
        enqueue_if_background(x, 0)
        enqueue_if_background(x, height - 1)
    for y in range(height):
        enqueue_if_background(0, y)
        enqueue_if_background(width - 1, y)

    while pending:
        x, y = pending.popleft()
        if x > 0:
            enqueue_if_background(x - 1, y)
        if x + 1 < width:
            enqueue_if_background(x + 1, y)
        if y > 0:
            enqueue_if_background(x, y - 1)
        if y + 1 < height:
            enqueue_if_background(x, y + 1)
    return mask


def convert(source: Path, destination: Path) -> None:
    source_image = Image.open(source).convert("RGB")
    width, height = source_image.size
    mask = exterior_black_mask(source_image)
    rgba = source_image.convert("RGBA")
    alpha = Image.new("L", (width, height), 255)
    alpha.putdata([0 if exterior else 255 for exterior in mask])
    rgba.putalpha(alpha)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(destination, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
