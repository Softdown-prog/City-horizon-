"""Guarded builder for City Horizon coaster train Type 1 Flame/Radical V4.

V4 uses CH_SHAPE_AUTHORING_V1 open_tub_loft for each car. The passenger cell, floor
and side walls are one hollow body rather than a solid hull plus detached wall panels.
This is intended to read as a compact classic tycoon coaster car instead of a small
sports car while keeping the frozen City Horizon camera/studio contract.
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
import build_coaster_track_guarded as track  # noqa: E402
import scene_gate  # noqa: E402
import shape_authoring as shape  # noqa: E402

ASSET_ID = "ride.coaster.train_flame_v4"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_STYLE_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.82
CAR_WIDTH = track.TILE * 0.58
CAR_GAP = track.TILE * 0.075
FLOOR_Z = track.RAIL_Z + 0.24
WHEEL_RADIUS = 0.070
WHEEL_DEPTH = 0.046
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


def add_flame_marks(prefix, y_center, material_orange, material_yellow):
    authored = []
    x = CAR_WIDTH * 0.505
    orange_profile = [
        (-CAR_LENGTH * 0.13, FLOOR_Z + 0.31),
        ( CAR_LENGTH * 0.03, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.15, FLOOR_Z + 0.42),
        ( CAR_LENGTH * 0.08, FLOOR_Z + 0.33),
        ( CAR_LENGTH * 0.20, FLOOR_Z + 0.31),
        ( CAR_LENGTH * 0.03, FLOOR_Z + 0.27),
    ]
    yellow_profile = [
        (-CAR_LENGTH * 0.035, FLOOR_Z + 0.315),
        ( CAR_LENGTH * 0.055, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.115, FLOOR_Z + 0.382),
        ( CAR_LENGTH * 0.072, FLOOR_Z + 0.322),
        ( CAR_LENGTH * 0.135, FLOOR_Z + 0.31),
        ( CAR_LENGTH * 0.04, FLOOR_Z + 0.29),
    ]
    for side, label in ((-1, "L"), (1, "R")):
        authored.append(shape.add_profile_prism(
            f"{prefix}_FlameOrange_{label}",
            x_center=side * x,
            thickness=0.018,
            y_center=y_center,
            profile_yz=[(y - y_center, z) for y, z in orange_profile],
            material=material_orange,
            role="coaster.train.decal",
            bevel=0.0,
        ))
        authored.append(shape.add_profile_prism(
            f"{prefix}_FlameYellow_{label}",
            x_center=side * (x + 0.002),
            thickness=0.016,
            y_center=y_center,
            profile_yz=[(y - y_center, z) for y, z in yellow_profile],
            material=material_yellow,
            role="coaster.train.decal",
            bevel=0.0,
        ))
    return authored


def tub_sections(y_center: float, lead: bool) -> list[dict]:
    """One integrated open passenger tub with a high rear shoulder and low nose."""
    nose_outer = 0.28 if lead else 0.34
    nose_inner = 0.18 if lead else 0.22
    return [
        {
            "y": y_center - CAR_LENGTH * 0.48,
            "outerHalfWidth": CAR_WIDTH * 0.41,
            "innerHalfWidth": CAR_WIDTH * 0.28,
            "outerBottomZ": track.RAIL_Z + 0.09,
            "innerFloorZ": FLOOR_Z + 0.11,
            "rimZ": FLOOR_Z + 0.64,
            "innerRimZ": FLOOR_Z + 0.61,
        },
        {
            "y": y_center - CAR_LENGTH * 0.33,
            "outerHalfWidth": CAR_WIDTH * 0.49,
            "innerHalfWidth": CAR_WIDTH * 0.35,
            "outerBottomZ": track.RAIL_Z + 0.07,
            "innerFloorZ": FLOOR_Z + 0.10,
            "rimZ": FLOOR_Z + 0.74,
            "innerRimZ": FLOOR_Z + 0.70,
        },
        {
            "y": y_center - CAR_LENGTH * 0.10,
            "outerHalfWidth": CAR_WIDTH * 0.50,
            "innerHalfWidth": CAR_WIDTH * 0.36,
            "outerBottomZ": track.RAIL_Z + 0.07,
            "innerFloorZ": FLOOR_Z + 0.10,
            "rimZ": FLOOR_Z + 0.70,
            "innerRimZ": FLOOR_Z + 0.66,
        },
        {
            "y": y_center + CAR_LENGTH * 0.12,
            "outerHalfWidth": CAR_WIDTH * 0.49,
            "innerHalfWidth": CAR_WIDTH * 0.36,
            "outerBottomZ": track.RAIL_Z + 0.08,
            "innerFloorZ": FLOOR_Z + 0.11,
            "rimZ": FLOOR_Z + 0.57,
            "innerRimZ": FLOOR_Z + 0.53,
        },
        {
            "y": y_center + CAR_LENGTH * 0.31,
            "outerHalfWidth": CAR_WIDTH * 0.43,
            "innerHalfWidth": CAR_WIDTH * 0.30,
            "outerBottomZ": track.RAIL_Z + 0.11,
            "innerFloorZ": FLOOR_Z + 0.13,
            "rimZ": FLOOR_Z + 0.41,
            "innerRimZ": FLOOR_Z + 0.38,
        },
        {
            "y": y_center + CAR_LENGTH * 0.48,
            "outerHalfWidth": CAR_WIDTH * nose_outer,
            "innerHalfWidth": CAR_WIDTH * nose_inner,
            "outerBottomZ": track.RAIL_Z + 0.15,
            "innerFloorZ": FLOOR_Z + 0.17,
            "rimZ": FLOOR_Z + 0.30,
            "innerRimZ": FLOOR_Z + 0.28,
        },
    ]


def build_car(index, y_center, lead, materials):
    body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat = materials
    authored = []
    prefix = f"FlameV4Car{index:02d}"

    # The defining V4 primitive: floor, cavity, side walls, rear shoulder and nose are one mesh.
    authored.append(shape.add_open_tub_loft(
        f"{prefix}_OpenTub",
        sections=tub_sections(y_center, lead),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.045,
    ))

    # A dark floor pad makes the cavity read immediately at gameplay scale.
    authored.append(shape.add_rounded_box(
        f"{prefix}_FootwellPad",
        location=(0.0, y_center + CAR_LENGTH * 0.055, FLOOR_Z + 0.145),
        dimensions=(CAR_WIDTH * 0.58, CAR_LENGTH * 0.34, 0.050),
        material=dark_mat,
        role="coaster.train.interior",
        bevel=0.024,
    ))

    seat_y = y_center - CAR_LENGTH * 0.10
    for col, x in enumerate((-CAR_WIDTH * 0.19, CAR_WIDTH * 0.19)):
        authored.append(shape.add_rounded_box(
            f"{prefix}_Seat_{col}",
            location=(x, seat_y + CAR_LENGTH * 0.025, FLOOR_Z + 0.25),
            dimensions=(CAR_WIDTH * 0.27, CAR_LENGTH * 0.24, 0.18),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.050,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_Backrest_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.095, FLOOR_Z + 0.47),
            dimensions=(CAR_WIDTH * 0.27, 0.105, 0.34),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.055,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_HeadPad_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.102, FLOOR_Z + 0.66),
            dimensions=(CAR_WIDTH * 0.18, 0.090, 0.10),
            material=dark_mat,
            role="coaster.train.seat",
            bevel=0.040,
        ))

    # A compact lap bar keeps the safety hardware readable without hiding the tub opening.
    authored.append(shape.add_rounded_box(
        f"{prefix}_LapBar",
        location=(0.0, seat_y + CAR_LENGTH * 0.095, FLOOR_Z + 0.43),
        dimensions=(CAR_WIDTH * 0.64, 0.065, 0.065),
        material=metal_mat,
        role="coaster.train.restraint",
        bevel=0.018,
    ))

    # Small front inset/badge only on the lead car; the nose silhouette itself comes from the tub loft.
    if lead:
        authored.append(shape.add_rounded_box(
            f"{prefix}_FrontBadge",
            location=(0.0, y_center + CAR_LENGTH * 0.465, FLOOR_Z + 0.27),
            dimensions=(CAR_WIDTH * 0.26, 0.038, 0.085),
            material=badge_mat,
            role="coaster.train.accent",
            bevel=0.018,
        ))

    authored.extend(add_flame_marks(prefix, y_center, orange_mat, yellow_mat))

    for local_y in (-CAR_LENGTH * 0.255, CAR_LENGTH * 0.255):
        for x in (-track.GAUGE * 0.49, track.GAUGE * 0.49):
            authored.append(add_wheel(
                f"{prefix}_Wheel_{local_y:+.3f}_{x:+.3f}",
                (x, y_center + local_y, track.RAIL_Z + 0.008),
                wheel_mat,
            ))

    return authored


def build_train():
    body_mat = bs.make_material("FlameV4Body", (0.57, 0.030, 0.022, 1.0), 0.46, 0.14)
    dark_mat = bs.make_material("FlameV4DarkTrim", (0.024, 0.029, 0.038, 1.0), 0.70)
    seat_mat = bs.make_material("FlameV4Seat", (0.017, 0.021, 0.028, 1.0), 0.76)
    metal_mat = bs.make_material("FlameV4Metal", (0.20, 0.23, 0.26, 1.0), 0.44, 0.28)
    wheel_mat = bs.make_material("FlameV4Wheel", (0.012, 0.016, 0.022, 1.0), 0.84)
    orange_mat = bs.make_material("FlameV4Orange", (0.94, 0.19, 0.020, 1.0), 0.54)
    yellow_mat = bs.make_material("FlameV4Yellow", (1.00, 0.56, 0.025, 1.0), 0.50)
    badge_mat = bs.make_material("FlameV4Badge", (0.78, 0.69, 0.48, 1.0), 0.56)
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
        authored.append(shape.add_rounded_box(
            f"FlameV4Coupler_{index}",
            location=(0.0, y_mid, track.RAIL_Z + 0.10),
            dimensions=(0.10, CAR_GAP * 0.95, 0.09),
            material=metal_mat,
            role="coaster.train.coupler",
            bevel=0.016,
        ))
    return authored


def write_metadata(output: Path, shape_report: dict):
    payload = {
        "contract": TRAIN_CONTRACT,
        "assetId": ASSET_ID,
        "styleId": STYLE_ID,
        "trackContract": "CH_COASTER_TRACK_V1",
        "shapeContract": shape.CONTRACT_ID,
        "shapeReportContract": shape.REPORT_CONTRACT,
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
        "visualIntent": "integrated_open_tub_flame_coaster_body",
        "detailPolicy": "silhouette_first_gameplay_readability",
        "prototypeStatus": "visual_review_v4_open_tub",
        "shapeStatus": shape_report.get("status"),
        "requiredShapePrimitive": "open_tub_loft",
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
    shape.load_contract()
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
    root["shapeContract"] = shape.CONTRACT_ID
    root["styleId"] = STYLE_ID
    root["trackContract"] = "CH_COASTER_TRACK_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    shape_report = shape.build_shape_report(
        scene=scene,
        objects=authored,
        asset_id=ASSET_ID,
        constraints={
            "maxXSymmetryError": 0.018,
            "maxAbsCenterOffsetX": 0.035,
            "minProjectedSouthOccupancy": 0.20,
            "maxProjectedSouthOccupancy": 0.88,
            "requiredPrimitiveMinimums": {"open_tub_loft": CAR_COUNT},
        },
    )
    shape.write_shape_report(output / "shape_report.json", shape_report)
    shape.require_shape_pass(shape_report)
    write_metadata(output, shape_report)

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
