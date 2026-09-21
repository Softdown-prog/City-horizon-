"""Fail-fast adapter for the raspadinha vendor Blender authoring scene.

This module reuses the existing geometry authoring code but adds the City Horizon
quality stages required for agent-driven work:
  preflight -> proxy SOUTH -> final four-direction bake.
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
import build_raspadinha_vendor_blender as rv  # noqa: E402
import scene_gate  # noqa: E402


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _parent_keep_world_fixed(obj, parent):
    """Preserve world transform when moving an authored part under an animation pivot."""
    world = obj.matrix_world.copy()
    bpy.context.view_layer.update()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world
    bpy.context.view_layer.update()


def _tag_semantics():
    mapping = {
        "Torso": ("character.torso", False),
        "Head": ("character.head", False),
        "Shoe_L": ("character.foot_left", True),
        "Shoe_R": ("character.foot_right", True),
        "Arm_L_Hand": ("character.hand_left", False),
        "Arm_R_Hand": ("character.hand_right", False),
        "CartBody": ("vendor.cart", False),
        "UmbrellaPole": ("vendor.umbrella_pole", False),
    }
    for name, (role, contact) in mapping.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError(f"CH_PREFLIGHT_AUTHORING_ERROR: missing authored object {name}")
        scene_gate.tag(obj, role, ground_contact=contact)


def build_for_gate(args):
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    src_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, src_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = rv.empty("AssetRoot")
    root["assetId"] = rv.ASSET_ID
    root["groundIncludedInAsset"] = False
    root["animationStates"] = "idle:1-4,greet:5-8,serve:9-12"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    # The original WIP helper could leave head children with the pivot offset
    # applied twice. Patch the helper in-memory so both gate builds and the later
    # final rebuild use a transform-preserving parent operation.
    rv.parent_keep_world = _parent_keep_world_fixed

    mats = rv.materials()
    rv.build_cart(root, mats)
    rig = rv.build_vendor(root, mats)
    rv.animate_vendor(rig)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    _tag_semantics()

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
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.12)
    bs.set_direction(root, bs.DIRECTIONS[0])
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return studio, scene, root, ground, authored, out


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _run_original_final(args):
    filtered = [
        sys.argv[0],
        "--",
        "--studio-preset", args.studio_preset,
        "--output", args.output,
    ]
    if args.save_blend:
        filtered.extend(["--save-blend", args.save_blend])
    old = sys.argv[:]
    try:
        sys.argv[:] = filtered
        rv.main()
    finally:
        sys.argv[:] = old


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out = build_for_gate(args)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint={"widthTiles": 1, "depthTiles": 1},
        profile=profile,
        asset_id=rv.ASSET_ID,
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        scene.frame_set(1)
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=rv.ASSET_ID,
            direction="south",
        )
        proxy_path = out / "proxy_report.json"
        proxy_path.write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError(
            "CH_FINAL_REQUIRES_APPROVED_PROXY: pass --approval-proxy-sha from the reviewed proxy report"
        )

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": rv.ASSET_ID,
        "proxySha256": approval,
        "reviewed": True,
    }
    (out / "proxy_approval.json").write_text(
        json.dumps(approval_record, indent=2), encoding="utf-8"
    )
    _run_original_final(args)
    print("[CH_GATE] final bake completed after explicit proxy approval")


if __name__ == "__main__":
    main()
