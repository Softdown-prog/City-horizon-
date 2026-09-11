#!/usr/bin/env python3
"""Prepare the authored concrete sidewalk variants for the runtime tile set.

The supplied art has a black presentation background.  This tool removes only
the dark region connected to the outer canvas (so intentional dark curb/shadow
details remain), crops to the actual tile and normalizes every result to the
same 128px logical width used by the isometric renderer.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image


DISPLAY_WIDTH = 128

# The runtime names are connection masks (N=1, E=2, S=4, W=8).  The authored
# edge/corner assets describe the *exposed* grass side, which is the inverse
# of that connection mask.
SOURCE_FOR_MASK = {
    0: "center",
    1: "center",
    2: "center",
    3: "corner_sw",
    4: "center",
    5: "edge_e",
    6: "corner_nw",
    7: "edge_w",
    8: "center",
    9: "corner_se",
    10: "edge_n",
    11: "edge_s",
    12: "corner_ne",
    13: "edge_e",
    14: "edge_n",
    15: "center",
}


def remove_presentation_background(source: Image.Image) -> Image.Image:
    """Flood-fill only near-black pixels reachable from the canvas edge."""
    image = source.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    transparent: set[tuple[int, int]] = set()
    pending: deque[tuple[int, int]] = deque()

    def is_background(x: int, y: int) -> bool:
        red, green, blue, alpha = pixels[x, y]
        # The source artwork's presentation backdrop is compressed black
        # rather than #000000.  Flood filling up to this threshold removes it
        # only when it is reachable from the outer canvas; dark grout and curb
        # shadows enclosed by the sprite remain intact.
        return alpha == 0 or max(red, green, blue) <= 64

    for x in range(width):
        pending.extend(((x, 0), (x, height - 1)))
    for y in range(1, height - 1):
        pending.extend(((0, y), (width - 1, y)))

    while pending:
        x, y = pending.popleft()
        if (x, y) in transparent or not is_background(x, y):
            continue
        transparent.add((x, y))
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                pending.append((nx, ny))

    alpha = Image.new("L", image.size, 255)
    alpha_pixels = alpha.load()
    for x, y in transparent:
        alpha_pixels[x, y] = 0
    image.putalpha(alpha)
    bbox = alpha.getbbox()
    if bbox is None:
        raise ValueError("sidewalk source contains no visible pixels")
    return image.crop(bbox)


def main() -> None:
    asset_dir = Path("assets/sidewalks/concrete_01")
    prepared: dict[str, Image.Image] = {}
    for name in set(SOURCE_FOR_MASK.values()):
        source = asset_dir / f"sidewalk_concrete_{name}.png"
        if not source.is_file():
            raise FileNotFoundError(source)
        cropped = remove_presentation_background(Image.open(source))
        height = round(cropped.height * DISPLAY_WIDTH / cropped.width)
        prepared[name] = cropped.resize((DISPLAY_WIDTH, height), Image.Resampling.LANCZOS)

    for mask, source_name in SOURCE_FOR_MASK.items():
        output = asset_dir / f"sidewalk_concrete_{mask:02d}.png"
        prepared[source_name].save(output, "PNG", optimize=True)
        print(f"wrote {output}")


if __name__ == "__main__":
    main()
