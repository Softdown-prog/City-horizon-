"""Guarded prototype builder for the City Horizon coaster train V0.

This stage upgrades the earlier single-car skeleton into a coherent four-car train
for SOUTH proxy review. It is still an art prototype, not the final runtime bake.
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

ASSET_ID = "ride.coaster.train_v0"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_V0"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.72
CAR_WIDTH = track.TILE * 0.58
CAR_GAP = track.TILE * 0.12
FLOOR_Z = track.RAIL_Z + 0.24
WHEEL_RADIUS = 0.13
WHEEL_DEPTH = 0.075
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
        vertices=24,
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


def add_cylinder_x(name, location, radius, depth, material, role):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=20,
        radius=radius,
        depth=depth,
        location=location,
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def build_car(index, y_center, lead, materials):
    body_mat, trim_mat, seat_mat, metal_mat, wheel_mat, accent_mat = materials
    authored = []
    prefix = f"Car{index:02d}"

    # Main tub: low body with raised side sills gives the car a proper vehicle silhouette.
    authored.append(add_box(
        f"{prefix}_Floor",
        (0.0, y_center, FLOOR_Z),
        (CAR_WIDTH * 0.48, CAR_LENGTH * 0.46, 0.10),
        body_mat,
        "coaster.train.body",
        bevel=0.07,
    ))
    side_x = CAR_WIDTH * 0.46
    for side, x in (("L", -side_x), ("R", side_x)):
        authored.append(add_box(
            f"{prefix}_Side_{side}",
            (x, y_center, FLOOR_Z + 0.22),
            (0.055, CAR_LENGTH * 0.40, 0.18),
            body_mat,
            "coaster.train.body",
            bevel=0.035,
        ))

    nose_y = y_center + CAR_LENGTH * 0.40
    authored.append(add_box(
        f"{prefix}_Nose",
        (0.0, nose_y, FLOOR_Z + 0.19),
        (CAR_WIDTH * (0.47 if lead else 0.43), CAR_LENGTH * 0.09, 0.18),
        accent_mat if lead else body_mat,
        "coaster.train.body",
        bevel=0.10 if lead else 0.06,
    ))
    authored.append(add_box(
        f"{prefix}_Rear",
        (0.0, y_center - CAR_LENGTH * 0.40, FLOOR_Z + 0.20),
        (CAR_WIDTH * 0.45, CAR_LENGTH * 0.07, 0.22),
        body_mat,
        "coaster.train.body",
        bevel=0.05,
    ))

    # Two rows x two seats. Seat bases are inset into the tub and backrests are taller.
    row_y = (-CAR_LENGTH * 0.18, CAR_LENGTH * 0.14)
    seat_x = (-CAR_WIDTH * 0.20, CAR_WIDTH * 0.20)
    for row, local_y in enumerate(row_y):
        y = y_center + local_y
        for col, x in enumerate(seat_x):
            authored.append(add_box(
                f"{prefix}_Seat_{row}_{col}",
                (x, y, FLOOR_Z + 0.23),
                (CAR_WIDTH * 0.16, CAR_LENGTH * 0.12, 0.13),
                seat_mat,
                "coaster.train.seat",
                bevel=0.035,
            ))
            authored.append(add_box(
                f"{prefix}_Backrest_{row}_{col}",
                (x, y - CAR_LENGTH * 0.08, FLOOR_Z + 0.45),
                (CAR_WIDTH * 0.16, 0.05, 0.22),
                seat_mat,
                "coaster.train.seat",
                bevel=0.03,
            ))

        # Safety bar plus two short pivots reads more mechanically than a floating rod.
        authored.append(add_box(
            f"{prefix}_LapBar_{row}",
            (0.0, y + CAR_LENGTH * 0.07, FLOOR_Z + 0.42),
            (CAR_WIDTH * 0.37, 0.032, 0.032),
            metal_mat,
            "coaster.train.restraint",
            bevel=0.012,
        ))
        for x in (-CAR_WIDTH * 0.34, CAR_WIDTH * 0.34):
            authored.append(add_box(
                f"{prefix}_LapPivot_{row}_{'L' if x < 0 else 'R'}",
                (x, y + CAR_LENGTH * 0.025, FLOOR_Z + 0.34),
                (0.025, 0.025, 0.10),
                metal_mat,
                "coaster.train.restraint",
                bevel=0.008,
            ))

    # Chassis and two visible wheel bogies.
    authored.append(add_box(
        f"{prefix}_Chassis",
        (0.0, y_center, track.RAIL_Z + 0.12),
        (track.GAUGE * 0.62, CAR_LENGTH * 0.34, 0.09),
        trim_mat,
        "coaster.train.chassis",
        bevel=0.025,
    ))

    wheel_y = (-CAR_LENGTH * 0.27, CAR_LENGTH * 0.27)
    wheel_x = (-track.GAUGE * 0.50, track.GAUGE * 0.50)
    for yi, local_y in enumerate(wheel_y):
        y = y_center + local_y
        for xi, x in enumerate(wheel_x):
            authored.append(add_wheel(
                f"{prefix}_Wheel_{yi}_{xi}",
                (x, y, track.RAIL_Z + 0.02),
                wheel_mat,
                "coaster.train.wheel",
            ))

    return authored


def build_train():
    body_mat = bs.make_material("TrainBody", (0.68, 0.065, 0.045, 1.0), 0.40, 0.24)
    trim_mat = bs.make_material("TrainTrim", (0.075, 0.085, 0.095, 1.0), 0.48, 0.22)
    seat_mat = bs.make_material("TrainSeat", (0.045, 0.060, 0.080, 1.0), 0.62)
    metal_mat = bs.make_material("TrainMetal", (0.30, 0.33, 0.35, 1.0), 0.32, 0.46)
    wheel_mat = bs.make_material("TrainWheel", (0.025, 0.030, 0.038, 1.0), 0.74)
    accent_mat = bs.make_material("TrainAccent", (0.88, 0.12, 0.055, 1.0), 0.36, 0.28)
    materials = (body_mat, trim_mat, seat_mat, metal_mat, wheel_mat, accent_mat)

    authored = []
    pitch = CAR_LENGTH + CAR_GAP
    center_offset = (CAR_COUNT - 1) * pitch * 0.5
    centers = []

    for index in range(CAR_COUNT):
        y_center = center_offset - index * pitch
        centers.append(y_center)
        authored.extend(build_car(index, y_center, lead=(index == 0), materials=materials))

    # Couplers connect the chassis mechanically instead of leaving floating gaps.
    for index in range(CAR_COUNT - 1):
        y_mid = (centers[index] + centers[index + 1]) * 0.5
        authored.append(add_box(
            f"CouplerBeam_{index}",
            (0.0, y_mid, track.RAIL_Z + 0.12),
            (0.055, CAR_GAP * 0.58, 0.055),
            metal_mat,
            "coaster.train.coupler",
            bevel=0.012,
        ))
        authored.append(add_cylinder_x(
            f"CouplerPin_{index}",
            (0.0, y_mid, track.RAIL_Z + 0.12),
            0.07,
            0.18,
            metal_mat,
            "coaster.train.coupler",
        ))

    return authored


def write_metadata(output: Path):
    payload = {
        "contract": TRAIN_CONTRACT,
        "assetId": ASSET_ID,
        "trackContract": "CH_COASTER_TRACK_V1",
        "pose": "flat_south",
        "carCount": CAR_COUNT,
        "passengerCapacityPerCar": 4,
        "passengerCapacityTotal": CAR_COUNT * 4,
        "rowsPerCar": 2,
        "seatsPerRow": 2,
        "trackGauge": track.GAUGE,
        "carLength": CAR_LENGTH,
        "carWidth": CAR_WIDTH,
        "carGap": CAR_GAP,
        "anchor": [0.0, 0.0, track.RAIL_Z],
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
