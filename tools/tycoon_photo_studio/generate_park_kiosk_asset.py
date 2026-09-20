#!/usr/bin/env python3
"""Expand CITY_HORIZON_PARK_KIOSK_V1 into TYCOON_ASSET_SOURCE_V1.

This generator intentionally starts from a non-residential silhouette: a short
park-service body, oversized floating canopy and one sign fin. It must not
reconstruct retired house geometry.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def box(name, location, dimensions, material, bevel=0.025):
    return {
        "type": "box",
        "name": name,
        "location": [round(float(v), 4) for v in location],
        "dimensions": [round(float(v), 4) for v in dimensions],
        "material": material,
        "bevel": bevel,
    }


def expand(recipe: dict) -> dict:
    if recipe.get("contract") != "CITY_HORIZON_PARK_KIOSK_V1":
        raise ValueError("Expected CITY_HORIZON_PARK_KIOSK_V1")

    fp = recipe["footprint"]
    if int(fp["widthTiles"]) != 1 or int(fp["depthTiles"]) != 1:
        raise ValueError("park kiosk pilot is intentionally a 1x1 asset")

    m = recipe["mass"]
    op = recipe["openings"]
    sign = recipe["sign"]
    mats = recipe["materials"]

    bw = float(m["bodyWidth"])
    bd = float(m["bodyDepth"])
    bh = float(m["bodyHeight"])
    base_h = float(m["baseHeight"])
    cw = float(m["canopyWidth"])
    cd = float(m["canopyDepth"])
    ct = float(m["canopyThickness"])
    cz = float(m["canopyZ"])

    if max(bw, cw) > 3.0 or max(bd, cd) > 3.0:
        raise ValueError("kiosk geometry exceeds 1x1 world footprint")
    if cw <= bw or cd <= bd:
        raise ValueError("canopy must visibly overhang the kiosk body")

    parts = []
    parts.append(box("Kiosk_Base", [0, 0, base_h / 2], [bw + 0.12, bd + 0.12, base_h], "base", 0.05))
    parts.append(box("Kiosk_Body", [0, 0, base_h + bh / 2], [bw, bd, bh], "body", 0.07))

    # Oversized floating canopy: the primary silhouette, intentionally unlike a house roof.
    parts.append(box("Kiosk_Canopy", [0, 0, cz], [cw, cd, ct], "canopy", 0.08))
    # Bold coral fascia on the gameplay-facing edges to reinforce toy/tycoon readability.
    fascia_h = 0.16
    parts.append(box("Kiosk_Fascia_South", [0, -cd / 2 + 0.035, cz - 0.01], [cw - 0.10, 0.07, fascia_h], "accent", 0.025))
    parts.append(box("Kiosk_Fascia_East", [cw / 2 - 0.035, 0, cz - 0.01], [0.07, cd - 0.10, fascia_h], "accent", 0.025))

    sill = float(op["sillZ"])
    sw = float(op["southWindowWidth"])
    sh = float(op["southWindowHeight"])
    ew = float(op["eastWindowWidth"])
    eh = float(op["eastWindowHeight"])
    inset = 0.035

    # Large service windows are graphic openings rather than realistic facade detail.
    parts.append(box("Kiosk_South_Window", [0, -bd / 2 - inset, sill + sh / 2], [sw, 0.06, sh], "glass", 0.018))
    parts.append(box("Kiosk_East_Window", [bw / 2 + inset, -0.02, sill + eh / 2], [0.06, ew, eh], "glass", 0.018))

    counter_d = float(op["counterDepth"])
    counter_t = float(op["counterThickness"])
    counter_z = sill - 0.03
    parts.append(box("Kiosk_South_Counter", [0, -bd / 2 - counter_d / 2, counter_z], [sw + 0.22, counter_d, counter_t], "counter", 0.035))
    parts.append(box("Kiosk_East_Counter", [bw / 2 + counter_d / 2, -0.02, counter_z], [counter_d, ew + 0.18, counter_t], "counter", 0.035))

    # Thick dark frames keep the openings readable after downsampling.
    frame = 0.075
    z_mid = sill + sh / 2
    parts.append(box("South_Frame_Top", [0, -bd / 2 - inset - 0.012, sill + sh + frame / 2], [sw + 0.16, 0.07, frame], "dark", 0.016))
    parts.append(box("South_Frame_Left", [-sw / 2 - frame / 2, -bd / 2 - inset - 0.012, z_mid], [frame, 0.07, sh + 0.10], "dark", 0.016))
    parts.append(box("South_Frame_Right", [sw / 2 + frame / 2, -bd / 2 - inset - 0.012, z_mid], [frame, 0.07, sh + 0.10], "dark", 0.016))

    # One oversized asymmetric sign fin is the secondary silhouette and category cue.
    swid = float(sign["width"])
    sdep = float(sign["depth"])
    shei = float(sign["height"])
    sx = float(sign["offsetX"])
    sy = float(sign["offsetY"])
    sign_z = cz + ct / 2 + shei / 2 - 0.03
    parts.append(box("Kiosk_Sign_Fin", [sx, sy, sign_z], [swid, sdep, shei], "accent", 0.07))
    parts.append(box("Kiosk_Sign_Inset", [sx, sy - sdep / 2 - 0.018, sign_z], [swid * 0.62, 0.04, shei * 0.44], "canopy", 0.025))

    # A simple rear service door prevents the back view from reading as an empty cube.
    door_h = 1.02
    door_w = 0.58
    parts.append(box("Kiosk_Rear_Service_Door", [-0.34, bd / 2 + inset, base_h + door_h / 2], [door_w, 0.06, door_h], "dark", 0.02))

    material_defs = {key: value for key, value in mats.items()}
    return {
        "contract": "TYCOON_ASSET_SOURCE_V1",
        "assetId": recipe["assetId"],
        "assetType": "static_building",
        "styleContract": recipe.get("styleContract", "CH_TYCOON_MINIATURE_V1"),
        "studioPreset": recipe.get("studioPreset", "CH_TYCOON_STUDIO_V1"),
        "footprint": {
            "widthTiles": 1,
            "depthTiles": 1,
            "occupiedCells": [[0, 0]],
        },
        "materials": material_defs,
        "parts": parts,
        "buildingPostProcess": recipe.get("buildingPostProcess", {}),
        "generation": {
            "sourceContract": recipe["contract"],
            "designGrammar": "floating_canopy_plus_sign_fin_v1",
            "partCount": len(parts),
            "retiredHouseGeometryReused": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    asset = expand(recipe)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(asset, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(asset["generation"], sort_keys=True))


if __name__ == "__main__":
    main()
