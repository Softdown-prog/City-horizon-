#!/usr/bin/env python3
"""Expand CITY_HORIZON_SUBURBAN_HOUSE_V1 into TYCOON_ASSET_SOURCE_V1.

This is the pre-Blender procedural stage for simple residential houses. Agents and
humans edit a compact architectural recipe first; this expander turns that plan into
the canonical primitive source consumed by build_scene.py. Blender is therefore a
renderer/baker, not the place where the design contract is hidden.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def box(name, location, dimensions, material, bevel=0.02):
    return {
        "type": "box",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "dimensions": [round(float(v), 4) for v in dimensions],
        "material": material,
        "bevel": float(bevel),
    }


def add_window(parts, face, center, width, height, sill_z, glass="glass", trim="trim", mullion=True):
    frame = 0.115
    depth = 0.105
    z = sill_z + height / 2
    if face in ("south", "north"):
        x = center
        y = -1 if face == "south" else 1
        wall_y = y * 1.0
        parts.append(box(f"{face.title()}WindowGlass_{len(parts)}", [x, wall_y, z], [width, depth * 0.70, height], glass, 0.01))
        parts.append(box(f"{face.title()}WindowTop_{len(parts)}", [x, wall_y + y * 0.045, z + height / 2 + frame / 2], [width + 0.20, depth, frame], trim, 0.012))
        parts.append(box(f"{face.title()}WindowBottom_{len(parts)}", [x, wall_y + y * 0.045, z - height / 2 - frame / 2], [width + 0.24, depth + 0.025, frame], trim, 0.012))
        parts.append(box(f"{face.title()}WindowLeft_{len(parts)}", [x - width / 2 - frame / 2, wall_y + y * 0.045, z], [frame, depth, height + 0.20], trim, 0.012))
        parts.append(box(f"{face.title()}WindowRight_{len(parts)}", [x + width / 2 + frame / 2, wall_y + y * 0.045, z], [frame, depth, height + 0.20], trim, 0.012))
        if mullion:
            parts.append(box(f"{face.title()}WindowMullion_{len(parts)}", [x, wall_y + y * 0.052, z], [0.065, depth + 0.01, height], trim, 0.008))
    else:
        y = center
        x = 1 if face == "east" else -1
        wall_x = x * 1.0
        parts.append(box(f"{face.title()}WindowGlass_{len(parts)}", [wall_x, y, z], [depth * 0.70, width, height], glass, 0.01))
        parts.append(box(f"{face.title()}WindowTop_{len(parts)}", [wall_x + x * 0.045, y, z + height / 2 + frame / 2], [depth, width + 0.20, frame], trim, 0.012))
        parts.append(box(f"{face.title()}WindowBottom_{len(parts)}", [wall_x + x * 0.045, y, z - height / 2 - frame / 2], [depth + 0.025, width + 0.24, frame], trim, 0.012))
        parts.append(box(f"{face.title()}WindowFront_{len(parts)}", [wall_x + x * 0.045, y - width / 2 - frame / 2, z], [depth, frame, height + 0.20], trim, 0.012))
        parts.append(box(f"{face.title()}WindowBack_{len(parts)}", [wall_x + x * 0.045, y + width / 2 + frame / 2, z], [depth, frame, height + 0.20], trim, 0.012))
        if mullion:
            parts.append(box(f"{face.title()}WindowMullion_{len(parts)}", [wall_x + x * 0.052, y, z], [depth + 0.01, 0.065, height], trim, 0.008))


def expand(plan):
    if plan.get("contract") != "CITY_HORIZON_SUBURBAN_HOUSE_V1":
        raise ValueError("Expected CITY_HORIZON_SUBURBAN_HOUSE_V1")
    if plan.get("styleContract") != "CH_STYLIZED_PRERENDER_V1":
        raise ValueError("Suburban house must opt into CH_STYLIZED_PRERENDER_V1")

    mass = plan["mass"]
    width = float(mass["width"])
    depth = float(mass["depth"])
    foundation_h = float(mass["foundationHeight"])
    wall_h = float(mass["wallHeight"])
    half_w = width / 2
    half_d = depth / 2
    parts = []

    # Primary massing.
    parts.append(box("Foundation", [0, 0, foundation_h / 2], [width + 0.20, depth + 0.20, foundation_h], "foundation", 0.045))
    parts.append(box("MainWalls", [0, 0, foundation_h + wall_h / 2], [width, depth, wall_h], "wall", 0.055))

    # Eave/contact bands are geometry, not painted fake AO.
    if plan["details"].get("eaveShadowBand", True):
        band_h = 0.14
        z = foundation_h + wall_h - 0.07
        parts.extend([
            box("EaveBandSouth", [0, -half_d - 0.025, z], [width, 0.08, band_h], "foundation", 0.012),
            box("EaveBandNorth", [0, half_d + 0.025, z], [width, 0.08, band_h], "foundation", 0.012),
            box("EaveBandEast", [half_w + 0.025, 0, z], [0.08, depth, band_h], "foundation", 0.012),
            box("EaveBandWest", [-half_w - 0.025, 0, z], [0.08, depth, band_h], "foundation", 0.012),
        ])

    roof = plan["roof"]
    parts.append({
        "type": "pyramid_roof",
        "name": "HipRoof",
        "location": [0.0, 0.0, float(roof["baseZ"]) + float(roof["depth"]) / 2],
        "radius": float(roof["radius"]),
        "depth": float(roof["depth"]),
        "material": "roof",
        "rotationDegrees": 45.0,
        "bevel": 0.035,
    })

    if roof.get("chimney", False):
        ox, oy = roof.get("chimneyOffset", [1.0, 0.5])
        parts.append(box("Chimney", [ox, oy, float(roof["baseZ"]) + 0.78], [0.46, 0.42, 1.16], "chimney", 0.022))
        parts.append(box("ChimneyCap", [ox, oy, float(roof["baseZ"]) + 1.39], [0.56, 0.52, 0.10], "foundation", 0.018))

    facade = plan["facade"]
    door_x = float(facade["doorOffsetX"])
    door_w = float(facade["doorWidth"])
    door_h = float(facade["doorHeight"])
    front_y = -half_d - 0.055
    door_z = foundation_h + door_h / 2
    parts.append(box("FrontDoor", [door_x, front_y, door_z], [door_w, 0.12, door_h], "door", 0.024))
    parts.append(box("DoorFrameLeft", [door_x - door_w / 2 - 0.075, front_y - 0.035, door_z], [0.12, 0.12, door_h + 0.18], "trim", 0.012))
    parts.append(box("DoorFrameRight", [door_x + door_w / 2 + 0.075, front_y - 0.035, door_z], [0.12, 0.12, door_h + 0.18], "trim", 0.012))
    parts.append(box("DoorFrameTop", [door_x, front_y - 0.035, foundation_h + door_h + 0.075], [door_w + 0.26, 0.12, 0.13], "trim", 0.012))
    parts.append(box("DoorHandle", [door_x + door_w * 0.28, front_y - 0.085, foundation_h + door_h * 0.52], [0.055, 0.045, 0.055], "metal", 0.008))

    mullion = bool(plan["details"].get("windowMullions", True))
    for spec in facade["frontWindows"]:
        # add_window uses normalized wall coordinate; replace with exact facade plane after creation.
        before = len(parts)
        add_window(parts, "south", float(spec["x"]), float(spec["width"]), float(spec["height"]), foundation_h + float(spec["sillZ"]), mullion=mullion)
        for part in parts[before:]:
            part["location"][1] = round(front_y - 0.01, 4)

    if plan["details"].get("sideWindows", True):
        sw = float(facade["sideWindowWidth"])
        sh = float(facade["sideWindowHeight"])
        ss = foundation_h + float(facade["sideWindowSillZ"])
        for face in ("east", "west"):
            before = len(parts)
            add_window(parts, face, 0.30, sw, sh, ss, mullion=mullion)
            for part in parts[before:]:
                part["location"][0] = round((half_w + 0.06) * (1 if face == "east" else -1), 4)

    if plan["details"].get("rearWindows", True):
        for x in (-1.10, 1.10):
            before = len(parts)
            add_window(parts, "north", x, 0.84, 0.86, foundation_h + 1.12, mullion=mullion)
            for part in parts[before:]:
                part["location"][1] = round(half_d + 0.06, 4)

    # Small porch adds suburban identity without dominating the footprint.
    if plan["details"].get("porch", True):
        porch_w = float(plan["details"]["porchWidth"])
        porch_d = float(plan["details"]["porchDepth"])
        porch_y = -half_d - porch_d / 2
        parts.append(box("PorchSlab", [door_x, porch_y, foundation_h + 0.06], [porch_w, porch_d, 0.12], "foundation", 0.025))
        canopy_z = foundation_h + door_h + 0.34
        parts.append(box("PorchCanopy", [door_x, porch_y + 0.02, canopy_z], [porch_w + 0.18, porch_d + 0.16, 0.16], "roof", 0.025))
        post_x = porch_w * 0.39
        for side in (-1, 1):
            parts.append(box(f"PorchPost_{side}", [door_x + side * post_x, porch_y - porch_d * 0.25, foundation_h + 1.16], [0.13, 0.13, 2.02], "trim", 0.018))
        step_depth = 0.24
        for i in range(int(plan["details"].get("frontSteps", 2))):
            parts.append(box(f"FrontStep_{i}", [door_x, -half_d - porch_d - 0.10 - i * 0.12, 0.08 + i * 0.055], [porch_w * (0.82 - i * 0.08), step_depth, 0.11], "foundation", 0.018))

    # Two tiny vents provide scale/detail without visual noise.
    for i in range(int(plan["details"].get("foundationVents", 0))):
        x = -0.72 + i * 1.44
        parts.append(box(f"FoundationVent_{i}", [x, half_d + 0.065, 0.18], [0.34, 0.08, 0.12], "metal", 0.008))

    fp = plan["footprint"]
    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "styleContract": plan["styleContract"],
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
            "seed": int(plan.get("seed", 0)),
            "proceduralStage": "pre_blender_plan_to_canonical_source_v1",
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
