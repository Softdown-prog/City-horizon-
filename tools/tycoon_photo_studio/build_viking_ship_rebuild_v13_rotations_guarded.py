"""Guarded four-rotation static bake for the approved City Horizon Viking ship V12.

This pass does not create swing animation frames.  It renders the exact same
approved static attraction in the four canonical City Horizon directions by
rotating AssetRoot while keeping camera and lighting fixed.
"""
from __future__ import annotations

import json

import bpy

import build_scene as bs
import scene_gate
import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v12_hull_finish_guarded as v12gate  # noqa: F401


ROTATION_CONTRACT = "CH_VIKING_STATIC_4_ROTATIONS_V1"


def _write_rotation_metadata(recipe, scene, root, out):
    # Let the V12 gate write its normal authoring metadata first.
    base.write_metadata(recipe, scene, out)
    path = out / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "viking_static_four_rotation_bake_v13"
    payload["rotationContract"] = ROTATION_CONTRACT
    payload["rotationPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    payload["directions"] = [direction["id"] for direction in bs.DIRECTIONS]
    payload["animationFramesDefined"] = False
    payload["swingFramesBaked"] = False
    payload["sourceRevision"] = "CH_VIKING_HULL_FINISH_V12"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v13_rotations_guarded.py"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    root["rotationContract"] = ROTATION_CONTRACT
    root["animationFramesDefined"] = False
    root["swingFramesBaked"] = False


def main():
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = base.build_for_gate(args)
    _write_rotation_metadata(recipe, scene, root, out)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        base.save_blend(args.save_blend)
        print(f"[CH_GATE] Viking V13 four-rotation preflight PASS: {preflight_path}")
        return

    if args.stage != "proxy":
        raise RuntimeError(
            "CH_VIKING_V13_STATIC_ONLY: this pass bakes four static rotations only; swing animation remains intentionally undefined"
        )

    reports = {}
    for direction in bs.DIRECTIONS:
        direction_id = direction["id"]
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        report = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / f"proxy_{direction_id}.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction=direction_id,
        )
        reports[direction_id] = report
        print(f"[CH_GATE] Viking V13 {direction_id.upper()} ready: {report['sha256']}")

    # Return the authored blend to the canonical south orientation before save.
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    (out / "proxy_report.json").write_text(
        json.dumps(
            {
                "contract": ROTATION_CONTRACT,
                "assetId": recipe["assetId"],
                "staticOnly": True,
                "swingFramesBaked": False,
                "directions": reports,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    base.save_blend(args.save_blend)
    print("[CH_GATE] Viking V13 four static rotations ready; no swing frames were created")


if __name__ == "__main__":
    main()
