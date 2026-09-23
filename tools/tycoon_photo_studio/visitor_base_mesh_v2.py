"""Continuous stylized City Horizon visitor base mesh V2.

V2 keeps the deterministic visitor rig but replaces cone-like limbs and prominent
joint balls with smooth multi-ring segments. The goal is a compact old-tycoon
human silhouette that reads as one body after sprite downsampling.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_visitor_guarded as rig_v1
import build_visitor_guarded_v2 as primitives
import visitor_base_mesh_v1 as base_v1


def _load_profile(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contract") != "CH_VISITOR_BASE_MESH_V2":
        raise RuntimeError("Expected CH_VISITOR_BASE_MESH_V2")
    return data


def _mul3(values, multipliers):
    return tuple(float(a) * float(b) for a, b in zip(values, multipliers))


def organic_limb(authored, parent, name, location, length, base_radius, profile, material, segments=18):
    """Build an articulated limb segment with a soft radius profile.

    Each segment remains independently parented for the existing rig, but its
    silhouette no longer reads as a straight cone/cylinder.
    """
    radii = [float(base_radius) * float(v) for v in profile]
    rings = len(radii)
    vertices = []
    for ring_index, radius in enumerate(radii):
        t = ring_index / max(1, rings - 1)
        z = -float(length) * t
        # Slightly oval cross-section reads more naturally at isometric scale.
        rx = radius
        ry = radius * 0.88
        for i in range(segments):
            angle = (2.0 * math.pi * i) / segments
            vertices.append((rx * math.cos(angle), ry * math.sin(angle), z))

    faces = []
    for r in range(rings - 1):
        a = r * segments
        b = (r + 1) * segments
        for i in range(segments):
            j = (i + 1) % segments
            faces.append((a + i, a + j, b + j, b + i))
    faces.append(tuple(reversed(range(segments))))
    last = (rings - 1) * segments
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
    authored.append(obj)
    return obj


def build_visitor(asset, base_mesh_profile_path):
    if asset.get("contract") != "CH_VISITOR_SOURCE_V1":
        raise RuntimeError("Expected CH_VISITOR_SOURCE_V1")

    profile = _load_profile(base_mesh_profile_path)
    mats = rig_v1.make_materials(asset)
    p = asset["proportions"]
    shape = profile["shape"]
    authored = []
    root = rig_v1.empty("AssetRoot")
    pose = rig_v1.empty("VisitorPoseRoot", root)

    pelvis_dims = tuple(map(float, p["pelvisDimensions"]))
    pelvis = primitives.ellipsoid(
        authored, pose, "Pelvis", (0.0, 0.0, float(p["pelvisCenterZ"])),
        _mul3(pelvis_dims, shape["pelvisScale"]), mats["pants"], 22, 14,
    )
    torso = base_v1.human_torso(
        authored, pose, "Torso", (0.0, 0.0, float(p["torsoCenterZ"])),
        p["torsoDimensions"], mats["shirt"], profile,
    )

    neck_scale = (
        float(p["neckRadius"]) * 0.82,
        float(p["neckRadius"]) * 0.82,
        float(p["neckDepth"]) * 0.46,
    )
    primitives.ellipsoid(authored, pose, "Neck", p["neckCenter"], neck_scale, mats["skin"], 16, 10)
    head = primitives.ellipsoid(
        authored, pose, "Head", p["headCenter"],
        _mul3(p["headScale"], shape["headScaleMultiplier"]), mats["skin"], 26, 18,
    )
    primitives.ellipsoid(
        authored, pose, "Hair", p["hairCenter"],
        _mul3(p["hairScale"], shape["hairScaleMultiplier"]), mats["hair"], 24, 16,
    )
    if asset.get("features", {}).get("nose", True):
        nose = tuple(float(v) * 0.70 for v in p["noseScale"])
        primitives.ellipsoid(authored, pose, "Nose", p["noseCenter"], nose, mats["skin"], 12, 8)

    rig = {"root": root, "pose": pose}

    upper_leg = float(p["upperLegLength"])
    lower_leg = float(p["lowerLegLength"])
    leg_radius = float(p["legRadius"])
    hip_z = float(p["hipZ"])
    hip_x = float(p["hipX"]) * float(shape["hipXMultiplier"])
    shoe_y = float(p["shoeForwardY"])
    shoe_dims = _mul3(p["shoeDimensions"], shape["shoeScale"])
    sole_dims = _mul3(p["soleDimensions"], shape["soleScale"])

    for side, x in (("L", -hip_x), ("R", hip_x)):
        hip = rig_v1.empty(f"Hip{side}", pose, (x, 0.0, hip_z))
        cap = shape["hipCapScale"]
        primitives.ellipsoid(
            authored, hip, f"HipCap{side}", (0.0, 0.0, -0.015),
            (leg_radius * cap[0], leg_radius * cap[1], leg_radius * cap[2]), mats["pants"], 16, 10,
        )
        organic_limb(authored, hip, f"UpperLeg{side}", (0.0, 0.0, 0.0), upper_leg,
                     leg_radius, shape["upperLegProfile"], mats["pants"], 18)
        knee = rig_v1.empty(f"Knee{side}", hip, (0.0, 0.0, -upper_leg))
        # Very small knee bridge: enough to avoid gaps, not enough to read as a ball.
        primitives.ellipsoid(
            authored, knee, f"KneeBridge{side}", (0.0, 0.0, 0.0),
            (leg_radius * 0.56, leg_radius * 0.52, leg_radius * 0.54), mats["pants"], 14, 8,
        )
        organic_limb(authored, knee, f"LowerLeg{side}", (0.0, 0.0, 0.0), lower_leg,
                     leg_radius, shape["lowerLegProfile"], mats["pants"], 18)
        shoe = primitives.ellipsoid(
            authored, knee, f"Shoe{side}",
            (0.0, shoe_y - 0.012, -lower_leg - float(p.get("shoeDrop", 0.010))),
            (shoe_dims[0] * 0.50, shoe_dims[1] * 0.53, shoe_dims[2] * 0.58), mats["shoe"], 18, 10,
        )
        sole = rig_v1.box(
            authored, knee, f"Sole{side}",
            (0.0, shoe_y, -lower_leg - float(p.get("soleDrop", 0.060))),
            sole_dims, mats["sole"], 0.008,
        )
        rig[f"hip{side}"] = hip
        rig[f"knee{side}"] = knee
        rig[f"shoe{side}"] = shoe
        rig[f"sole{side}"] = sole

    shoulder_x = float(p["shoulderX"]) * float(shape["shoulderXMultiplier"])
    shoulder_z = float(p["shoulderZ"]) + float(shape["shoulderZOffset"])
    upper_arm = float(p["upperArmLength"])
    forearm = float(p["forearmLength"])
    arm_radius = float(p["armRadius"])
    hand_scale = tuple(float(v) * float(shape["handScaleMultiplier"]) for v in p["handScale"])

    for side, x in (("L", -shoulder_x), ("R", shoulder_x)):
        shoulder = rig_v1.empty(f"Shoulder{side}", pose, (x, 0.0, shoulder_z))
        cap = shape["shoulderCapScale"]
        primitives.ellipsoid(
            authored, shoulder, f"ShoulderBlend{side}", (0.0, 0.0, -0.018),
            (arm_radius * cap[0], arm_radius * cap[1], arm_radius * cap[2]), mats["shirt"], 16, 10,
        )
        organic_limb(authored, shoulder, f"UpperArm{side}", (0.0, 0.0, 0.0), upper_arm,
                     arm_radius, shape["upperArmProfile"], mats["shirt"], 18)
        elbow = rig_v1.empty(f"Elbow{side}", shoulder, (0.0, 0.0, -upper_arm))
        primitives.ellipsoid(
            authored, elbow, f"ElbowBridge{side}", (0.0, 0.0, 0.0),
            (arm_radius * 0.48, arm_radius * 0.46, arm_radius * 0.50), mats["skin"], 12, 8,
        )
        organic_limb(authored, elbow, f"Forearm{side}", (0.0, 0.0, 0.0), forearm,
                     arm_radius, shape["forearmProfile"], mats["skin"], 16)
        hand = primitives.ellipsoid(
            authored, elbow, f"Hand{side}", (0.0, 0.0, -forearm - 0.016),
            hand_scale, mats["skin"], 12, 8,
        )
        rig[f"shoulder{side}"] = shoulder
        rig[f"elbow{side}"] = elbow
        rig[f"hand{side}"] = hand

    rig["pelvis"] = pelvis
    rig["torso"] = torso
    rig["head"] = head
    root["baseMeshContract"] = profile["contract"]
    root["baseMeshId"] = profile["id"]
    return authored, rig
