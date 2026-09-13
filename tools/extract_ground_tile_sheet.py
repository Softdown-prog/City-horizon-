"""Extract trial ground-tile candidates from a black-matte reference sheet.

This is an intake tool, not an importer. It never resizes a candidate or
places it in assets/. Each foreground component is preserved as detected,
then its exterior JPEG-black matte is made transparent. The ground-tile
validator remains the authority that decides whether a candidate can enter
the game.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


FOREGROUND_MIN_CHANNEL = 36
MATTE_MAX_CHANNEL = 64


def foreground_components(image: Image.Image, minimum_pixels: int) -> list[tuple[int, tuple[int, int, int, int]]]:
    """Find non-black connected components in a JPEG presentation sheet."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    seen = bytearray(width * height)
    components: list[tuple[int, tuple[int, int, int, int]]] = []
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if seen[index] or max(pixels[x, y]) <= FOREGROUND_MIN_CHANNEL:
                continue
            seen[index] = 1
            pending = [(x, y)]
            count = 0
            left = right = x
            top = bottom = y
            while pending:
                current_x, current_y = pending.pop()
                count += 1
                left = min(left, current_x)
                right = max(right, current_x)
                top = min(top, current_y)
                bottom = max(bottom, current_y)
                for nx, ny in ((current_x - 1, current_y), (current_x + 1, current_y),
                               (current_x, current_y - 1), (current_x, current_y + 1),
                               (current_x - 1, current_y - 1), (current_x + 1, current_y - 1),
                               (current_x - 1, current_y + 1), (current_x + 1, current_y + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    neighbor = ny * width + nx
                    if not seen[neighbor] and max(pixels[nx, ny]) > FOREGROUND_MIN_CHANNEL:
                        seen[neighbor] = 1
                        pending.append((nx, ny))
            if count >= minimum_pixels:
                components.append((count, (left, top, right + 1, bottom + 1)))
    return sorted(components, key=lambda item: (item[1][1], item[1][0]))


def remove_exterior_matte(image: Image.Image) -> Image.Image:
    """Remove only dark pixels connected to a crop edge, retaining tile shadows."""
    image = image.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    transparent = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if transparent[index]:
            return
        red, green, blue, _ = pixels[x, y]
        if max(red, green, blue) <= MATTE_MAX_CHANNEL:
            transparent[index] = 1
            pending.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(1, height - 1):
        enqueue(0, y)
        enqueue(width - 1, y)
    while pending:
        x, y = pending.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)

    for y in range(height):
        for x in range(width):
            if transparent[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="reference JPEG/PNG sheet")
    parser.add_argument("output", type=Path, help="trial output directory; never assets/")
    parser.add_argument("--minimum-pixels", type=int, default=4000)
    parser.add_argument("--padding", type=int, default=2)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to((Path.cwd() / "assets").resolve()):
        parser.error("trial extraction must not write into canonical assets/")
    if args.minimum_pixels <= 0 or args.padding < 0:
        parser.error("minimum-pixels must be positive and padding must be non-negative")

    with Image.open(args.source) as source:
        image = source.convert("RGB")
    components = foreground_components(image, args.minimum_pixels)
    args.output.mkdir(parents=True, exist_ok=True)
    for index, (pixels, bounds) in enumerate(components):
        left, top, right, bottom = bounds
        crop_bounds = (max(0, left - args.padding), max(0, top - args.padding),
                       min(image.width, right + args.padding), min(image.height, bottom + args.padding))
        tile = remove_exterior_matte(image.crop(crop_bounds))
        path = args.output / f"candidate_{index:03d}.png"
        tile.save(path, "PNG", optimize=True)
        print(f"[EXTRACTED] {path.name}: source_pixels={pixels}, crop={tile.width}x{tile.height}, source_bounds={bounds}")
    print(f"extracted {len(components)} trial candidates; validate them before any normalization or import")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
