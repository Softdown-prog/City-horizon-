"""CH Blender guarded adapter for the procedural City Horizon Ferris wheel.

The game remains 2D. Blender/CH Blender is only the offline authoring and
pre-render environment. New agent-authored geometry must pass:

    preflight -> SOUTH proxy -> human review -> final 4-direction bake

This adapter intentionally stops before final production until a reviewed proxy
SHA is supplied by the CH Blender job contract.
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
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import build_ferris_wheel as fw  # noqa: E402
import scene_gate  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _tag_semantics():
    # Attraction-oriented tags. They do not turn the wheel into a character;
    # they make important authored pieces discoverable to the scene gate/review.
    mapping = {
        "LoadingPlatform": ("attraction.loading_platform", True),
        "WheelOuterRing": ("attraction.wheel_ring", False),
        "WheelHub": ("attraction.wheel_hub", False),
        "Support_South_L": ("attraction.support", True),
        "Support_South_R": ("attraction.support", True),
        "Support_North_L": ("attraction.support", True),
        "Support_North_R": ("attraction.support", True),
    }
    for name, (role, contact) in mapping.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"CH_PREFLIGHT_AUTHORING_ERROR: missing authored object {name}")
        scene_gate.tag(obj, role, ground_contact=contact)


def build_for_gate(args):
    recipe = fw.load_json(args.recipe)
    if recipe.get("contract") != "CITY_HORIZON_FERRIS_WHEEL_V1":
        raise RuntimeError("Expected CITY_HORIZON_FERRIS_WHEEL_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    # Source is deliberately supersampled; gameplay review happens through the
    # CH Blender proxy and later canonical downsample. Runtime remains 2D PNG.
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    mats = fw.make_materials(recipe)
    root = fw.empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = "animated_attraction"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = "3x2"
    root["proceduralContract"] = recipe["contract"]
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    fw.build_supports(root, recipe["geometry"], mats)
    rotor, gondolas = fw.build_wheel(root, recipe["geometry"], mats)
    fw.animate(rotor, gondolas, recipe["animation"])

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        receiver_mat,
        0.0,
    )

    authored = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH" and obj != ground
    ]

    # Camera orientation remains frozen. Only orthographic scale is fitted to
    # the actual attraction envelope to avoid crop while preserving CH_CAMERA_V1.
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
    bpy.context.view_layer.update()
    _tag_semantics()

    return recipe, studio, scene, root, ground, authored, out


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, ground, authored, out = build_for_gate(args)

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
        _save_blend(args.save_blend)
        print(f"[CH_GATE] Ferris wheel preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        # Human review is always the gameplay-oriented SOUTH proxy first.
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(
            json.dumps(proxy, indent=2), encoding="utf-8"
        )
        _save_blend(args.save_blend)
        print(f"[CH_GATE] Ferris wheel proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )

    # Final rendering is intentionally not duplicated here. CH Blender owns the
    # approval barrier; the canonical animated four-direction/downsample bake is
    # the next implementation step after the first SOUTH proxy is accepted.
    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )
    raise RuntimeError(
        "CH_FERRIS_FINAL_NOT_IMPLEMENTED: proxy approval recorded; implement canonical animated 4-direction/downsample bake next"
    )


if __name__ == "__main__":
    main()
