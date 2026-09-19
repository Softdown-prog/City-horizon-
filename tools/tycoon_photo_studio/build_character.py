"""Bake one canonical City Horizon visitor into an 8-direction, 8-frame walk cycle.

The model is intentionally simple and deterministic: every direction and frame comes
from the same 3D source, the frozen CH_TYCOON_STUDIO_V1 camera/light rig, and one
parametric walk pose. This is the visual-coherence gate before adding more NPCs.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_scene as studio_base


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def add_empty(name, parent=None, location=(0.0, 0.0, 0.0)):
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.empty_display_type = "PLAIN_AXES"
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    obj.location = tuple(location)
    return obj


def add_box_child(authored, parent, name, location, dimensions, material, bevel=0.02):
    bpy.ops.mesh.primitive_cube_add(location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(dimensions)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0.0:
        modifier = obj.modifiers.new(name="CharacterBevel", type="BEVEL")
        modifier.width = float(bevel)
        modifier.segments = 2
    obj.parent = parent
    obj.location = tuple(location)
    authored.append(obj)
    return obj


def add_cylinder_child(authored, parent, name, location, radius, depth, material, vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    obj.parent = parent
    obj.location = tuple(location)
    authored.append(obj)
    return obj


def add_sphere_child(authored, parent, name, location, scale, material, segments=20, rings=12):
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


def build_materials(asset):
    materials = {}
    for key, spec in asset["materials"].items():
        materials[key] = studio_base.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.8)),
            float(spec.get("metallic", 0.0)),
        )
    return materials


def build_character(asset):
    if asset.get("contract") != "TYCOON_CHARACTER_SOURCE_V1":
        raise RuntimeError("Character source must use TYCOON_CHARACTER_SOURCE_V1")

    materials = build_materials(asset)
    p = asset["proportions"]
    authored = []

    direction_root = add_empty("CharacterDirectionRoot")
    pose_root = add_empty("CharacterPoseRoot", direction_root)

    # Core silhouette: jeans, red short-sleeve top, head and hair.
    add_box_child(
        authored, pose_root, "Pelvis",
        (0.0, 0.0, float(p["pelvisCenterZ"])),
        p["pelvisDimensions"], materials["jeans"], 0.055,
    )
    add_box_child(
        authored, pose_root, "Torso",
        (0.0, 0.0, float(p["torsoCenterZ"])),
        p["torsoDimensions"], materials["shirt"], 0.085,
    )

    torso_depth = float(p["torsoDimensions"][1])
    torso_width = float(p["torsoDimensions"][0])
    stripe_z = p.get("shirtStripeZ", [1.38, 1.48])
    for index, z in enumerate(stripe_z):
        add_box_child(
            authored, pose_root, f"ShirtStripe{index}",
            (0.0, -torso_depth * 0.505, float(z)),
            (torso_width * 0.93, 0.018, 0.035), materials["shirtStripe"], 0.005,
        )

    add_cylinder_child(
        authored, pose_root, "Neck", p.get("neckCenter", [0.0, 0.0, 1.66]),
        float(p.get("neckRadius", 0.075)), float(p.get("neckDepth", 0.14)), materials["skin"], 12,
    )
    add_sphere_child(
        authored, pose_root, "Head", p["headCenter"], p["headScale"], materials["skin"], 24, 14,
    )
    add_sphere_child(
        authored, pose_root, "Hair", p["hairCenter"], p["hairScale"], materials["hair"], 20, 10,
    )
    add_sphere_child(
        authored, pose_root, "Nose", p.get("noseCenter", [0.0, -0.166, 1.815]),
        p.get("noseScale", [0.035, 0.048, 0.040]), materials["skin"], 12, 8,
    )
    add_sphere_child(
        authored, pose_root, "EarL", p.get("earLCenter", [-0.151, -0.005, 1.81]),
        p.get("earScale", [0.028, 0.020, 0.042]), materials["skin"], 10, 6,
    )
    add_sphere_child(
        authored, pose_root, "EarR", p.get("earRCenter", [0.151, -0.005, 1.81]),
        p.get("earScale", [0.028, 0.020, 0.042]), materials["skin"], 10, 6,
    )

    add_box_child(
        authored, pose_root, "Daypack", p.get("daypackCenter", [0.0, 0.205, 1.36]),
        p.get("daypackDimensions", [0.34, 0.16, 0.43]), materials["backpack"],
        float(p.get("daypackBevel", 0.075)),
    )
    add_box_child(
        authored, pose_root, "PackTop", p.get("packTopCenter", [0.0, 0.205, 1.57]),
        p.get("packTopDimensions", [0.26, 0.14, 0.08]), materials["backpack"], 0.035,
    )

    rig = {
        "directionRoot": direction_root,
        "poseRoot": pose_root,
    }

    upper_leg = float(p["upperLegLength"])
    lower_leg = float(p["lowerLegLength"])
    leg_radius = float(p["legRadius"])
    hip_x = float(p["hipX"])
    hip_z = float(p["hipZ"])
    shoe_dimensions = p.get("shoeDimensions", [0.22, 0.34, 0.11])
    sole_dimensions = p.get("soleDimensions", [0.225, 0.35, 0.025])
    shoe_y = float(p.get("shoeForwardY", -0.070))

    for side, x in (("L", -hip_x), ("R", hip_x)):
        hip = add_empty(f"Hip{side}", pose_root, (x, 0.0, hip_z))
        add_cylinder_child(
            authored, hip, f"UpperLeg{side}", (0.0, 0.0, -upper_leg * 0.5),
            leg_radius, upper_leg, materials["jeans"], 12,
        )
        knee = add_empty(f"Knee{side}", hip, (0.0, 0.0, -upper_leg))
        add_cylinder_child(
            authored, knee, f"LowerLeg{side}", (0.0, 0.0, -lower_leg * 0.5),
            leg_radius * 0.90, lower_leg, materials["jeans"], 12,
        )
        add_box_child(
            authored, knee, f"Shoe{side}",
            (0.0, shoe_y, -lower_leg - 0.010),
            shoe_dimensions, materials["shoe"], 0.035,
        )
        add_box_child(
            authored, knee, f"Sole{side}",
            (0.0, shoe_y, -lower_leg - 0.066),
            sole_dimensions, materials["sole"], 0.010,
        )
        rig[f"hip{side}"] = hip
        rig[f"knee{side}"] = knee

    upper_arm = float(p["upperArmLength"])
    forearm = float(p["forearmLength"])
    arm_radius = float(p["armRadius"])
    shoulder_x = float(p["shoulderX"])
    shoulder_z = float(p["shoulderZ"])
    hand_scale = p.get("handScale", [0.073, 0.066, 0.090])

    for side, x in (("L", -shoulder_x), ("R", shoulder_x)):
        shoulder = add_empty(f"Shoulder{side}", pose_root, (x, 0.0, shoulder_z))
        add_cylinder_child(
            authored, shoulder, f"UpperArm{side}", (0.0, 0.0, -upper_arm * 0.5),
            arm_radius, upper_arm, materials["shirt"], 12,
        )
        elbow = add_empty(f"Elbow{side}", shoulder, (0.0, 0.0, -upper_arm))
        add_cylinder_child(
            authored, elbow, f"Forearm{side}", (0.0, 0.0, -forearm * 0.5),
            arm_radius * 0.82, forearm, materials["skin"], 12,
        )
        add_sphere_child(
            authored, elbow, f"Hand{side}", (0.0, 0.0, -forearm - 0.035),
            hand_scale, materials["skin"], 12, 8,
        )
        rig[f"shoulder{side}"] = shoulder
        rig[f"elbow{side}"] = elbow

    return authored, rig


def apply_walk_pose(rig, animation, frame_index):
    frame_count = int(animation["frameCount"])
    phase = (2.0 * math.pi * frame_index) / frame_count
    stride = math.radians(float(animation["strideDegrees"]))
    arm_swing = math.radians(float(animation["armSwingDegrees"]))
    knee_bend = math.radians(float(animation["kneeBendDegrees"]))
    elbow_base = math.radians(float(animation["elbowBaseDegrees"]))
    elbow_bend = math.radians(float(animation["elbowBendDegrees"]))
    bob = float(animation["verticalBob"])
    sway = math.radians(float(animation["torsoSwayDegrees"]))

    left_wave = math.sin(phase)
    right_wave = -left_wave

    rig["hipL"].rotation_euler = (left_wave * stride, 0.0, 0.0)
    rig["hipR"].rotation_euler = (right_wave * stride, 0.0, 0.0)
    rig["kneeL"].rotation_euler = (max(0.0, left_wave) * knee_bend, 0.0, 0.0)
    rig["kneeR"].rotation_euler = (max(0.0, right_wave) * knee_bend, 0.0, 0.0)

    rig["shoulderL"].rotation_euler = (-left_wave * arm_swing, 0.0, 0.0)
    rig["shoulderR"].rotation_euler = (-right_wave * arm_swing, 0.0, 0.0)
    rig["elbowL"].rotation_euler = (elbow_base + max(0.0, -left_wave) * elbow_bend, 0.0, 0.0)
    rig["elbowR"].rotation_euler = (elbow_base + max(0.0, -right_wave) * elbow_bend, 0.0, 0.0)

    # Two vertical contacts per cycle; the root remains anchored to the same world origin.
    rig["poseRoot"].location = (0.0, 0.0, bob * (0.5 - 0.5 * math.cos(2.0 * phase)))
    rig["poseRoot"].rotation_euler = (0.0, 0.0, sway * math.sin(phase))
    bpy.context.view_layer.update()


def set_direction(rig, direction):
    rig["directionRoot"].rotation_euler[2] = math.radians(float(direction["rotationDegrees"]))
    bpy.context.view_layer.update()


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)
    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError(
            f"Character requests studio {asset.get('studioPreset')!r}, but loaded {studio.get('id')!r}"
        )

    studio_base.clear_scene()
    scene = studio_base.configure_scene(studio, output_dir)
    authored, rig = build_character(asset)

    receiver = studio["shadowReceiver"]
    ground_material = studio_base.make_material(
        "CharacterShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = studio_base.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        ground_material,
        0.0,
    )

    animation = asset["animation"]
    frame_count = int(animation["frameCount"])
    directions = asset["directions"]
    asset_id = asset["assetId"]
    frame_metadata = []

    for direction in directions:
        set_direction(rig, direction)
        frames = []
        for frame_index in range(frame_count):
            apply_walk_pose(rig, animation, frame_index)
            frame_token = f"f{frame_index:02d}"
            direction_id = direction["id"]
            color_name = f"{asset_id}_{direction_id}_{frame_token}_color_source.png"
            shadow_name = f"{asset_id}_{direction_id}_{frame_token}_shadow_source.png"

            studio_base.render_color_pass(
                scene, authored, ground, os.path.join(output_dir, color_name)
            )
            studio_base.render_shadow_pass(
                scene, authored, ground, os.path.join(output_dir, shadow_name)
            )
            frames.append({
                "frame": frame_index,
                "phase": round(frame_index / frame_count, 6),
                "colorSource": color_name,
                "shadowSource": shadow_name,
                "groundOriginSourcePx": studio_base.ground_origin_source_px(scene),
            })
        frame_metadata.append({
            "id": direction["id"],
            "rotationDegrees": direction["rotationDegrees"],
            "frames": frames,
        })

    metadata = {
        "contract": "TYCOON_CHARACTER_BAKE_V1",
        "sourceContract": asset["contract"],
        "sourceObject": asset_id,
        "assetStatus": asset.get("status", "production_candidate"),
        "assetType": asset.get("assetType", "visitor_npc"),
        "runtime": asset.get("runtime", {
            "contract": "CH_ACTOR_RUNTIME_V1",
            "anchorPolicy": "shared_projected_world_origin",
        }),
        "footprint": asset["footprint"],
        "assetConfig": os.path.basename(args.asset_config),
        "studioPreset": studio["id"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderDevice": studio["render"]["device"],
        "samples": scene.cycles.samples,
        "cameraContract": studio["camera"]["contract"],
        "gridContract": "CH_GRID_V1",
        "projection": studio["camera"]["projection"],
        "yawDegrees": studio["camera"]["yawDegrees"],
        "elevationDegrees": studio["camera"]["elevationDegrees"],
        "tileWidth": 128,
        "tileHeight": 64,
        "renderResolution": [scene.render.resolution_x, scene.render.resolution_y],
        "finalResolution": studio["render"]["finalResolution"],
        "orthoScale": scene.camera.data.ortho_scale,
        "directionOrder": [item["id"] for item in directions],
        "directions": frame_metadata,
        "animation": animation,
        "rotationPolicy": {
            "cameraRotates": False,
            "characterRootRotates": True,
            "lightsRotate": False,
            "fixedWorldLighting": True,
        },
        "postProcess": studio["postProcess"],
        "sourceSummary": {
            "materialCount": len(asset["materials"]),
            "meshPartCount": len(authored),
            "sourceMode": "single_parametric_character_rig_v1",
        },
        "coherenceRule": "One model, one rig, one parametric loop; never redraw or regenerate individual frames independently.",
        "note": "First NPC sequence consistency test. Human visual approval remains mandatory.",
    }
    Path(output_dir, "character_studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print("Tycoon Character Baker V1 source sequence generated:", asset_id)
    print("studio:", studio["id"])
    print("directions:", len(directions), "framesPerDirection:", frame_count)


if __name__ == "__main__":
    main()
