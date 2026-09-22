"""CH Blender guarded adapter for the procedural City Horizon Ferris wheel.

The game remains 2D. Blender/CH Blender is only the offline authoring and
pre-render environment. New agent-authored geometry must pass:

    preflight -> SOUTH proxy -> human review -> final 4-direction bake

The final stage renders every animation frame in SOUTH/EAST/WEST/NORTH, then
runs the canonical City Horizon postprocess/downsample so the runtime package is
transparent RGBA PNG rather than runtime 3D.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
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
import ferris_wheel_detail_pass as detail_pass  # noqa: E402
import ferris_wheel_maturity_pass as maturity_pass  # noqa: E402
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
    footprint = recipe["footprint"]
    root["footprint"] = f"{footprint['widthTiles']}x{footprint['depthTiles']}"
    root["proceduralContract"] = recipe["contract"]
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    fw.build_supports(root, recipe["geometry"], mats)
    rotor, gondolas = fw.build_wheel(root, recipe["geometry"], mats)
    detail_pass.apply_detail_pass(root, rotor, gondolas, recipe["geometry"], mats, fw)
    maturity_pass.apply_maturity_pass(root, rotor, gondolas, recipe["geometry"], mats, fw)
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

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(int(recipe["animation"].get("frameStart", 1)))
    bpy.context.view_layer.update()
    _tag_semantics()

    return recipe, studio, scene, root, ground, authored, out


def _frame_metadata(recipe, studio, scene, frame, directions_meta):
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    final_res = tuple(map(int, studio["render"]["finalResolution"]))
    animation = recipe["animation"]
    return {
        "sourceObject": recipe["assetId"],
        "assetType": "animated_attraction",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_ANIMATED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_ferris_wheel_guarded.py",
        "studioPreset": studio["id"],
        "styleContract": recipe.get("styleContract", "CH_TYCOON_MINIATURE_V1"),
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True,
        },
        "animation": {
            "frame": frame,
            "frameStart": int(animation.get("frameStart", 1)),
            "frameEnd": int(animation.get("frameEnd", 12)),
            "fps": int(animation.get("fps", 8)),
            "looping": bool(animation.get("looping", True)),
            "keepGondolasUpright": bool(animation.get("keepGondolasUpright", True)),
        },
        "sourceSummary": {
            "groundIncludedInAsset": False,
            "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
            "detailPass": "FERRIS_2D_READABILITY_V1",
            "maturityPass": "FERRIS_MATURITY_V1",
        },
        "directions": directions_meta,
    }


def render_final_animation(recipe, studio, scene, root, ground, authored, out, approval_sha, studio_preset_path):
    animation = recipe["animation"]
    frame_start = int(animation.get("frameStart", 1))
    frame_end = int(animation.get("frameEnd", 12))
    fps = int(animation.get("fps", 8))
    source_root = out / "final_source"
    runtime_root = out / "runtime"
    source_root.mkdir(parents=True, exist_ok=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    for frame in range(frame_start, frame_end + 1):
        frame_dir = source_root / f"frame_{frame:03d}"
        frame_dir.mkdir(parents=True, exist_ok=True)
        directions_meta = []
        scene.frame_set(frame)
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            color_name = f"{recipe['assetId']}_{direction['id']}_color_source.png"
            shadow_name = f"{recipe['assetId']}_{direction['id']}_shadow_source.png"
            bs.render_color_pass(scene, authored, ground, str(frame_dir / color_name))
            origin_px = bs.ground_origin_source_px(scene)
            bs.render_shadow_pass(scene, authored, ground, str(frame_dir / shadow_name))
            directions_meta.append({
                "id": direction["id"],
                "quarterTurns": direction["quarterTurns"],
                "rotationDegrees": direction["rotationDegrees"],
                "colorSource": color_name,
                "shadowSource": shadow_name,
                "groundOriginSourcePx": origin_px,
            })
        metadata = _frame_metadata(recipe, studio, scene, frame, directions_meta)
        (frame_dir / "studio_metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )

    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    python_exe = shutil.which("python")
    if not python_exe:
        raise RuntimeError("CH_FERRIS_POSTPROCESS_PYTHON_NOT_FOUND: runner Python is required")
    post_script = HERE / "postprocess_ferris_animation.py"
    cmd = [
        python_exe,
        str(post_script),
        "--input", str(source_root),
        "--output", str(runtime_root),
        "--studio-preset", str(Path(studio_preset_path).resolve()),
        "--asset-id", recipe["assetId"],
        "--frame-start", str(frame_start),
        "--frame-end", str(frame_end),
        "--fps", str(fps),
        "--approved-proxy-sha", approval_sha,
    ]
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))

    final_record = {
        "contract": "CH_FERRIS_FINAL_BAKE_V1",
        "status": "ok",
        "assetId": recipe["assetId"],
        "approvedProxySha256": approval_sha,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
        "backgroundIncluded": False,
        "directions": [d["id"] for d in bs.DIRECTIONS],
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "frameCount": frame_end - frame_start + 1,
        "fps": fps,
        "runtimeDir": "runtime",
        "sourceDir": "final_source",
    }
    (out / "final_bake_report.json").write_text(json.dumps(final_record, indent=2), encoding="utf-8")


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
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] Ferris wheel proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")

    render_final_animation(
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
    _save_blend(args.save_blend)
    print("[CH_GATE] Ferris wheel final 4-direction animated runtime bake complete")


if __name__ == "__main__":
    main()
