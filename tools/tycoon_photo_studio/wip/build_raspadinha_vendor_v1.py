"""WIP Blender authoring scene for the City Horizon raspadinha cart + vendor.

This is intentionally a *design scene*, not a promoted runtime asset yet.
It follows CH_CAMERA_V1 / CH_TYCOON_STUDIO_V1 and keeps the asset itself free of
terrain/grass.  The user-supplied concept art is used only as visual direction;
all geometry is rebuilt in Blender so the asset can rotate consistently.

Initial animation block (12 frames @ 8 fps):
  1-4   idle / small head glance
  5-8   greeting / wave to passing pedestrians
  9-12  serving / reaching toward the shaved-ice counter

The whole asset lives under AssetRoot.  Camera and lights remain world-fixed;
AssetRoot is therefore ready for the canonical SOUTH/EAST/WEST/NORTH rotations.

Run from repo root, for example:
  blender --background --python tools/tycoon_photo_studio/wip/build_raspadinha_vendor_v1.py -- \
      --studio-preset tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json \
      --save-blend out/wip/raspadinha_vendor_v1/raspadinha_vendor_v1.blend
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
PHOTO_STUDIO = HERE.parent
if str(PHOTO_STUDIO) not in sys.path:
    sys.path.insert(0, str(PHOTO_STUDIO))

import build_scene as bs  # noqa: E402


ASSET_ID = "prop.raspadinha_vendor.01"
FPS = 8
FRAME_START = 1
FRAME_END = 12


def args_from_blender():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--preview-direction", choices=["south", "east", "west", "north"], default="south")
    return p.parse_args(argv)


def mat(name, rgba, rough=0.72, metallic=0.0):
    return bs.make_material(name, rgba, roughness=rough, metallic=metallic)


def box(name, loc, dims, material, bevel=0.035, parent=None):
    obj = bs.add_box(name, loc, dims, material, bevel)
    if parent:
        obj.parent = parent
    return obj


def sphere(name, loc, radius, material, parent=None, scale=(1.0, 1.0, 1.0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    return obj


def cylinder(name, loc, radius, depth, material, rotation=(0, 0, 0), parent=None, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    if parent:
        obj.parent = parent
    bevel = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    bevel.width = min(radius * 0.18, 0.025)
    bevel.segments = 2
    return obj


def empty(name, loc, parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = loc
    if parent:
        obj.parent = parent
    return obj


def parent_keep_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def create_umbrella_panel(name, angle0, angle1, z_center, radius, material, parent):
    # Four vertices make one sloping fabric wedge.  The slight skirt drop keeps
    # the silhouette readable after downsample without requiring cloth sim.
    inner_r = 0.08
    apex_z = z_center + 0.34
    rim_z = z_center
    skirt_z = z_center - 0.08
    verts = [
        (inner_r * math.cos((angle0 + angle1) * 0.5), inner_r * math.sin((angle0 + angle1) * 0.5), apex_z),
        (radius * math.cos(angle0), radius * math.sin(angle0), rim_z),
        (radius * math.cos(angle1), radius * math.sin(angle1), rim_z),
        ((radius * 0.96) * math.cos((angle0 + angle1) * 0.5), (radius * 0.96) * math.sin((angle0 + angle1) * 0.5), skirt_z),
    ]
    faces = [(0, 1, 3), (0, 3, 2)]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    obj.parent = parent
    return obj


def build_cart(root, M):
    cart = empty("CartRoot", (-0.45, 0.0, 0.0), root)

    # Body and serving top.
    box("CartBody", (-0.45, 0.0, 0.62), (1.70, 0.92, 1.02), M["blue"], 0.055, cart)
    box("CartFrontPanel", (-0.45, -0.48, 0.66), (1.48, 0.055, 0.63), M["cream"], 0.018, cart)
    box("CartCounter", (-0.45, 0.0, 1.18), (1.84, 1.00, 0.10), M["metal"], 0.028, cart)
    box("IceBin", (-0.57, 0.12, 1.39), (0.78, 0.62, 0.38), M["metal_dark"], 0.035, cart)
    box("IceBinTop", (-0.57, 0.12, 1.59), (0.82, 0.66, 0.055), M["metal"], 0.018, cart)

    # Crushed ice remains deliberately chunky so it reads at game scale.
    for i, (x, y) in enumerate([(-0.78,-0.04),(-0.55,-0.02),(-0.34,0.02),(-0.69,0.18),(-0.45,0.20),(-0.29,0.23)]):
        sphere(f"Ice_{i}", (x, y, 1.64), 0.095, M["ice"], cart, (1.15, 0.9, 0.55))

    # Wheel + hub on the visible service side.  Rear leg keeps cart grounded.
    cylinder("Wheel", (-0.77, -0.52, 0.42), 0.36, 0.12, M["rubber"], rotation=(math.radians(90), 0, 0), parent=cart, verts=32)
    cylinder("WheelHub", (-0.77, -0.59, 0.42), 0.13, 0.15, M["metal"], rotation=(math.radians(90), 0, 0), parent=cart, verts=24)
    box("SupportLeg", (0.34, 0.30, 0.22), (0.10, 0.10, 0.44), M["dark"], 0.018, cart)

    # Push handle.
    box("HandleBar", (-1.39, 0.20, 0.95), (0.55, 0.09, 0.09), M["blue_dark"], 0.035, cart)

    # Syrup bottles.
    syrup_x = [-0.05, 0.14, 0.33, 0.52]
    syrup_mats = [M["red"], M["cyan"], M["yellow"], M["green"]]
    for i, (x, sm) in enumerate(zip(syrup_x, syrup_mats)):
        cylinder(f"SyrupBottle_{i}", (x, -0.25, 1.42), 0.075, 0.34, sm, parent=cart, verts=20)
        cylinder(f"SyrupNozzle_{i}", (x, -0.25, 1.63), 0.022, 0.10, M["cream"], parent=cart, verts=16)

    # Cup stack and one finished shaved ice.
    for i in range(5):
        cylinder(f"CupStack_{i}", (0.63, 0.02, 1.28 + i * 0.045), 0.10 + i * 0.002, 0.12, M["cream"], parent=cart, verts=24)
    cylinder("ServingCup", (0.57, -0.27, 1.35), 0.105, 0.24, M["cream"], parent=cart, verts=24)
    sphere("ServingIcePink", (0.54, -0.27, 1.52), 0.12, M["pink"], cart, (1.0, 0.95, 0.78))
    sphere("ServingIceBlue", (0.62, -0.27, 1.52), 0.10, M["cyan"], cart, (0.95, 0.9, 0.75))

    # Simplified sign: no runtime dependency on generated text during this WIP.
    sign = empty("FrontSign", (0,0,0), cart)
    box("SignSun", (-0.88, -0.515, 0.84), (0.28, 0.035, 0.22), M["yellow"], 0.045, sign)
    box("SignWave", (-0.45, -0.518, 0.43), (1.22, 0.035, 0.08), M["cyan"], 0.018, sign)
    for i, width in enumerate((0.86, 1.04, 0.72)):
        box(f"SignLetterBand_{i}", (-0.37, -0.52, 0.76 - i * 0.16), (width, 0.035, 0.055), M["blue_dark"], 0.015, sign)

    # Umbrella pole and alternating bicolor panels.
    pole_x, pole_y = -0.52, 0.18
    cylinder("UmbrellaPole", (pole_x, pole_y, 2.20), 0.035, 2.08, M["metal_dark"], parent=cart, verts=20)
    umbrella = empty("UmbrellaRoot", (pole_x, pole_y, 0), cart)
    panels = 8
    for i in range(panels):
        a0 = math.radians(i * 360 / panels)
        a1 = math.radians((i + 1) * 360 / panels)
        create_umbrella_panel(f"UmbrellaPanel_{i}", a0, a1, 3.10, 1.20, M["pink"] if i % 2 == 0 else M["cyan"], umbrella)
    cylinder("UmbrellaCap", (pole_x, pole_y, 3.48), 0.085, 0.12, M["metal"], parent=cart, verts=24)

    return cart


def build_vendor(root, M):
    vendor = empty("VendorRoot", (0.78, 0.16, 0.0), root)

    # Legs / shoes.
    box("Leg_L", (0.66, 0.16, 0.55), (0.23, 0.26, 0.82), M["pants"], 0.05, vendor)
    box("Leg_R", (0.93, 0.16, 0.55), (0.23, 0.26, 0.82), M["pants"], 0.05, vendor)
    box("Shoe_L", (0.63, 0.08, 0.15), (0.30, 0.42, 0.18), M["dark"], 0.07, vendor)
    box("Shoe_R", (0.96, 0.08, 0.15), (0.30, 0.42, 0.18), M["dark"], 0.07, vendor)

    # Torso, apron and head.
    box("Torso", (0.79, 0.16, 1.35), (0.72, 0.42, 0.86), M["shirt"], 0.13, vendor)
    box("Apron", (0.79, -0.08, 1.28), (0.58, 0.06, 0.82), M["blue"], 0.045, vendor)
    sphere("Head", (0.79, 0.08, 2.02), 0.31, M["skin"], vendor, (0.92, 0.84, 1.06))
    sphere("Nose", (0.79, -0.205, 2.02), 0.075, M["skin"], vendor, (0.85, 1.0, 0.85))
    box("Mustache", (0.79, -0.276, 1.94), (0.25, 0.035, 0.07), M["hair"], 0.03, vendor)

    # Cap: blue crown, cream front card, small pink/blue identity bead.
    sphere("CapCrown", (0.79, 0.10, 2.29), 0.30, M["blue"], vendor, (1.0, 0.90, 0.46))
    box("CapFront", (0.79, -0.17, 2.27), (0.34, 0.08, 0.22), M["cream"], 0.035, vendor)
    box("CapBrim", (0.79, -0.35, 2.20), (0.42, 0.28, 0.055), M["blue_dark"], 0.06, vendor)
    sphere("CapLogo", (0.79, -0.217, 2.29), 0.055, M["pink"], vendor, (0.85, 0.45, 1.0))

    # Head pivot allows a subtle idle glance without shifting ground anchor.
    head_pivot = empty("HeadPivot", (0.79, 0.08, 1.82), vendor)
    for name in ("Head", "Nose", "Mustache", "CapCrown", "CapFront", "CapBrim", "CapLogo"):
        parent_keep_world(bpy.data.objects[name], head_pivot)

    # Articulated arm chains.  Geometry is intentionally chunky/readable.
    def arm_chain(prefix, shoulder_loc, side_sign):
        shoulder = empty(prefix + "Shoulder", shoulder_loc, vendor)
        upper = cylinder(prefix + "Upper", (0.0, 0.0, -0.26), 0.11, 0.52, M["shirt"], parent=shoulder)
        elbow = empty(prefix + "Elbow", (0.0, 0.0, -0.52), shoulder)
        fore = cylinder(prefix + "Fore", (0.0, 0.0, -0.24), 0.095, 0.48, M["skin"], parent=elbow)
        hand = sphere(prefix + "Hand", (0.0, 0.0, -0.52), 0.12, M["skin"], elbow, (0.9, 0.8, 1.0))
        shoulder.rotation_mode = "XYZ"
        elbow.rotation_mode = "XYZ"
        shoulder.rotation_euler = (0.0, math.radians(side_sign * 12), math.radians(side_sign * 16))
        return shoulder, elbow, hand

    left_shoulder, left_elbow, left_hand = arm_chain("Arm_L_", (0.44, 0.10, 1.64), -1)
    right_shoulder, right_elbow, right_hand = arm_chain("Arm_R_", (1.14, 0.10, 1.64), 1)

    # Towel hint at waist.
    box("Towel", (1.13, -0.08, 1.05), (0.16, 0.05, 0.50), M["cream"], 0.025, vendor)
    box("TowelStripe1", (1.13, -0.112, 0.93), (0.15, 0.015, 0.035), M["pink"], 0.01, vendor)
    box("TowelStripe2", (1.13, -0.112, 0.86), (0.15, 0.015, 0.035), M["pink"], 0.01, vendor)

    return {
        "root": vendor,
        "head": head_pivot,
        "left_shoulder": left_shoulder,
        "left_elbow": left_elbow,
        "left_hand": left_hand,
        "right_shoulder": right_shoulder,
        "right_elbow": right_elbow,
        "right_hand": right_hand,
    }


def set_rot(obj, frame, xyz_deg):
    obj.rotation_euler = tuple(math.radians(v) for v in xyz_deg)
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def animate_vendor(rig):
    scene = bpy.context.scene
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS

    head = rig["head"]
    ls, le = rig["left_shoulder"], rig["left_elbow"]
    rs, re = rig["right_shoulder"], rig["right_elbow"]

    # Idle: neutral -> glance -> neutral.  Conservative motion only.
    set_rot(head, 1, (0, 0, 0))
    set_rot(head, 3, (0, 0, -8))
    set_rot(head, 4, (0, 0, 0))
    set_rot(ls, 1, (0, -12, -16)); set_rot(le, 1, (0, 0, 0))
    set_rot(rs, 1, (0, 12, 16)); set_rot(re, 1, (0, 0, 0))
    set_rot(ls, 4, (0, -12, -16)); set_rot(le, 4, (0, 0, 0))
    set_rot(rs, 4, (0, 12, 16)); set_rot(re, 4, (0, 0, 0))

    # Greeting/wave: right arm rises; elbow bends; head follows the passer-by.
    set_rot(head, 5, (0, 0, -7))
    set_rot(rs, 5, (42, -10, -50)); set_rot(re, 5, (-35, 0, -10))
    set_rot(rs, 6, (48, -8, -62)); set_rot(re, 6, (-52, 0, 8))
    set_rot(rs, 7, (43, -7, -48)); set_rot(re, 7, (-40, 0, -10))
    set_rot(head, 8, (0, 0, 0))
    set_rot(rs, 8, (0, 12, 16)); set_rot(re, 8, (0, 0, 0))

    # Serve: left arm reaches over the counter while right arm supports the cup.
    set_rot(head, 9, (10, 0, 7))
    set_rot(ls, 9, (25, -42, 34)); set_rot(le, 9, (-48, 0, 18))
    set_rot(rs, 9, (16, 26, -26)); set_rot(re, 9, (-28, 0, -8))
    set_rot(ls, 10, (34, -52, 40)); set_rot(le, 10, (-62, 0, 20))
    set_rot(rs, 10, (18, 30, -30)); set_rot(re, 10, (-36, 0, -12))
    set_rot(ls, 11, (26, -44, 34)); set_rot(le, 11, (-50, 0, 17))
    set_rot(rs, 11, (14, 22, -22)); set_rot(re, 11, (-27, 0, -8))
    set_rot(head, 12, (0, 0, 0))
    set_rot(ls, 12, (0, -12, -16)); set_rot(le, 12, (0, 0, 0))
    set_rot(rs, 12, (0, 12, 16)); set_rot(re, 12, (0, 0, 0))

    # Linear interpolation avoids floaty cartoon easing at tiny sprite scale.
    for obj in (head, ls, le, rs, re):
        if obj.animation_data and obj.animation_data.action:
            for curve in obj.animation_data.action.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"


def build_scene(studio):
    bs.clear_scene()
    out_dir = os.path.abspath("out/wip/raspadinha_vendor_v1")
    scene = bs.configure_scene(studio, tuple(studio["render"]["sourceResolution"]), out_dir)
    scene.render.film_transparent = True

    M = {
        "blue": mat("RaspadinhaBlue", (0.035, 0.36, 0.78, 1)),
        "blue_dark": mat("RaspadinhaBlueDark", (0.025, 0.16, 0.34, 1)),
        "cyan": mat("RaspadinhaCyan", (0.02, 0.62, 0.95, 1)),
        "pink": mat("RaspadinhaPink", (0.94, 0.055, 0.28, 1)),
        "red": mat("SyrupRed", (0.78, 0.025, 0.035, 1)),
        "yellow": mat("SyrupYellow", (0.94, 0.65, 0.04, 1)),
        "green": mat("SyrupGreen", (0.05, 0.55, 0.17, 1)),
        "cream": mat("WarmCream", (0.92, 0.88, 0.76, 1)),
        "shirt": mat("VendorShirt", (0.87, 0.82, 0.69, 1)),
        "pants": mat("VendorPants", (0.035, 0.16, 0.29, 1)),
        "skin": mat("VendorSkin", (0.64, 0.31, 0.14, 1)),
        "hair": mat("VendorHair", (0.055, 0.035, 0.025, 1)),
        "dark": mat("DarkRubber", (0.035, 0.04, 0.05, 1)),
        "rubber": mat("WheelRubber", (0.025, 0.03, 0.035, 1), 0.88),
        "metal": mat("BrushedMetal", (0.46, 0.50, 0.54, 1), 0.42, 0.35),
        "metal_dark": mat("DarkMetal", (0.21, 0.24, 0.27, 1), 0.45, 0.35),
        "ice": mat("CrushedIce", (0.76, 0.91, 0.96, 1), 0.28),
    }

    root = empty("AssetRoot", (0, 0, 0), None)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["animationStates"] = "idle:1-4,greet:5-8,serve:9-12"
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"

    build_cart(root, M)
    rig = build_vendor(root, M)
    animate_vendor(rig)

    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    return scene, root


def main():
    args = args_from_blender()
    studio = bs.load_json(args.studio_preset)
    scene, root = build_scene(studio)

    direction_degrees = {"south": 0.0, "east": 90.0, "west": 270.0, "north": 180.0}
    root.rotation_euler[2] = math.radians(direction_degrees[args.preview_direction])
    bpy.context.view_layer.update()

    # Make the current WIP easy to inspect interactively.  No terrain object is
    # authored: the City Horizon map owns the ground.
    scene.frame_set(1)
    print(f"[raspadinha_wip] built {ASSET_ID}; frames={FRAME_START}-{FRAME_END}; dir={args.preview_direction}")
    print("[raspadinha_wip] groundIncludedInAsset=False; transparent scene enabled")

    if args.save_blend:
        target = Path(args.save_blend)
        target.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(target.resolve()))
        print(f"[raspadinha_wip] saved blend: {target}")


if __name__ == "__main__":
    main()
