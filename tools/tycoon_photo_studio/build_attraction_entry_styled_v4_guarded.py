"""Guarded v4 builder for the shared City Horizon attraction entrance.

Sequence remains mandatory:
    preflight -> SOUTH proxy -> explicit review -> final

This builder keeps the approved mathematical skeleton and applies the v4
architecture/readability pass on top. Runtime output remains 2D RGBA.
"""
from __future__ import annotations

import json
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

import attraction_entry_style_pass_v4 as style_pass  # noqa: E402
import build_attraction_entry_skeleton_guarded as skeleton  # noqa: E402
import build_scene as bs  # noqa: E402
import build_ferris_wheel as fw  # noqa: E402
import scene_gate  # noqa: E402


def main():
    args = skeleton.parse_args()
    recipe = skeleton.load_json(args.recipe)
    if recipe.get("contract") != "CITY_HORIZON_ATTRACTION_ENTRANCE_V1":
        raise RuntimeError("Expected CITY_HORIZON_ATTRACTION_ENTRANCE_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    mats = skeleton.make_materials(recipe)
    root = fw.empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = recipe["assetType"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["proceduralContract"] = recipe["contract"]
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["designStage"] = "themed_style_pass_v4_architecture_and_readability"
    root["sharedAttractionEntrance"] = True

    authored = skeleton.build_skeleton(root, recipe, mats)
    authored.extend(style_pass.apply_style_pass(root, recipe, mats, fw, scene_gate))

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

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

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
        skeleton.save_blend(args.save_blend)
        print(f"[CH_GATE] attraction entrance v4 preflight PASS: {preflight_path}")
        return

    proxy = scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=out / "proxy_south.png",
        profile=profile,
        asset_id=recipe["assetId"],
        direction="south",
    )
    (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    skeleton.save_blend(args.save_blend)
    print(f"[CH_GATE] attraction entrance v4 SOUTH proxy ready: {proxy['sha256']}")


if __name__ == "__main__":
    main()
