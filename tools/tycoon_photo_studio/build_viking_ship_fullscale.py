#!/usr/bin/env python3
"""Clean-room full-scale Viking/pirate ship authoring for City Horizon.

This builder intentionally imports no previous Viking builder, geometry module or rebuild
recipe.  It uses only generic CH Blender helpers plus geometry authored in this file.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

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

CONTRACT = "CH_VIKING_SHIP_FULLSCALE_V1"
ASSET_ID = "attraction.park_viking_ship.01"


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


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def beam_between(name, start, end, width, depth, material, parent=None, bevel=0.025):
    a, b = Vector(start), Vector(end)
    direction = b - a
    length = direction.length
    if length <= 1e-6:
        raise RuntimeError(f"zero length beam: {name}")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(a + b) * 0.5)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (float(width), float(depth), float(length))
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new(name="EdgeBreak", type="BEVEL")
        mod.width = float(bevel)
        mod.segments = 1
    if parent is not None:
        obj.parent = parent
    return obj


def build_platform(root, g, mats):
    top = float(g["platformTopZ"])
    slab_h = float(g["platformSlabHeight"])
    width = float(g["platformWidth"])
    depth = float(g["platformDepth"])
    under_h = float(g["underframeHeight"])

    slab = fw.box("FullscalePlatformDeck", (0.0, 0.0, top - slab_h * 0.5),
                  (width, depth, slab_h), mats["platformWhite"], 0.025, root)

    ground_contacts = []
    for x in (-width * 0.44, -width * 0.15, width * 0.15, width * 0.44):
        for y in (-depth * 0.43, depth * 0.43):
            col = fw.box(f"PlatformColumn_{x:+.2f}_{y:+.2f}",
                         (x, y, under_h * 0.5), (0.46, 0.46, under_h),
                         mats["steelDark"], 0.018, root)
            ground_contacts.append(col)
            fw.box(f"PlatformFoot_{x:+.2f}_{y:+.2f}",
                   (x, y, 0.10), (0.82, 0.82, 0.20), mats["steelMid"], 0.012, root)

    z_brace = under_h * 0.55
    for y in (-depth * 0.43, depth * 0.43):
        beam_between(f"PlatformLongRail_{y:+.2f}", (-width * 0.46, y, z_brace),
                     (width * 0.46, y, z_brace), 0.24, 0.24, mats["steelDark"], root, 0.012)
    for x in (-width * 0.44, width * 0.44):
        beam_between(f"PlatformDepthRail_{x:+.2f}", (x, -depth * 0.43, z_brace),
                     (x, depth * 0.43, z_brace), 0.24, 0.24, mats["steelDark"], root, 0.012)

    stair_steps = int(g["stairSteps"])
    stair_w = float(g["stairWidth"])
    stair_run = float(g["stairRun"])
    step_h = top / stair_steps
    step_d = stair_run / stair_steps
    stair_y0 = -depth * 0.5 - stair_run * 0.5
    for i in range(stair_steps):
        h = step_h * (i + 1)
        y = stair_y0 + step_d * (i + 0.5)
        fw.box(f"EntryStep_{i:02d}", (0.0, y, h * 0.5),
               (stair_w, step_d * 0.94, h), mats["platformWhite"], 0.012, root)

    rail_h = float(g["railingHeight"])
    post_r = 0.055
    rail_z0 = top + 0.05
    rail_z1 = top + rail_h
    perimeter = [
        (-width * 0.5, -depth * 0.5), (width * 0.5, -depth * 0.5),
        (width * 0.5, depth * 0.5), (-width * 0.5, depth * 0.5),
    ]
    for idx, (x, y) in enumerate(perimeter):
        fw.cylinder_between(f"RailPostCorner_{idx}", (x, y, rail_z0), (x, y, rail_z1),
                            post_r, mats["steelDark"], root, vertices=10)
    segments = 8
    for side_y in (-depth * 0.5, depth * 0.5):
        for i in range(segments + 1):
            x = -width * 0.5 + width * i / segments
            if side_y < 0 and abs(x) < stair_w * 0.62:
                continue
            fw.cylinder_between(f"RailPostY_{side_y:+.1f}_{i}", (x, side_y, rail_z0),
                                (x, side_y, rail_z1), post_r, mats["steelDark"], root, vertices=10)
        for z in (top + rail_h * 0.52, top + rail_h):
            fw.cylinder_between(f"RailY_{side_y:+.1f}_{z:.2f}",
                                (-width * 0.5, side_y, z), (width * 0.5, side_y, z),
                                0.045, mats["steelDark"], root, vertices=10)
    for side_x in (-width * 0.5, width * 0.5):
        for i in range(7):
            y = -depth * 0.5 + depth * i / 6
            fw.cylinder_between(f"RailPostX_{side_x:+.1f}_{i}", (side_x, y, rail_z0),
                                (side_x, y, rail_z1), post_r, mats["steelDark"], root, vertices=10)
        for z in (top + rail_h * 0.52, top + rail_h):
            fw.cylinder_between(f"RailX_{side_x:+.1f}_{z:.2f}",
                                (side_x, -depth * 0.5, z), (side_x, depth * 0.5, z),
                                0.045, mats["steelDark"], root, vertices=10)

    return slab, ground_contacts


def build_frame(root, g, mats):
    pivot_z = float(g["pivotZ"])
    foot_x = float(g["supportFootHalfX"])
    half_y = float(g["supportPlaneHalfY"])
    top_x = float(g["supportTopHalfX"])
    bw = float(g["supportBeamWidth"])
    bd = float(g["supportBeamDepth"])

    footings = []
    supports = []
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            x = x_sign * foot_x
            foot = fw.box(f"FrameFoot_{side}_{label}", (x, y, 0.16),
                          (1.45, 1.20, 0.32), mats["steelMid"], 0.022, root)
            footings.append(foot)
            start = (x, y, 0.72)
            end = (x_sign * top_x, y, pivot_z)
            supports.append(beam_between(f"MainLeg_{side}_{label}", start, end, bw, bd,
                                         mats["steelBlue"], root, 0.035))
            inner_start = (x * 0.82, y, 1.05)
            inner_end = (x_sign * (top_x * 1.55), y, pivot_z - 1.15)
            beam_between(f"GoldLeg_{side}_{label}", inner_start, inner_end, 0.46, 0.34,
                         mats["yellow"], root, 0.020)

        brace_z = pivot_z * 0.52
        beam_between(f"FrameCross_{side}", (-foot_x * 0.62, y, brace_z),
                     (foot_x * 0.62, y, brace_z), 0.34, 0.30, mats["steelDark"], root, 0.015)
        beam_between(f"FrameBraceA_{side}", (-foot_x * 0.62, y, brace_z),
                     (top_x * 0.5, y, pivot_z - 1.4), 0.24, 0.22, mats["steelDark"], root, 0.012)
        beam_between(f"FrameBraceB_{side}", (foot_x * 0.62, y, brace_z),
                     (-top_x * 0.5, y, pivot_z - 1.4), 0.24, 0.22, mats["steelDark"], root, 0.012)

    axle = fw.cylinder("MainAxle", (0.0, 0.0, pivot_z), float(g["axleRadius"]),
                       half_y * 2.18, mats["steelDark"],
                       rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=24)
    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * (half_y + 0.10)
        fw.cylinder(f"Bearing_{side}", (0.0, y, pivot_z), float(g["bearingRadius"]),
                    float(g["bearingDepth"]), mats["gold"],
                    rotation=(math.radians(90.0), 0.0, 0.0), parent=root, vertices=24)
    return footings, supports, axle


def build_hull(parent, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    body_depth = float(g["shipBodyDepth"])
    sections = [
        (-half_len, half_w * 0.20, 0.55, -0.25, -body_depth * 0.58),
        (-half_len * 0.88, half_w * 0.62, 0.15, -0.62, -body_depth * 0.82),
        (-half_len * 0.60, half_w * 0.92, -0.05, -0.82, -body_depth * 0.96),
        (-half_len * 0.28, half_w, -0.12, -0.90, -body_depth),
        (0.0, half_w * 1.02, -0.15, -0.92, -body_depth * 1.02),
        (half_len * 0.28, half_w, -0.12, -0.90, -body_depth),
        (half_len * 0.60, half_w * 0.92, -0.05, -0.82, -body_depth * 0.96),
        (half_len * 0.88, half_w * 0.62, 0.15, -0.62, -body_depth * 0.82),
        (half_len, half_w * 0.20, 0.55, -0.25, -body_depth * 0.58),
    ]
    verts = []
    for x, w, top, mid, keel in sections:
        verts.extend([(x, -w, top), (x, -w * 0.92, mid), (x, -w * 0.35, keel),
                      (x, w * 0.35, keel), (x, w * 0.92, mid), (x, w, top)])
    ring = 6
    faces = []
    for s in range(len(sections) - 1):
        a, b = s * ring, (s + 1) * ring
        for r in range(ring):
            n = (r + 1) % ring
            faces.append((a + r, a + n, b + n, b + r))
    faces.append(tuple(range(ring - 1, -1, -1)))
    last = (len(sections) - 1) * ring
    faces.append(tuple(last + i for i in range(ring)))
    mesh = bpy.data.meshes.new("FullscaleVikingHullMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("VikingHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = parent
    bevel = hull.modifiers.new(name="HullEdgeBreak", type="BEVEL")
    bevel.width = 0.055
    bevel.segments = 1

    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        for i in range(len(sections) - 1):
            x0, w0, z0, _, _ = sections[i]
            x1, w1, z1, _, _ = sections[i + 1]
            fw.cylinder_between(f"Gunwale_{label}_{i:02d}", (x0, side * w0, z0 + 0.12),
                                (x1, side * w1, z1 + 0.12), 0.11, mats["gold"], parent, vertices=12)
        fw.box(f"HullAccent_{label}", (0.0, side * (half_w + 0.045), -1.00),
               (float(g["shipLength"]) * 0.76, 0.055, 0.13), mats["red"], 0.008, parent)

    for sign, label in ((-1.0, "L"), (1.0, "R")):
        a = (sign * half_len * 0.92, 0.0, 0.40)
        b = (sign * half_len * 1.03, 0.0, 1.55)
        c = (sign * half_len * 1.08, 0.0, 2.55)
        beam_between(f"ProwLower_{label}", a, b, 0.34, 0.42, mats["woodLight"], parent, 0.020)
        beam_between(f"ProwUpper_{label}", b, c, 0.28, 0.36, mats["gold"], parent, 0.020)
        fw.box(f"ProwCap_{label}", (c[0], c[1], c[2] + 0.12),
               (0.62, 0.54, 0.46), mats["gold"], 0.035, parent)
    return hull


def build_ship(root, g, mats):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["runtimeLayer"] = "motion_overlay"
    boat = fw.empty("BoatRoot", (0.0, 0.0, -float(g["boatDrop"])), pivot)
    boat["runtimeLayer"] = "motion_overlay"

    top_x = float(g["suspensionTopHalfX"])
    attach_x = float(g["suspensionAttachHalfX"])
    half_y = float(g["suspensionHalfY"])
    w, d = float(g["suspensionWidth"]), float(g["suspensionDepth"])
    attach_z = -float(g["boatDrop"]) + 0.25
    for x_sign, label in ((-1.0, "L"), (1.0, "R")):
        for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
            beam_between(f"Suspension_{side}_{label}",
                         (x_sign * top_x, y_sign * half_y, -0.15),
                         (x_sign * attach_x, y_sign * half_y, attach_z),
                         w, d, mats["yellow"], pivot, 0.022)

    hull = build_hull(boat, g, mats)
    rows = int(g["seatRows"])
    span = float(g["seatSpan"])
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * (i / max(1, rows - 1))
        fw.box(f"SeatBase_{i:02d}", (x, 0.0, 0.15),
               (0.72, half_w * 1.55, 0.20), mats["seatRed"], 0.035, boat)
        fw.box(f"SeatBack_{i:02d}", (x + 0.24, 0.0, 0.55),
               (0.16, half_w * 1.50, 0.64), mats["steelDark"], 0.028, boat)
        fw.cylinder_between(f"SafetyBar_{i:02d}",
                            (x - 0.12, -half_w * 0.68, 0.68),
                            (x - 0.12, half_w * 0.68, 0.68),
                            0.045, mats["steelLight"], boat, vertices=10)

    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot, hull


def is_descendant(obj, ancestor):
    current = obj.parent
    while current is not None:
        if current == ancestor:
            return True
        current = current.parent
    return False


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    if recipe.get("assetId") != ASSET_ID:
        raise RuntimeError(f"Expected assetId {ASSET_ID}")
    policy = recipe.get("authoringPolicy", {})
    if policy.get("legacyVikingImportsAllowed") is not False or policy.get("legacyRecipeInheritanceAllowed") is not False:
        raise RuntimeError("CH_VIKING_CLEAN_ROOM_POLICY_FAIL")

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
    root["assetType"] = recipe["assetType"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["styleContract"] = recipe.get("styleContract")
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = "7x6"
    root["proceduralContract"] = CONTRACT
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["legacyVikingImportsUsed"] = False

    platform, platform_contacts = build_platform(root, recipe["geometry"], mats)
    footings, supports, axle = build_frame(root, recipe["geometry"], mats)
    pivot, hull = build_ship(root, recipe["geometry"], mats)

    for obj in platform_contacts + footings:
        scene_gate.tag(obj, "attraction.ground_contact", ground_contact=True)
    scene_gate.tag(platform, "attraction.loading_platform", ground_contact=False)
    scene_gate.tag(hull, "attraction.gondola", ground_contact=False)
    scene_gate.tag(axle, "attraction.pivot_axle", ground_contact=False)
    for obj in supports:
        scene_gate.tag(obj, "attraction.support", ground_contact=False)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material("ShadowReceiver", receiver["materialColor"],
                                    float(receiver.get("roughness", 1.0)))
    receiver_dims = [max(float(receiver["dimensions"][0]), 21.0),
                     max(float(receiver["dimensions"][1]), 18.0),
                     float(receiver["dimensions"][2])]
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver_dims, receiver_mat, 0.0)

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    for obj in authored:
        obj["runtimeLayer"] = "motion_overlay" if is_descendant(obj, pivot) else "static_base"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.13)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    metadata = {
        "contract": CONTRACT,
        "assetId": ASSET_ID,
        "stage": "clean_room_fullscale_geometry_gate",
        "cameraContract": "CH_CAMERA_V1",
        "footprint": recipe["footprint"],
        "recipe": "tools/tycoon_photo_studio/assets/park_viking_ship_fullscale_7x6.viking.json",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_fullscale.py",
        "legacyVikingImportsUsed": False,
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
    }
    (out / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    profile = scene_gate.load_profile(args.preflight_profile)
    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(scene=scene, authored=authored,
                                         footprint=recipe["footprint"], profile=profile,
                                         asset_id=ASSET_ID, report_path=preflight_path)
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        return
    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(scene=scene, authored=authored,
                                        output_path=out / "proxy_south.png",
                                        profile=profile, asset_id=ASSET_ID, direction="south")
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        save_blend(args.save_blend)
        return
    raise RuntimeError("CH_VIKING_FINAL_NOT_DEFINED: approve clean-room proxy first")


if __name__ == "__main__":
    main()
