#!/usr/bin/env python3
"""Guarded activity-overlay baker for CITY_HORIZON_SMALL_COMMERCIAL_V1 shops.

The base building remains untouched. This baker renders a transparent runtime
pass containing only warm illuminated glazing. CH_BUILDING_ACTIVITY_OVERLAY_V1
then composites that pass while a visitor activity is active.

V1 intentionally supports the shared small-commercial geometry used by the
approved bakery and coffee shop. It does not special-case screen coordinates:
overlay geometry is authored in the same building/world space as the source
recipe and therefore rotates into SOUTH/EAST/WEST/NORTH with AssetRoot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_scene as bs  # noqa: E402
import generate_small_commercial_asset as commercial  # noqa: E402

CONTRACT = "CH_BUILDING_ACTIVITY_OVERLAY_V1"
SUPPORTED_SUBTYPES = {"bakery", "coffee_shop"}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), required=True)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def warm_material(name: str, rgba, emission_strength: float):
    mat = bs.make_material(name, rgba, 0.30)
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if principled is not None:
        for key in ("Emission Color", "Emission"):
            if key in principled.inputs:
                principled.inputs[key].default_value = tuple(rgba)
                break
        if "Emission Strength" in principled.inputs:
            principled.inputs["Emission Strength"].default_value = float(emission_strength)
    return mat


def add_box(name, loc, dims, material, parent):
    obj = bs.add_box(name, loc, dims, material, 0.010)
    obj.parent = parent
    return obj


def add_light_geometry(recipe: dict, root):
    mass = recipe["mass"]
    facade = recipe["facade"]
    width = float(mass["width"])
    depth = float(mass["depth"])
    base_h = float(mass.get("baseHeight", 0.14))
    front_y = -depth / 2.0
    back_y = depth / 2.0
    east_x = width / 2.0
    west_x = -width / 2.0

    win_w = float(facade["windowWidth"])
    win_h = float(facade["windowHeight"])
    sill = float(facade["windowSill"])
    door_w = float(facade["doorWidth"])
    door_h = float(facade["doorHeight"])
    door_x = width / 2.0 - door_w / 2.0 - 0.34

    warm = warm_material("ActivityWarmStorefront", [1.0, 0.62, 0.20, 1.0], 3.0)
    soft = warm_material("ActivityWarmSideGlass", [1.0, 0.78, 0.38, 1.0], 2.2)
    objects = []

    # These centers/dimensions deliberately match generate_small_commercial_asset.py.
    for label, x in (("Left", -1.46), ("Right", 0.36)):
        objects.append(add_box(
            f"ActivityFrontWindow{label}",
            [x, front_y - 0.112, sill + win_h / 2.0],
            [win_w * 0.94, 0.026, win_h * 0.88], warm, root))

    objects.append(add_box(
        "ActivityDoorGlass",
        [door_x, front_y - 0.126, base_h + door_h * 0.69],
        [door_w * 0.60, 0.026, door_h * 0.40], soft, root))

    for face, x, outward in (("East", east_x, 1.0), ("West", west_x, -1.0)):
        count = int(recipe.get("sideWindows", {}).get(face.lower(), 0))
        if count <= 0:
            continue
        span = depth - 1.10
        step = span / count
        for index in range(count):
            y = -span / 2.0 + step * (index + 0.5)
            if face == "West":
                y = -y
            objects.append(add_box(
                f"Activity{face}Window{index}",
                [x + outward * 0.112, y, 1.18],
                [0.026, 0.82, 0.70], soft, root))

    if recipe.get("rear", {}).get("smallWindow", False):
        objects.append(add_box(
            "ActivityRearWindow", [0.78, back_y + 0.112, 1.26],
            [1.00, 0.026, 0.62], soft, root))
    return objects


def set_visible(objects, visible: bool):
    for obj in objects:
        obj.hide_render = not visible
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = visible


def render(scene, path: Path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main():
    args = parse_args()
    recipe_path = Path(args.recipe).resolve()
    studio_path = Path(args.studio_preset).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    recipe = bs.load_json(str(recipe_path))
    studio = bs.load_json(str(studio_path))
    if recipe.get("contract") != "CITY_HORIZON_SMALL_COMMERCIAL_V1":
        raise RuntimeError("SHOP_ACTIVITY_RECIPE_CONTRACT_MISMATCH")
    if recipe.get("subtype") not in SUPPORTED_SUBTYPES:
        raise RuntimeError(f"SHOP_ACTIVITY_UNSUPPORTED_SUBTYPE:{recipe.get('subtype')}")

    asset = commercial.expand(recipe)
    asset_id = asset["assetId"]
    report = {
        "contract": "CH_SCENE_PREFLIGHT_V1",
        "status": "pass",
        "assetId": asset_id,
        "activityContract": CONTRACT,
        "stage": args.stage,
        "effects": ["front_window_glow", "door_glow", "side_window_glow", "rear_window_glow"],
        "baseBuildingModified": False,
        "directionPolicy": "rotate_asset_root_keep_camera_lights_fixed",
    }
    write_json(output / "preflight_report.json", report)
    if args.stage == "preflight":
        print(f"[shop_activity] {asset_id} preflight OK")
        return

    src_res, final_res = bs.compute_dynamic_resolution(asset, studio)
    bs.clear_scene()
    scene = bs.configure_scene(studio, src_res, str(output))
    base_objects = bs.build_asset(asset, asset_config_path=str(recipe_path))
    root = bs.create_asset_root(base_objects)
    bs.validate_footprint_scale(asset, base_objects)
    calibrated_scale = bs.calibrate_ortho_scale(scene, base_objects, safety_margin=0.14)
    overlay_objects = add_light_geometry(recipe, root)

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        set_visible(base_objects, True)
        set_visible(overlay_objects, True)
        render(scene, output / "proxy_south_active.png")
        shutil.copyfile(output / "proxy_south_active.png", output / "proxy_south.png")
        set_visible(base_objects, False)
        render(scene, output / "proxy_south_overlay.png")
        write_json(output / "proxy_report.json", {
            "contract": "CH_PROXY_RENDER_V1",
            "assetId": asset_id,
            "direction": "south",
            "sha256": sha256(output / "proxy_south.png"),
            "activityEffects": report["effects"],
        })
        print(f"[shop_activity] {asset_id} SOUTH proxy ready")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("SHOP_ACTIVITY_FINAL_REQUIRES_APPROVED_PROXY_SHA")

    set_visible(base_objects, False)
    set_visible(overlay_objects, True)
    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        direction_id = direction["id"]
        filename = f"{asset_id}_activity_{direction_id}.png"
        render(scene, output / filename)
        directions.append({
            "id": direction_id,
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "source": filename,
        })

    write_json(output / "studio_metadata.json", {
        "contract": "CH_BUILDING_ACTIVITY_OVERLAY_BAKE_V1",
        "activityContract": CONTRACT,
        "assetId": asset_id,
        "frameCount": 1,
        "layout": "single_frame",
        "sourceResolution": [scene.render.resolution_x, scene.render.resolution_y],
        "finalResolution": list(final_res),
        "groundOriginSourcePx": bs.ground_origin_source_px(scene),
        "calibratedOrthoScale": calibrated_scale,
        "directions": directions,
        "effects": report["effects"],
        "recipe": recipe_path.as_posix(),
    })
    write_json(output / "proxy_approval.json", {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": asset_id,
        "proxyReviewed": True,
        "approvedProxySha256": approval,
    })
    print(f"[shop_activity] {asset_id} final four-direction light overlay rendered")


if __name__ == "__main__":
    main()
