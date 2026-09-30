"""Guarded prototype builder for the simple City Horizon coaster car.

The first gate intentionally renders one empty SOUTH-facing flat car only.
No inverted poses are part of CH_COASTER_CAR_V0.
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_coaster_track_guarded as track  # noqa: E402

ASSET_ID = "ride.coaster.car_v0"
CAR_CONTRACT = "CH_COASTER_CAR_V0"
FOOTPRINT = {"widthTiles": 1, "depthTiles": 1}

CAR_LENGTH = track.TILE * 0.72
CAR_WIDTH = track.TILE * 0.58
BODY_HEIGHT = track.TILE * 0.30
FLOOR_Z = track.RAIL_Z + 0.24
WHEEL_RADIUS = 0.13
WHEEL_DEPTH = 0.075


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
        modifier = obj.modifiers.new("SoftEdges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def add_wheel(name, location, material, role):
    # Wheel axle runs along X, matching the coaster gauge across the track.
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


def build_car():
    body_mat = bs.make_material("CarBody", (0.72, 0.10, 0.08, 1.0), 0.42, 0.25)
    trim_mat = bs.make_material("CarTrim", (0.10, 0.12, 0.13, 1.0), 0.48, 0.20)
    seat_mat = bs.make_material("Seat", (0.08, 0.10, 0.12, 1.0), 0.65)
    metal_mat = bs.make_material("RestraintMetal", (0.34, 0.37, 0.38, 1.0), 0.34, 0.42)
    wheel_mat = bs.make_material("Wheel", (0.05, 0.055, 0.06, 1.0), 0.72)

    authored = []

    # Low open-top body so the silhouette reads clearly at gameplay size.
    authored.append(add_box(
        "CarFloor",
        (0.0, 0.0, FLOOR_Z),
        (CAR_WIDTH * 0.48, CAR_LENGTH * 0.46, 0.10),
        body_mat,
        "coaster.car.body",
        bevel=0.07,
    ))
    authored.append(add_box(
        "CarNose",
        (0.0, CAR_LENGTH * 0.39, FLOOR_Z + 0.16),
        (CAR_WIDTH * 0.46, CAR_LENGTH * 0.11, 0.18),
        body_mat,
        "coaster.car.body",
        bevel=0.08,
    ))
    authored.append(add_box(
        "CarRear",
        (0.0, -CAR_LENGTH * 0.40, FLOOR_Z + 0.20),
        (CAR_WIDTH * 0.46, CAR_LENGTH * 0.08, 0.24),
        body_mat,
        "coaster.car.body",
        bevel=0.05,
    ))

    # Two rows, two seats per row.
    row_y = (-CAR_LENGTH * 0.18, CAR_LENGTH * 0.14)
    seat_x = (-CAR_WIDTH * 0.20, CAR_WIDTH * 0.20)
    for row, y in enumerate(row_y):
        for col, x in enumerate(seat_x):
            authored.append(add_box(
                f"Seat_{row}_{col}",
                (x, y, FLOOR_Z + 0.23),
                (CAR_WIDTH * 0.16, CAR_LENGTH * 0.12, 0.13),
                seat_mat,
                "coaster.car.seat",
                bevel=0.035,
            ))
            authored.append(add_box(
                f"Backrest_{row}_{col}",
                (x, y - CAR_LENGTH * 0.08, FLOOR_Z + 0.43),
                (CAR_WIDTH * 0.16, 0.05, 0.20),
                seat_mat,
                "coaster.car.seat",
                bevel=0.025,
            ))

        authored.append(add_box(
            f"LapBar_{row}",
            (0.0, y + CAR_LENGTH * 0.07, FLOOR_Z + 0.42),
            (CAR_WIDTH * 0.37, 0.035, 0.035),
            metal_mat,
            "coaster.car.restraint",
            bevel=0.012,
        ))

    # Dark lower chassis centered over the rail gauge.
    authored.append(add_box(
        "Chassis",
        (0.0, 0.0, track.RAIL_Z + 0.12),
        (track.GAUGE * 0.62, CAR_LENGTH * 0.34, 0.09),
        trim_mat,
        "coaster.car.chassis",
        bevel=0.025,
    ))

    wheel_y = (-CAR_LENGTH * 0.27, CAR_LENGTH * 0.27)
    wheel_x = (-track.GAUGE * 0.50, track.GAUGE * 0.50)
    for yi, y in enumerate(wheel_y):
        for xi, x in enumerate(wheel_x):
            authored.append(add_wheel(
                f"Wheel_{yi}_{xi}",
                (x, y, track.RAIL_Z + 0.02),
                wheel_mat,
                "coaster.car.wheel",
            ))

    return authored


def write_metadata(output: Path):
    payload = {
        "contract": CAR_CONTRACT,
        "assetId": ASSET_ID,
        "trackContract": "CH_COASTER_TRACK_V1",
        "pose": "flat_south",
        "passengerCapacity": 4,
        "rows": 2,
        "seatsPerRow": 2,
        "inversionFramesRequired": False,
        "trackGauge": track.GAUGE,
        "carLength": CAR_LENGTH,
        "carWidth": CAR_WIDTH,
        "anchor": [0.0, 0.0, track.RAIL_Z],
    }
    (output / "car_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored = build_car()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["carContract"] = CAR_CONTRACT
    root["trackContract"] = "CH_COASTER_TRACK_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.18)
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
                output_path=output / f"car_{direction['id']}.png",
                profile=profile,
                asset_id=ASSET_ID,
                direction=direction["id"],
            )


if __name__ == "__main__":
    main()
