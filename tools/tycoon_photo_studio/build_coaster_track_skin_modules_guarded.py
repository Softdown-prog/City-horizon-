"""Guarded Blender authoring for City Horizon coaster track-skin modules.

The procedural centerline/track geometry remains authoritative. This builder
creates only optional visual overlay modules for CH_COASTER_TRACK_SKIN_V1:
  - joint plate
  - chain-lift cap
  - brake fin

Pipeline: preflight -> SOUTH proxy -> human review -> final module bake.
"""
from __future__ import annotations

import argparse
import json
import math
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

ASSET_ID = "coaster.track_skin.classic_steel_01.modules"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 1}
MODULE_IDS = ("joint_plate", "chain_lift", "brake_fin")


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


def _empty(name: str, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def _box(name, loc, dims, mat, *, parent, bevel=0.025):
    obj = bs.add_box(name, loc, dims, mat, bevel)
    obj.parent = parent
    return obj


def _cylinder(name, loc, radius, depth, mat, *, parent, vertices=24, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth,
                                       location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.parent = parent
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new(name="SoftEdges", type="BEVEL")
    bevel.width = min(0.018, radius * 0.16)
    bevel.segments = 2
    return obj


def _save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def _materials():
    return {
        "rail": bs.make_material("TrackModule_Steel", (0.34, 0.40, 0.43, 1.0), roughness=0.33, metallic=0.78),
        "rail_hi": bs.make_material("TrackModule_SteelHighlight", (0.62, 0.68, 0.70, 1.0), roughness=0.25, metallic=0.86),
        "dark": bs.make_material("TrackModule_DarkSteel", (0.075, 0.09, 0.10, 1.0), roughness=0.42, metallic=0.72),
        "red": bs.make_material("TrackModule_RedSpine", (0.58, 0.10, 0.075, 1.0), roughness=0.48, metallic=0.26),
        "chain": bs.make_material("TrackModule_Chain", (0.16, 0.18, 0.19, 1.0), roughness=0.30, metallic=0.88),
    }


def _module_base(parent, x, mats, name):
    # A short red spine + twin rail stubs give each detail correct visual context.
    _box(f"{name}_Spine", (x, 0.0, 0.28), (1.30, 0.24, 0.20), mats["red"], parent=parent, bevel=0.035)
    for side, y in (("L", -0.38), ("R", 0.38)):
        rail = _cylinder(f"{name}_Rail_{side}", (x, y, 0.52), 0.065, 1.30, mats["rail"],
                         parent=parent, vertices=20, rotation=(0.0, math.radians(90.0), 0.0))
        rail.scale.z = 1.0
    for dx in (-0.46, 0.0, 0.46):
        _box(f"{name}_Tie_{dx:+.2f}", (x + dx, 0.0, 0.38), (0.10, 0.94, 0.10), mats["dark"], parent=parent, bevel=0.015)


def build_modules(root, mats):
    modules = {}

    # JOINT PLATE — compact bolted bridge over the spine and between the rails.
    joint = _empty("Module_JointPlate", root)
    modules["joint_plate"] = joint
    x = -1.80
    _module_base(joint, x, mats, "Joint")
    plate = _box("JointPlate_Main", (x, 0.0, 0.58), (0.34, 0.72, 0.085), mats["rail_hi"], parent=joint, bevel=0.028)
    scene_gate.tag(plate, "coaster.skin.joint_plate")
    for sx in (-0.115, 0.115):
        for sy in (-0.245, 0.245):
            _cylinder(f"JointBolt_{sx}_{sy}", (x + sx, sy, 0.635), 0.030, 0.055, mats["dark"], parent=joint, vertices=14)

    # CHAIN LIFT — dark guide channel with readable repeating chain blocks.
    chain = _empty("Module_ChainLift", root)
    modules["chain_lift"] = chain
    x = 0.0
    _module_base(chain, x, mats, "Chain")
    guide = _box("ChainGuide", (x, 0.0, 0.59), (1.02, 0.18, 0.12), mats["dark"], parent=chain, bevel=0.020)
    scene_gate.tag(guide, "coaster.skin.chain_lift")
    for i, dx in enumerate((-0.40, -0.20, 0.0, 0.20, 0.40)):
        link = _box(f"ChainLink_{i}", (x + dx, 0.0, 0.675), (0.11, 0.26, 0.055), mats["chain"], parent=chain, bevel=0.018)
        link.rotation_euler[2] = math.radians(22.0 if i % 2 == 0 else -22.0)

    # BRAKE FIN — vertical blade on a red/steel mounting shoe.
    brake = _empty("Module_BrakeFin", root)
    modules["brake_fin"] = brake
    x = 1.80
    _module_base(brake, x, mats, "Brake")
    shoe = _box("BrakeMount", (x, 0.0, 0.55), (0.48, 0.26, 0.14), mats["dark"], parent=brake, bevel=0.025)
    fin = _box("BrakeFin", (x, 0.0, 0.82), (0.34, 0.055, 0.48), mats["rail_hi"], parent=brake, bevel=0.020)
    scene_gate.tag(fin, "coaster.skin.brake_fin")
    _box("BrakeFin_RedFoot", (x, 0.0, 0.57), (0.40, 0.34, 0.10), mats["red"], parent=brake, bevel=0.018)
    return modules


def build_for_gate(args):
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["assetType"] = "coaster_track_skin_module_kit"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = "CH_STYLIZED_PRERENDER_V1"
    root["runtimeRepresentation"] = "2D_RGBA_overlay_atlas"
    root["geometryAuthority"] = "CH_COASTER_TRACK_GEOMETRY_V1"
    root["skinContract"] = "CH_COASTER_TRACK_SKIN_V1"
    root["footprint"] = "2x1"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"

    modules = build_modules(root, _materials())

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.18)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return studio, scene, root, ground, authored, modules, out


def render_final(studio, scene, root, ground, authored, modules, out, approval):
    module_root = out / "runtime_modules"
    module_root.mkdir(parents=True, exist_ok=True)
    records = []
    for module_id in MODULE_IDS:
        for obj in authored:
            obj.hide_render = True
        module = modules[module_id]
        for obj in authored:
            parent = obj.parent
            while parent is not None and parent != module:
                parent = parent.parent
            if parent == module:
                obj.hide_render = False
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            bpy.context.view_layer.update()
            path = module_root / f"{module_id}_{direction['id']}.png"
            bs.render_color_pass(scene, authored, ground, str(path))
            records.append({"module": module_id, "direction": direction["id"], "path": path.name})

    for obj in authored:
        obj.hide_render = False
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    (out / "final_bake_report.json").write_text(json.dumps({
        "contract": "CH_COASTER_TRACK_SKIN_MODULE_BAKE_V1",
        "status": "ok",
        "assetId": ASSET_ID,
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "approvedProxySha256": approval,
        "modules": records,
    }, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, modules, out = build_for_gate(args)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(scene=scene, authored=authored, footprint=FOOTPRINT,
                                         profile=profile, asset_id=ASSET_ID,
                                         report_path=preflight_path)
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        _save_blend(args.save_blend)
        print(f"[CH_GATE] coaster track skin module preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(scene=scene, authored=authored,
                                        output_path=out / "proxy_south.png",
                                        profile=profile, asset_id=ASSET_ID,
                                        direction="south")
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        _save_blend(args.save_blend)
        print(f"[CH_GATE] coaster track skin proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first")
    render_final(studio, scene, root, ground, authored, modules, out, approval)
    _save_blend(args.save_blend)
    print("[CH_GATE] coaster track skin final module bake complete")


if __name__ == "__main__":
    main()
