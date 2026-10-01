"""Final guarded City Horizon carousel baker using CH_CAROUSEL_ROTATION_V1.

This builder reuses the approved V4 visual construction, then replaces the inherited
rotor animation with the canonical 48 unique angular samples. Frames 1..48 are
exported; frame 49 is the non-exported 360-degree loop closure key.
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
import scene_gate  # noqa: E402
import build_carousel_classic_guarded as classic  # noqa: E402
import build_carousel_city_horizon_v4_guarded as v4  # noqa: E402
import carousel_rotation_contract as rotation_contract  # noqa: E402


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


def build_scene(recipe, studio, out):
    scene, root, rotor, ground, authored = v4.build_scene(recipe, studio, out)
    spec = rotation_contract.apply_rotor_sampling(rotor, recipe)
    root["animationContract"] = "CH_CAROUSEL_ROTATION_V1"
    root["exportedFrameCount"] = spec["frameCount"]
    root["angularStepDegrees"] = spec["angularStepDegrees"]
    scene.frame_start = spec["frameStart"]
    scene.frame_end = spec["loopClosureFrame"]
    scene.frame_set(spec["frameStart"])
    bpy.context.view_layer.update()
    return scene, root, rotor, ground, authored


def main():
    args = parse_args()
    recipe_path = Path(args.recipe).resolve()
    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    if recipe.get("contract") != "CITY_HORIZON_CAROUSEL_V1":
        raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V1 recipe")
    rotation_contract.validate_recipe(recipe)

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    profile = scene_gate.load_profile(args.preflight_profile)
    scene, root, rotor, ground, authored = build_scene(recipe, studio, out)

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

    frame_start = int(recipe["animation"]["frameStart"])
    if args.stage == "preflight":
        classic._save_blend(args.save_blend)
        print(f"[CH_GATE] Carousel 48-frame preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(frame_start)
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        classic._save_blend(args.save_blend)
        print(f"[CH_GATE] Carousel 48-frame proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png and pass its SHA-256"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "animationContract": "CH_CAROUSEL_ROTATION_V1",
        "exportedFrameCount": 48,
        "angularStepDegrees": 7.5,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")

    classic.render_final_animation(
        recipe,
        studio,
        scene,
        root,
        ground,
        authored,
        out,
        approval,
        args.studio_preset,
    )
    classic._save_blend(args.save_blend)
    print("[CH_GATE] Carousel final bake complete: 48 unique frames x 4 directions")


if __name__ == "__main__":
    main()
