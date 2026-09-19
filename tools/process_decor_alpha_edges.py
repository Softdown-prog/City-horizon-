#!/usr/bin/env python3
"""Apply conservative runtime alpha-edge preparation to decoration PNGs.

The tool never keys colours out of the source artwork.  It preserves every
existing alpha value, then fills the RGB values of fully transparent pixels
from the closest visible pixel.  This prevents SDL linear sampling from mixing
an asset edge with a black/white matte.  ``--soften-hard-edge`` additionally
creates a single low-alpha exterior antialias band only for sprites that have
no partial-alpha pixels at all.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


def nearest_visible_rgb(image: Image.Image) -> Image.Image:
    """Extrude RGB into transparent pixels while leaving alpha untouched."""
    width, height = image.size
    source = image.load()
    result = image.copy()
    target = result.load()
    owner = [-1] * (width * height)
    queue: deque[int] = deque()

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if source[x, y][3] != 0:
                owner[index] = index
                queue.append(index)

    # A completely transparent source has no meaningful edge colour.
    if not queue:
        return result

    while queue:
        index = queue.popleft()
        x, y = index % width, index // width
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            nindex = ny * width + nx
            if owner[nindex] != -1:
                continue
            owner[nindex] = owner[index]
            queue.append(nindex)

    for y in range(height):
        for x in range(width):
            if source[x, y][3] != 0:
                continue
            ox, oy = owner[y * width + x] % width, owner[y * width + x] // width
            red, green, blue, _ = source[ox, oy]
            target[x, y] = (red, green, blue, 0)
    return result


def soften_binary_edge(image: Image.Image) -> Image.Image:
    """Create one conservative exterior AA ring for alpha-only hard edges."""
    width, height = image.size
    original = image.copy()
    source = original.load()
    target = image.load()
    for y in range(height):
        for x in range(width):
            if source[x, y][3] != 0:
                continue
            samples = []
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height and source[nx, ny][3] == 255:
                    samples.append(source[nx, ny][:3])
            if not samples:
                continue
            red = sum(pixel[0] for pixel in samples) // len(samples)
            green = sum(pixel[1] for pixel in samples) // len(samples)
            blue = sum(pixel[2] for pixel in samples) // len(samples)
            target[x, y] = (red, green, blue, 56)
    return image


def remove_reachable_neutral_backdrop(image: Image.Image) -> Image.Image:
    """Remove a white/gray checkerboard only when it is reachable as backdrop.

    Unlike colour-keying, this never deletes neutral material enclosed by the
    sprite.  The flood can travel through transparent pixels and neutral matte
    pixels, beginning strictly at the outside of the canvas.
    """
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    remove = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def candidate(x: int, y: int) -> bool:
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0:
            return True
        maximum, minimum = max(red, green, blue), min(red, green, blue)
        # The generated checkerboard uses near-neutral light values.  Dark
        # outlines and cyan-tinted metal are deliberately excluded.
        return alpha == 255 and maximum >= 170 and maximum - minimum <= 10

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if visited[index] or not candidate(x, y):
            return
        visited[index] = 1
        if pixels[x, y][3] != 0:
            remove[index] = 1
        queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)
    for y in range(height):
        for x in range(width):
            if remove[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
    return image


def process(source: Path, destination: Path, soften_hard_edge: bool, remove_neutral_backdrop: bool) -> None:
    image = Image.open(source).convert("RGBA")
    if remove_neutral_backdrop:
        image = remove_reachable_neutral_backdrop(image)
    alpha = image.getchannel("A")
    values = list(alpha.getdata())
    binary_alpha = all(value in (0, 255) for value in values)
    result = nearest_visible_rgb(image)
    if soften_hard_edge and binary_alpha:
        result = soften_binary_edge(result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.save(destination, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--soften-hard-edge", action="store_true")
    parser.add_argument("--remove-neutral-backdrop", action="store_true")
    args = parser.parse_args()
    process(args.source, args.destination, args.soften_hard_edge, args.remove_neutral_backdrop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
