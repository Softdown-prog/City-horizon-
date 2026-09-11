#!/usr/bin/env python3
"""Convert crop reference images with black or gray checkerboard backdrops to RGBA.

The exterior-only flood fill removes a studio-black backdrop and grayscale
checkerboards without treating dark details enclosed by the crop as background.
It keeps the original canvas and is safe for uniformly sized crop overlays.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


def is_backdrop(red: int, green: int, blue: int) -> bool:
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    saturation = (maximum - minimum) / maximum if maximum else 0.0
    # Black studio backdrops, plus the light/neutral checkerboards seen in
    # generated crop references. Keeping the latter above 82 avoids eating
    # intentionally black outlines around foliage.
    return maximum <= 48 or (maximum >= 82 and saturation <= 0.12)


def exterior_backdrop_mask(image: Image.Image) -> bytearray:
    width, height = image.size
    pixels = image.load()
    mask = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if mask[index]:
            return
        if is_backdrop(*pixels[x, y][:3]):
            mask[index] = 1
            pending.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while pending:
        x, y = pending.popleft()
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                enqueue(next_x, next_y)
    return mask


def remove_outer_chroma_halo(image: Image.Image) -> None:
    """Discard only the unmistakable green/yellow key pixels on the outer edge."""
    width, height = image.size
    pixels = image.load()
    for _ in range(2):
        exterior = exterior_backdrop_mask(image)
        remove: list[tuple[int, int]] = []
        for y in range(height):
            for x in range(width):
                red, green, blue, alpha = pixels[x, y]
                if alpha == 0:
                    continue
                touches_exterior = any(
                    0 <= next_x < width and 0 <= next_y < height and exterior[next_y * width + next_x]
                    for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
                )
                chroma_green = green >= 220 and red <= 140 and blue <= 64
                chroma_yellow = red >= 220 and green >= 220 and blue <= 64
                if touches_exterior and (chroma_green or chroma_yellow):
                    remove.append((x, y))
        for x, y in remove:
            pixels[x, y] = (0, 0, 0, 0)


def convert(source: Path, destination: Path) -> None:
    image = Image.open(source).convert("RGBA")
    width, height = image.size
    pixels = image.load()
    mask = exterior_backdrop_mask(image)
    for y in range(height):
        for x in range(width):
            red, green, blue, _ = pixels[x, y]
            maximum = max(red, green, blue)
            minimum = min(red, green, blue)
            saturation = (maximum - minimum) / maximum if maximum else 0.0
            # Checkerboard regions can be fully enclosed by foliage, so the
            # neutral light portion is also removed outside the flood-fill.
            # Dark, low-saturation outlines remain protected by the exterior
            # mask and are never deleted solely because they are gray.
            enclosed_checkerboard = maximum >= 82 and saturation <= 0.12
            if mask[y * width + x] or enclosed_checkerboard:
                pixels[x, y] = (0, 0, 0, 0)
    remove_outer_chroma_halo(image)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
