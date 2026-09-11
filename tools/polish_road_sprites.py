#!/usr/bin/env python3
"""Apply a consistent, readable asphalt finish to the existing road-mask sprites.

The geometry, alpha channel, lane markings and filenames are preserved.  Only
near-neutral dark road pixels are lifted from near-black to a cooler mid-gray,
which keeps road segments readable against the grass without touching the
RoadSystem's connectivity masks.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ASPHALT_TARGET = (82, 91, 94)


def polish(source: Path) -> None:
    image = Image.open(source).convert("RGBA")
    polished: list[tuple[int, int, int, int]] = []

    for red, green, blue, alpha in image.getdata():
        # Preserve transparent antialiasing fringe and non-neutral paint such
        # as yellow lane dashes, white guides and curb highlights.
        neutral = max(red, green, blue) - min(red, green, blue) <= 16
        luminance = (red * 2126 + green * 7152 + blue * 722) // 10_000
        if alpha > 12 and neutral and luminance < 100:
            # Dark asphalt becomes a softer slate, with the strongest lift on
            # the almost-black pixels that dominated the previous appearance.
            blend = 0.56 if luminance < 65 else 0.34
            red = round(red * (1.0 - blend) + ASPHALT_TARGET[0] * blend)
            green = round(green * (1.0 - blend) + ASPHALT_TARGET[1] * blend)
            blue = round(blue * (1.0 - blend) + ASPHALT_TARGET[2] * blend)
        polished.append((red, green, blue, alpha))

    image.putdata(polished)
    image.save(source, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    arguments = parser.parse_args()

    for sprite in sorted(arguments.directory.glob("road_*.png")):
        polish(sprite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
