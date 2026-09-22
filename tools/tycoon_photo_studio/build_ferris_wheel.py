#!/usr/bin/env python3
"""Procedural Ferris wheel prototype for City Horizon.

The game remains 2D. Blender/CH Blender is only the deterministic authoring and
pre-render environment used to create the final RGBA sprites.
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
    return {
        key: bs.make_material(
            spec.get("name", key),
            spec["rgba"],
            float(spec.get("roughness", 0.72)),
            float(spec.get("metallic", 0.0)),
        )
        for key, spec in recipe["materials"].items()
    }


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
    bevel.width = min(float(radius) * 0.18, 0.04)
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def torus(name, location, major_radius, minor_radius, material, rotation=(0.0, 0.0, 0.0), parent=None):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=float(major_radius),
        minor_radius=float(minor_radius),
        major_segments=64,
        minor_segments=12,
        location=tuple(location),
        rotation=tuple(rotation),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    return obj


def cylinder_between(name, start, end, radius, material, parent=None, vertices=24):
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    midpoint = (a + b) * 0.5
    obj = cylinder(name, midpoint, radius, delta.length, material, parent=parent, vertices=vertices)
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    return obj


def build_railing(root, name, start, end, z0, height, radius, material, posts=4):
    a = Vector((start[0], start[1], z0))
    b = Vector((end[0], end[1], z0))
    for i in range(posts + 1):
        t = i / posts
        p = a.lerp(b, t)
        cylinder(
            f"{name}_Post_{i}",
            (p.x, p.y, z0 + height * 0.5),
            radius,
            height,
            material,
            parent=root,
            vertices=16,
        )
    cylinder_between(
        f"{name}_TopRail",
        (a.x, a.y, z0 + height),
        (b.x, b.y, z0 + height),
        radius,
        material,
        root,
        vertices=16,
    )
    cylinder_between(
        f"{name}_MidRail",
        (a.x, a.y, z0 + height * 0.52),
        (b.x, b.y, z0 + height * 0.52),
        radius * 0.88,
        material,
        root,
        vertices=16,
    )


def build_supports(root, g, mats):
    center = Vector((0.0, 0.0, float(g["wheelCenterZ"])))
    half_x = float(g["supportBaseHalfWidth"])
    half_y = float(g["supportBaseHalfDepth"])
    foot_z = float(g["supportFootZ"])
    support_r = float(g["supportRadius"])
    beam_h = float(g.get("baseBeamHeight", 0.24))
    beam_d = float(g.get("baseBeamDepth", 0.34))

    # Substantial structural sills visually anchor the A-frames instead of leaving
    # four isolated poles apparently planted directly into the terrain.
    for side_y, label in ((-half_y, "South"), (half_y, "North")):
        box(
            f"BaseBeam_{label}",
            (0.0, side_y, beam_h * 0.5),
            (half_x * 2.35, beam_d, beam_h),
            mats["platform"],
            0.055,
            root,
        )
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
                vertices=28,
            )
            box(
                f"Foot_{label}_{x_label}",
                (side_x, side_y, 0.11),
                (0.48, 0.52, 0.22),
                mats["dark"],
                0.06,
                root,
            )

    platform_w = float(g["entryPlatformWidth"])
    platform_d = float(g["entryPlatformDepth"])
    platform_h = float(g["entryPlatformHeight"])
    platform_y = -half_y - platform_d * 0.48
    box(
        "LoadingPlatform",
        (0.0, platform_y, platform_h * 0.5),
        (platform_w, platform_d, platform_h),
        mats["platform"],
        0.065,
        root,
    )

    # Three broad steps centered on the loading side.
    stair_w = float(g.get("stairWidth", 0.92))
    stair_d = float(g.get("stairDepth", 0.54))
    step_count = max(2, int(g.get("stairSteps", 3)))
    step_depth = stair_d / step_count
    for i in range(step_count):
        h = platform_h * (i + 1) / step_count
        y = platform_y - platform_d * 0.5 - stair_d + step_depth * (i + 0.5)
        box(
            f"LoadingStep_{i}",
            (0.0, y, h * 0.5),
            (stair_w, step_depth * 1.04, h),
            mats["platform"],
            0.035,
            root,
        )

    # Safety railings leave the stair opening clear and give the platform a real
    # amusement-park loading-zone read at gameplay scale.
    rail_h = float(g.get("railingHeight", 0.72))
    rail_r = float(g.get("railingRadius", 0.035))
    side_x = platform_w * 0.5 - 0.08
    front_y = platform_y - platform_d * 0.5 + 0.05
    back_y = platform_y + platform_d * 0.5 - 0.05
    build_railing(root, "RailLeft", (-side_x, front_y), (-side_x, back_y), platform_h, rail_h, rail_r, mats["frame"], 3)
    build_railing(root, "RailRight", (side_x, front_y), (side_x, back_y), platform_h, rail_h, rail_r, mats["frame"], 3)
    gate_half = stair_w * 0.58
    build_railing(root, "RailFrontLeft", (-side_x, front_y), (-gate_half, front_y), platform_h, rail_h, rail_r, mats["frame"], 2)
    build_railing(root, "RailFrontRight", (gate_half, front_y), (side_x, front_y), platform_h, rail_h, rail_r, mats["frame"], 2)

    # Cross-member under the axle helps the support structure read as engineered.
    cylinder_between(
        "AxleBraceSouthNorth",
        (0.0, -half_y * 0.82, center.z),
        (0.0, half_y * 0.82, center.z),
        support_r * 1.12,
        mats["hub"],
        root,
        vertices=28,
    )


def build_gondola(pivot, index, body_z, g, mats, accent_key):
    w = float(g["gondolaWidth"])
    d = float(g["gondolaDepth"])
    h = float(g["gondolaBodyHeight"])
    roof_h = float(g["gondolaRoofHeight"])

    # Rounded lower tub plus slightly wider floor and canopy make each gondola
    # feel like a proper cabin rather than a colored cube.
    box(
        f"GondolaFloor_{index:02d}",
        (0.0, 0.0, body_z - h * 0.44),
        (w * 1.04, d * 1.04, 0.10),
        mats["dark"],
        0.055,
        pivot,
    )
    box(
        f"GondolaBody_{index:02d}",
        (0.0, 0.0, body_z),
        (w, d, h),
        mats[accent_key],
        0.13,
        pivot,
    )
    box(
        f"GondolaRoof_{index:02d}",
        (0.0, 0.0, body_z + h * 0.55),
        (w * 1.14, d * 1.14, roof_h),
        mats["frame"],
        0.085,
        pivot,
    )

    # Chunky corner posts + front safety bar survive the final 2D downsample.
    post_r = 0.035
    post_h = h * 0.68
    post_z = body_z + h * 0.48
    front_y = -d * 0.48
    for side, x in (("L", -w * 0.39), ("R", w * 0.39)):
        cylinder(
            f"GondolaPost_{index:02d}_{side}",
            (x, front_y, post_z),
            post_r,
            post_h,
            mats["frame"],
            parent=pivot,
            vertices=14,
        )
    cylinder_between(
        f"GondolaSafetyBar_{index:02d}",
        (-w * 0.38, front_y, body_z + h * 0.52),
        (w * 0.38, front_y, body_z + h * 0.52),
        0.035,
        mats["hub"],
        pivot,
        vertices=14,
    )


def build_wheel(root, g, mats):
    radius = float(g["wheelRadius"])
    center_z = float(g["wheelCenterZ"])
    ring_r = float(g["ringTubeRadius"])
    spoke_r = float(g["spokeRadius"])
    hub_r = float(g["hubRadius"])
    axle_depth = float(g["axleDepth"])

    rotor = empty("WheelRotor", (0.0, 0.0, center_z), root)

    # Double rim gives the 2D sprite a stronger silhouette after downsample.
    for offset, scale in ((0.0, 1.0), (0.0, 0.91)):
        torus(
            "WheelOuterRing" if scale == 1.0 else "WheelInnerRing",
            (0.0, offset, 0.0),
            radius * scale,
            ring_r if scale == 1.0 else ring_r * 0.72,
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
        vertices=36,
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
            vertices=20,
        )
        cylinder(
            f"RimNode_{i:02d}",
            (x, 0.0, z),
            ring_r * 1.38,
            0.24,
            mats["hub"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=rotor,
            vertices=18,
        )

        pivot = empty(f"GondolaPivot_{i:02d}", (x, 0.0, z), rotor)
        gondola_pivots.append(pivot)

        cylinder(
            f"GondolaHanger_{i:02d}",
            (0.0, 0.0, -gondola_drop * 0.5),
            0.045,
            gondola_drop,
            mats["hub"],
            parent=pivot,
            vertices=18,
        )

        body_z = -gondola_drop - float(g["gondolaBodyHeight"]) * 0.48
        build_gondola(pivot, i, body_z, g, mats, accent_cycle[i % len(accent_cycle)])

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
    scene = bs.configure_scene(studio, (2048, 2048), str(Path(args.save_blend).parent))
    scene.render.film_transparent = True

    mats = make_materials(recipe)
    root = empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["groundIncludedInAsset"] = False
    root["runtimeTarget"] = "2D_RGBA_pre_rendered_sprite"
    root["footprint"] = "3x2"
    root["proceduralContract"] = recipe["contract"]

    build_supports(root, recipe["geometry"], mats)
    rotor, gondolas = build_wheel(root, recipe["geometry"], mats)
    animate(rotor, gondolas, recipe["animation"])

    direction_degrees = {"south": 0.0, "east": 90.0, "west": 270.0, "north": 180.0}
    root.rotation_euler[2] = math.radians(direction_degrees[args.preview_direction])

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)

    target = Path(args.save_blend)
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target.resolve()))

    print(
        f"[ferris_wheel] built {recipe['assetId']} | gondolas={len(gondolas)} | "
        f"frames={scene.frame_start}-{scene.frame_end} @ {scene.render.fps}fps | "
        f"direction={args.preview_direction} | runtimeTarget=2D_RGBA_pre_rendered_sprite"
    )


if __name__ == "__main__":
    main()
