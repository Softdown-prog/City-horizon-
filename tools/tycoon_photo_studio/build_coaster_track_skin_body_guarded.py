"""Guarded Blender authoring for the Classic Steel 01 full track-body skin.

This asset is the visual shell for one repeatable coaster track segment. The
procedural centerline/geometry remains authoritative for route, gauge, physics
and support placement. Runtime stamps this visual module over that geometry,
but this Blender asset never changes simulation state.
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

ASSET_ID = "coaster.track_skin.classic_steel_01.body"
FOOTPRINT = {"widthTiles": 1, "depthTiles": 1}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="proxy")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def _empty(name, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def _box(name, loc, dims, mat, parent, bevel=0.025):
    obj = bs.add_box(name, loc, dims, mat, bevel)
    obj.parent = parent
    return obj


def _cylinder(name, loc, radius, depth, mat, parent, vertices=24, rotation=(0.0, 0.0, 0.0)):
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


def materials():
    return {
        "rail": bs.make_material("ClassicSteel_Rail", (0.34, 0.40, 0.43, 1.0), roughness=0.30, metallic=0.82),
        "rail_hi": bs.make_material("ClassicSteel_RailHighlight", (0.62, 0.68, 0.70, 1.0), roughness=0.23, metallic=0.90),
        "dark": bs.make_material("ClassicSteel_Dark", (0.075, 0.09, 0.10, 1.0), roughness=0.44, metallic=0.70),
        "red": bs.make_material("ClassicSteel_RedSpine", (0.58, 0.10, 0.075, 1.0), roughness=0.46, metallic=0.25),
        "red_side": bs.make_material("ClassicSteel_RedSide", (0.28, 0.045, 0.035, 1.0), roughness=0.54, metallic=0.18),
    }


def build_body(root, mats):
    # One tile / 3 metre repeatable body. Gauge matches CH_COASTER_TRACK_GEOMETRY_V1.
    length = 3.0
    gauge_half = 0.42

    spine = _box("TrackBody_Spine", (0.0, 0.0, 0.28), (length, 0.26, 0.22), mats["red"], root, 0.040)
    scene_gate.tag(spine, "coaster.skin.track_body")
    _box("TrackBody_SpineSideL", (0.0, -0.155, 0.27), (length, 0.055, 0.18), mats["red_side"], root, 0.018)
    _box("TrackBody_SpineSideR", (0.0, 0.155, 0.27), (length, 0.055, 0.18), mats["red_side"], root, 0.018)

    for i, x in enumerate((-1.20, -0.60, 0.0, 0.60, 1.20)):
        _box(f"TrackBody_Tie_{i}", (x, 0.0, 0.42), (0.13, 1.10, 0.12), mats["dark"], root, 0.018)

    for side, y in (("L", -gauge_half), ("R", gauge_half)):
        _cylinder(f"TrackBody_Rail_{side}", (0.0, y, 0.57), 0.070, length, mats["rail"], root,
                  vertices=24, rotation=(0.0, 1.57079632679, 0.0))
        _cylinder(f"TrackBody_RailHi_{side}", (0.0, y - 0.018, 0.607), 0.025, length, mats["rail_hi"], root,
                  vertices=18, rotation=(0.0, 1.57079632679, 0.0))

    for x in (-1.20, -0.60, 0.0, 0.60, 1.20):
        for y in (-gauge_half, gauge_half):
            _box(f"TrackBody_Chair_{x:+.2f}_{y:+.2f}", (x, y, 0.505), (0.16, 0.18, 0.10), mats["dark"], root, 0.014)


def build_scene(args):
    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bs.clear_scene()
    scene = bs.configure_scene(studio, tuple(map(int, studio["render"]["sourceResolution"])), str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    root = _empty("AssetRoot")
    root["assetId"] = ASSET_ID
    root["assetType"] = "coaster_track_skin_body"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["skinContract"] = "CH_COASTER_TRACK_SKIN_V1"
    root["geometryAuthority"] = "CH_COASTER_TRACK_GEOMETRY_V1"
    root["runtimeRepresentation"] = "2D_RGBA_track_body_skin"
    root["footprint"] = "1x1"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"

    build_body(root, materials())
    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"], float(receiver.get("roughness", 1.0)))
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver["dimensions"], receiver_mat, 0.0)
    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.20)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return studio, scene, root, ground, authored, out


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def render_final_directions(scene, root, authored, profile, out, approval):
    runtime = out / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    directions = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        direction_id = direction["id"]
        path = runtime / f"track_body_{direction_id}.png"
        record = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=path,
            profile=profile,
            asset_id=ASSET_ID,
            direction=direction_id,
        )
        directions.append({
            "id": direction_id,
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "path": f"runtime/{path.name}",
            "sha256": record["sha256"],
            "bytes": record["bytes"],
        })

    approval_record = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_track_body_skin",
    }
    (out / "proxy_approval.json").write_text(json.dumps(approval_record, indent=2), encoding="utf-8")
    final_record = {
        "contract": "CH_COASTER_TRACK_BODY_BAKE_V1",
        "status": "ok",
        "assetId": ASSET_ID,
        "approvedProxySha256": approval,
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "geometryAuthority": "CH_COASTER_TRACK_GEOMETRY_V1",
        "runtimeRepresentation": "2D_RGBA_track_body_skin",
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
        "directions": directions,
    }
    (out / "final_bake_report.json").write_text(json.dumps(final_record, indent=2), encoding="utf-8")
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    studio, scene, root, ground, authored, out = build_scene(args)
    preflight_path = out / "preflight_report.json"
    report = scene_gate.run_preflight(scene=scene, authored=authored, footprint=FOOTPRINT,
                                      profile=profile, asset_id=ASSET_ID, report_path=preflight_path)
    scene_gate.require_pass(report)
    if args.stage == "preflight":
        save_blend(args.save_blend)
        return
    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(scene=scene, authored=authored,
                                        output_path=out / "proxy_south.png",
                                        profile=profile, asset_id=ASSET_ID,
                                        direction="south")
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        save_blend(args.save_blend)
        print(f"[CH_GATE] Classic Steel track-body proxy SOUTH ready: {proxy['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY")
    render_final_directions(scene, root, authored, profile, out, approval)
    studio_metadata = {
        "contract": "CH_COASTER_TRACK_BODY_STUDIO_METADATA_V1",
        "assetId": ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "geometryAuthority": "CH_COASTER_TRACK_GEOMETRY_V1",
        "runtimeRepresentation": "2D_RGBA_track_body_skin",
        "studioFingerprint": report.get("studioFingerprint"),
        "directionOrder": [d["id"] for d in bs.DIRECTIONS],
    }
    (out / "studio_metadata.json").write_text(json.dumps(studio_metadata, indent=2), encoding="utf-8")
    save_blend(args.save_blend)
    print("[CH_GATE] Classic Steel track-body final 4-direction runtime bake complete")


if __name__ == "__main__":
    main()
