"""CH Character Studio Blender underlay + pose landmarks.

Runs inside CH Blender. The script renders one transparent 48x64 spatial
underlay for the requested approved-actor frame and also exports projected
landmarks for all S/E/N/W idle + 8 walk states. Character Studio uses those
landmarks to move painted appearance between animation frames without owning or
changing the approved locomotion.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

FRAME = (48, 64)
ANCHOR = (24, 60)
DIRECTIONS = ("S", "E", "N", "W")
FRAMES = ("idle",) + tuple(f"walk_{index:02d}" for index in range(8))
DIRECTION_ANGLE = {
    "S": 0.0,
    "E": math.pi / 2.0,
    "N": math.pi,
    "W": -math.pi / 2.0,
}


def script_args() -> list[str]:
    argv = sys.argv
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--direction", choices=DIRECTIONS, default="S")
    parser.add_argument("--frame", choices=FRAMES, default="idle")
    parser.add_argument("--stage", default="preflight")
    parser.add_argument("--preflight-profile")
    parser.add_argument("--approval-proxy-sha")
    args, _ = parser.parse_known_args(script_args())
    return args


def load_spec(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("contract") != "CH_CHARACTER_ART_SPEC_V0":
        raise RuntimeError("Expected CH_CHARACTER_ART_SPEC_V0")
    if data.get("frame", {}).get("size") != [48, 64]:
        raise RuntimeError("Character Studio V0 requires 48x64 frames")
    if data.get("frame", {}).get("groundAnchor") != [24, 60]:
        raise RuntimeError("Character Studio V0 requires ground anchor [24,60]")
    return data


def rgba(hex_value: str) -> tuple[float, float, float, float]:
    h = hex_value.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


def material(name: str, color: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba(color)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba(color)
        bsdf.inputs["Roughness"].default_value = 0.82
        bsdf.inputs["Specular IOR Level"].default_value = 0.18
    return mat


def rotate_local(point: tuple[float, float, float], direction: str) -> Vector:
    """Rotate actor-local (lateral, depth, vertical) around world Z."""
    x, depth, z = point
    angle = DIRECTION_ANGLE[direction]
    c, s = math.cos(angle), math.sin(angle)
    return Vector((c * x - s * depth, s * x + c * depth, z))


def phase_state(frame: str) -> tuple[float, float, float]:
    if frame == "idle":
        return 0.0, 0.0, 0.0
    index = int(frame.rsplit("_", 1)[1])
    phase = index / 8.0
    return (
        math.sin(2.0 * math.pi * phase),
        math.cos(2.0 * math.pi * phase),
        0.004 * abs(math.sin(4.0 * math.pi * phase)),
    )


def pose_points(spec: dict, direction: str, frame: str) -> dict[str, Vector]:
    """Approved CH Actor-style joint positions in Blender world coordinates."""
    body = spec.get("appearance", {}).get("body", {})
    shoulder_scale = float(body.get("shoulderWidth", 1.0))
    sine, cosine, bob = phase_state(frame)

    local: dict[str, tuple[float, float, float]] = {
        "root": (0.0, 0.0, 0.04),
        "pelvis": (0.0, 0.0, 0.72 + bob),
        "chest": (0.0, 0.0, 1.08 + bob),
        "neck": (0.0, 0.0, 1.34 + bob),
        "head": (0.0, 0.0, 1.52 + bob),
        "head_top": (0.0, 0.0, 1.70 + bob),
    }

    for sign, label in ((-1, "L"), (1, "R")):
        swing = sign * sine
        depth = 0.145 * swing + 0.025 * sign * cosine
        lifted = max(0.0, swing) * 0.032 + max(0.0, sign * cosine) * 0.012
        local[f"hip_{label}"] = (sign * 0.09, 0.0, 0.72 + bob)
        local[f"knee_{label}"] = (
            sign * 0.10,
            depth * 0.42 - 0.028 * max(0.0, swing),
            0.42 + lifted * 0.33 + bob,
        )
        local[f"ankle_{label}"] = (
            sign * (0.10 + 0.008 * abs(sine)),
            depth,
            0.13 + lifted + bob,
        )
        local[f"foot_{label}"] = (
            sign * (0.10 + 0.008 * abs(sine)),
            depth + 0.055,
            0.07 + lifted + bob,
        )

        opposite = -sign * sine
        local[f"shoulder_{label}"] = (sign * 0.22 * shoulder_scale, 0.0, 1.12 + bob)
        local[f"elbow_{label}"] = (
            sign * 0.27 * shoulder_scale,
            0.055 * opposite,
            0.91 + bob,
        )
        local[f"hand_{label}"] = (
            sign * 0.24 * shoulder_scale,
            0.115 * opposite + 0.01,
            0.70 + bob,
        )

    return {name: rotate_local(point, direction) for name, point in local.items()}


def add_uv_sphere(name: str, location: Vector, scale, mat, *, z_rotation: float = 0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.rotation_euler[2] = z_rotation
    obj.data.materials.append(mat)
    return obj


def add_capsule(name: str, a: Vector, b: Vector, radius: float, mat):
    delta = b - a
    length = delta.length
    mid = (a + b) * 0.5
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=length, location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta.normalized())
    add_uv_sphere(name + "_A", a, (radius, radius, radius), mat)
    add_uv_sphere(name + "_B", b, (radius, radius, radius), mat)
    return obj


def setup_camera(scene: bpy.types.Scene) -> bpy.types.Object:
    bpy.ops.object.camera_add(location=(3.2, -3.2, 2.7))
    camera = bpy.context.object
    camera.name = "CH_ACTOR_CAMERA"
    scene.camera = camera
    target = Vector((0, 0, 0.84))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.05
    return camera


def setup_scene(spec: dict, direction: str, frame: str) -> tuple[bpy.types.Object, dict[str, Vector]]:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = FRAME[0]
    scene.render.resolution_y = FRAME[1]
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "Medium High Contrast"

    world = scene.world or bpy.data.worlds.new("CH_CHARACTER_WORLD")
    scene.world = world
    world.color = (0.035, 0.045, 0.04)

    palette = spec["appearance"]["palette"]
    skin = material("CH_SKIN", palette["skin"])
    hair = material("CH_HAIR", palette["hair"])
    primary = material("CH_PRIMARY", palette["primary"])
    secondary = material("CH_SECONDARY", palette["secondary"])
    shoes = material("CH_SHOES", palette["shoes"])

    body = spec.get("appearance", {}).get("body", {})
    head_scale = float(body.get("headScale", 1.0))
    torso_scale = float(body.get("torsoWidth", 1.0))
    leg_scale = float(body.get("legWidth", 1.0))
    angle = DIRECTION_ANGLE[direction]
    points = pose_points(spec, direction, frame)

    root = bpy.data.objects.new("CH_CHARACTER_ROOT", None)
    bpy.context.collection.objects.link(root)

    torso_obj = add_uv_sphere(
        "Torso", points["chest"] + Vector((0, 0, -0.03)),
        (0.23 * torso_scale, 0.16, 0.36), primary, z_rotation=angle,
    )
    torso_obj.parent = root
    pelvis = add_uv_sphere("Pelvis", points["pelvis"], (0.19, 0.14, 0.16), secondary, z_rotation=angle)
    pelvis.parent = root

    for label in ("L", "R"):
        add_capsule(f"Leg_{label}_Upper", points[f"hip_{label}"], points[f"knee_{label}"], 0.055 * leg_scale, secondary).parent = root
        add_capsule(f"Leg_{label}_Lower", points[f"knee_{label}"], points[f"ankle_{label}"], 0.05 * leg_scale, secondary).parent = root
        foot = add_uv_sphere(f"Foot_{label}", points[f"foot_{label}"], (0.075, 0.13, 0.05), shoes, z_rotation=angle)
        foot.parent = root

        add_capsule(f"Arm_{label}_Upper", points[f"shoulder_{label}"], points[f"elbow_{label}"], 0.05, primary).parent = root
        add_capsule(f"Arm_{label}_Lower", points[f"elbow_{label}"], points[f"hand_{label}"], 0.045, primary).parent = root
        add_uv_sphere(f"Hand_{label}", points[f"hand_{label}"], (0.055, 0.055, 0.065), skin).parent = root

    add_uv_sphere("Neck", points["neck"], (0.07, 0.07, 0.08), skin).parent = root
    add_uv_sphere("Head", points["head"], (0.145 * head_scale, 0.135 * head_scale, 0.17 * head_scale), skin, z_rotation=angle).parent = root
    hair_position = points["head"] + Vector((0, 0, 0.07))
    add_uv_sphere("HairMass", hair_position, (0.155 * head_scale, 0.145 * head_scale, 0.11 * head_scale), hair, z_rotation=angle).parent = root

    camera = setup_camera(scene)

    bpy.ops.object.light_add(type="AREA", location=(-2.5, -3.0, 4.5))
    key = bpy.context.object
    key.name = "CH_KEY_LIGHT"
    key.data.energy = 650
    key.data.shape = "DISK"
    key.data.size = 4.0

    bpy.ops.object.light_add(type="AREA", location=(2.0, 1.0, 2.4))
    fill = bpy.context.object
    fill.name = "CH_FILL_LIGHT"
    fill.data.energy = 180
    fill.data.size = 3.0

    return camera, points


def project_landmarks(scene: bpy.types.Scene, camera: bpy.types.Object, points: dict[str, Vector]) -> dict[str, list[float]]:
    projected: dict[str, list[float]] = {}
    for name, point in points.items():
        co = world_to_camera_view(scene, camera, point)
        projected[name] = [
            round(float(co.x) * FRAME[0], 3),
            round((1.0 - float(co.y)) * FRAME[1], 3),
        ]
    return projected


def build_landmark_package(spec: dict, scene: bpy.types.Scene, camera: bpy.types.Object) -> dict:
    frames: dict[str, dict] = {}
    for direction in DIRECTIONS:
        for frame in FRAMES:
            key = f"{direction}:{frame}"
            frames[key] = {
                "direction": direction,
                "frame": frame,
                "points": project_landmarks(scene, camera, pose_points(spec, direction, frame)),
            }
    return {
        "contract": "CH_CHARACTER_LANDMARKS_V0",
        "frameSize": list(FRAME),
        "groundAnchor": list(ANCHOR),
        "camera": "CH_ACTOR_CAMERA_V1",
        "motionSource": "approved_ch_actor",
        "regions": {
            "head": ["head", "head_top", "neck"],
            "torso": ["neck", "chest", "pelvis", "shoulder_L", "shoulder_R"],
            "left_arm": ["shoulder_L", "elbow_L", "hand_L"],
            "right_arm": ["shoulder_R", "elbow_R", "hand_R"],
            "left_leg": ["hip_L", "knee_L", "ankle_L", "foot_L"],
            "right_leg": ["hip_R", "knee_R", "ankle_R", "foot_R"],
        },
        "frames": frames,
    }


def render_base(output_dir: Path, spec: dict, direction: str, frame: str, camera: bpy.types.Object) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str((output_dir / "base.png").resolve())
    bpy.ops.render.render(write_still=True)

    landmarks = build_landmark_package(spec, scene, camera)
    (output_dir / "landmarks.json").write_text(
        json.dumps(landmarks, indent=2) + "\n", encoding="utf-8"
    )

    report = {
        "contract": "CH_CHARACTER_STUDIO_BASE_PASS_V0",
        "status": "ok",
        "frame": {"size": list(FRAME), "groundAnchor": list(ANCHOR)},
        "pose": {"direction": direction, "frame": frame},
        "outputs": {"base": "base.png", "landmarks": "landmarks.json"},
        "ownership": "spatial_underlay_and_pose_landmarks_only",
    }
    (output_dir / "character_base_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    spec = load_spec(args.character_spec)
    camera, _ = setup_scene(spec, args.direction, args.frame)
    render_base(args.output, spec, args.direction, args.frame, camera)
    print(json.dumps({
        "status": "ok",
        "characterId": spec["characterId"],
        "direction": args.direction,
        "frame": args.frame,
        "output": str(args.output),
        "landmarks": str(args.output / "landmarks.json"),
    }))


if __name__ == "__main__":
    main()
