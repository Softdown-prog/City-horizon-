"""Validate a TYCOON_ASSET_BAKE_V1 package produced by the Blender bake."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


EXPECTED_ORDER = ["south", "east", "west", "north"]
EXPECTED_TURNS = {"south": 0, "east": 1, "west": 3, "north": 2}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    return parser.parse_args()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_png(path: Path):
    require(path.is_file(), f"Missing PNG: {path}")
    with Image.open(path) as image:
        require(image.format == "PNG", f"Not a PNG: {path}")
        require(image.width > 0 and image.height > 0, f"Invalid PNG dimensions: {path}")
        image.verify()


def main():
    args = parse_args()
    manifest_path = Path(args.manifest)
    require(manifest_path.is_file(), f"Manifest does not exist: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent

    require(manifest.get("contract") == "TYCOON_ASSET_BAKE_V1", "Wrong bake contract")
    require(manifest.get("cameraContract") == "CH_CAMERA_V1", "Wrong camera contract")
    require(manifest.get("gridContract") == "CH_GRID_V1", "Wrong grid contract")
    require(manifest.get("directionCount") == 4, "Direction count must be four")
    require(manifest.get("directionOrder") == EXPECTED_ORDER, "Canonical direction order changed")

    footprint = manifest.get("footprint", {})
    require(footprint.get("widthTiles") == 1, "POC footprint width must be one tile")
    require(footprint.get("depthTiles") == 1, "POC footprint depth must be one tile")
    require(manifest.get("candidatePostProcess", {}).get("variantId") == 3, "Candidate visual recipe must remain variant 03 for this proof")

    views = manifest.get("views", [])
    require(len(views) == 4, "Manifest must contain exactly four view records")
    require([view.get("direction") for view in views] == EXPECTED_ORDER, "View records are not in canonical order")

    turns = {view.get("direction"): view.get("quarterTurns") for view in views}
    require(turns == EXPECTED_TURNS, f"Quarter-turn mapping changed: {turns}")

    pivots = {(view["pivot"]["x"], view["pivot"]["y"]) for view in views}
    require(len(pivots) == 1, f"Four views do not share one projected world-origin pivot: {sorted(pivots)}")

    alpha_bounds = []
    for view in views:
        direction = view["direction"]
        file_path = base / view["file"]
        validate_png(file_path)
        validate_png(base / view["colorPass"])
        validate_png(base / view["shadowPass"])
        bounds = view.get("spriteAlphaBounds")
        require(isinstance(bounds, list) and len(bounds) == 4, f"Missing alpha bounds for {direction}")
        require(bounds[2] > bounds[0] and bounds[3] > bounds[1], f"Empty alpha bounds for {direction}: {bounds}")
        alpha_bounds.append(tuple(bounds))

    # The test kiosk is deliberately asymmetric, so a four-view package should not
    # collapse to one identical silhouette/bounds record for every direction.
    require(len(set(alpha_bounds)) >= 2, "Four-direction bake did not produce distinct directional bounds")

    atlas = manifest.get("atlas", {})
    atlas_frames = atlas.get("frames", [])
    require([frame.get("direction") for frame in atlas_frames] == EXPECTED_ORDER, "Atlas direction order changed")
    for frame in atlas_frames:
        require(frame.get("w", 0) > 0 and frame.get("h", 0) > 0, f"Invalid atlas frame: {frame}")
        require("pivotX" in frame and "pivotY" in frame, f"Atlas frame missing trimmed pivot: {frame}")

    files = manifest.get("files", {})
    required_package_keys = (
        "south",
        "east",
        "west",
        "north",
        "spriteSheet",
        "atlas",
        "reviewSheet",
        "styleMatrix",
        "context4Dir",
    )
    for key in required_package_keys:
        require(key in files, f"Manifest files node is missing {key}")
        validate_png(base / files[key])

    shared_pivot = next(iter(pivots))
    print("TYCOON_ASSET_BAKE_V1 validation passed")
    print("directionOrder:", EXPECTED_ORDER)
    print("quarterTurns:", EXPECTED_TURNS)
    print("sharedPivot:", shared_pivot)
    print("distinctDirectionalBounds:", len(set(alpha_bounds)))


if __name__ == "__main__":
    main()
