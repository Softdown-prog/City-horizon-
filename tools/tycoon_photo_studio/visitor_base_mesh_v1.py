"""Canonical reusable City Horizon visitor base mesh.

This module turns the approved visual-target profile into one deterministic body.
Animation, direction rotation and export are intentionally handled elsewhere.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_visitor_guarded as v1
import build_visitor_guarded_v2 as v2


def _load_profile(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contract") != "CH_VISITOR_BASE_MESH_V1":
        raise RuntimeError("Expected CH_VISITOR_BASE_MESH_V1")
    return data


def _mul3(values, multipliers):
    return tuple(float(a) * float(b) for a, b in zip(values, multipliers))


def human_torso(authored, parent, name, location, dimensions, material, profile):
    width, depth, height = map(float, dimensions)
    spec = profile["shape"]["torso"]
    segments = int(spec.get("segments", 20))
    rings = spec["rings"]
    vertices = []
    for ring in rings:
        z = float(ring["z"]) * height
        rx = width * float(ring["width"]) * 0.5
        ry = depth * float(ring["depth"]) * 0.5
        for i in range(segments):
            angle = (2.0 * math.pi * i) / segments
            vertices.append((rx * math.cos(angle), ry * math.sin(angle), z))

    faces = []
    for r in range(len(rings) - 1):
        start = r * segments
        nxt = (r + 1) * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((start + i, start + j, nxt + j, nxt + i))
    faces.append(tuple(reversed(range(segments))))
    last = (len(rings) - 1) * segments
    faces.append(tuple(last + i for i in range(segments)))

    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True

    levels = int(spec.get("subdivision", 1))
    if levels > 0:
        modifier = obj.modifiers.new(name="VisitorBaseMeshSubdivision", type="SUBSURF")
        modifier.subdivision_type = "CATMULL_CLARK"
        modifier.levels = levels
        modifier.render_levels = levels
    authored.append(obj)
    return obj


def build_visitor(asset, base_mesh_profile_path):
    if asset.get("contract") != "CH_VISITOR_SOURCE_V1":
        raise RuntimeError("Expected CH_VISITOR_SOURCE_V1")
    profile = _load_profile(base_mesh_profile_path)
    mats = v1.make_materials(asset)
    p = asset["proportions"]
    shape = profile["shape"]
    authored = []
    root = v1.empty("AssetRoot")
    pose = v1.empty("VisitorPoseRoot", root)

    pelvis_dims = tuple(map(float, p["pelvisDimensions"]))
    pelvis = v2.ellipsoid(
        authored, pose, "Pelvis",
        (0.0, 0.0, float(p["pelvisCenterZ"])),
        _mul3(pelvis_dims, shape["pelvisScale"]), mats["pants"], 20, 12,
    )
    torso = human_torso(
        authored, pose, "Torso",
        (0.0, 0.0, float(p["torsoCenterZ"])),
        p["torsoDimensions"], mats["shirt"], profile,
    )

    neck_scale = (float(p["neckRadius"]) * 0.92, float(p["neckRadius"]) * 0.92, float(p["neckDepth"]) * 0.52)
    v2.ellipsoid(authored, pose, "Neck", p["neckCenter"], neck_scale, mats["skin"], 16, 10)
    head = v2.ellipsoid(
        authored, pose, "Head", p["headCenter"],
        _mul3(p["headScale"], shape["headScaleMultiplier"]), mats["skin"], 24, 16,
    )
    v2.ellipsoid(
        authored, pose, "Hair", p["hairCenter"],
        _mul3(p["hairScale"], shape["hairScaleMultiplier"]), mats["hair"], 22, 14,
    )
    if asset.get("features", {}).get("nose", True):
        nose = tuple(float(v) * 0.82 for v in p["noseScale"])
        v2.ellipsoid(authored, pose, "Nose", p["noseCenter"], nose, mats["skin"], 12, 8)

    rig = {"root": root, "pose": pose}
    upper_leg = float(p["upperLegLength"])
    lower_leg = float(p["lowerLegLength"])
    leg_radius = float(p["legRadius"])
    hip_z = float(p["hipZ"])
    hip_x = float(p["hipX"]) * 0.92
    shoe_y = float(p["shoeForwardY"])
    shoe_dims = _mul3(p["shoeDimensions"], shape["shoeScale"])
    sole_dims = (float(p["soleDimensions"][0]) * 0.88, float(p["soleDimensions"][1]) * 0.86, float(p["soleDimensions"][2]))

    for side, x in (("L", -hip_x), ("R", hip_x)):
        hip = v1.empty(f"Hip{side}", pose, (x, 0.0, hip_z))
        cap = shape["hipCapScale"]
        v2.ellipsoid(authored, hip, f"HipCap{side}", (0.0, 0.0, -0.018),
                     (leg_radius * cap[0], leg_radius * cap[1], leg_radius * cap[2]), mats["pants"], 16, 10)
        v2.tapered_limb(authored, hip, f"UpperLeg{side}", (0.0, 0.0, -upper_leg * 0.5),
                        upper_leg, leg_radius * float(shape["upperLegRadiusMultiplier"]), leg_radius * 0.80, mats["pants"])
        knee = v1.empty(f"Knee{side}", hip, (0.0, 0.0, -upper_leg))
        v2.ellipsoid(authored, knee, f"KneeCap{side}", (0.0, 0.0, 0.0),
                     (leg_radius * 0.75, leg_radius * 0.72, leg_radius * 0.72), mats["pants"], 14, 8)
        v2.tapered_limb(authored, knee, f"LowerLeg{side}", (0.0, 0.0, -lower_leg * 0.5),
                        lower_leg, leg_radius * 0.76, leg_radius * float(shape["lowerLegRadiusMultiplier"]), mats["pants"])
        shoe = v2.ellipsoid(authored, knee, f"Shoe{side}",
                            (0.0, shoe_y - 0.014, -lower_leg - float(p.get("shoeDrop", 0.010))),
                            (shoe_dims[0] * 0.50, shoe_dims[1] * 0.53, shoe_dims[2] * 0.60), mats["shoe"], 18, 10)
        sole = v1.box(authored, knee, f"Sole{side}",
                      (0.0, shoe_y, -lower_leg - float(p.get("soleDrop", 0.060))),
                      sole_dims, mats["sole"], 0.010)
        rig[f"hip{side}"] = hip
        rig[f"knee{side}"] = knee
        rig[f"shoe{side}"] = shoe
        rig[f"sole{side}"] = sole

    shoulder_x = float(p["shoulderX"]) * 0.91
    shoulder_z = float(p["shoulderZ"]) - 0.010
    upper_arm = float(p["upperArmLength"])
    forearm = float(p["forearmLength"])
    arm_radius = float(p["armRadius"])
    cap = shape["shoulderCapScale"]
    hand_scale = tuple(float(v) * float(shape["handScaleMultiplier"]) for v in p["handScale"])

    for side, x in (("L", -shoulder_x), ("R", shoulder_x)):
        shoulder = v1.empty(f"Shoulder{side}", pose, (x, 0.0, shoulder_z))
        v2.ellipsoid(authored, shoulder, f"ShoulderCap{side}", (0.0, 0.0, -0.028),
                     (arm_radius * cap[0], arm_radius * cap[1], arm_radius * cap[2]), mats["shirt"], 16, 10)
        v2.tapered_limb(authored, shoulder, f"UpperArm{side}", (0.0, 0.0, -upper_arm * 0.5),
                        upper_arm, arm_radius * float(shape["upperArmRadiusMultiplier"]), arm_radius * 0.76, mats["shirt"])
        elbow = v1.empty(f"Elbow{side}", shoulder, (0.0, 0.0, -upper_arm))
        v2.ellipsoid(authored, elbow, f"ElbowCap{side}", (0.0, 0.0, 0.0),
                     (arm_radius * 0.68, arm_radius * 0.65, arm_radius * 0.66), mats["skin"], 12, 8)
        v2.tapered_limb(authored, elbow, f"Forearm{side}", (0.0, 0.0, -forearm * 0.5),
                        forearm, arm_radius * 0.70, arm_radius * float(shape["forearmRadiusMultiplier"]), mats["skin"])
        hand = v2.ellipsoid(authored, elbow, f"Hand{side}", (0.0, 0.0, -forearm - 0.020),
                            hand_scale, mats["skin"], 12, 8)
        rig[f"shoulder{side}"] = shoulder
        rig[f"elbow{side}"] = elbow
        rig[f"hand{side}"] = hand

    rig["pelvis"] = pelvis
    rig["torso"] = torso
    rig["head"] = head
    root["baseMeshContract"] = profile["contract"]
    root["baseMeshId"] = profile["id"]
    return authored, rig
