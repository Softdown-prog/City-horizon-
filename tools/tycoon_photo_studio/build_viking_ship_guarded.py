#!/usr/bin/env python3
"""Guarded CH Blender authoring entrypoint for the City Park Viking ship ride.

This is an offline procedural 3D authoring tool. Runtime remains pre-rendered 2D.
The first gate intentionally produces only preflight/proxy output; animation
frames are deferred until the user approves geometry, footprint and art direction.
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
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))

import build_scene as bs  # noqa: E402
import build_ferris_wheel as fw  # noqa: E402
import scene_gate  # noqa: E402

CONTRACT = "CITY_HORIZON_VIKING_SHIP_RIDE_V1"
ASSET_ID = "attraction.park_viking_ship.01"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--save-blend", default=None)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def sphere(name, location, scale, material, parent=None, segments=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        location=tuple(location),
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = tuple(scale)
    obj.data.materials.append(material)
    bevel = obj.modifiers.new(name="EdgeSoftening", type="BEVEL")
    bevel.width = 0.03
    bevel.segments = 2
    if parent is not None:
        obj.parent = parent
    return obj


def hull_sections(g):
    half_len = float(g["shipLength"]) * 0.5
    half_w = float(g["shipHalfWidth"])
    # x, half width, gunwale z, mid-side z, keel z.  Ends lift to a Viking prow.
    return [
        (-half_len, half_w * 0.25, -0.82, -1.58, -2.58),
        (-half_len * 0.86, half_w * 0.72, -1.20, -1.95, -3.08),
        (-half_len * 0.58, half_w * 0.94, -1.47, -2.20, -3.42),
        (-half_len * 0.24, half_w, -1.55, -2.31, -3.58),
        (0.0, half_w, -1.58, -2.35, -3.62),
        (half_len * 0.24, half_w, -1.55, -2.31, -3.58),
        (half_len * 0.58, half_w * 0.94, -1.47, -2.20, -3.42),
        (half_len * 0.86, half_w * 0.72, -1.20, -1.95, -3.08),
        (half_len, half_w * 0.25, -0.82, -1.58, -2.58),
    ]


def build_hull(pivot, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.92, mid_z),
            (x, -width * 0.34, bottom_z),
            (x, width * 0.34, bottom_z),
            (x, width * 0.92, mid_z),
            (x, width, top_z),
        ])

    faces = []
    for section_index in range(len(sections) - 1):
        a = section_index * ring_count
        b = (section_index + 1) * ring_count
        for ring_index in range(ring_count):
            nxt = (ring_index + 1) % ring_count
            faces.append((a + ring_index, a + nxt, b + nxt, b + ring_index))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    last = (len(sections) - 1) * ring_count
    faces.append(tuple(last + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new("VikingHullMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("VikingHull", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = pivot
    bevel = hull.modifiers.new(name="HullEdgeSoftening", type="BEVEL")
    bevel.width = 0.11
    bevel.segments = 3

    # Gunwale rails follow the curved upper outline instead of a rectangular box.
    for side, side_label in ((-1.0, "Front"), (1.0, "Back")):
        for index in range(len(sections) - 1):
            x0, w0, z0, _, _ = sections[index]
            x1, w1, z1, _, _ = sections[index + 1]
            fw.cylinder_between(
                f"Gunwale_{side_label}_{index:02d}",
                (x0, side * w0, z0 + 0.05),
                (x1, side * w1, z1 + 0.05),
                0.105,
                mats["woodLight"],
                pivot,
                vertices=18,
            )

    # Park-color fascia deliberately breaks the historical all-brown read.
    for side, label in ((-1.0, "Front"), (1.0, "Back")):
        y = side * (float(g["shipHalfWidth"]) + 0.015)
        fw.box(f"HullRedFascia_{label}", (0.0, y, -2.22), (8.85, 0.075, 0.54), mats["red"], 0.035, pivot)
        fw.box(f"HullWhiteStripe_{label}", (0.0, y + side * 0.018, -2.17), (8.40, 0.045, 0.105), mats["white"], 0.018, pivot)

    # A raised interior deck and dark longitudinal spine give a manufactured-ride read.
    fw.box("ShipDeck", (0.0, 0.0, float(g["shipDeckZ"])), (9.15, 2.46, 0.18), mats["woodDark"], 0.06, pivot)
    fw.box("ShipDeckCenterStrip", (0.0, 0.0, float(g["shipDeckZ"]) + 0.105), (8.80, 0.22, 0.06), mats["red"], 0.02, pivot)

    return hull, sections


def build_viking_prows(pivot, g, mats):
    half_len = float(g["shipLength"]) * 0.5
    for sign, label in ((-1.0, "Left"), (1.0, "Right")):
        points = [
            (sign * (half_len - 0.15), 0.0, -1.10),
            (sign * (half_len + 0.28), 0.0, -0.36),
            (sign * (half_len + 0.43), 0.0, 0.43),
        ]
        fw.cylinder_between(f"ProwNeck_{label}_A", points[0], points[1], 0.19, mats["woodLight"], pivot, vertices=18)
        fw.cylinder_between(f"ProwNeck_{label}_B", points[1], points[2], 0.16, mats["gold"], pivot, vertices=18)
        sphere(
            f"DragonHead_{label}",
            (sign * (half_len + 0.53), 0.0, 0.52),
            (0.43, 0.34, 0.31),
            mats["gold"],
            pivot,
        )
        # Two compact white horns read at proxy scale without turning the ride into a literal replica.
        fw.cylinder_between(
            f"DragonHorn_{label}_A",
            (sign * (half_len + 0.48), -0.18, 0.70),
            (sign * (half_len + 0.25), -0.29, 1.05),
            0.055,
            mats["white"],
            pivot,
            vertices=12,
        )
        fw.cylinder_between(
            f"DragonHorn_{label}_B",
            (sign * (half_len + 0.48), 0.18, 0.70),
            (sign * (half_len + 0.25), 0.29, 1.05),
            0.055,
            mats["white"],
            pivot,
            vertices=12,
        )


def build_shields(pivot, g, mats):
    x_positions = (-4.05, -2.72, -1.36, 0.0, 1.36, 2.72, 4.05)
    colours = ("red", "white", "steelDark", "red", "white", "steelDark", "red")
    y_base = float(g["shipHalfWidth"]) + 0.095
    for side, side_label in ((-1.0, "Front"), (1.0, "Back")):
        for index, (x, key) in enumerate(zip(x_positions, colours)):
            y = side * y_base
            fw.cylinder(
                f"Shield_{side_label}_{index:02d}",
                (x, y, -2.08),
                0.39,
                0.105,
                mats[key],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=pivot,
                vertices=24,
            )
            fw.cylinder(
                f"ShieldBoss_{side_label}_{index:02d}",
                (x, y + side * 0.075, -2.08),
                0.105,
                0.075,
                mats["gold"] if index % 2 == 0 else mats["steelMid"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=pivot,
                vertices=18,
            )


def build_seats_and_restraints(pivot, g, mats):
    rows = max(5, int(g.get("seatRows", 7)))
    usable = 7.20
    for index in range(rows):
        t = index / max(1, rows - 1)
        x = -usable * 0.5 + usable * t
        # Red upholstered seat with black back/restraint keeps the attraction colorful at 2D scale.
        fw.box(f"SeatBase_{index:02d}", (x, 0.0, -1.49), (0.66, 2.05, 0.26), mats["seatRed"], 0.08, pivot)
        fw.box(f"SeatBack_{index:02d}", (x + 0.22, 0.0, -1.13), (0.17, 2.03, 0.56), mats["steelDark"], 0.055, pivot)
        fw.cylinder_between(
            f"SafetyBar_{index:02d}",
            (x - 0.10, -0.93, -1.02),
            (x - 0.10, 0.93, -1.02),
            0.045,
            mats["steelLight"],
            pivot,
            vertices=14,
        )
        fw.cylinder_between(
            f"SafetyBarRed_{index:02d}",
            (x - 0.10, -0.44, -1.02),
            (x - 0.10, 0.44, -1.02),
            0.055,
            mats["red"],
            pivot,
            vertices=14,
        )


def build_base(root, g, mats):
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    base_h = float(g["baseHeight"])
    deck_w = float(g["deckWidth"])
    deck_d = float(g["deckDepth"])
    deck_h = float(g["deckHeight"])

    base = fw.box("BaseFrame", (0.0, 0.0, base_h * 0.5), (base_w, base_d, base_h), mats["steelDark"], 0.08, root)
    fw.box("BaseDeck", (0.0, 0.18, base_h + deck_h * 0.5), (deck_w, deck_d, deck_h), mats["platform"], 0.055, root)

    # Color blocking on the industrial base ties the attraction to the Ferris-wheel family.
    for side_y, label in ((-1.0, "Front"), (1.0, "Back")):
        y = side_y * (base_d * 0.5 - 0.05)
        fw.box(f"BaseRedFascia_{label}", (0.0, y, 0.40), (base_w - 0.55, 0.11, 0.48), mats["red"], 0.035, root)
        for index, x in enumerate((-5.6, -3.9, -2.2, -0.55, 1.1, 2.75, 4.4, 5.9)):
            fw.box(f"BaseWhiteMark_{label}_{index:02d}", (x, y + side_y * 0.065, 0.40), (0.48, 0.05, 0.19), mats["white"], 0.015, root)
    for side_x, label in ((-1.0, "Left"), (1.0, "Right")):
        x = side_x * (base_w * 0.5 - 0.05)
        fw.box(f"BaseRedFascia_{label}", (x, 0.0, 0.40), (0.11, base_d - 0.55, 0.48), mats["red"], 0.035, root)

    return base


def build_supports(root, g, mats):
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    radius = float(g["supportRadius"])

    support_objects = []
    for y, side_label in ((-half_y, "Front"), (half_y, "Back")):
        for x, x_label in ((-half_x, "L"), (half_x, "R")):
            support_objects.append(
                fw.cylinder_between(
                    f"Support_{side_label}_{x_label}",
                    (x, y, 0.34),
                    (0.0, y, pivot_z),
                    radius,
                    mats["steelDark"],
                    root,
                    vertices=28,
                )
            )
            fw.box(
                f"SupportFoot_{side_label}_{x_label}",
                (x, y, 0.31),
                (0.86, 0.92, 0.62),
                mats["steelMid"],
                0.09,
                root,
            )
            fw.box(
                f"SupportFootRed_{side_label}_{x_label}",
                (x, y - 0.02, 0.54),
                (0.58, 0.96, 0.16),
                mats["red"],
                0.035,
                root,
            )

        # Cream inner braces and a red cross-member make the structure read as a park machine.
        fw.cylinder_between(
            f"InnerBrace_{side_label}_L",
            (-half_x * 0.74, y, 0.58),
            (0.0, y, pivot_z * 0.88),
            radius * 0.55,
            mats["steelLight"],
            root,
            vertices=20,
        )
        fw.cylinder_between(
            f"InnerBrace_{side_label}_R",
            (half_x * 0.74, y, 0.58),
            (0.0, y, pivot_z * 0.88),
            radius * 0.55,
            mats["steelLight"],
            root,
            vertices=20,
        )
        fw.box(
            f"RedCrossMember_{side_label}",
            (0.0, y, 2.35),
            (6.65, 0.26, 0.30),
            mats["red"],
            0.06,
            root,
        )
        fw.box(
            f"WhiteCrossStripe_{side_label}",
            (0.0, y - (0.145 if y < 0 else -0.145), 2.35),
            (2.15, 0.045, 0.10),
            mats["white"],
            0.02,
            root,
        )

    # Main axle and visible colored collars.
    fw.cylinder(
        "MainAxle",
        (0.0, 0.0, pivot_z),
        float(g["axleRadius"]),
        float(g["axleDepth"]),
        mats["steelDark"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=root,
        vertices=36,
    )
    for y, label in ((-half_y, "Front"), (half_y, "Back")):
        fw.cylinder(
            f"AxleRedCollar_{label}",
            (0.0, y, pivot_z),
            float(g["axleRadius"]) * 1.42,
            0.32,
            mats["red"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=28,
        )
        fw.cylinder(
            f"AxleWhiteBand_{label}",
            (0.0, y + (-0.18 if y < 0 else 0.18), pivot_z),
            float(g["axleRadius"]) * 1.22,
            0.12,
            mats["white"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=root,
            vertices=28,
        )

    return support_objects


def build_loading_zone(root, g, mats):
    base_d = float(g["baseDepth"])
    width = float(g["loadingPlatformWidth"])
    depth = float(g["loadingPlatformDepth"])
    height = float(g["loadingPlatformHeight"])
    platform_y = -(base_d * 0.5 - depth * 0.56)
    fw.box("LoadingPlatform", (0.0, platform_y, height * 0.5 + 0.34), (width, depth, height), mats["platform"], 0.065, root)
    fw.box("LoadingPlatformRedInlay", (0.0, platform_y, 0.34 + height + 0.045), (width * 0.72, depth * 0.72, 0.09), mats["red"], 0.025, root)

    stair_w = float(g["stairWidth"])
    stair_d = float(g["stairDepth"])
    step_count = max(3, int(g["stairSteps"]))
    step_depth = stair_d / step_count
    front_edge = -base_d * 0.5 + 0.06
    for index in range(step_count):
        frac = (index + 1) / step_count
        step_h = (0.34 + height) * frac
        y = front_edge + step_depth * (index + 0.5)
        fw.box(
            f"BoardingStep_{index:02d}",
            (0.0, y, step_h * 0.5),
            (stair_w, step_depth * 1.05, step_h),
            mats["steelMid"],
            0.035,
            root,
        )
        fw.box(
            f"BoardingStepRedTread_{index:02d}",
            (0.0, y, step_h + 0.025),
            (stair_w * 0.96, step_depth * 0.92, 0.05),
            mats["red"],
            0.015,
            root,
        )
        fw.box(
            f"BoardingStepWhiteEdge_{index:02d}",
            (0.0, y - step_depth * 0.43, step_h + 0.055),
            (stair_w * 0.98, 0.055, 0.08),
            mats["white"],
            0.012,
            root,
        )

    rail_h = float(g["railingHeight"])
    rail_r = float(g["railingRadius"])
    side_x = width * 0.5 - 0.08
    front_y = platform_y - depth * 0.5 + 0.05
    back_y = platform_y + depth * 0.5 - 0.05
    fw.build_railing(root, "LoadRailLeft", (-side_x, front_y), (-side_x, back_y), 0.34 + height, rail_h, rail_r, mats["steelDark"], 4)
    fw.build_railing(root, "LoadRailRight", (side_x, front_y), (side_x, back_y), 0.34 + height, rail_h, rail_r, mats["steelDark"], 4)
    gate = stair_w * 0.62
    fw.build_railing(root, "LoadRailFrontL", (-side_x, front_y), (-gate, front_y), 0.34 + height, rail_h, rail_r, mats["steelDark"], 3)
    fw.build_railing(root, "LoadRailFrontR", (gate, front_y), (side_x, front_y), 0.34 + height, rail_h, rail_r, mats["steelDark"], 3)

    # A compact operator console is machinery, not a ticket booth.
    fw.box("OperatorConsole", (width * 0.40, platform_y + 0.18, 1.06), (0.72, 0.58, 1.10), mats["red"], 0.07, root)
    fw.box("OperatorConsoleTop", (width * 0.40, platform_y + 0.18, 1.64), (0.78, 0.64, 0.10), mats["steelDark"], 0.04, root)
    fw.box("OperatorConsoleFace", (width * 0.40, platform_y - 0.13, 1.16), (0.46, 0.035, 0.30), mats["teal"], 0.025, root)


def build_swing_group(root, g, mats):
    pivot_z = float(g["pivotZ"])
    pivot = fw.empty("SwingPivot", (0.0, 0.0, pivot_z), root)
    pivot["animationReady"] = True
    pivot["rotationAxis"] = "Y"
    pivot["runtimeLayer"] = "motion_overlay"

    half_y = float(g["supportHalfDepth"])
    # Four rigid hanger bars make the pendulum mechanism unmistakable.
    for x, x_label in ((-2.80, "L"), (2.80, "R")):
        for y_sign, side_label in ((-1.0, "Front"), (1.0, "Back")):
            fw.cylinder_between(
                f"SwingArm_{side_label}_{x_label}",
                (0.0, y_sign * (half_y - 0.32), 0.0),
                (x, y_sign * 1.22, -1.48),
                0.105,
                mats["steelMid"],
                pivot,
                vertices=20,
            )
            # Colored collar near the boat connection.
            sphere(
                f"SwingJoint_{side_label}_{x_label}",
                (x, y_sign * 1.22, -1.48),
                (0.18, 0.18, 0.18),
                mats["red"],
                pivot,
                segments=18,
                rings=10,
            )

    build_hull(pivot, g, mats)
    build_viking_prows(pivot, g, mats)
    build_shields(pivot, g, mats)
    build_seats_and_restraints(pivot, g, mats)
    pivot.rotation_euler[1] = math.radians(float(g.get("previewSwingDegrees", 0.0)))
    return pivot


def tag_scene(base, supports, root, pivot):
    scene_gate.tag(base, "attraction.base", ground_contact=True)
    for obj in supports:
        scene_gate.tag(obj, "attraction.support", ground_contact=True)
    platform = bpy.data.objects.get("LoadingPlatform")
    if platform is not None:
        scene_gate.tag(platform, "attraction.loading_platform", ground_contact=False)
    hull = bpy.data.objects.get("VikingHull")
    if hull is not None:
        scene_gate.tag(hull, "attraction.gondola", ground_contact=False)
    axle = bpy.data.objects.get("MainAxle")
    if axle is not None:
        scene_gate.tag(axle, "attraction.pivot_axle", ground_contact=False)
    root["motionLayerContract"] = "CH_ATTRACTION_MOTION_OVERLAY_V1"
    root["motionPivot"] = pivot.name


def build_for_gate(args):
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT} recipe")
    if recipe.get("assetId") != ASSET_ID:
        raise RuntimeError(f"Expected assetId {ASSET_ID}")
    if recipe.get("footprint", {}).get("widthTiles") != 5 or recipe.get("footprint", {}).get("depthTiles") != 4:
        raise RuntimeError("Viking ship first contract is locked to a 5x4 footprint")

    studio = bs.load_json(args.studio_preset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    scene = bs.configure_scene(studio, source_res, str(out))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    mats = fw.make_materials(recipe)
    root = fw.empty("AssetRoot")
    root["assetId"] = recipe["assetId"]
    root["assetType"] = recipe["assetType"]
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["styleContract"] = recipe.get("styleContract", "CH_TYCOON_MINIATURE_V1")
    root["runtimeRepresentation"] = "2D_RGBA_pre_rendered_sprite"
    root["groundIncludedInAsset"] = False
    root["footprint"] = "5x4"
    root["proceduralContract"] = CONTRACT
    root["directionPolicy"] = "rotate_asset_root_keep_camera_lights_fixed"
    root["animationPrepared"] = True
    root["animationFramesDefined"] = False

    base = build_base(root, recipe["geometry"], mats)
    supports = build_supports(root, recipe["geometry"], mats)
    build_loading_zone(root, recipe["geometry"], mats)
    pivot = build_swing_group(root, recipe["geometry"], mats)

    receiver = studio["shadowReceiver"]
    receiver_mat = bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    # Scale shadow receiver to the true 5x4 attraction footprint for authoring review.
    receiver_dims = [max(float(receiver["dimensions"][0]), 15.0), max(float(receiver["dimensions"][1]), 12.0), float(receiver["dimensions"][2])]
    ground = bs.add_box("ShadowReceiverPlane", receiver["location"], receiver_dims, receiver_mat, 0.0)

    authored = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj != ground]
    for obj in authored:
        obj["runtimeLayer"] = "motion_overlay" if _is_descendant_of(obj, pivot) else "static_base"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.13)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    tag_scene(base, supports, root, pivot)
    return recipe, studio, scene, root, pivot, ground, authored, out


def _is_descendant_of(obj, ancestor):
    current = obj.parent
    while current is not None:
        if current == ancestor:
            return True
        current = current.parent
    return False


def write_metadata(recipe, scene, out):
    payload = {
        "contract": CONTRACT,
        "assetId": recipe["assetId"],
        "stage": "geometry_proxy_v1",
        "cameraContract": "CH_CAMERA_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tile": [128, 64],
        "footprint": recipe["footprint"],
        "ticketBoothIncluded": False,
        "visualCompatibilityReference": "attraction.park_ferris_wheel.01",
        "animation": recipe["animation"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "recipe": "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.viking.json",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_guarded.py",
    }
    (out / "studio_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = build_for_gate(args)
    write_metadata(recipe, scene, out)

    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        save_blend(args.save_blend)
        print(f"[CH_GATE] Viking ship preflight PASS: {preflight_path}")
        return

    if args.stage == "proxy":
        bs.set_direction(root, bs.DIRECTIONS[0])
        bpy.context.view_layer.update()
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / "proxy_south.png",
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        (out / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        save_blend(args.save_blend)
        print(f"[CH_GATE] Viking ship SOUTH proxy ready: {proxy['sha256']}")
        return

    raise RuntimeError(
        "CH_VIKING_FINAL_NOT_DEFINED: first approve the geometry proxy, then define swing frame count/arc/fps before final bake"
    )


if __name__ == "__main__":
    main()
