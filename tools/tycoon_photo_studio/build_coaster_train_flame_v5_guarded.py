"""Guarded builder for City Horizon coaster train Type 1 Flame/Radical V5.

V5 targets the compact open coaster-car silhouette from the current visual review:
low open tub, raised rear shoulder cowls, two exposed seats with over-shoulder
restraints, a short front fascia, visible bogie hardware and long flame side graphics.
The design remains an original City Horizon asset and uses the frozen CH camera/studio.
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
import build_coaster_track_guarded as track  # noqa: E402
import scene_gate  # noqa: E402
import shape_authoring as shape  # noqa: E402

ASSET_ID = "ride.coaster.train_flame_v5"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_STYLE_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.75
CAR_WIDTH = track.TILE * 0.60
CAR_GAP = track.TILE * 0.065
FLOOR_Z = track.RAIL_Z + 0.22
WHEEL_RADIUS = 0.075
WHEEL_DEPTH = 0.052
GUIDE_WHEEL_RADIUS = 0.050
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


def tag_custom(obj, role: str):
    obj["ch.semanticRole"] = role
    obj["chShapeContract"] = shape.CONTRACT_ID
    return obj


def add_bar_between(name, start, end, radius, material, role, vertices=14):
    a = Vector(start)
    b = Vector(end)
    delta = b - a
    length = delta.length
    if length <= 1.0e-5:
        raise ValueError(f"{name}: bar endpoints are coincident")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices,
        radius=radius,
        depth=length,
        location=(a + b) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(delta.normalized())
    obj.data.materials.append(material)
    tag_custom(obj, role)
    return obj


def add_wheel(name, location, material, radius=WHEEL_RADIUS, depth=WHEEL_DEPTH):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=radius,
        depth=depth,
        location=location,
        rotation=(0.0, math.pi * 0.5, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    tag_custom(obj, "coaster.train.wheel")
    return obj


def tub_sections(y_center: float, lead: bool) -> list[dict]:
    """Low open chassis shell. The tall shoulder silhouette is authored separately."""
    front_outer = 0.43 if lead else 0.46
    return [
        {
            "y": y_center - CAR_LENGTH * 0.47,
            "outerHalfWidth": CAR_WIDTH * 0.48,
            "innerHalfWidth": CAR_WIDTH * 0.36,
            "outerBottomZ": track.RAIL_Z + 0.08,
            "innerFloorZ": FLOOR_Z + 0.08,
            "rimZ": FLOOR_Z + 0.43,
            "innerRimZ": FLOOR_Z + 0.39,
        },
        {
            "y": y_center - CAR_LENGTH * 0.30,
            "outerHalfWidth": CAR_WIDTH * 0.50,
            "innerHalfWidth": CAR_WIDTH * 0.37,
            "outerBottomZ": track.RAIL_Z + 0.07,
            "innerFloorZ": FLOOR_Z + 0.08,
            "rimZ": FLOOR_Z + 0.41,
            "innerRimZ": FLOOR_Z + 0.37,
        },
        {
            "y": y_center - CAR_LENGTH * 0.05,
            "outerHalfWidth": CAR_WIDTH * 0.50,
            "innerHalfWidth": CAR_WIDTH * 0.38,
            "outerBottomZ": track.RAIL_Z + 0.07,
            "innerFloorZ": FLOOR_Z + 0.08,
            "rimZ": FLOOR_Z + 0.34,
            "innerRimZ": FLOOR_Z + 0.31,
        },
        {
            "y": y_center + CAR_LENGTH * 0.22,
            "outerHalfWidth": CAR_WIDTH * 0.49,
            "innerHalfWidth": CAR_WIDTH * 0.37,
            "outerBottomZ": track.RAIL_Z + 0.08,
            "innerFloorZ": FLOOR_Z + 0.10,
            "rimZ": FLOOR_Z + 0.32,
            "innerRimZ": FLOOR_Z + 0.29,
        },
        {
            "y": y_center + CAR_LENGTH * 0.47,
            "outerHalfWidth": CAR_WIDTH * front_outer,
            "innerHalfWidth": CAR_WIDTH * 0.31,
            "outerBottomZ": track.RAIL_Z + 0.12,
            "innerFloorZ": FLOOR_Z + 0.12,
            "rimZ": FLOOR_Z + 0.40,
            "innerRimZ": FLOOR_Z + 0.36,
        },
    ]


def shoulder_cowl_profile() -> list[tuple[float, float]]:
    """Longitudinal Y/Z outline of the raised rear side shoulder shell."""
    return [
        (-CAR_LENGTH * 0.44, FLOOR_Z + 0.20),
        (-CAR_LENGTH * 0.44, FLOOR_Z + 0.76),
        (-CAR_LENGTH * 0.34, FLOOR_Z + 0.88),
        (-CAR_LENGTH * 0.18, FLOOR_Z + 0.91),
        (-CAR_LENGTH * 0.04, FLOOR_Z + 0.83),
        ( CAR_LENGTH * 0.10, FLOOR_Z + 0.62),
        ( CAR_LENGTH * 0.27, FLOOR_Z + 0.43),
        ( CAR_LENGTH * 0.40, FLOOR_Z + 0.32),
        ( CAR_LENGTH * 0.40, FLOOR_Z + 0.20),
        ( CAR_LENGTH * 0.16, FLOOR_Z + 0.16),
        (-CAR_LENGTH * 0.14, FLOOR_Z + 0.15),
    ]


def add_flame_marks(prefix, y_center, material_orange, material_yellow):
    """Long side flame graphics that follow the raised cowl instead of floating between cars."""
    authored = []
    x = CAR_WIDTH * 0.505
    orange_profile = [
        (-CAR_LENGTH * 0.25, FLOOR_Z + 0.34),
        (-CAR_LENGTH * 0.10, FLOOR_Z + 0.39),
        ( CAR_LENGTH * 0.03, FLOOR_Z + 0.53),
        (-CAR_LENGTH * 0.01, FLOOR_Z + 0.40),
        ( CAR_LENGTH * 0.18, FLOOR_Z + 0.47),
        ( CAR_LENGTH * 0.08, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.30, FLOOR_Z + 0.37),
        ( CAR_LENGTH * 0.13, FLOOR_Z + 0.27),
        (-CAR_LENGTH * 0.12, FLOOR_Z + 0.28),
    ]
    yellow_profile = [
        (-CAR_LENGTH * 0.12, FLOOR_Z + 0.34),
        (-CAR_LENGTH * 0.02, FLOOR_Z + 0.39),
        ( CAR_LENGTH * 0.06, FLOOR_Z + 0.46),
        ( CAR_LENGTH * 0.035, FLOOR_Z + 0.38),
        ( CAR_LENGTH * 0.16, FLOOR_Z + 0.41),
        ( CAR_LENGTH * 0.09, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.21, FLOOR_Z + 0.35),
        ( CAR_LENGTH * 0.11, FLOOR_Z + 0.30),
        (-CAR_LENGTH * 0.05, FLOOR_Z + 0.30),
    ]
    for side, label in ((-1, "L"), (1, "R")):
        authored.append(shape.add_profile_prism(
            f"{prefix}_FlameOrange_{label}",
            x_center=side * x,
            thickness=0.020,
            y_center=y_center,
            profile_yz=orange_profile,
            material=material_orange,
            role="coaster.train.decal",
            bevel=0.0,
        ))
        authored.append(shape.add_profile_prism(
            f"{prefix}_FlameYellow_{label}",
            x_center=side * (x + 0.003),
            thickness=0.016,
            y_center=y_center,
            profile_yz=yellow_profile,
            material=material_yellow,
            role="coaster.train.decal",
            bevel=0.0,
        ))
    return authored


def add_restraint(prefix, seat_x, seat_y, material, authored):
    """Three-bar over-shoulder restraint silhouette for one seat."""
    half = CAR_WIDTH * 0.075
    rear_y = seat_y - CAR_LENGTH * 0.07
    front_y = seat_y + CAR_LENGTH * 0.08
    top_z = FLOOR_Z + 0.79
    lap_z = FLOOR_Z + 0.43
    for side_index, dx in enumerate((-half, half)):
        authored.append(add_bar_between(
            f"{prefix}_HarnessArm_{side_index}",
            (seat_x + dx, rear_y, top_z),
            (seat_x + dx, front_y, lap_z),
            0.035,
            material,
            "coaster.train.restraint",
        ))
    authored.append(add_bar_between(
        f"{prefix}_HarnessTop",
        (seat_x - half, rear_y, top_z),
        (seat_x + half, rear_y, top_z),
        0.038,
        material,
        "coaster.train.restraint",
    ))


def build_car(index, y_center, lead, materials):
    body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat = materials
    authored = []
    prefix = f"FlameV5Car{index:02d}"

    # Low open tub: compact lower body rather than a tall bathtub silhouette.
    authored.append(shape.add_open_tub_loft(
        f"{prefix}_OpenTub",
        sections=tub_sections(y_center, lead),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.040,
    ))

    # Raised left/right shoulder cowls create the characteristic coaster-car profile.
    cowls = shape.add_mirrored_profile_pair(
        f"{prefix}_ShoulderCowl",
        x_center=CAR_WIDTH * 0.455,
        thickness=CAR_WIDTH * 0.13,
        y_center=y_center,
        profile_yz=shoulder_cowl_profile(),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.040,
    )
    authored.extend(cowls)

    # Dark chassis and footwell keep the opening readable and expose the mechanical base.
    authored.append(shape.add_rounded_box(
        f"{prefix}_Chassis",
        location=(0.0, y_center, track.RAIL_Z + 0.13),
        dimensions=(CAR_WIDTH * 0.72, CAR_LENGTH * 0.74, 0.12),
        material=dark_mat,
        role="coaster.train.chassis",
        bevel=0.025,
    ))
    authored.append(shape.add_rounded_box(
        f"{prefix}_FootwellPad",
        location=(0.0, y_center + CAR_LENGTH * 0.10, FLOOR_Z + 0.13),
        dimensions=(CAR_WIDTH * 0.57, CAR_LENGTH * 0.30, 0.055),
        material=dark_mat,
        role="coaster.train.interior",
        bevel=0.022,
    ))

    seat_y = y_center - CAR_LENGTH * 0.11
    for col, x in enumerate((-CAR_WIDTH * 0.19, CAR_WIDTH * 0.19)):
        authored.append(shape.add_rounded_box(
            f"{prefix}_Seat_{col}",
            location=(x, seat_y + CAR_LENGTH * 0.025, FLOOR_Z + 0.25),
            dimensions=(CAR_WIDTH * 0.27, CAR_LENGTH * 0.23, 0.18),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.050,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_Backrest_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.085, FLOOR_Z + 0.49),
            dimensions=(CAR_WIDTH * 0.27, 0.115, 0.40),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.060,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_HeadPad_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.092, FLOOR_Z + 0.72),
            dimensions=(CAR_WIDTH * 0.17, 0.100, 0.12),
            material=dark_mat,
            role="coaster.train.seat",
            bevel=0.045,
        ))
        add_restraint(f"{prefix}_Seat{col}", x, seat_y, metal_mat, authored)

    # Short front fascia is a separate readable face, with a small badge on the lead car.
    authored.append(shape.add_rounded_box(
        f"{prefix}_FrontFascia",
        location=(0.0, y_center + CAR_LENGTH * 0.455, FLOOR_Z + 0.30),
        dimensions=(CAR_WIDTH * 0.76, 0.070, 0.30),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.040,
    ))
    if lead:
        authored.append(shape.add_rounded_box(
            f"{prefix}_FrontBadge",
            location=(0.0, y_center + CAR_LENGTH * 0.493, FLOOR_Z + 0.32),
            dimensions=(CAR_WIDTH * 0.28, 0.028, 0.090),
            material=badge_mat,
            role="coaster.train.accent",
            bevel=0.018,
        ))

    authored.extend(add_flame_marks(prefix, y_center, orange_mat, yellow_mat))

    # Main road wheels plus smaller guide/up-stop wheels give a coaster bogie read.
    for local_y in (-CAR_LENGTH * 0.25, CAR_LENGTH * 0.25):
        for x in (-track.GAUGE * 0.50, track.GAUGE * 0.50):
            authored.append(add_wheel(
                f"{prefix}_RoadWheel_{local_y:+.3f}_{x:+.3f}",
                (x, y_center + local_y, track.RAIL_Z + 0.015),
                wheel_mat,
            ))
            authored.append(add_wheel(
                f"{prefix}_GuideWheel_{local_y:+.3f}_{x:+.3f}",
                (x, y_center + local_y + CAR_LENGTH * 0.075, track.RAIL_Z - 0.075),
                wheel_mat,
                radius=GUIDE_WHEEL_RADIUS,
                depth=0.042,
            ))

    return authored


def build_train():
    body_mat = bs.make_material("FlameV5Body", (0.56, 0.025, 0.018, 1.0), 0.44, 0.15)
    dark_mat = bs.make_material("FlameV5DarkTrim", (0.020, 0.025, 0.034, 1.0), 0.72)
    seat_mat = bs.make_material("FlameV5Seat", (0.014, 0.018, 0.024, 1.0), 0.78)
    metal_mat = bs.make_material("FlameV5Metal", (0.16, 0.18, 0.21, 1.0), 0.46, 0.34)
    wheel_mat = bs.make_material("FlameV5Wheel", (0.010, 0.013, 0.018, 1.0), 0.86)
    orange_mat = bs.make_material("FlameV5Orange", (0.93, 0.15, 0.016, 1.0), 0.54)
    yellow_mat = bs.make_material("FlameV5Yellow", (1.00, 0.50, 0.020, 1.0), 0.50)
    badge_mat = bs.make_material("FlameV5Badge", (0.80, 0.72, 0.54, 1.0), 0.58)
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
            f"FlameV5Coupler_{index}",
            location=(0.0, y_mid, track.RAIL_Z + 0.10),
            dimensions=(0.12, CAR_GAP * 0.96, 0.10),
            material=metal_mat,
            role="coaster.train.coupler",
            bevel=0.018,
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
        "visualIntent": "compact_open_coaster_car_with_raised_shoulder_cowls",
        "detailPolicy": "silhouette_first_gameplay_readability",
        "prototypeStatus": "visual_review_v5_shoulder_shell",
        "shapeStatus": shape_report.get("status"),
        "requiredShapePrimitive": "open_tub_loft",
        "referenceTraits": [
            "low_open_tub",
            "raised_rear_side_shoulders",
            "two_exposed_seats",
            "over_shoulder_restraints",
            "short_front_fascia",
            "visible_bogie_hardware",
            "long_side_flame_graphics"
        ]
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
            "maxXSymmetryError": 0.020,
            "maxAbsCenterOffsetX": 0.040,
            "minProjectedSouthOccupancy": 0.20,
            "maxProjectedSouthOccupancy": 0.90,
            "requiredPrimitiveMinimums": {
                "open_tub_loft": CAR_COUNT,
                "profile_prism": CAR_COUNT * 6
            },
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
