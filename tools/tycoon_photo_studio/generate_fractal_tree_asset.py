"""Expand a compact fractal-tree spec into TYCOON_ASSET_SOURCE_V1 parts.

The generator deliberately emits only primitives already supported by build_scene.py
(curve and cylinder). This keeps the Blender renderer simple and deterministic while
allowing tree structure to be authored procedurally.
"""

import argparse
import json
import math
import random
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def point_from(start, length, yaw_deg, elevation_deg):
    yaw = math.radians(yaw_deg)
    elevation = math.radians(elevation_deg)
    horizontal = math.cos(elevation) * length
    return [
        start[0] + math.cos(yaw) * horizontal,
        start[1] + math.sin(yaw) * horizontal,
        start[2] + math.sin(elevation) * length,
    ]


def r3(point):
    return [round(float(v), 4) for v in point]


def expand_fractal_tree(spec):
    rng = random.Random(int(spec.get("seed", 1)))
    levels = int(spec.get("levels", 3))
    if not 1 <= levels <= 4:
        raise ValueError("fractal tree levels must be between 1 and 4")

    branch_factor = int(spec.get("branchFactor", 2))
    if branch_factor != 2:
        raise ValueError("classic Tycoon fractal tree currently requires branchFactor=2")

    origin = [float(v) for v in spec.get("origin", [0.0, 0.0, 1.55])]
    base_length = float(spec.get("baseLength", 0.88))
    length_decay = float(spec.get("lengthDecay", 0.68))
    base_radius = float(spec.get("baseRadius", 0.085))
    radius_decay = float(spec.get("radiusDecay", 0.70))
    initial_elevation = float(spec.get("initialElevationDegrees", 54.0))
    elevation_gain = float(spec.get("elevationGainDegrees", 7.0))
    yaw_spread = float(spec.get("yawSpreadDegrees", 56.0))
    yaw_jitter = float(spec.get("yawJitterDegrees", 9.0))
    elevation_jitter = float(spec.get("elevationJitterDegrees", 5.0))
    material = str(spec["material"])
    prefix = str(spec.get("name", "FractalTree"))

    parts = []
    counter = 0

    def branch(start, length, radius, yaw_deg, elevation_deg, level):
        nonlocal counter
        end = point_from(start, length, yaw_deg, elevation_deg)
        counter += 1
        parts.append({
            "type": "curve",
            "name": f"{prefix}_Branch_{counter:02d}",
            "points": [r3(start), r3(end)],
            "material": material,
            "bevel": round(radius, 4),
            "bevelResolution": 0,
            "resolution": 1,
        })
        if level >= levels:
            return

        next_length = length * length_decay
        next_radius = radius * radius_decay
        next_elevation = elevation_deg + elevation_gain
        for side in (-1.0, 1.0):
            child_yaw = yaw_deg + side * yaw_spread + rng.uniform(-yaw_jitter, yaw_jitter)
            child_elevation = next_elevation + rng.uniform(-elevation_jitter, elevation_jitter)
            branch(end, next_length, next_radius, child_yaw, child_elevation, level + 1)

    trunk_count = int(spec.get("primaryBranches", 4))
    base_yaw = float(spec.get("baseYawDegrees", -22.0))
    yaw_step = 360.0 / max(1, trunk_count)
    for i in range(trunk_count):
        yaw = base_yaw + i * yaw_step + rng.uniform(-7.0, 7.0)
        elevation = initial_elevation + rng.uniform(-4.0, 4.0)
        branch(origin, base_length, base_radius, yaw, elevation, 1)

    return parts


def main():
    args = parse_args()
    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if source.get("contract") != "TYCOON_FRACTAL_TREE_SOURCE_V1":
        raise ValueError("input must use TYCOON_FRACTAL_TREE_SOURCE_V1")

    output = {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "assetId": source["assetId"],
        "assetType": source.get("assetType", "static_decor"),
        "studioPreset": source["studioPreset"],
        "footprint": source["footprint"],
        "materials": source["materials"],
        "parts": [],
    }

    output["parts"].extend(source.get("baseParts", []))
    output["parts"].extend(expand_fractal_tree(source["fractalTree"]))
    output["parts"].extend(source.get("canopyParts", []))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"generated {out_path} with {len(output['parts'])} parts")


if __name__ == "__main__":
    main()
