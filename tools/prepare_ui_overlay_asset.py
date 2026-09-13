"""Convert a black-matte UI reference into a fixed-canvas RGBA game asset.

Only near-black pixels connected to the outer canvas are made transparent.
Dark strokes, shadows and details enclosed by the UI artwork remain opaque.
The canvas is deliberately not cropped: atlas coordinates and panel placement
must stay deterministic in the SDL UI.
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


BACKGROUND_MAX_CHANNEL = 52


def remove_exterior_black_matte(source: Image.Image) -> Image.Image:
    image = source.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    exterior = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if exterior[index]:
            return
        red, green, blue, alpha = pixels[x, y]
        if alpha == 0 or max(red, green, blue) <= BACKGROUND_MAX_CHANNEL:
            exterior[index] = 1
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
            if exterior[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
    return image


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--expected-width", type=int, help="optional fixed canvas width for this UI family")
    parser.add_argument("--expected-height", type=int, help="optional fixed canvas height for this UI family")
    args = parser.parse_args()

    with Image.open(args.source) as source:
        if (args.expected_width is None) != (args.expected_height is None):
            parser.error("declare both expected-width and expected-height, or neither")
        if args.expected_width is not None and source.size != (args.expected_width, args.expected_height):
            parser.error(f"source is {source.width}x{source.height}; expected "
                         f"{args.expected_width}x{args.expected_height}")
        prepared = remove_exterior_black_matte(source)
    bounds = prepared.getchannel("A").getbbox()
    if bounds is None:
        parser.error("background removal produced an empty asset")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    prepared.save(args.destination, "PNG", optimize=True)
    print(f"prepared {args.destination}: canvas={prepared.width}x{prepared.height}, opaque_bounds={bounds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
