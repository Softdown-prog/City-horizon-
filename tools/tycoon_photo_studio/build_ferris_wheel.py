#!/usr/bin/env python3
"""Procedural Ferris wheel prototype for City Horizon.

This is the first geometry/animation prototype for CITY_HORIZON_FERRIS_WHEEL_V1.
It intentionally reuses the frozen City Horizon Blender studio and produces no
terrain mesh. The game remains 2D; Blender is only the deterministic authoring
and bake environment.

Current prototype goals:
- original compact park Ferris wheel silhouette;
- 3x2 footprint;
- paired A-frame supports;
- 12 gondolas distributed radially;
- wheel rotation around the Y axis;
- gondolas counter-rotate so they remain upright;
- AssetRoot ready for SOUTH/EAST/WEST/NORTH rotation;
- transparent render background and canonical camera/light setup.

This script saves a .blend prototype first. Animation packaging/downsample is a
later gate after the geometry is visually accepted.
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_scene as bs  # noqa: E402


def blender_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--save-blend", required=True)
    parser.add_argument(
        "--preview-direction",
        choices=["south", "east", "west", "north"],
        default="south",
    )
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def empty(name, location=(0.0, 0.0, 0.0), parent=None):
    obj = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = tuple(location)
    obj.rotation_mode = "XYZ"
    if parent is not None:
        obj.parent = parent
    return obj


def make_materials(recipe):
    result = {}
    for key, spec in recipe["materials"].items():
        result[key] = bs.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.72)),
            float(spec.get("metallic", 0.0)),
        )
    return result


def box(name, location, dimensions, material, bevel=0.035, parent=None):
    obj = bs.add_box(name, location, dimensions, material, bevel)
    if parent is not None:
        obj.parent = parent
    return obj


def cylinder(name, location, radius, depth, material, rotation=(0.0, 0.0, 0.0), parent=None, vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=float(radius),
        depth=float(depth),
        location=tuple(location),
        rotation=tuple(rotation),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    bevel.width = min(float(radius) * 0.18, 0.035)
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def torus(name, location, major_radius, minor_radius, material, rotation=(0.0, 0.0, 0.0), parent=None):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=float(major_radius),
        minor_radius=float(minor_radius),
        major_segments=64,
        minor_segments=10,
        location=tuple(location),
        rotation=tuple(rotation),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def cylinder_between(name, start, end, radius, material, parent=None):
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    length = delta.length
    midpoint = (a + b) * 0.5
    obj = cylinder(name, midpoint, radius, length, material, parent=parent)
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def build_supports(root, g, mats):
    center = Vector((0.0, 0.0, float(g["wheelCenterZ"])))
    half_x = float(g["supportBaseHalfWidth"])
    half_y = float(g["supportBaseHalfDepth"])
    foot_z = float(g["supportFootZ"])
    support_r = float(g["supportRadius"])

    for side_y, label in ((-half_y, "South"), (half_y, "North")):
        for side_x, x_label in ((-half_x, "L"), (half_x, "R")):
            start = (side_x, side_y, foot_z)
            end = (0.0, side_y * 0.18, center.z)
            cylinder_between(
                f"Support_{label}_{x_label}",
                start,
                end,
                support_r,
                mats["frame"],
                root,
            )
            box(
                f"Foot_{label}_{x_label}",
                (side_x, side_y, 0.09),
                (0.38, 0.42, 0.18),
                mats["dark"],
                0.045,
                root,
            )

    platform_w = float(g["entryPlatformWidth"])
    platform_d = float(g["entryPlatformDepth"])
    platform_h = float(g["entryPlatformHeight"])
    box(
        "LoadingPlatform",
        (0.0, -half_y - platform_d * 0.48, platform_h / 2.0),
        (platform_w, platform_d, platform_h),
        mats["platform"],
        0.055,
        root,
    )


def build_wheel(root, g, mats):
    radius = float(g["wheelRadius"])
    center_z = float(g["wheelCenterZ"])
    ring_r = float(g["ringTubeRadius"])
    spoke_r = float(g["spokeRadius"])
    hub_r = float(g["hubRadius"])
    axle_depth = float(g["axleDepth"])

    rotor = empty("WheelRotor", (0.0, 0.0, center_z), root)

    # Torus defaults to the XY plane. Rotating 90 degrees about X places it in XZ.
    torus(
        "WheelOuterRing",
        (0.0, 0.0, 0.0),
        radius,
        ring_r,
        mats["wheel"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=rotor,
    )

    cylinder(
        "WheelHub",
        (0.0, 0.0, 0.0),
        hub_r,
        axle_depth,
        mats["hub"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=rotor,
        vertices=32,
    )

    gondola_pivots = []
    count = int(g["gondolaCount"])
    gondola_drop = float(g["gondolaDrop"])
    accent_cycle = ("accentA", "accentB", "accentC")

    for i in range(count):
        angle = 2.0 * math.pi * i / count
        x = math.sin(angle) * radius
        z = math.cos(angle) * radius

        cylinder_between(
            f"Spoke_{i:02d}",
            (0.0, 0.0, 0.0),
            (x, 0.0, z),
            spoke_r,
            mats["wheel"],
            rotor,
        )

        # Small rim node helps the wheel retain a readable radial rhythm after downsample.
        cylinder(
            f"RimNode_{i:02d}",
            (x, 0.0, z),
            ring_r * 1.30,
            0.18,
            mats["hub"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=rotor,
            vertices=16,
        )

        pivot = empty(f"GondolaPivot_{i:02d}", (x, 0.0, z), rotor)
        gondola_pivots.append(pivot)

        hanger_len = gondola_drop
        cylinder(
            f"GondolaHanger_{i:02d}",
            (0.0, 0.0, -hanger_len * 0.5),
            0.035,
            hanger_len,
            mats["hub"],
            parent=pivot,
            vertices=16,
        )

        body_z = -hanger_len - float(g["gondolaBodyHeight"]) * 0.48
        accent_key = accent_cycle[i % len(accent_cycle)]
        box(
            f"GondolaBody_{i:02d}",
            (0.0, 0.0, body_z),
            (
                float(g["gondolaWidth"]),
                float(g["gondolaDepth"]),
                float(g["gondolaBodyHeight"]),
            ),
            mats[accent_key],
            0.075,
            pivot,
        )
        box(
            f"GondolaRoof_{i:02d}",
            (0.0, 0.0, body_z + float(g["gondolaBodyHeight"]) * 0.53),
            (
                float(g["gondolaWidth"]) * 1.08,
                float(g["gondolaDepth"]) * 1.08,
                float(g["gondolaRoofHeight"]),
            ),
            mats["frame"],
            0.055,
            pivot,
        )

    return rotor, gondola_pivots


def animate(rotor, gondola_pivots, spec):
    scene = bpy.context.scene
    start = int(spec.get("frameStart", 1))
    end = int(spec.get("frameEnd", 12))
    fps = int(spec.get("fps", 8))
    revolutions = float(spec.get("revolutionsPerLoop", 1.0))

    scene.frame_start = start
    scene.frame_end = end
    scene.render.fps = fps
    rotor.rotation_mode = "XYZ"

    total = max(1, end - start + 1)
    for frame in range(start, end + 1):
        phase = (frame - start) / total
        angle = math.tau * revolutions * phase
        rotor.rotation_euler[1] = angle
        rotor.keyframe_insert(data_path="rotation_euler", frame=frame)

        if bool(spec.get("keepGondolasUpright", True)):
            for pivot in gondola_pivots:
                pivot.rotation_euler[1] = -angle
                pivot.keyframe_insert(data_path="rotation_euler", frame=frame)

    for obj in [rotor, *gondola_pivots]:
        if obj.animation_data and obj.animation_data.action:
            for curve in obj.animation_data.action.fcurves:
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"

    scene.frame_set(start)


def main():
    args = blender_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != "CITY_HORIZON_FERRIS_WHEEL_V1":
        raise RuntimeError("Expected CITY_HORIZON_FERRIS_WHEEL_V1 recipe")

    studio = bs.load_json(args.studio_preset)
    bs.clear_scene()

    # 3x2 attraction prototype: source resolution is deliberately supersampled.
    scene = bs.configure_scene(studio, (2048, 2048), str(Path(args.save_blend).parent))
    scene.render.film_transparent = True

    mats = make_materials(recipe)
    root = empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["footprint"] = "3x2"
    root["proceduralContract"] = recipe["contract"]

    build_supports(root, recipe["geometry"], mats)
    rotor, gondolas = build_wheel(root, recipe["geometry"], mats)
    animate(rotor, gondolas, recipe["animation"])

    direction_degrees = {"south": 0.0, "east": 90.0, "west": 270.0, "north": 180.0}
    root.rotation_euler[2] = math.radians(direction_degrees[args.preview_direction])

    # Fit camera to actual geometry while preserving the canonical camera orientation.
    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)

    target = Path(args.save_blend)
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target.resolve()))

    print(
        f"[ferris_wheel] built {recipe['assetId']} | gondolas={len(gondolas)} | "
        f"frames={scene.frame_start}-{scene.frame_end} @ {scene.render.fps}fps | "
        f"direction={args.preview_direction} | groundIncludedInAsset=False"
    )


if __name__ == "__main__":
    main()
