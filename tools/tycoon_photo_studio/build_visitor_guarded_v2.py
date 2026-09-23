"""Organic-silhouette refinement for the guarded City Horizon visitor MVP.

V2 deliberately keeps the V1 quality gate, animation policy and runtime intent,
but replaces boxy body primitives with a tapered torso, rounded pelvis, tapered
limbs, shoulder caps and rounded shoes. The goal is old-tycoon readability without
a block-character silhouette.
"""
from __future__ import annotations

import bpy

import build_visitor_guarded as v1


def _smooth(obj):
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    return obj


def _bevel(obj, width, segments=2):
    if width > 0.0:
        modifier = obj.modifiers.new(name="VisitorOrganicBevel", type="BEVEL")
        modifier.width = float(width)
        modifier.segments = int(segments)
    return obj


def tapered_prism(authored, parent, name, location, dimensions, material,
                   top_width_scale=1.0, bottom_width_scale=0.78,
                   top_depth_scale=0.96, bottom_depth_scale=0.82,
                   bevel=0.045):
    width, depth, height = map(float, dimensions)
    z0 = -height * 0.5
    z1 = height * 0.5
    bw = width * bottom_width_scale * 0.5
    bd = depth * bottom_depth_scale * 0.5
    tw = width * top_width_scale * 0.5
    td = depth * top_depth_scale * 0.5
    vertices = [
        (-bw, -bd, z0), (bw, -bd, z0), (bw, bd, z0), (-bw, bd, z0),
        (-tw, -td, z1), (tw, -td, z1), (tw, td, z1), (-tw, td, z1),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5),
        (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0),
    ]
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    _bevel(obj, bevel, 3)
    authored.append(obj)
    return obj


def ellipsoid(authored, parent, name, location, scale, material, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=int(segments), ring_count=int(rings), radius=1.0, location=(0.0, 0.0, 0.0)
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(map(float, scale))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    _smooth(obj)
    authored.append(obj)
    return obj


def tapered_limb(authored, parent, name, location, length, upper_radius, lower_radius, material):
    bpy.ops.mesh.primitive_cone_add(
        vertices=16,
        radius1=float(lower_radius),
        radius2=float(upper_radius),
        depth=float(length),
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    _bevel(obj, min(float(upper_radius), float(lower_radius)) * 0.25, 2)
    _smooth(obj)
    authored.append(obj)
    return obj


def build_visitor_v2(asset):
    if asset.get("contract") != "CH_VISITOR_SOURCE_V1":
        raise RuntimeError("Expected CH_VISITOR_SOURCE_V1")

    mats = v1.make_materials(asset)
    p = asset["proportions"]
    authored = []
    root = v1.empty("AssetRoot")
    pose = v1.empty("VisitorPoseRoot", root)

    pelvis_dims = list(map(float, p["pelvisDimensions"]))
    pelvis = ellipsoid(
        authored, pose, "Pelvis",
        (0.0, 0.0, float(p["pelvisCenterZ"])),
        (pelvis_dims[0] * 0.50, pelvis_dims[1] * 0.50, pelvis_dims[2] * 0.62),
        mats["pants"], 18, 10,
    )
    torso = tapered_prism(
        authored, pose, "Torso",
        (0.0, 0.0, float(p["torsoCenterZ"])),
        p["torsoDimensions"], mats["shirt"],
        top_width_scale=1.00,
        bottom_width_scale=0.74,
        top_depth_scale=0.96,
        bottom_depth_scale=0.78,
        bevel=0.060,
    )

    neck_scale = (float(p["neckRadius"]), float(p["neckRadius"]), float(p["neckDepth"]) * 0.58)
    ellipsoid(authored, pose, "Neck", p["neckCenter"], neck_scale, mats["skin"], 14, 8)
    head = ellipsoid(authored, pose, "Head", p["headCenter"], p["headScale"], mats["skin"], 22, 14)
    ellipsoid(authored, pose, "Hair", p["hairCenter"], p["hairScale"], mats["hair"], 20, 12)
    if asset.get("features", {}).get("nose", True):
        ellipsoid(authored, pose, "Nose", p["noseCenter"], p["noseScale"], mats["skin"], 12, 8)

    rig = {"root": root, "pose": pose}

    upper_leg = float(p["upperLegLength"])
    lower_leg = float(p["lowerLegLength"])
    leg_radius = float(p["legRadius"])
    hip_z = float(p["hipZ"])
    hip_x = float(p["hipX"])
    shoe_y = float(p["shoeForwardY"])
    shoe_dims = list(map(float, p["shoeDimensions"]))

    for side, x in (("L", -hip_x), ("R", hip_x)):
        hip = v1.empty(f"Hip{side}", pose, (x, 0.0, hip_z))
        ellipsoid(
            authored, hip, f"HipCap{side}", (0.0, 0.0, -0.025),
            (leg_radius * 1.10, leg_radius * 1.02, leg_radius * 1.08), mats["pants"], 14, 8,
        )
        tapered_limb(
            authored, hip, f"UpperLeg{side}", (0.0, 0.0, -upper_leg * 0.5),
            upper_leg, leg_radius * 1.03, leg_radius * 0.90, mats["pants"],
        )
        knee = v1.empty(f"Knee{side}", hip, (0.0, 0.0, -upper_leg))
        ellipsoid(
            authored, knee, f"KneeCap{side}", (0.0, 0.0, 0.0),
            (leg_radius * 0.90, leg_radius * 0.86, leg_radius * 0.82), mats["pants"], 14, 8,
        )
        tapered_limb(
            authored, knee, f"LowerLeg{side}", (0.0, 0.0, -lower_leg * 0.5),
            lower_leg, leg_radius * 0.88, leg_radius * 0.70, mats["pants"],
        )
        shoe = ellipsoid(
            authored, knee, f"Shoe{side}",
            (0.0, shoe_y - 0.018, -lower_leg - float(p.get("shoeDrop", 0.010))),
            (shoe_dims[0] * 0.50, shoe_dims[1] * 0.53, shoe_dims[2] * 0.60),
            mats["shoe"], 16, 8,
        )
        sole = v1.box(
            authored, knee, f"Sole{side}",
            (0.0, shoe_y, -lower_leg - float(p.get("soleDrop", 0.060))),
            p["soleDimensions"], mats["sole"], 0.012,
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
        shoulder = v1.empty(f"Shoulder{side}", pose, (x, 0.0, shoulder_z))
        ellipsoid(
            authored, shoulder, f"ShoulderCap{side}", (0.0, 0.0, -0.015),
            (arm_radius * 1.25, arm_radius * 1.16, arm_radius * 1.25), mats["shirt"], 14, 8,
        )
        tapered_limb(
            authored, shoulder, f"UpperArm{side}", (0.0, 0.0, -upper_arm * 0.5),
            upper_arm, arm_radius * 1.05, arm_radius * 0.83, mats["shirt"],
        )
        elbow = v1.empty(f"Elbow{side}", shoulder, (0.0, 0.0, -upper_arm))
        ellipsoid(
            authored, elbow, f"ElbowCap{side}", (0.0, 0.0, 0.0),
            (arm_radius * 0.82, arm_radius * 0.78, arm_radius * 0.80), mats["skin"], 12, 7,
        )
        tapered_limb(
            authored, elbow, f"Forearm{side}", (0.0, 0.0, -forearm * 0.5),
            forearm, arm_radius * 0.78, arm_radius * 0.61, mats["skin"],
        )
        hand = ellipsoid(
            authored, elbow, f"Hand{side}", (0.0, 0.0, -forearm - 0.026),
            p["handScale"], mats["skin"], 12, 8,
        )
        rig[f"shoulder{side}"] = shoulder
        rig[f"elbow{side}"] = elbow
        rig[f"hand{side}"] = hand

    rig["pelvis"] = pelvis
    rig["torso"] = torso
    rig["head"] = head
    return authored, rig


# Reuse the proven V1 gate/orchestration, replacing only the body authoring stage.
v1.build_visitor = build_visitor_v2

if __name__ == "__main__":
    v1.main()
