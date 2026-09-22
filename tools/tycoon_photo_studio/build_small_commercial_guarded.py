"""Guarded CH Blender builder for CITY_HORIZON_SMALL_COMMERCIAL_V1 recipes.

Flow:
    recipe -> deterministic expander -> TYCOON_ASSET_SOURCE_V1
           -> CH Blender scene -> preflight -> SOUTH proxy -> human review
           -> final four directions (+ CH_COLOR_MASK_V1 when declared)

This builder is reusable for compact commercial buildings; the bakery is the
first production exemplar.
"""
from __future__ import annotations

import argparse
import hashlib
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
import ch_color_mask as color_mask  # noqa: E402
import generate_small_commercial_asset as commercial  # noqa: E402
import scene_gate  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def _repo_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    path.relative_to(REPO_ROOT)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _save_blend(value: str | None):
    if not value:
        return
    path = _repo_path(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def build_for_gate(args):
    recipe_path = _repo_path(args.recipe)
    studio_path = _repo_path(args.studio_preset)
    out = _repo_path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    asset = commercial.expand(recipe)
    studio = json.loads(studio_path.read_text(encoding="utf-8"))
    asset_id = asset["assetId"]
    footprint = asset["footprint"]

    # Keep the deterministic expanded source with the CI artifact so agents can
    # inspect exactly what the recipe produced without reverse-engineering Blender.
    (out / "expanded_source.json").write_text(
        json.dumps(asset, indent=2) + "\n", encoding="utf-8"
    )

    auto_src, auto_final = bs.compute_dynamic_resolution(asset, studio)
    bs.clear_scene()
    scene = bs.configure_scene(studio, auto_src, str(out))
    authored = bs.build_asset(asset, asset_config_path=str(recipe_path))
    root = bs.create_asset_root(authored)

    root["assetId"] = asset_id
    root["assetType"] = "building"
    root["sourceContract"] = recipe["contract"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = f"{footprint['widthTiles']}x{footprint['depthTiles']}"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["recipePath"] = recipe_path.relative_to(REPO_ROOT).as_posix()
    root["recipeSha256"] = _sha256(recipe_path)

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

    calibrated_scale = bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    mask_spec = color_mask.normalize_spec(asset)
    mask_assignment = (
        color_mask.assignment_summary(authored, mask_spec) if mask_spec else None
    )

    return {
        "recipe": recipe,
        "recipePath": recipe_path,
        "asset": asset,
        "assetId": asset_id,
        "footprint": footprint,
        "studio": studio,
        "scene": scene,
        "root": root,
        "ground": ground,
        "authored": authored,
        "out": out,
        "srcResolution": auto_src,
        "finalResolution": auto_final,
        "orthoScale": calibrated_scale,
        "maskSpec": mask_spec,
        "maskAssignment": mask_assignment,
    }


def render_final(ctx):
    asset_id = ctx["assetId"]
    scene = ctx["scene"]
    root = ctx["root"]
    ground = ctx["ground"]
    authored = ctx["authored"]
    out = ctx["out"]
    mask_spec = ctx["maskSpec"]

    directions_meta = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        direction_id = direction["id"]
        color_name = f"{asset_id}_{direction_id}_color_source.png"
        shadow_name = f"{asset_id}_{direction_id}_shadow_source.png"
        mask_name = f"{asset_id}_{direction_id}_mask_source.png" if mask_spec else None

        bs.render_color_pass(scene, authored, ground, str(out / color_name))
        origin_px = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))
        if mask_spec:
            color_mask.render_mask_pass(
                scene, authored, ground, str(out / mask_name), mask_spec
            )

        record = {
            "id": direction_id,
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin_px,
        }
        if mask_name:
            record["maskSource"] = mask_name
        directions_meta.append(record)

    recipe_path = ctx["recipePath"]
    metadata = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "sourceObject": asset_id,
        "assetType": "static_building",
        "sourceContract": ctx["recipe"]["contract"],
        "assetConfig": recipe_path.relative_to(REPO_ROOT).as_posix(),
        "recipeSha256": _sha256(recipe_path),
        "studioPreset": ctx["studio"]["id"],
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": ctx["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(ctx["srcResolution"]),
        "finalResolution": list(ctx["finalResolution"]),
        "orthoScaleCalibrated": ctx["orthoScale"],
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True
        },
        "colorMask": (
            color_mask.metadata(mask_spec, ctx["maskAssignment"])
            if mask_spec else {"enabled": False}
        ),
        "generation": ctx["asset"].get("generation", {}),
        "designIntent": ctx["asset"].get("designIntent", {}),
        "directions": directions_meta,
    }
    (out / "studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    ctx = build_for_gate(args)

    preflight_path = ctx["out"] / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=ctx["scene"],
        authored=ctx["authored"],
        footprint=ctx["footprint"],
        profile=profile,
        asset_id=ctx["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] {ctx['assetId']} preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(ctx["root"], bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=ctx["scene"],
            authored=ctx["authored"],
            output_path=ctx["out"] / "proxy_south.png",
            profile=profile,
            asset_id=ctx["assetId"],
            direction="south",
        )
        (ctx["out"] / "proxy_report.json").write_text(
            json.dumps(proxy, indent=2), encoding="utf-8"
        )
        _save_blend(args.save_blend)
        print(f"[CH_GATE] {ctx['assetId']} proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first and pass its SHA-256"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ctx["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }
    (ctx["out"] / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )
    render_final(ctx)
    _save_blend(args.save_blend)
    print(f"[CH_GATE] {ctx['assetId']} final four-direction source bake complete")


if __name__ == "__main__":
    main()
