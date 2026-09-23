#!/usr/bin/env python3
"""Guarded activity-overlay baker for building.ice_cream_shop.01.

Produces only temporary runtime effects for CH_BUILDING_ACTIVITY_OVERLAY_V1:
- warm illuminated storefront / door / side / rear windows;
- a decorative backing plate that fully covers the authored static popsicle board;
- the popsicle board rotating in 8 deterministic frames while activity is active.

The approved building art remains the alignment authority. Camera calibration is
performed against the complete V3 building before base geometry is hidden, so
all overlay frames share the exact source canvas and ground anchor.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_scene as bs  # noqa: E402
import generate_ice_cream_shop_asset_v3 as ice_v3  # noqa: E402


CONTRACT = "CH_BUILDING_ACTIVITY_OVERLAY_V1"
ASSET_ID = "building.ice_cream_shop.01"
FRAME_COUNT = 8
FPS = 4


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), required=True)
    return parser.parse_args(argv)


def warm_material(name, rgba, emission_strength=2.0, roughness=0.38):
    mat = bs.make_material(name, rgba, roughness)
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


def box(name, loc, dims, material, bevel=0.01):
    return bs.add_box(name, loc, dims, material, bevel)


def part_by_name(asset, name):
    for part in asset.get("parts", []):
        if part.get("name") == name:
            return part
    raise RuntimeError(f"ICE_CREAM_ACTIVITY_MISSING_PART:{name}")


def add_overlay_geometry(asset, recipe, root):
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

    glow = warm_material("IceCreamActivityWarmGlow", [1.0, 0.56, 0.16, 1.0], 3.0, 0.28)
    soft_glow = warm_material("IceCreamActivitySoftGlow", [1.0, 0.76, 0.34, 1.0], 2.2, 0.34)
    backing = warm_material("IceCreamActivitySpinnerBacking", [0.98, 0.87, 0.67, 1.0], 1.15, 0.48)
    spinner = warm_material("IceCreamActivitySpinner", [1.0, 0.66, 0.12, 1.0], 1.6, 0.40)
    stripe = warm_material("IceCreamActivitySpinnerStripe", [0.96, 0.30, 0.47, 1.0], 1.5, 0.42)

    static_overlay = []
    active_glow = []

    # Storefront windows.
    for label, x in (("Left", -1.46), ("Right", 0.36)):
        active_glow.append(box(
            f"ActivityFrontWindow{label}",
            [x, front_y - 0.112, sill + win_h / 2.0],
            [win_w * 0.94, 0.026, win_h * 0.88],
            glow,
            0.012,
        ))

    # Lit door glass / entrance cue.
    active_glow.append(box(
        "ActivityDoorGlass",
        [door_x, front_y - 0.126, base_h + door_h * 0.69],
        [door_w * 0.60, 0.026, door_h * 0.40],
        soft_glow,
        0.012,
    ))

    # Side windows, matching the generic commercial geometry exactly.
    for face, x, outward in (("East", east_x, 1.0), ("West", west_x, -1.0)):
        count = int(recipe.get("sideWindows", {}).get(face.lower(), 0))
        if count <= 0:
            continue
        span = depth - 1.10
        step = span / count
        for i in range(count):
            y = -span / 2.0 + step * (i + 0.5)
            if face == "West":
                y = -y
            active_glow.append(box(
                f"Activity{face}Window{i}",
                [x + outward * 0.112, y, 1.18],
                [0.026, 0.82, 0.70],
                soft_glow,
                0.010,
            ))

    if recipe.get("rear", {}).get("smallWindow", False):
        active_glow.append(box(
            "ActivityRearWindow",
            [0.78, back_y + 0.112, 1.26],
            [1.00, 0.026, 0.62],
            soft_glow,
            0.010,
        ))

    # Cover the authored static sign before drawing the rotating activity sign.
    # The backing is intentionally a visible decorative plaque, not an eraser.
    spinner_part = part_by_name(asset, "IceCreamSpinner")
    spinner_loc = [float(v) for v in spinner_part["location"]]
    spinner_dims = [float(v) for v in spinner_part["dimensions"]]
    plate_loc = [spinner_loc[0], spinner_loc[1] - 0.055, spinner_loc[2]]
    static_overlay.append(box(
        "ActivitySpinnerBackingPlate",
        plate_loc,
        [spinner_dims[0] + 0.24, 0.10, spinner_dims[2] + 0.22],
        backing,
        0.12,
    ))
    animated_board = box(
        "ActivitySpinnerBoard",
        [spinner_loc[0], spinner_loc[1] - 0.125, spinner_loc[2]],
        [spinner_dims[0], 0.08, spinner_dims[2]],
        spinner,
        0.20,
    )
    animated_stripe = box(
        "ActivitySpinnerStripe",
        [spinner_loc[0], spinner_loc[1] - 0.171, spinner_loc[2] + 0.05],
        [spinner_dims[0] * 0.66, 0.026, 0.15],
        stripe,
        0.045,
    )

    overlay_objects = static_overlay + active_glow + [animated_board, animated_stripe]
    for obj in overlay_objects:
        obj.parent = root
    return {
        "all": overlay_objects,
        "static": static_overlay,
        "glow": active_glow,
        "animated": [animated_board, animated_stripe],
    }


def set_base_visible(base_objects, visible):
    for obj in base_objects:
        obj.hide_render = not visible
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = visible


def set_overlay_visible(overlay_objects, visible):
    for obj in overlay_objects:
        obj.hide_render = not visible
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = visible


def set_spinner_frame(animated, frame_index):
    angle = (2.0 * math.pi * frame_index) / FRAME_COUNT
    for obj in animated:
        obj.rotation_euler[2] = angle


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def write_report(output, stage, asset, scene=None, calibrated_scale=None):
    report = {
        "contract": "CH_ICE_CREAM_ACTIVITY_OVERLAY_REPORT_V1",
        "activityContract": CONTRACT,
        "assetId": ASSET_ID,
        "stage": stage,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "effects": ["window_glow", "door_glow", "side_window_glow", "rear_window_glow", "rotating_popsicle"],
        "alignmentAuthority": "approved_full_building_v3",
        "baseSpinnerCoveredByDecorativeBacking": True,
        "sourcePartCount": len(asset.get("parts", [])),
    }
    if scene is not None:
        report["sourceResolution"] = [scene.render.resolution_x, scene.render.resolution_y]
        report["groundOriginSourcePx"] = bs.ground_origin_source_px(scene)
    if calibrated_scale is not None:
        report["calibratedOrthoScale"] = calibrated_scale
    (output / "activity_overlay_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    recipe = bs.load_json(args.recipe)
    studio = bs.load_json(args.studio_preset)
    asset = ice_v3.expand(recipe)

    if asset.get("assetId") != ASSET_ID:
        raise RuntimeError(f"ICE_CREAM_ACTIVITY_WRONG_ASSET:{asset.get('assetId')}")
    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError("ICE_CREAM_ACTIVITY_STUDIO_MISMATCH")
    animation = asset.get("animation", {})
    if int(animation.get("frameEnd", 0)) - int(animation.get("frameStart", 1)) + 1 != FRAME_COUNT:
        raise RuntimeError("ICE_CREAM_ACTIVITY_FRAME_COUNT_MISMATCH")
    part_by_name(asset, "IceCreamSpinner")
    for required in ("FrontWindowLeft_Glass", "FrontWindowRight_Glass", "FrontDoorGlass"):
        part_by_name(asset, required)

    if args.stage == "preflight":
        write_report(output, "preflight", asset)
        print("[ice_cream_activity] preflight OK")
        return

    src_res, final_res = bs.compute_dynamic_resolution(asset, studio)
    bs.clear_scene()
    scene = bs.configure_scene(studio, src_res, str(output))
    base_objects = bs.build_asset(asset, asset_config_path=args.recipe)
    root = bs.create_asset_root(base_objects)
    bs.validate_footprint_scale(asset, base_objects)
    calibrated_scale = bs.calibrate_ortho_scale(scene, base_objects, safety_margin=0.12)
    overlay = add_overlay_geometry(asset, recipe, root)

    # All overlay effects are deliberately shadowless/groundless. They are a
    # transparent runtime pass over already-rendered approved building art.
    set_overlay_visible(overlay["all"], True)

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        set_spinner_frame(overlay["animated"], 1)
        set_base_visible(base_objects, True)
        render(scene, output / "proxy_south_active.png")
        set_base_visible(base_objects, False)
        render(scene, output / "proxy_south_overlay.png")
        write_report(output, "proxy", asset, scene, calibrated_scale)
        print("[ice_cream_activity] SOUTH proxy rendered")
        return

    set_base_visible(base_objects, False)
    direction_records = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        direction_id = direction["id"]
        frames = []
        for frame_index in range(FRAME_COUNT):
            set_spinner_frame(overlay["animated"], frame_index)
            bpy.context.view_layer.update()
            filename = f"{ASSET_ID}_activity_{direction_id}_frame_{frame_index + 1:02d}.png"
            render(scene, output / filename)
            frames.append({"frame": frame_index + 1, "source": filename})
        direction_records.append({**direction, "frames": frames})

    metadata = {
        "contract": "CH_BUILDING_ACTIVITY_OVERLAY_BAKE_V1",
        "activityContract": CONTRACT,
        "assetId": ASSET_ID,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "playback": "loop",
        "layout": "horizontal",
        "sourceResolution": [scene.render.resolution_x, scene.render.resolution_y],
        "finalResolution": list(final_res),
        "groundOriginSourcePx": bs.ground_origin_source_px(scene),
        "calibratedOrthoScale": calibrated_scale,
        "directions": direction_records,
        "effects": ["window_glow", "door_glow", "rotating_popsicle"],
    }
    (output / "activity_overlay_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    write_report(output, "final", asset, scene, calibrated_scale)
    print("[ice_cream_activity] final 4-direction overlay frames rendered")


if __name__ == "__main__":
    main()
