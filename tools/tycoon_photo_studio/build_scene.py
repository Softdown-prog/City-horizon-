"""Tycoon Photo Studio POC scene.

Build one small park kiosk in a fixed CH_CAMERA_V1-like studio and bake an
object color pass plus a Cycles shadow-catcher pass. This is intentionally a
single visual proof, not a general asset editor.
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_material(name, rgba, roughness=0.72, metallic=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(name, location, dimensions, material, bevel=0.035):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if bevel > 0:
        modifier = obj.modifiers.new(name="ProductionBevel", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def add_pyramid_roof(name, location, radius, depth, material):
    bpy.ops.mesh.primitive_cone_add(
        vertices=4,
        radius1=radius,
        radius2=0.0,
        depth=depth,
        location=location,
        rotation=(0.0, 0.0, math.radians(45.0)),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(name="RoofEdgeSoftening", type="BEVEL")
    bevel.width = 0.025
    bevel.segments = 2
    return obj


def add_uv_sphere(name, location, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def add_area_light(name, location, energy, color, size, use_shadow=True):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    if hasattr(data, "use_shadow"):
        data.use_shadow = use_shadow
    obj = bpy.data.objects.new(name=name, object_data=data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    target = Vector((0.0, 0.0, 1.15))
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def add_camera():
    target = Vector((0.0, 0.0, 1.25))
    horizontal_distance = 8.0
    yaw = math.radians(45.0)
    elevation = math.radians(30.0)
    location = Vector(
        (
            math.cos(yaw) * horizontal_distance,
            -math.sin(yaw) * horizontal_distance,
            target.z + math.tan(elevation) * horizontal_distance,
        )
    )

    data = bpy.data.cameras.new("CH_CAMERA_V1")
    data.type = "ORTHO"
    data.ortho_scale = 5.6
    obj = bpy.data.objects.new("CH_CAMERA_V1", data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (target - location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = obj
    return obj


def build_kiosk():
    cream = make_material("PaintedCream", (0.72, 0.58, 0.37, 1.0), roughness=0.78)
    cream_light = make_material("TrimIvory", (0.90, 0.78, 0.56, 1.0), roughness=0.72)
    heritage_red = make_material("HeritageRed", (0.47, 0.075, 0.055, 1.0), roughness=0.74)
    red_light = make_material("AwningRed", (0.64, 0.12, 0.085, 1.0), roughness=0.70)
    dark_wood = make_material("DarkWood", (0.19, 0.085, 0.035, 1.0), roughness=0.86)
    brass = make_material("Brass", (0.62, 0.34, 0.055, 1.0), roughness=0.48, metallic=0.36)
    glass = make_material("DarkGlass", (0.045, 0.075, 0.085, 1.0), roughness=0.32)
    stone = make_material("PlinthStone", (0.20, 0.18, 0.16, 1.0), roughness=0.92)

    authored = []
    authored.append(add_box("Kiosk_Platform", (0.0, 0.0, 0.16), (2.85, 2.45, 0.32), stone, 0.05))
    authored.append(add_box("Kiosk_Body", (0.0, 0.0, 1.25), (2.35, 1.95, 1.85), cream, 0.055))
    authored.append(add_box("FrontLowerPanel", (0.0, -0.995, 0.73), (2.05, 0.07, 0.62), heritage_red, 0.018))
    authored.append(add_box("EastLowerPanel", (1.195, 0.0, 0.73), (0.07, 1.65, 0.62), heritage_red, 0.018))

    authored.append(add_box("FrontWindow", (0.0, -1.018, 1.53), (1.42, 0.055, 0.73), glass, 0.012))
    authored.append(add_box("FrontWindowTop", (0.0, -1.055, 1.94), (1.62, 0.085, 0.11), cream_light, 0.012))
    authored.append(add_box("FrontWindowBottom", (0.0, -1.08, 1.10), (1.62, 0.20, 0.12), dark_wood, 0.015))
    authored.append(add_box("FrontWindowLeft", (-0.78, -1.055, 1.53), (0.10, 0.085, 0.78), cream_light, 0.012))
    authored.append(add_box("FrontWindowRight", (0.78, -1.055, 1.53), (0.10, 0.085, 0.78), cream_light, 0.012))
    authored.append(add_box("FrontMullion", (0.0, -1.065, 1.53), (0.065, 0.075, 0.71), brass, 0.008))

    authored.append(add_box("EastWindow", (1.218, 0.12, 1.52), (0.055, 1.00, 0.61), glass, 0.012))
    authored.append(add_box("EastWindowTop", (1.255, 0.12, 1.86), (0.085, 1.16, 0.10), cream_light, 0.01))
    authored.append(add_box("EastWindowBottom", (1.255, 0.12, 1.18), (0.085, 1.16, 0.10), dark_wood, 0.01))

    for x in (-1.22, 1.22):
        authored.append(add_box(f"FrontPost_{x:+.2f}", (x, -1.16, 1.28), (0.12, 0.12, 2.22), dark_wood, 0.018))

    authored.append(add_box("Awning", (0.0, -1.27, 2.08), (1.92, 0.62, 0.13), red_light, 0.028))
    authored.append(add_box("RoofFascia", (0.0, 0.0, 2.31), (2.78, 2.36, 0.18), heritage_red, 0.035))
    authored.append(add_pyramid_roof("KioskRoof", (0.0, 0.0, 2.72), 1.82, 0.76, red_light))

    authored.append(add_box("FrontSign", (0.0, -1.24, 2.29), (1.38, 0.10, 0.32), heritage_red, 0.035))
    authored.append(add_box("FrontSignInset", (0.0, -1.30, 2.29), (0.96, 0.035, 0.11), cream_light, 0.01))
    authored.append(add_box("RoofTrimFront", (0.0, -1.22, 2.39), (2.36, 0.07, 0.06), brass, 0.012))
    authored.append(add_box("RoofTrimEast", (1.40, 0.0, 2.39), (0.07, 1.95, 0.06), brass, 0.012))
    authored.append(add_uv_sphere("RoofFinial", (0.0, 0.0, 3.15), 0.11, brass))
    return authored


def configure_scene(output_dir):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True

    try:
        scene.view_settings.view_transform = "Standard"
    except Exception:
        pass
    try:
        scene.view_settings.look = "Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    world = scene.world or bpy.data.worlds.new("PhotoStudioWorld")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.13, 0.16, 0.20, 1.0)
    background.inputs["Strength"].default_value = 0.42

    add_camera()
    add_area_light("Key_Warm_NW", (-5.6, -6.2, 8.5), 980.0, (1.0, 0.79, 0.60), 4.1, True)
    add_area_light("Fill_Cool_SE", (5.0, 4.5, 5.2), 315.0, (0.52, 0.68, 1.0), 5.5, False)
    os.makedirs(output_dir, exist_ok=True)


def render_color_pass(scene, authored, ground, output_dir):
    ground.hide_render = True
    if hasattr(ground, "is_shadow_catcher"):
        ground.is_shadow_catcher = False
    for obj in authored:
        obj.hide_render = False
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = True
    scene.render.filepath = os.path.join(output_dir, "tycoon_photo_studio_color_source.png")
    bpy.ops.render.render(write_still=True)


def render_shadow_reference(scene, authored, ground, output_dir):
    ground.hide_render = False
    if hasattr(ground, "is_shadow_catcher"):
        ground.is_shadow_catcher = True
    for obj in authored:
        obj.hide_render = False
        if hasattr(obj, "visible_camera"):
            obj.visible_camera = False
        if hasattr(obj, "visible_shadow"):
            obj.visible_shadow = True

    scene.render.filepath = os.path.join(output_dir, "tycoon_photo_studio_shadow_reference.png")
    bpy.ops.render.render(write_still=True)


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    clear_scene()
    configure_scene(output_dir)

    authored = build_kiosk()
    ground_material = make_material("ShadowReceiver", (0.82, 0.82, 0.82, 1.0), roughness=1.0)
    ground = add_box("ShadowReceiverPlane", (0.0, 0.0, -0.055), (7.5, 7.5, 0.10), ground_material, 0.0)

    scene = bpy.context.scene
    render_color_pass(scene, authored, ground, output_dir)
    render_shadow_reference(scene, authored, ground, output_dir)

    metadata = {
        "poc": "TYCOON_PHOTO_STUDIO_POC_V1",
        "sourceObject": "park_kiosk_1x1",
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderDevice": "CPU",
        "samples": scene.cycles.samples,
        "cameraContract": "CH_CAMERA_V1",
        "projection": "orthographic",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "groundRead": "2:1 dimetric target",
        "renderResolution": [scene.render.resolution_x, scene.render.resolution_y],
        "orthoScale": scene.camera.data.ortho_scale,
        "lighting": {
            "key": "warm northwest area light",
            "fill": "cool southeast area light",
            "worldStrength": 0.42
        },
        "shadowMode": "Cycles shadow catcher with object hidden from camera",
        "note": "POC scene only; aesthetic approval requires review of final downsampled variants."
    }
    with open(os.path.join(output_dir, "studio_metadata.json"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)

    print("Tycoon Photo Studio POC source passes generated in", output_dir)


if __name__ == "__main__":
    main()
