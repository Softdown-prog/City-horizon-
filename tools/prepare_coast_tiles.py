#!/usr/bin/env python3
"""Normalize and validate isometric coast tiles for City Horizon.

The runtime contract is a 128x64 logical diamond. Source artwork may contain
transparent margins or a larger presentation canvas; this tool trims only
transparent margins, fits the visible diamond to the logical canvas, and
exports 170x85 presentation assets plus a JSON report.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable

from PIL import Image


LOGICAL = (128, 64)
VISUAL = (170, 85)
ALLOWED = re.compile(
    r"^(coast_(sand|grass|shallow|water|border|corner|cliff|rock|rocky|waves)"
    r"(?:_[a-z0-9]+)*|"
    r"ocean_(deep|shallow)_\d{2}|shoreline_foam_(ne_sw|nw_se)_\d{2}|"
    r"water_(ripple|pump_splash|caustics)_\d{2})\.png$"
)


def trim_transparent(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    return image.crop(bbox) if bbox else image


def normalize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.width == 0 or image.height == 0 or image.width * LOGICAL[1] != image.height * LOGICAL[0]:
        raise ValueError(
            f"source canvas {image.width}x{image.height} is not the exact 2:1 isometric ratio"
        )
    image = trim_transparent(image)
    if image.width == 0 or image.height == 0:
        raise ValueError("empty image after transparent trim")
    fitted = image.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.paste(fitted, (0, 0), fitted)
    return canvas


def pngs(root: Path) -> Iterable[Path]:
    yield from sorted(root.rglob("*.png"))


def process(source: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in pngs(source):
        relative = path.relative_to(source)
        if not ALLOWED.fullmatch(path.name):
            raise ValueError(f"unsupported coast asset outside pipeline: {relative}")
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as image:
            normalized = normalize(image, VISUAL)
            normalized.save(target, "PNG", optimize=True)
            rows.append({
                "source": str(relative).replace("\\", "/"),
                "output": str(relative).replace("\\", "/"),
                "source_size": list(image.size),
                "output_size": list(normalized.size),
                "logical_size": list(LOGICAL),
            })
    report = {"logical_tile": list(LOGICAL), "visual_asset": list(VISUAL), "tiles": rows}
    (output / "coast_tile_adjustment_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="directory containing coast PNGs")
    parser.add_argument("output", type=Path, help="directory for adjusted PNGs")
    args = parser.parse_args()
    try:
        report = process(args.source, args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Adjusted {len(report['tiles'])} coast tiles to {VISUAL[0]}x{VISUAL[1]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
