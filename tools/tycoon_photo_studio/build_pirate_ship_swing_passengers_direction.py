#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy

import build_pirate_ship_swing_passengers as core


def _extract_direction() -> str:
    argv = sys.argv
    if "--direction" not in argv:
        raise RuntimeError("CH_PIRATE_SWING_DIRECTION_REQUIRED")
    i = argv.index("--direction")
    if i + 1 >= len(argv):
        raise RuntimeError("CH_PIRATE_SWING_DIRECTION_VALUE_MISSING")
    direction = argv[i + 1].lower()
    del argv[i:i + 2]
    valid = {d["id"] for d in core.base.bs.DIRECTIONS}
    if direction not in valid:
        raise RuntimeError(f"CH_PIRATE_SWING_BAD_DIRECTION:{direction}")
    return direction


def main() -> None:
    direction_id = _extract_direction()
    a = core.base.argv()
    c = core.base.load(a.recipe)
    studio = core.base.bs.load_json(a.studio_preset)
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    core.base.bs.clear_scene()
    scene = core.base.bs.configure_scene(
        studio,
        tuple(map(int, studio["render"]["sourceResolution"])),
        str(out),
    )
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    M = {k: core.base.material(v) for k, v in c["materials"].items()}
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    root = bpy.context.object
    root.name = "AssetRoot"
    root["assetId"] = core.base.ASSET
    root["cameraContract"] = "CH_CAMERA_V1"
    root["styleContract"] = c["styleContract"]
    root["footprint"] = f"{c['footprint']['widthTiles']}x{c['footprint']['depthTiles']}"
    root["proceduralContract"] = core.base.CONTRACT
    root["animationContract"] = core.ANIMATION_CONTRACT
    root["passengerOverlayContract"] = core.PASSENGER_CONTRACT
    root["colorMaskContract"] = core.COLOR_MASK_CONTRACT
    root["rideCapacity"] = core.CAPACITY

    core.base.build(root, c, M)
    pivot = core._make_swing_pivot(root, c)
    slots = core._add_passengers(pivot, c)

    # The original authored geometry was built for the former 7x6 footprint.
    # Scale the whole authored hierarchy uniformly so the approved topology and
    # animation remain intact while the attraction honestly fits the 4x3 tile contract.
    model_scale = float(c.get("modelScale", 1.0))
    root.scale = (model_scale, model_scale, model_scale)
    root["modelScale"] = model_scale
    bpy.context.view_layer.update()

    mask_counts = core._tag_color_masks()
    overlay_validation = core._assert_passenger_binding(c)

    recv = studio["shadowReceiver"]
    rm = core.base.bs.make_material(
        "ShadowReceiver", recv["materialColor"], float(recv.get("roughness", 1.0))
    )
    ground = core.base.bs.add_box(
        "ShadowReceiverPlane",
        recv["location"],
        [30, 21, float(recv["dimensions"][2])],
        rm,
        0,
    )
    authored = [o for o in bpy.context.scene.objects if o.type == "MESH" and o != ground]
    core.base.bs.calibrate_ortho_scale(scene, authored, safety_margin=.16)

    selected = next(d for d in core.base.bs.DIRECTIONS if d["id"] == direction_id)
    core.base.bs.set_direction(root, selected)
    bpy.context.view_layer.update()

    metadata = {
        "contract": core.ANIMATION_CONTRACT,
        "assetId": core.base.ASSET,
        "cameraContract": "CH_CAMERA_V1",
        "direction": direction_id,
        "footprint": c["footprint"],
        "modelScale": model_scale,
        "frameCount": core.FRAME_COUNT,
        "fps": core.FPS,
        "amplitudeDegrees": core.AMPLITUDE_DEGREES,
        "anglesDegrees": core.APPROVED_SWING_ANGLES,
        "rotationAxis": "Y",
        "motion": "approved_viking_v15",
        "swingApproval": {
            "commit": "a9f6e02b63a06462f10133b405ee85921f172e40",
            "reviewWorkflowRun": 36350851439,
            "approvedProxySha256": "c92f1feac2c816599edfac0bf00aa1a645389b7cca86f3350b6b73bd9d33e89b"
        },
        "passengerOverlayContract": core.PASSENGER_CONTRACT,
        "passengerVisualRecipeSource": "CH_COASTER_PASSENGER_OVERLAY_V1 / approved Viking V15 CHActor recipe",
        "capacity": core.CAPACITY,
        "seatSlots": slots,
        "overlayValidation": overlay_validation,
        "colorMaskContract": core.COLOR_MASK_CONTRACT,
        "colorMasks": {
            "primary": "fixed A-frame supports / muletas",
            "secondary": "boat hull, seats and boat decoration",
            "taggedObjectCounts": mask_counts
        },
        "parallelBake": True
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (out / "passenger_overlay_manifest.json").write_text(json.dumps({
        "contract": core.PASSENGER_CONTRACT,
        "assetId": core.base.ASSET,
        "direction": direction_id,
        "capacity": core.CAPACITY,
        "seatSlots": slots,
        "actorSource": "CHActor",
        "visualRecipeSource": "CH_COASTER_PASSENGER_OVERLAY_V1",
        "motionParent": "SwingPivot",
        "compositionMode": "depth_correct_blender_composite_plus_transparent_overlay",
        "frameCount": core.FRAME_COUNT,
        "validation": overlay_validation
    }, indent=2), encoding="utf-8")
    (out / "color_mask_manifest.json").write_text(json.dumps({
        "contract": core.COLOR_MASK_CONTRACT,
        "assetId": core.base.ASSET,
        "direction": direction_id,
        "primaryColor": {
            "target": "A-frame supports / muletas",
            "file": f"mask_primary_{direction_id}.png",
            "animated": False
        },
        "secondaryColor": {
            "target": "boat",
            "filePattern": f"mask_secondary_{direction_id}_%02d.png",
            "animated": True
        },
        "frameCount": core.FRAME_COUNT
    }, indent=2), encoding="utf-8")

    profile = core.base.scene_gate.load_profile(a.preflight_profile)
    pivot.rotation_euler[1] = 0.0
    pre = core.base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=c["footprint"],
        profile=profile,
        asset_id=core.base.ASSET,
        report_path=out / "preflight_report.json"
    )
    core.base.scene_gate.require_pass(pre)

    cycle = core.angles()
    frames = []
    canonical_report = None

    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    core.render_color_mask(scene, out / f"mask_primary_{direction_id}.png", "primary")

    for index, angle in enumerate(cycle):
        pivot.rotation_euler[1] = math.radians(angle)
        bpy.context.view_layer.update()
        occupied_name = f"swing_{direction_id}_{index:02d}.png"
        report = core.base.scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / occupied_name,
            profile=profile,
            asset_id=core.base.ASSET,
            direction=direction_id
        )
        if index == 0:
            canonical_report = dict(report)
            (out / f"proxy_{direction_id}.png").write_bytes((out / occupied_name).read_bytes())

        states = core._set_passenger_only(True)
        overlay_name = f"passengers_{direction_id}_{index:02d}.png"
        core.base.scene_gate.render_proxy(
            scene=scene,
            authored=None,
            output_path=out / overlay_name,
            profile=profile,
            asset_id=core.base.ASSET,
            direction=direction_id
        )
        core._restore_visibility(states)

        secondary_mask = f"mask_secondary_{direction_id}_{index:02d}.png"
        core.render_color_mask(scene, out / secondary_mask, "secondary")

        frames.append({
            "direction": direction_id,
            "frameIndex": index,
            "angleDegrees": round(angle, 6),
            "occupiedFile": occupied_name,
            "passengerOverlayFile": overlay_name,
            "primaryMaskFile": f"mask_primary_{direction_id}.png",
            "secondaryMaskFile": secondary_mask,
            "sha256": report["sha256"]
        })

    if canonical_report is None:
        raise RuntimeError("CH_PIRATE_SWING_CANONICAL_PROXY_MISSING")
    canonical_report["path"] = str(out / f"proxy_{direction_id}.png")
    (out / "proxy_report.json").write_text(json.dumps(canonical_report, indent=2), encoding="utf-8")
    (out / f"swing_frames_{direction_id}.json").write_text(json.dumps({
        "contract": core.ANIMATION_CONTRACT,
        "status": "ok",
        "direction": direction_id,
        "frameCount": core.FRAME_COUNT,
        "fps": core.FPS,
        "amplitudeDegrees": core.AMPLITUDE_DEGREES,
        "anglesDegrees": cycle,
        "swingApproval": "Viking V15 / human reviewed",
        "frames": frames
    }, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    core.base.bs.set_direction(root, selected)
    bpy.context.view_layer.update()
    if a.save_blend:
        q = Path(a.save_blend).resolve()
        q.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(q))


if __name__ == "__main__":
    main()
