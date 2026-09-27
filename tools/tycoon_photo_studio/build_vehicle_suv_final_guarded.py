"""Final four-direction CH Blender bake for the approved City Horizon SUV V2.

This stage reuses the exact vehicle.road.suv_01 geometry from
build_vehicle_suv_guarded.py. It rotates AssetRoot while keeping the frozen
CH_CAMERA_V1 camera and CH_TYCOON_STUDIO_V1 lighting fixed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import build_vehicle_suv_guarded as base  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = base.ASSET_ID


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("final",), required=True)
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", required=True)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    approval_sha = args.approval_proxy_sha.lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval_sha):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY_SHA")

    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored = base.build_suv()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["visualContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["vehicleClass"] = "compact_suv"
    root["proxyRevision"] = 2
    root["bodyColorMaskReady"] = True
    root["runtimeTrafficReady"] = False
    root["headlightOverlayReady"] = False
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"

    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint={"widthTiles": 1, "depthTiles": 2},
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(preflight)

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "proxySha256": approval_sha,
        "reviewed": True,
        "approvedRevision": 2,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (output / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )

    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        png_name = f"{ASSET_ID}_{direction['id']}.png"
        render = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / png_name,
            profile=profile,
            asset_id=ASSET_ID,
            direction=direction["id"],
        )
        directions.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "file": png_name,
            "sha256": render["sha256"],
            "resolution": render["resolution"],
            "engine": render["engine"],
        })

    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    metadata = {
        "contract": "CH_VEHICLE_DIRECTIONAL_BAKE_V1",
        "assetId": ASSET_ID,
        "status": "review_ready",
        "approvedProxySha256": approval_sha,
        "proxyRevision": 2,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "visualContract": "CH_STYLIZED_PRERENDER_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True,
        },
        "bodyColorMaskReady": True,
        "runtimeTrafficReady": False,
        "headlightOverlayReady": False,
        "directions": directions,
    }
    (output / "studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print("[CH_GATE] SUV V2 four-direction review bake complete")


if __name__ == "__main__":
    main()
