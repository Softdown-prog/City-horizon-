"""Guarded CH Blender authoring pass for City Horizon visitor pedestrians.

This is the Visitor MVP gate. It intentionally starts small:

    preflight -> SOUTH idle + walk A/B proxy -> human review

The same parametric rig is intended for male/female visitor variants. Individual
walk frames are never redrawn independently; every frame is a deterministic pose
of the same 3D source.
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


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--asset-config", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    return p.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def empty(name, parent=None, location=(0.0, 0.0, 0.0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.rotation_mode = "XYZ"
    obj.location = tuple(location)
    if parent is not None:
        obj.parent = parent
    return obj


def box(authored, parent, name, location, dimensions, material, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(dimensions)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0.0:
        mod = obj.modifiers.new(name="VisitorBevel", type="BEVEL")
        mod.width = float(bevel)
        mod.segments = 2
    obj.parent = parent
    obj.location = tuple(location)
    authored.append(obj)
    return obj


def cylinder(authored, parent, name, location, radius, depth, material, vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=float(radius),
        depth=float(depth),
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    authored.append(obj)
    return obj


def sphere(authored, parent, name, location, scale, material, segments=18, rings=10):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=1.0,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    authored.append(obj)
    return obj


def make_materials(asset):
    result = {}
    for key, spec in asset["materials"].items():
        result[key] = bs.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.94)),
            float(spec.get("metallic", 0.0)),
        )
    return result


def build_visitor(asset):
    if asset.get("contract") != "CH_VISITOR_SOURCE_V1":
        raise RuntimeError("Expected CH_VISITOR_SOURCE_V1")

    mats = make_materials(asset)
    p = asset["proportions"]
    authored = []
    root = empty("AssetRoot")
    pose = empty("VisitorPoseRoot", root)

    pelvis = box(
        authored, pose, "Pelvis",
        (0.0, 0.0, float(p["pelvisCenterZ"])),
        p["pelvisDimensions"], mats["pants"], 0.045,
    )
    torso = box(
        authored, pose, "Torso",
        (0.0, 0.0, float(p["torsoCenterZ"])),
        p["torsoDimensions"], mats["shirt"], 0.070,
    )
    cylinder(
        authored, pose, "Neck", p["neckCenter"],
        p["neckRadius"], p["neckDepth"], mats["skin"], 12,
    )
    head = sphere(
        authored, pose, "Head", p["headCenter"], p["headScale"], mats["skin"], 20, 12,
    )
    sphere(
        authored, pose, "Hair", p["hairCenter"], p["hairScale"], mats["hair"], 18, 10,
    )
    if asset.get("features", {}).get("nose", True):
        sphere(
            authored, pose, "Nose", p["noseCenter"], p["noseScale"], mats["skin"], 10, 6,
        )

    rig = {"root": root, "pose": pose}

    upper_leg = float(p["upperLegLength"])
    lower_leg = float(p["lowerLegLength"])
    leg_radius = float(p["legRadius"])
    hip_z = float(p["hipZ"])
    hip_x = float(p["hipX"])
    shoe_y = float(p["shoeForwardY"])

    for side, x in (("L", -hip_x), ("R", hip_x)):
        hip = empty(f"Hip{side}", pose, (x, 0.0, hip_z))
        cylinder(
            authored, hip, f"UpperLeg{side}", (0.0, 0.0, -upper_leg * 0.5),
            leg_radius, upper_leg, mats["pants"], 12,
        )
        knee = empty(f"Knee{side}", hip, (0.0, 0.0, -upper_leg))
        cylinder(
            authored, knee, f"LowerLeg{side}", (0.0, 0.0, -lower_leg * 0.5),
            leg_radius * 0.88, lower_leg, mats["pants"], 12,
        )
        shoe = box(
            authored, knee, f"Shoe{side}",
            (0.0, shoe_y, -lower_leg - float(p.get("shoeDrop", 0.010))),
            p["shoeDimensions"], mats["shoe"], 0.030,
        )
        sole = box(
            authored, knee, f"Sole{side}",
            (0.0, shoe_y, -lower_leg - float(p.get("soleDrop", 0.066))),
            p["soleDimensions"], mats["sole"], 0.008,
        )
        rig[f"hip{side}"] = hip
        rig[f"knee{side}"] = knee
        rig[f"shoe{side}"] = shoe
        rig[f"sole{side}"] = sole

    shoulder_x = float(p["shoulderX"])
    shoulder_z = float(p["shoulderZ"])
    upper_arm = float(p["upperArmLength"])
    forearm = float(p["forearmLength"])
    arm_radius = float(p["armRadius"])

    for side, x in (("L", -shoulder_x), ("R", shoulder_x)):
        shoulder = empty(f"Shoulder{side}", pose, (x, 0.0, shoulder_z))
        cylinder(
            authored, shoulder, f"UpperArm{side}", (0.0, 0.0, -upper_arm * 0.5),
            arm_radius, upper_arm, mats["shirt"], 12,
        )
        elbow = empty(f"Elbow{side}", shoulder, (0.0, 0.0, -upper_arm))
        cylinder(
            authored, elbow, f"Forearm{side}", (0.0, 0.0, -forearm * 0.5),
            arm_radius * 0.80, forearm, mats["skin"], 12,
        )
        hand = sphere(
            authored, elbow, f"Hand{side}", (0.0, 0.0, -forearm - 0.026),
            p["handScale"], mats["skin"], 10, 6,
        )
        rig[f"shoulder{side}"] = shoulder
        rig[f"elbow{side}"] = elbow
        rig[f"hand{side}"] = hand

    rig["pelvis"] = pelvis
    rig["torso"] = torso
    rig["head"] = head
    return authored, rig


def idle_pose(rig):
    for key in ("hipL", "hipR", "kneeL", "kneeR", "shoulderL", "shoulderR", "elbowL", "elbowR"):
        rig[key].rotation_euler = (0.0, 0.0, 0.0)
    rig["pose"].location = (0.0, 0.0, 0.0)
    rig["pose"].rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def walk_pose(rig, walk, frame_index):
    if int(walk.get("frameCount", 2)) != 2:
        raise RuntimeError("CH_VISITOR_MVP_V1 currently requires exactly two walk frames")
    wave = 1.0 if int(frame_index) == 0 else -1.0
    stride = math.radians(float(walk["strideDegrees"]))
    arm = math.radians(float(walk["armSwingDegrees"]))
    knee = math.radians(float(walk["kneeBendDegrees"]))
    elbow = math.radians(float(walk.get("elbowDegrees", 5.0)))

    rig["hipL"].rotation_euler = (wave * stride, 0.0, 0.0)
    rig["hipR"].rotation_euler = (-wave * stride, 0.0, 0.0)
    rig["kneeL"].rotation_euler = ((knee if wave < 0.0 else 0.0), 0.0, 0.0)
    rig["kneeR"].rotation_euler = ((knee if wave > 0.0 else 0.0), 0.0, 0.0)
    rig["shoulderL"].rotation_euler = (-wave * arm, 0.0, 0.0)
    rig["shoulderR"].rotation_euler = (wave * arm, 0.0, 0.0)
    rig["elbowL"].rotation_euler = (elbow, 0.0, 0.0)
    rig["elbowR"].rotation_euler = (elbow, 0.0, 0.0)
    rig["pose"].location = (0.0, 0.0, float(walk.get("verticalBob", 0.0)))
    rig["pose"].rotation_euler = (0.0, 0.0, math.radians(float(walk.get("torsoSwayDegrees", 0.0))) * wave)
    bpy.context.view_layer.update()


def set_direction(rig, direction):
    rig["root"].rotation_euler[2] = math.radians(float(direction["rotationDegrees"]))
    bpy.context.view_layer.update()


def south_direction(asset):
    for direction in asset["directions"]:
        if direction["id"] == "south":
            return direction
    raise RuntimeError("CH_VISITOR_SOURCE_V1 requires a south direction")


def tag_semantics(rig):
    scene_gate.tag(rig["torso"], "character.torso")
    scene_gate.tag(rig["head"], "character.head")
    scene_gate.tag(rig["handL"], "character.hand_left")
    scene_gate.tag(rig["handR"], "character.hand_right")
    scene_gate.tag(rig["soleL"], "character.foot_left", ground_contact=True)
    scene_gate.tag(rig["soleR"], "character.foot_right", ground_contact=True)


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def build_for_gate(args):
    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)
    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError("Visitor/studio preset mismatch")

    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored, rig = build_visitor(asset)
    root = rig["root"]
    root["assetId"] = asset["assetId"]
    root["assetType"] = "visitor_npc"
    root["visitorContract"] = asset["contract"]
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["walkFrameCount"] = int(asset["walk"]["frameCount"])

    receiver = studio["shadowReceiver"]
    ground_mat = bs.make_material(
        "VisitorShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        ground_mat,
        0.0,
    )

    set_direction(rig, south_direction(asset))
    idle_pose(rig)
    tag_semantics(rig)
    return asset, studio, scene, ground, authored, rig, out


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    asset, studio, scene, ground, authored, rig, out = build_for_gate(args)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=asset["footprint"],
        profile=profile,
        asset_id=asset["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        print(f"[CH_GATE] Visitor preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        south = south_direction(asset)
        set_direction(rig, south)
        idle_pose(rig)
        idle = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=asset["assetId"],
            direction="south_idle",
        )

        walk_reports = []
        for frame_index, label in ((0, "walk_a"), (1, "walk_b")):
            walk_pose(rig, asset["walk"], frame_index)
            report = scene_gate.render_proxy(
                scene=scene,
                authored=authored,
                output_path=out / f"proxy_south_{label}.png",
                profile=profile,
                asset_id=asset["assetId"],
                direction=f"south_{label}",
            )
            walk_reports.append({"frame": frame_index, "label": label, "sha256": report["sha256"]})

        idle["visitorContract"] = "CH_VISITOR_PROXY_V1"
        idle["pose"] = "idle"
        idle["walkCompanions"] = walk_reports
        idle["walkPolicy"] = "two conservative opposite contact poses; no frame regeneration"
        (out / "proxy_report.json").write_text(json.dumps(idle, indent=2), encoding="utf-8")
        save_blend(args.save_blend)
        print(f"[CH_GATE] Visitor SOUTH proxy ready: {idle['sha256']}")
        return

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review SOUTH visitor proxy first")
    raise RuntimeError(
        "CH_VISITOR_FINAL_GATE_V1: final four-direction bake is intentionally disabled until the first SOUTH idle/walk proxy is visually approved"
    )


if __name__ == "__main__":
    main()
