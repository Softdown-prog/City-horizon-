#!/usr/bin/env python3
"""Expand a game-first tycoon house plan into TYCOON_ASSET_SOURCE_V1.

This generator intentionally does NOT reuse the older suburban-house grammar.
The authored proportions, color blocks and secondary masses are designed from the
start for CH_TYCOON_MINIATURE_V1: compact body, dominant roof, oversized readable
openings and a small amount of simple landscaping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def box(name, location, dimensions, material, bevel=0.03):
    return {
        "type": "box",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "dimensions": [round(float(v), 4) for v in dimensions],
        "material": material,
        "bevel": float(bevel),
    }


def sphere(name, location, radius, material, segments=16, rings=8):
    return {
        "type": "uv_sphere",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "radius": float(radius),
        "segments": int(segments),
        "rings": int(rings),
        "material": material,
    }


def hip_roof(name, location, radius, depth, material="roof"):
    return {
        "type": "pyramid_roof",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "radius": float(radius),
        "depth": float(depth),
        "material": material,
        "rotationDegrees": 45.0,
        "bevel": 0.045,
    }


def add_window_south(parts, name, x, y, z, width, height, trim="trim", glass="glass", shutters=False):
    frame = 0.13
    depth = 0.12
    parts.append(box(f"{name}Glass", [x, y, z], [width, 0.07, height], glass, 0.015))
    parts.append(box(f"{name}Top", [x, y - 0.04, z + height / 2 + frame / 2], [width + 0.25, depth, frame], trim, 0.018))
    parts.append(box(f"{name}Bottom", [x, y - 0.04, z - height / 2 - frame / 2], [width + 0.30, depth + 0.03, frame], trim, 0.018))
    parts.append(box(f"{name}Left", [x - width / 2 - frame / 2, y - 0.04, z], [frame, depth, height + 0.24], trim, 0.018))
    parts.append(box(f"{name}Right", [x + width / 2 + frame / 2, y - 0.04, z], [frame, depth, height + 0.24], trim, 0.018))
    parts.append(box(f"{name}Mullion", [x, y - 0.055, z], [0.075, depth + 0.01, height], trim, 0.012))
    if shutters:
        shutter_w = 0.23
        parts.append(box(f"{name}ShutterL", [x - width / 2 - 0.23, y - 0.065, z], [shutter_w, 0.08, height + 0.10], "shutter", 0.018))
        parts.append(box(f"{name}ShutterR", [x + width / 2 + 0.23, y - 0.065, z], [shutter_w, 0.08, height + 0.10], "shutter", 0.018))


def add_window_north(parts, name, x, y, z, width, height, trim="trim", glass="glass"):
    frame = 0.12
    depth = 0.11
    parts.append(box(f"{name}Glass", [x, y, z], [width, 0.07, height], glass, 0.015))
    parts.append(box(f"{name}Top", [x, y + 0.04, z + height / 2 + frame / 2], [width + 0.22, depth, frame], trim, 0.016))
    parts.append(box(f"{name}Bottom", [x, y + 0.04, z - height / 2 - frame / 2], [width + 0.26, depth + 0.02, frame], trim, 0.016))
    parts.append(box(f"{name}Left", [x - width / 2 - frame / 2, y + 0.04, z], [frame, depth, height + 0.20], trim, 0.016))
    parts.append(box(f"{name}Right", [x + width / 2 + frame / 2, y + 0.04, z], [frame, depth, height + 0.20], trim, 0.016))


def add_window_side(parts, name, face, x, y, z, width, height, trim="trim", glass="glass"):
    frame = 0.12
    depth = 0.11
    sign = 1 if face == "east" else -1
    offset = 0.045 * sign
    parts.append(box(f"{name}Glass", [x, y, z], [0.07, width, height], glass, 0.015))
    parts.append(box(f"{name}Top", [x + offset, y, z + height / 2 + frame / 2], [depth, width + 0.22, frame], trim, 0.016))
    parts.append(box(f"{name}Bottom", [x + offset, y, z - height / 2 - frame / 2], [depth + 0.02, width + 0.26, frame], trim, 0.016))
    parts.append(box(f"{name}Front", [x + offset, y - width / 2 - frame / 2, z], [depth, frame, height + 0.20], trim, 0.016))
    parts.append(box(f"{name}Back", [x + offset, y + width / 2 + frame / 2, z], [depth, frame, height + 0.20], trim, 0.016))


def expand(plan):
    if plan.get("contract") != "CITY_HORIZON_TYCOON_HOUSE_V1":
        raise ValueError("Expected CITY_HORIZON_TYCOON_HOUSE_V1")
    if plan.get("styleContract") != "CH_STYLIZED_PRERENDER_V1":
        raise ValueError("Tycoon house keeps CH_STYLIZED_PRERENDER_V1 as technical base")
    if plan.get("artDirectionContract") != "CH_TYCOON_MINIATURE_V1":
        raise ValueError("Tycoon house must opt into CH_TYCOON_MINIATURE_V1")

    mass = plan["mass"]
    width = float(mass["width"])
    depth = float(mass["depth"])
    foundation_h = float(mass["foundationHeight"])
    wall_h = float(mass["wallHeight"])
    half_w = width / 2.0
    half_d = depth / 2.0
    wall_top = foundation_h + wall_h
    parts = []

    # Chunky, simple base and body: game piece first, real house second.
    parts.append(box("Foundation", [0, 0, foundation_h / 2], [width + 0.24, depth + 0.24, foundation_h], "foundation", 0.055))
    parts.append(box("MainBody", [0, 0, foundation_h + wall_h / 2], [width, depth, wall_h], "wall", 0.075))

    if plan["details"].get("foundationBand", True):
        parts.append(box("FoundationBandSouth", [0, -half_d - 0.045, foundation_h + 0.08], [width + 0.12, 0.12, 0.16], "trim", 0.025))
        parts.append(box("FoundationBandEast", [half_w + 0.045, 0, foundation_h + 0.08], [0.12, depth + 0.12, 0.16], "trim", 0.025))
        parts.append(box("FoundationBandWest", [-half_w - 0.045, 0, foundation_h + 0.08], [0.12, depth + 0.12, 0.16], "trim", 0.025))

    # Bright fascia makes the roof/body separation read at game scale.
    fascia_z = wall_top - 0.02
    parts.append(box("FasciaSouth", [0, -half_d - 0.055, fascia_z], [width + 0.20, 0.14, 0.16], "trim", 0.025))
    parts.append(box("FasciaNorth", [0, half_d + 0.055, fascia_z], [width + 0.20, 0.14, 0.16], "trim", 0.025))
    parts.append(box("FasciaEast", [half_w + 0.055, 0, fascia_z], [0.14, depth + 0.20, 0.16], "trim", 0.025))
    parts.append(box("FasciaWest", [-half_w - 0.055, 0, fascia_z], [0.14, depth + 0.20, 0.16], "trim", 0.025))

    roof = plan["roof"]
    roof_depth = float(roof["depth"])
    roof_base = float(roof["baseZ"])
    parts.append(hip_roof("MainRoof", [0, 0, roof_base + roof_depth / 2], float(roof["radius"]), roof_depth))

    # A protruding front bay gives the silhouette a toy-like asymmetry and depth.
    bay = plan["frontBay"]
    if bay.get("enabled", True):
        bay_x = float(bay["x"])
        bay_projection = float(bay["projection"])
        bay_w = float(bay["width"])
        bay_h = float(bay["height"])
        bay_y = -half_d - bay_projection / 2
        parts.append(box("FrontBayBody", [bay_x, bay_y, foundation_h + bay_h / 2], [bay_w, bay_projection, bay_h], "wall", 0.070))
        bay_roof_depth = float(bay["roofDepth"])
        bay_roof_base = foundation_h + bay_h
        parts.append(hip_roof("FrontBayRoof", [bay_x, bay_y, bay_roof_base + bay_roof_depth / 2], float(bay["roofRadius"]), bay_roof_depth))
        parts.append(box("FrontBayFascia", [bay_x, -half_d - bay_projection - 0.035, bay_roof_base - 0.02], [bay_w + 0.20, 0.11, 0.15], "trim", 0.022))

        facade = plan["facade"]
        front_window_z = foundation_h + float(facade["windowSillZ"]) + float(facade["frontWindowHeight"]) / 2
        add_window_south(
            parts, "FrontBayWindow", bay_x, -half_d - bay_projection - 0.065, front_window_z,
            float(facade["frontWindowWidth"]), float(facade["frontWindowHeight"]),
            shutters=bool(facade.get("shutters", True)),
        )
        if plan["details"].get("windowPlanter", True):
            parts.append(box("FrontWindowPlanter", [bay_x, -half_d - bay_projection - 0.15, front_window_z - 0.66], [1.10, 0.26, 0.22], "accent", 0.040))

    facade = plan["facade"]
    door_x = float(facade["doorOffsetX"])
    door_w = float(facade["doorWidth"])
    door_h = float(facade["doorHeight"])
    front_y = -half_d - 0.07
    door_z = foundation_h + door_h / 2
    parts.append(box("FrontDoor", [door_x, front_y, door_z], [door_w, 0.14, door_h], "door", 0.045))
    parts.append(box("DoorFrameLeft", [door_x - door_w / 2 - 0.09, front_y - 0.045, door_z], [0.14, 0.13, door_h + 0.22], "trim", 0.022))
    parts.append(box("DoorFrameRight", [door_x + door_w / 2 + 0.09, front_y - 0.045, door_z], [0.14, 0.13, door_h + 0.22], "trim", 0.022))
    parts.append(box("DoorFrameTop", [door_x, front_y - 0.045, foundation_h + door_h + 0.09], [door_w + 0.34, 0.13, 0.16], "trim", 0.022))
    parts.append(box("DoorHandle", [door_x + door_w * 0.28, front_y - 0.095, foundation_h + door_h * 0.50], [0.07, 0.05, 0.07], "accent", 0.012))

    if plan["details"].get("porch", True):
        porch_w = float(plan["details"]["porchWidth"])
        porch_d = float(plan["details"]["porchDepth"])
        porch_y = -half_d - porch_d / 2
        parts.append(box("PorchSlab", [door_x, porch_y, foundation_h + 0.055], [porch_w, porch_d, 0.14], "foundation", 0.040))
        canopy_z = foundation_h + door_h + 0.34
        parts.append(box("PorchCanopy", [door_x, porch_y + 0.02, canopy_z], [porch_w + 0.24, porch_d + 0.20, 0.18], "roof", 0.040))
        for side in (-1, 1):
            parts.append(box(f"PorchPost_{side}", [door_x + side * porch_w * 0.40, porch_y - porch_d * 0.25, foundation_h + 0.98], [0.15, 0.15, 1.72], "trim", 0.024))
        for i in range(int(plan["details"].get("frontSteps", 2))):
            parts.append(box(f"FrontStep_{i}", [door_x, -half_d - porch_d - 0.08 - i * 0.13, 0.08 + i * 0.055], [porch_w * (0.88 - i * 0.08), 0.26, 0.12], "foundation", 0.026))

    # Side windows are intentionally large and simple.
    side_z = foundation_h + float(facade["windowSillZ"]) + float(facade["sideWindowHeight"]) / 2
    add_window_side(parts, "EastWindow", "east", half_w + 0.07, 0.20, side_z, float(facade["sideWindowWidth"]), float(facade["sideWindowHeight"]))
    add_window_side(parts, "WestWindow", "west", -half_w - 0.07, 0.20, side_z, float(facade["sideWindowWidth"]), float(facade["sideWindowHeight"]))

    rear_y = half_d + 0.07
    add_window_north(parts, "RearWindowL", -0.95, rear_y, side_z, 0.86, 0.82)
    add_window_north(parts, "RearWindowR", 0.95, rear_y, side_z, 0.86, 0.82)

    if roof.get("chimney", True):
        ox, oy = roof.get("chimneyOffset", [1.0, 0.45])
        chimney_z = roof_base + 0.78
        parts.append(box("ChunkyChimney", [ox, oy, chimney_z], [0.48, 0.46, 1.08], "door", 0.035))
        parts.append(box("ChunkyChimneyCap", [ox, oy, chimney_z + 0.57], [0.62, 0.60, 0.12], "trim", 0.025))

    if plan["details"].get("landscaping", True):
        shrub_y = -half_d - 0.58
        parts.append(sphere("FrontShrubLeft", [-1.82, shrub_y, 0.48], 0.43, "shrub"))
        parts.append(sphere("FrontShrubRight", [1.72, shrub_y + 0.08, 0.45], 0.40, "shrub"))
        parts.append(box("ShrubPlanterLeft", [-1.82, shrub_y, 0.20], [0.72, 0.72, 0.30], "trim", 0.045))
        parts.append(box("ShrubPlanterRight", [1.72, shrub_y + 0.08, 0.20], [0.68, 0.68, 0.28], "trim", 0.045))

    fp = plan["footprint"]
    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "styleContract": plan["styleContract"],
        "artDirectionContract": plan["artDirectionContract"],
        "assetId": plan["assetId"],
        "assetType": "building",
        "studioPreset": plan["studioPreset"],
        "floors": 1,
        "footprint": {
            "widthTiles": int(fp["widthTiles"]),
            "depthTiles": int(fp["depthTiles"]),
            "occupiedCells": [[x, y] for y in range(int(fp["depthTiles"])) for x in range(int(fp["widthTiles"]))],
        },
        "materials": plan["materials"],
        "parts": parts,
        "buildingPostProcess": plan.get("buildingPostProcess", {}),
        "generation": {
            "sourceContract": plan["contract"],
            "styleContract": plan["styleContract"],
            "artDirectionContract": plan["artDirectionContract"],
            "seed": int(plan.get("seed", 0)),
            "proceduralStage": "game_first_plan_to_canonical_source_v1",
            "partCount": len(parts),
            "designIntent": plan.get("designIntent", {}),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    source = expand(plan)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(source["generation"], sort_keys=True))


if __name__ == "__main__":
    main()
