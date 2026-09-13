#!/usr/bin/env python3
"""Prepare the approved City Horizon water master as one strict runtime tile.

This tool is deliberately non-creative: it only removes a uniform opaque black
presentation backdrop, fits the detected approved 2:1 diamond to the existing
CH_COAST_V1 visual canvas, and writes an isolated 6x6 pilot scenario.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


LOGICAL_SIZE = (128, 64)
VISUAL_SIZE = (170, 85)
WATER_RELATIVE_PATH = "assets/terrain/coast_adjusted/water_surface_v2_master.png"


def black_backdrop_to_alpha(master: Image.Image) -> Image.Image:
    """Convert only the opaque near-black presentation field to alpha.

    The source is JPEG, so its black presentation field includes compression
    residue.  Water pixels are substantially brighter; removing only neutral
    values at or below 64 preserves the approved water colour and caustics.
    """
    rgba = master.convert("RGBA")
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            r, g, b, a = pixels[x, y]
            if r <= 64 and g <= 64 and b <= 64:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def exact_diamond_alpha(size: tuple[int, int]) -> Image.Image:
    """Return an antialiased CH_GRID_V1 2:1 diamond mask for a visual canvas."""
    width, height = size
    mask = Image.new("L", size, 0)
    pixels = mask.load()
    samples = 4
    for y in range(height):
        for x in range(width):
            covered = 0
            for sy in range(samples):
                for sx in range(samples):
                    px = (x + (sx + 0.5) / samples) / width
                    py = (y + (sy + 0.5) / samples) / height
                    if abs(px - 0.5) * 2.0 + abs(py - 0.5) * 2.0 <= 1.0:
                        covered += 1
            pixels[x, y] = round(255 * covered / (samples * samples))
    return mask


def prepare_master(source: Path, destination: Path) -> dict[str, object]:
    with Image.open(source) as input_image:
        transparent = black_backdrop_to_alpha(input_image)
    bbox = transparent.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("master has no opaque pixels after backdrop removal")

    # The presentation canvas itself is already the approved 2:1 framing.
    # Keeping it avoids re-centering against JPEG-compressed edge pixels.
    ratio = transparent.width / transparent.height
    expected_ratio = VISUAL_SIZE[0] / VISUAL_SIZE[1]
    if abs(ratio - expected_ratio) > 0.02:
        raise ValueError(
            f"approved diamond ratio {ratio:.5f} is outside the 2:1 contract tolerance"
        )

    # This is a uniform resample of the already-approved diamond, never a crop
    # or artistic edit.  170x85 maps to the 128x64 logical footprint in the
    # existing native renderer.
    fitted = black_backdrop_to_alpha(transparent.resize(VISUAL_SIZE, Image.Resampling.LANCZOS))
    # Preserve the key-created alpha while constraining it to the exact tile
    # footprint.  This removes both JPEG background residue and any pixels
    # outside the canonical 2:1 diamond.
    fitted.putalpha(ImageChops.darker(fitted.getchannel("A"), exact_diamond_alpha(VISUAL_SIZE)))
    alpha = fitted.getchannel("A")
    if alpha.getbbox() != (0, 0, VISUAL_SIZE[0], VISUAL_SIZE[1]):
        raise ValueError("normalized diamond does not occupy the complete visual canvas")
    if alpha.getpixel((0, 0)) != 0 or alpha.getpixel((VISUAL_SIZE[0] - 1, 0)) != 0:
        raise ValueError("normalized top corners must remain transparent")
    if any(max(fitted.getpixel((x, y))[:3]) <= 64 and alpha.getpixel((x, y)) > 0
           for y in range(VISUAL_SIZE[1]) for x in range(VISUAL_SIZE[0])):
        raise ValueError("near-black backdrop residue remains inside the diamond mask")

    destination.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(destination, "PNG", optimize=True)
    return {
        "source": str(source),
        "destination": str(destination),
        "logicalTile": list(LOGICAL_SIZE),
        "visualCanvas": list(VISUAL_SIZE),
        "sourceDiamondBounds": list(bbox),
        "sourceDiamondRatio": ratio,
        "alpha": "RGBA real; outside diamond transparent",
        "anchor": "top of visual diamond = CH_RENDER_V1 tile visual top",
    }


def pilot_scenario() -> dict[str, object]:
    terrain = [
        {"tileX": x, "tileY": y, "texture": WATER_RELATIVE_PATH}
        for y in range(-3, 3)
        for x in range(-3, 3)
    ]
    return {
        "saveVersion": 7,
        "cityFunds": 0,
        "simulation": {"day": 1, "month": 1, "year": 1, "speed": 0},
        "nextBuildingInstanceId": 1,
        "currentPopulation": 0,
        "lastPropertyTaxYear": 0,
        "ownedParcelIds": [],
        "terrain": terrain,
        "buildings": [],
        "roads": [],
        "sidewalks": [],
        "farmingTiles": [],
        "agriculturalInventory": [],
        "serviceVehicles": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="approved water master image")
    parser.add_argument("asset_root", type=Path, help="existing runtime asset root, e.g. build/Debug")
    args = parser.parse_args()

    destination = args.asset_root / WATER_RELATIVE_PATH
    report = prepare_master(args.source, destination)
    pilot_path = args.asset_root / "assets/scenarios/water_surface_v2_pilot_6x6.json"
    pilot_path.parent.mkdir(parents=True, exist_ok=True)
    pilot_path.write_text(json.dumps(pilot_scenario(), indent=2) + "\n", encoding="utf-8")
    report["pilotScenario"] = str(pilot_path)
    (destination.with_suffix(".json")).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
