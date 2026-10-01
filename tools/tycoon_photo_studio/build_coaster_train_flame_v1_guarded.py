"""Guarded builder for City Horizon coaster train Type 1: Flame/Radical.

The reference image is used only as a style guide. This builder intentionally keeps
geometry simple enough for small isometric 2D sprites: a strong closed-car silhouette,
raised side shells, dark bucket seats, simple restraints and large flame accents.
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

ASSET_ID = "ride.coaster.train_flame_v1"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_STYLE_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.78
CAR_WIDTH = track.TILE * 0.60
CAR_GAP = track.TILE * 0.08
FLOOR_Z = track.RAIL_Z + 0.24
WHEEL_RADIUS = 0.095
WHEEL_DEPTH = 0.060
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


def add_wheel(name, location, material, role):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20,
        radius=WHEEL_RADIUS,
        depth=WHEEL_DEPTH,
        location=location,
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def add_profile_prism(name, x_center, thickness, y_center, profile, material, role, bevel=0.0):
    """Extrude a simple Y/Z profile across X for a stylized side shell."""
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


def add_flame(name, x_center, y_center, z_center, side, scale, material):
    """A tiny triangular prism used as a deliberately simple flame graphic."""
    depth = 0.018
    sx = depth if side > 0 else -depth
    x0 = x_center
    x1 = x_center + sx
    sy = 0.28 * scale
    sz = 0.18 * scale
    verts = [
        (x0, y_center - sy, z_center - sz),
        (x0, y_center + sy, z_center - sz * 0.25),
        (x0, y_center - sy * 0.15, z_center + sz),
        (x1, y_center - sy, z_center - sz),
        (x1, y_center + sy, z_center - sz * 0.25),
        (x1, y_center - sy * 0.15, z_center + sz),
    ]
    faces = [(0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]
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
    prefix = f"FlameCar{index:02d}"

    # Closed low tub: the main silhouette, deliberately much simpler than the reference.
    authored.append(add_box(
        f"{prefix}_Tub",
        (0.0, y_center, FLOOR_Z + 0.10),
        (CAR_WIDTH * 0.47, CAR_LENGTH * 0.44, 0.20),
        body_mat,
        "coaster.train.body",
        bevel=0.11,
    ))
    authored.append(add_box(
        f"{prefix}_Underbody",
        (0.0, y_center, track.RAIL_Z + 0.12),
        (CAR_WIDTH * 0.36, CAR_LENGTH * 0.34, 0.09),
        dark_mat,
        "coaster.train.chassis",
        bevel=0.035,
    ))

    # Raised side shells make the car read as a proper molded coaster vehicle.
    side_x = CAR_WIDTH * 0.47
    profile = [
        (-CAR_LENGTH * 0.42, FLOOR_Z + 0.16),
        (-CAR_LENGTH * 0.34, FLOOR_Z + 0.46),
        (-CAR_LENGTH * 0.12, FLOOR_Z + 0.58),
        ( CAR_LENGTH * 0.25, FLOOR_Z + 0.55),
        ( CAR_LENGTH * 0.40, FLOOR_Z + 0.30),
        ( CAR_LENGTH * 0.42, FLOOR_Z + 0.16),
    ]
    for side, x in ((-1, -side_x), (1, side_x)):
        authored.append(add_profile_prism(
            f"{prefix}_SideShell_{'L' if side < 0 else 'R'}",
            x,
            CAR_WIDTH * 0.055,
            y_center,
            profile,
            body_mat,
            "coaster.train.body",
            bevel=0.035,
        ))

        # Two large readable flame marks instead of detailed decals.
        outer_x = x + side * CAR_WIDTH * 0.035
        authored.append(add_flame(
            f"{prefix}_FlameOrange_{'L' if side < 0 else 'R'}",
            outer_x,
            y_center + CAR_LENGTH * 0.03,
            FLOOR_Z + 0.36,
            side,
            CAR_LENGTH * 0.82,
            orange_mat,
        ))
        authored.append(add_flame(
            f"{prefix}_FlameYellow_{'L' if side < 0 else 'R'}",
            outer_x + side * 0.002,
            y_center + CAR_LENGTH * 0.01,
            FLOOR_Z + 0.37,
            side,
            CAR_LENGTH * 0.48,
            yellow_mat,
        ))

    # Raised front cowl; the lead car gets a stronger rounded nose and simple badge.
    front_y = y_center + CAR_LENGTH * 0.39
    authored.append(add_box(
        f"{prefix}_FrontCowl",
        (0.0, front_y, FLOOR_Z + 0.34),
        (CAR_WIDTH * (0.47 if lead else 0.44), CAR_LENGTH * 0.085, 0.29),
        body_mat,
        "coaster.train.body",
        bevel=0.12 if lead else 0.07,
    ))
    if lead:
        authored.append(add_box(
            f"{prefix}_FrontBadge",
            (0.0, front_y + CAR_LENGTH * 0.088, FLOOR_Z + 0.34),
            (CAR_WIDTH * 0.20, 0.018, 0.075),
            badge_mat,
            "coaster.train.accent",
            bevel=0.018,
        ))

    # One two-seat row keeps the final sprite readable at gameplay size.
    seat_y = y_center - CAR_LENGTH * 0.05
    seat_x = (-CAR_WIDTH * 0.21, CAR_WIDTH * 0.21)
    for col, x in enumerate(seat_x):
        authored.append(add_box(
            f"{prefix}_Seat_{col}",
            (x, seat_y, FLOOR_Z + 0.30),
            (CAR_WIDTH * 0.16, CAR_LENGTH * 0.16, 0.16),
            seat_mat,
            "coaster.train.seat",
            bevel=0.055,
        ))
        authored.append(add_box(
            f"{prefix}_Backrest_{col}",
            (x, seat_y - CAR_LENGTH * 0.10, FLOOR_Z + 0.55),
            (CAR_WIDTH * 0.16, 0.060, 0.25),
            seat_mat,
            "coaster.train.seat",
            bevel=0.055,
        ))
        authored.append(add_box(
            f"{prefix}_Headrest_{col}",
            (x, seat_y - CAR_LENGTH * 0.105, FLOOR_Z + 0.79),
            (CAR_WIDTH * 0.12, 0.052, 0.09),
            dark_mat,
            "coaster.train.seat",
            bevel=0.04,
        ))

    # Simple U-like lap restraint: one readable bar with two support arms.
    authored.append(add_box(
        f"{prefix}_LapBar",
        (0.0, seat_y + CAR_LENGTH * 0.10, FLOOR_Z + 0.49),
        (CAR_WIDTH * 0.36, 0.036, 0.036),
        metal_mat,
        "coaster.train.restraint",
        bevel=0.014,
    ))
    for x in (-CAR_WIDTH * 0.33, CAR_WIDTH * 0.33):
        authored.append(add_box(
            f"{prefix}_LapArm_{'L' if x < 0 else 'R'}",
            (x, seat_y + CAR_LENGTH * 0.055, FLOOR_Z + 0.39),
            (0.028, 0.028, 0.12),
            metal_mat,
            "coaster.train.restraint",
            bevel=0.012,
        ))

    # Compact wheel sets stay mostly in shadow under the molded body.
    wheel_y = (-CAR_LENGTH * 0.27, CAR_LENGTH * 0.27)
    wheel_x = (-track.GAUGE * 0.50, track.GAUGE * 0.50)
    for yi, local_y in enumerate(wheel_y):
        for xi, x in enumerate(wheel_x):
            authored.append(add_wheel(
                f"{prefix}_Wheel_{yi}_{xi}",
                (x, y_center + local_y, track.RAIL_Z + 0.015),
                wheel_mat,
                "coaster.train.wheel",
            ))

    return authored


def build_train():
    body_mat = bs.make_material("FlameBody", (0.56, 0.035, 0.025, 1.0), 0.42, 0.20)
    dark_mat = bs.make_material("FlameDarkTrim", (0.030, 0.036, 0.045, 1.0), 0.64)
    seat_mat = bs.make_material("FlameSeat", (0.020, 0.025, 0.032, 1.0), 0.72)
    metal_mat = bs.make_material("FlameMetal", (0.24, 0.27, 0.30, 1.0), 0.36, 0.42)
    wheel_mat = bs.make_material("FlameWheel", (0.018, 0.022, 0.028, 1.0), 0.78)
    orange_mat = bs.make_material("FlameOrange", (0.95, 0.22, 0.025, 1.0), 0.50)
    yellow_mat = bs.make_material("FlameYellow", (1.00, 0.62, 0.035, 1.0), 0.46)
    badge_mat = bs.make_material("FlameBadge", (0.78, 0.70, 0.50, 1.0), 0.52)
    materials = (body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat)

    authored = []
    pitch = CAR_LENGTH + CAR_GAP
    center_offset = (CAR_COUNT - 1) * pitch * 0.5
    centers = []

    for index in range(CAR_COUNT):
        y_center = center_offset - index * pitch
        centers.append(y_center)
        authored.extend(build_car(index, y_center, lead=(index == 0), materials=materials))

    # Couplers remain compact and nearly hidden between bodies.
    for index in range(CAR_COUNT - 1):
        y_mid = (centers[index] + centers[index + 1]) * 0.5
        authored.append(add_box(
            f"FlameCoupler_{index}",
            (0.0, y_mid, track.RAIL_Z + 0.11),
            (0.050, CAR_GAP * 0.50, 0.050),
            metal_mat,
            "coaster.train.coupler",
            bevel=0.012,
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
        "visualIntent": "stylized_flame_radical_closed_body",
        "detailPolicy": "gameplay_readability_over_micro_detail",
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
