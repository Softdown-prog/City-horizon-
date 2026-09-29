"""CH Character Studio Blender underlay.

Runs inside CH Blender. It builds a deterministic low-detail actor underlay from
CH_CHARACTER_ART_SPEC_V0 and renders a transparent 48x64 base pass. The final
visible style belongs to Character Studio paint layers, not this script.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

FRAME = (48, 64)
ANCHOR = (24, 60)


def script_args() -> list[str]:
    argv = sys.argv
    return argv[argv.index("--") + 1 :] if "--" in argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--character-spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4)) + (1.0,)


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


def add_uv_sphere(name: str, location, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
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


def setup_scene(spec: dict) -> bpy.types.Object:
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
    shoulder = float(body.get("shoulderWidth", 1.0))
    torso = float(body.get("torsoWidth", 1.0))
    legw = float(body.get("legWidth", 1.0))

    root = bpy.data.objects.new("CH_CHARACTER_ROOT", None)
    bpy.context.collection.objects.link(root)

    hip_z = 0.72
    chest_z = 1.12
    head_z = 1.52

    torso_obj = add_uv_sphere("Torso", (0, 0, 1.05), (0.23*torso, 0.16, 0.36), primary)
    torso_obj.parent = root
    pelvis = add_uv_sphere("Pelvis", (0, 0, hip_z), (0.19, 0.14, 0.16), secondary)
    pelvis.parent = root

    for sign, label in ((-1, "L"), (1, "R")):
        hip = Vector((sign*0.09, 0, hip_z))
        knee = Vector((sign*0.10, 0, 0.42))
        ankle = Vector((sign*0.10, 0, 0.13))
        add_capsule(f"Leg_{label}_Upper", hip, knee, 0.055*legw, secondary).parent = root
        add_capsule(f"Leg_{label}_Lower", knee, ankle, 0.05*legw, secondary).parent = root
        foot = add_uv_sphere(f"Foot_{label}", (sign*0.10, -0.035, 0.07), (0.075, 0.13, 0.05), shoes)
        foot.parent = root

        sh = Vector((sign*0.22*shoulder, 0, chest_z))
        elbow = Vector((sign*0.27*shoulder, 0, 0.91))
        hand = Vector((sign*0.24*shoulder, 0, 0.70))
        add_capsule(f"Arm_{label}_Upper", sh, elbow, 0.05, primary).parent = root
        add_capsule(f"Arm_{label}_Lower", elbow, hand, 0.045, primary).parent = root
        add_uv_sphere(f"Hand_{label}", hand, (0.055,0.055,0.065), skin).parent = root

    neck = add_uv_sphere("Neck", (0,0,1.34), (0.07,0.07,0.08), skin)
    neck.parent = root
    head = add_uv_sphere("Head", (0,0,head_z), (0.145*head_scale,0.135*head_scale,0.17*head_scale), skin)
    head.parent = root
    hair_obj = add_uv_sphere("HairMass", (0,0.015,head_z+0.07), (0.155*head_scale,0.145*head_scale,0.11*head_scale), hair)
    hair_obj.parent = root

    # CH actor camera: fixed orthographic 45 yaw / 30 pitch.
    bpy.ops.object.camera_add(location=(3.2, -3.2, 2.7))
    camera = bpy.context.object
    camera.name = "CH_ACTOR_CAMERA"
    scene.camera = camera
    target = Vector((0, 0, 0.84))
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.05

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

    return root


def render_base(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.filepath = str((output_dir / "base.png").resolve())
    bpy.ops.render.render(write_still=True)

    report = {
        "contract": "CH_CHARACTER_STUDIO_BASE_PASS_V0",
        "status": "ok",
        "frame": {"size": list(FRAME), "groundAnchor": list(ANCHOR)},
        "output": "base.png",
        "ownership": "spatial_underlay_only",
    }
    (output_dir / "character_base_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    spec = load_spec(args.character_spec)
    setup_scene(spec)
    render_base(args.output)
    print(json.dumps({"status":"ok","characterId":spec["characterId"],"output":str(args.output)}))


if __name__ == "__main__":
    main()
