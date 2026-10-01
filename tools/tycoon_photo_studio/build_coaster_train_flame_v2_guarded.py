"""Guarded builder for City Horizon coaster train Type 1 Flame/Radical V2.

V2 keeps the V1 mechanical contract but rebuilds the visible body silhouette: the side
shells are integrated into the tub, the flame graphics are smaller, the wheel gear is
more hidden, and the passenger cell is framed by a rear shoulder cowl and compact nose.
The goal is gameplay readability, not high-detail reference reproduction.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_coaster_track_guarded as track  # noqa: E402

ASSET_ID = "ride.coaster.train_flame_v2"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_STYLE_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.80
CAR_WIDTH = track.TILE * 0.58
CAR_GAP = track.TILE * 0.075
FLOOR_Z = track.RAIL_Z + 0.24
WHEEL_RADIUS = 0.078
WHEEL_DEPTH = 0.052
CAR_COUNT = 4


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def add_box(name, location, scale, material, role, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        mod = obj.modifiers.new("SoftEdges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def add_wheel(name, location, material):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=WHEEL_RADIUS,
        depth=WHEEL_DEPTH,
        location=location,
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    scene_gate.tag(obj, "coaster.train.wheel")
    return obj


def add_profile_prism(name, x_center, thickness, y_center, profile, material, role, bevel=0.0):
    x0 = x_center - thickness * 0.5
    x1 = x_center + thickness * 0.5
    verts = []
    for x in (x0, x1):
        verts.extend((x, y_center + y, z) for y, z in profile)
    n = len(profile)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if bevel > 0.0:
        mod = obj.modifiers.new("SoftEdges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def add_flame_mark(name, x_center, y_center, z_center, side, length, height, material):
    """Small five-point side mark; deliberately graphic rather than detailed."""
    depth = 0.014
    x0 = x_center
    x1 = x_center + (depth if side > 0 else -depth)
    points = [
        (-0.48 * length, -0.22 * height),
        (0.18 * length, -0.20 * height),
        (0.48 * length, 0.02 * height),
        (0.06 * length, 0.02 * height),
        (-0.14 * length, 0.50 * height),
    ]
    verts = []
    for x in (x0, x1):
        verts.extend((x, y_center + y, z_center + z) for y, z in points)
    n = len(points)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    scene_gate.tag(obj, "coaster.train.decal")
    return obj


def build_car(index, y_center, lead, materials):
    body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat = materials
    authored = []
    prefix = f"FlameV2Car{index:02d}"

    # Deeper unified tub: one readable body mass instead of a flat platform.
    authored.append(add_box(
        f"{prefix}_Tub",
        (0.0, y_center, FLOOR_Z + 0.12),
        (CAR_WIDTH * 0.47, CAR_LENGTH * 0.45, 0.24),
        body_mat,
        "coaster.train.body",
        bevel=0.13,
    ))
    authored.append(add_box(
        f"{prefix}_Underbody",
        (0.0, y_center, track.RAIL_Z + 0.11),
        (CAR_WIDTH * 0.32, CAR_LENGTH * 0.34, 0.075),
        dark_mat,
        "coaster.train.chassis",
        bevel=0.03,
    ))

    # Side shells now rise mainly around the seat backs and taper toward the nose.
    side_x = CAR_WIDTH * 0.445
    side_profile = [
        (-CAR_LENGTH * 0.42, FLOOR_Z + 0.18),
        (-CAR_LENGTH * 0.35, FLOOR_Z + 0.48),
        (-CAR_LENGTH * 0.20, FLOOR_Z + 0.64),
        ( CAR_LENGTH * 0.02, FLOOR_Z + 0.62),
        ( CAR_LENGTH * 0.24, FLOOR_Z + 0.42),
        ( CAR_LENGTH * 0.41, FLOOR_Z + 0.22),
        ( CAR_LENGTH * 0.43, FLOOR_Z + 0.18),
    ]
    for side, x in ((-1, -side_x), (1, side_x)):
        authored.append(add_profile_prism(
            f"{prefix}_SideShell_{'L' if side < 0 else 'R'}",
            x,
            CAR_WIDTH * 0.105,
            y_center,
            side_profile,
            body_mat,
            "coaster.train.body",
            bevel=0.05,
        ))
        # Low skirt visually welds the shell into the tub.
        authored.append(add_box(
            f"{prefix}_SideSkirt_{'L' if side < 0 else 'R'}",
            (x, y_center + CAR_LENGTH * 0.02, FLOOR_Z + 0.18),
            (CAR_WIDTH * 0.065, CAR_LENGTH * 0.36, 0.13),
            body_mat,
            "coaster.train.body",
            bevel=0.045,
        ))
        outer_x = x + side * CAR_WIDTH * 0.060
        authored.append(add_flame_mark(
            f"{prefix}_FlameOrange_{'L' if side < 0 else 'R'}",
            outer_x,
            y_center + CAR_LENGTH * 0.06,
            FLOOR_Z + 0.34,
            side,
            CAR_LENGTH * 0.34,
            0.28,
            orange_mat,
        ))
        authored.append(add_flame_mark(
            f"{prefix}_FlameYellow_{'L' if side < 0 else 'R'}",
            outer_x + side * 0.002,
            y_center + CAR_LENGTH * 0.055,
            FLOOR_Z + 0.345,
            side,
            CAR_LENGTH * 0.20,
            0.17,
            yellow_mat,
        ))

    # Passenger cell: dark footwell, two bucket seats, and a rear shoulder cowl.
    seat_y = y_center - CAR_LENGTH * 0.06
    authored.append(add_box(
        f"{prefix}_Footwell",
        (0.0, y_center + CAR_LENGTH * 0.11, FLOOR_Z + 0.27),
        (CAR_WIDTH * 0.31, CAR_LENGTH * 0.16, 0.035),
        dark_mat,
        "coaster.train.interior",
        bevel=0.025,
    ))
    authored.append(add_box(
        f"{prefix}_RearShoulderCowl",
        (0.0, y_center - CAR_LENGTH * 0.31, FLOOR_Z + 0.48),
        (CAR_WIDTH * 0.43, CAR_LENGTH * 0.085, 0.23),
        body_mat,
        "coaster.train.body",
        bevel=0.09,
    ))

    seat_x = (-CAR_WIDTH * 0.205, CAR_WIDTH * 0.205)
    for col, x in enumerate(seat_x):
        authored.append(add_box(
            f"{prefix}_Seat_{col}",
            (x, seat_y, FLOOR_Z + 0.31),
            (CAR_WIDTH * 0.155, CAR_LENGTH * 0.145, 0.15),
            seat_mat,
            "coaster.train.seat",
            bevel=0.06,
        ))
        authored.append(add_box(
            f"{prefix}_Backrest_{col}",
            (x, seat_y - CAR_LENGTH * 0.095, FLOOR_Z + 0.56),
            (CAR_WIDTH * 0.155, 0.055, 0.25),
            seat_mat,
            "coaster.train.seat",
            bevel=0.06,
        ))
        authored.append(add_box(
            f"{prefix}_Headrest_{col}",
            (x, seat_y - CAR_LENGTH * 0.10, FLOOR_Z + 0.80),
            (CAR_WIDTH * 0.115, 0.050, 0.085),
            dark_mat,
            "coaster.train.seat",
            bevel=0.04,
        ))

    # Compact restraint across both seats with short vertical pivots.
    authored.append(add_box(
        f"{prefix}_LapBar",
        (0.0, seat_y + CAR_LENGTH * 0.085, FLOOR_Z + 0.49),
        (CAR_WIDTH * 0.34, 0.032, 0.032),
        metal_mat,
        "coaster.train.restraint",
        bevel=0.014,
    ))
    for x in (-CAR_WIDTH * 0.315, CAR_WIDTH * 0.315):
        authored.append(add_box(
            f"{prefix}_LapArm_{'L' if x < 0 else 'R'}",
            (x, seat_y + CAR_LENGTH * 0.045, FLOOR_Z + 0.40),
            (0.026, 0.026, 0.11),
            metal_mat,
            "coaster.train.restraint",
            bevel=0.010,
        ))

    # A compact front cowl makes every car feel enclosed; the lead car gets a stronger nose.
    front_y = y_center + CAR_LENGTH * 0.38
    authored.append(add_box(
        f"{prefix}_FrontCowl",
        (0.0, front_y, FLOOR_Z + 0.32),
        (CAR_WIDTH * (0.46 if lead else 0.43), CAR_LENGTH * (0.11 if lead else 0.075), 0.22),
        body_mat,
        "coaster.train.body",
        bevel=0.14 if lead else 0.08,
    ))
    if lead:
        authored.append(add_box(
            f"{prefix}_LeadApron",
            (0.0, y_center + CAR_LENGTH * 0.455, FLOOR_Z + 0.18),
            (CAR_WIDTH * 0.40, CAR_LENGTH * 0.045, 0.11),
            body_mat,
            "coaster.train.body",
            bevel=0.08,
        ))
        authored.append(add_box(
            f"{prefix}_FrontBadge",
            (0.0, y_center + CAR_LENGTH * 0.462, FLOOR_Z + 0.33),
            (CAR_WIDTH * 0.17, 0.015, 0.055),
            badge_mat,
            "coaster.train.accent",
            bevel=0.016,
        ))

    # Wheel hardware is intentionally small and dark under the body.
    wheel_y = (-CAR_LENGTH * 0.26, CAR_LENGTH * 0.26)
    wheel_x = (-track.GAUGE * 0.49, track.GAUGE * 0.49)
    for yi, local_y in enumerate(wheel_y):
        for xi, x in enumerate(wheel_x):
            authored.append(add_wheel(
                f"{prefix}_Wheel_{yi}_{xi}",
                (x, y_center + local_y, track.RAIL_Z + 0.010),
                wheel_mat,
            ))

    return authored


def build_train():
    body_mat = bs.make_material("FlameV2Body", (0.56, 0.035, 0.025, 1.0), 0.44, 0.18)
    dark_mat = bs.make_material("FlameV2DarkTrim", (0.026, 0.031, 0.040, 1.0), 0.66)
    seat_mat = bs.make_material("FlameV2Seat", (0.018, 0.022, 0.029, 1.0), 0.74)
    metal_mat = bs.make_material("FlameV2Metal", (0.22, 0.25, 0.28, 1.0), 0.40, 0.36)
    wheel_mat = bs.make_material("FlameV2Wheel", (0.014, 0.018, 0.024, 1.0), 0.80)
    orange_mat = bs.make_material("FlameV2Orange", (0.93, 0.20, 0.020, 1.0), 0.52)
    yellow_mat = bs.make_material("FlameV2Yellow", (1.00, 0.58, 0.030, 1.0), 0.48)
    badge_mat = bs.make_material("FlameV2Badge", (0.76, 0.68, 0.48, 1.0), 0.54)
    materials = (body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat)

    authored = []
    pitch = CAR_LENGTH + CAR_GAP
    center_offset = (CAR_COUNT - 1) * pitch * 0.5
    centers = []

    for index in range(CAR_COUNT):
        y_center = center_offset - index * pitch
        centers.append(y_center)
        authored.extend(build_car(index, y_center, lead=(index == 0), materials=materials))

    for index in range(CAR_COUNT - 1):
        y_mid = (centers[index] + centers[index + 1]) * 0.5
        authored.append(add_box(
            f"FlameV2Coupler_{index}",
            (0.0, y_mid, track.RAIL_Z + 0.10),
            (0.045, CAR_GAP * 0.52, 0.045),
            metal_mat,
            "coaster.train.coupler",
            bevel=0.010,
        ))

    return authored


def write_metadata(output: Path):
    payload = {
        "contract": TRAIN_CONTRACT,
        "assetId": ASSET_ID,
        "styleId": STYLE_ID,
        "trackContract": "CH_COASTER_TRACK_V1",
        "pose": "flat_south",
        "carCount": CAR_COUNT,
        "passengerCapacityPerCar": 2,
        "passengerCapacityTotal": CAR_COUNT * 2,
        "rowsPerCar": 1,
        "seatsPerRow": 2,
        "trackGauge": track.GAUGE,
        "carLength": CAR_LENGTH,
        "carWidth": CAR_WIDTH,
        "carGap": CAR_GAP,
        "anchor": [0.0, 0.0, track.RAIL_Z],
        "visualIntent": "stylized_flame_radical_integrated_body_v2",
        "detailPolicy": "strong_silhouette_low_micro_detail",
        "revisionNotes": [
            "integrated side shells into tub",
            "reduced flame graphic size",
            "added rear shoulder cowl and footwell",
            "smaller hidden wheel hardware",
            "stronger lead-car nose",
        ],
        "prototypeStatus": "visual_review_only",
    }
    (output / "train_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_studio_metadata(output: Path, args):
    payload = {
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": args.stage,
        "runtimeRepresentation": "2D_RGBA_pre_rendered",
    }
    (output / "studio_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    scene = bs.configure_scene(studio, (640, 640), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored = build_train()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trainContract"] = TRAIN_CONTRACT
    root["styleId"] = STYLE_ID
    root["trackContract"] = "CH_COASTER_TRACK_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.16)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / "proxy_south.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="south",
        )
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
            raise ValueError("The final bake requires the reviewed SOUTH proxy SHA-256")
        (output / "proxy_approval.json").write_text(json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": ASSET_ID,
            "reviewed": True,
            "proxySha256": args.approval_proxy_sha,
        }, indent=2), encoding="utf-8")
        write_studio_metadata(output, args)
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            scene_gate.render_proxy(
                scene=scene,
                authored=authored,
                output_path=output / f"train_{direction['id']}.png",
                profile=profile,
                asset_id=ASSET_ID,
                direction=direction["id"],
            )


if __name__ == "__main__":
    main()
