"""Guarded builder for City Horizon coaster train Type 1 Flame/Radical V3.

V3 is the first coaster train built on CH_SHAPE_AUTHORING_V1. The body is no longer
assembled mainly from detached boxes: each car gets one tapered longitudinal loft,
mirrored integrated side walls, objective symmetry/centering diagnostics, and the same
frozen City Horizon camera/studio contract used by production assets.
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

ASSET_ID = "ride.coaster.train_flame_v3"
TRAIN_CONTRACT = "CH_COASTER_TRAIN_STYLE_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 2, "depthTiles": 5}

CAR_LENGTH = track.TILE * 0.80
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
        (-CAR_LENGTH * 0.12, FLOOR_Z + 0.31),
        ( CAR_LENGTH * 0.05, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.16, FLOOR_Z + 0.43),
        ( CAR_LENGTH * 0.08, FLOOR_Z + 0.32),
        ( CAR_LENGTH * 0.19, FLOOR_Z + 0.31),
        ( CAR_LENGTH * 0.03, FLOOR_Z + 0.27),
    ]
    yellow_profile = [
        (-CAR_LENGTH * 0.03, FLOOR_Z + 0.315),
        ( CAR_LENGTH * 0.06, FLOOR_Z + 0.34),
        ( CAR_LENGTH * 0.11, FLOOR_Z + 0.385),
        ( CAR_LENGTH * 0.07, FLOOR_Z + 0.32),
        ( CAR_LENGTH * 0.13, FLOOR_Z + 0.31),
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


def build_car(index, y_center, lead, materials):
    body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat = materials
    authored = []
    prefix = f"FlameV3Car{index:02d}"

    # Main body: one continuous tapered hull. The front narrows instead of ending as a box.
    sections = [
        {"y": y_center - CAR_LENGTH * 0.47, "halfWidth": CAR_WIDTH * 0.39, "bottomZ": track.RAIL_Z + 0.08, "topZ": FLOOR_Z + 0.17},
        {"y": y_center - CAR_LENGTH * 0.34, "halfWidth": CAR_WIDTH * 0.48, "bottomZ": track.RAIL_Z + 0.07, "topZ": FLOOR_Z + 0.22},
        {"y": y_center - CAR_LENGTH * 0.08, "halfWidth": CAR_WIDTH * 0.50, "bottomZ": track.RAIL_Z + 0.07, "topZ": FLOOR_Z + 0.24},
        {"y": y_center + CAR_LENGTH * 0.18, "halfWidth": CAR_WIDTH * 0.49, "bottomZ": track.RAIL_Z + 0.08, "topZ": FLOOR_Z + 0.27},
        {"y": y_center + CAR_LENGTH * 0.36, "halfWidth": CAR_WIDTH * 0.43, "bottomZ": track.RAIL_Z + 0.10, "topZ": FLOOR_Z + 0.30},
        {"y": y_center + CAR_LENGTH * 0.48, "halfWidth": CAR_WIDTH * (0.27 if lead else 0.34), "bottomZ": track.RAIL_Z + 0.13, "topZ": FLOOR_Z + 0.25},
    ]
    authored.append(shape.add_symmetric_section_loft(
        f"{prefix}_BodyLoft",
        sections=sections,
        material=body_mat,
        role="coaster.train.body",
        bevel=0.055,
    ))

    # Integrated side walls rise around the shoulders and flow down into the tapered nose.
    side_profile = [
        (-CAR_LENGTH * 0.39, FLOOR_Z + 0.20),
        (-CAR_LENGTH * 0.32, FLOOR_Z + 0.54),
        (-CAR_LENGTH * 0.19, FLOOR_Z + 0.70),
        (-CAR_LENGTH * 0.03, FLOOR_Z + 0.72),
        ( CAR_LENGTH * 0.15, FLOOR_Z + 0.58),
        ( CAR_LENGTH * 0.32, FLOOR_Z + 0.39),
        ( CAR_LENGTH * 0.40, FLOOR_Z + 0.28),
        ( CAR_LENGTH * 0.36, FLOOR_Z + 0.22),
        ( CAR_LENGTH * 0.12, FLOOR_Z + 0.26),
        (-CAR_LENGTH * 0.16, FLOOR_Z + 0.27),
        (-CAR_LENGTH * 0.34, FLOOR_Z + 0.22),
    ]
    left, right = shape.add_mirrored_profile_pair(
        f"{prefix}_SideWall",
        x_center=CAR_WIDTH * 0.455,
        thickness=CAR_WIDTH * 0.095,
        y_center=y_center,
        profile_yz=side_profile,
        material=body_mat,
        role="coaster.train.body",
        bevel=0.045,
    )
    authored.extend((left, right))

    # Dark inset floor makes the passenger cell read as a cockpit, without excessive detail.
    authored.append(shape.add_rounded_box(
        f"{prefix}_Footwell",
        location=(0.0, y_center + CAR_LENGTH * 0.07, FLOOR_Z + 0.285),
        dimensions=(CAR_WIDTH * 0.61, CAR_LENGTH * 0.31, 0.065),
        material=dark_mat,
        role="coaster.train.interior",
        bevel=0.028,
    ))

    # Rear shoulder bridge visually joins the two side walls behind the seats.
    authored.append(shape.add_rounded_box(
        f"{prefix}_RearBridge",
        location=(0.0, y_center - CAR_LENGTH * 0.29, FLOOR_Z + 0.47),
        dimensions=(CAR_WIDTH * 0.82, CAR_LENGTH * 0.10, 0.30),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.085,
    ))

    seat_y = y_center - CAR_LENGTH * 0.07
    for col, x in enumerate((-CAR_WIDTH * 0.205, CAR_WIDTH * 0.205)):
        authored.append(shape.add_rounded_box(
            f"{prefix}_Seat_{col}",
            location=(x, seat_y, FLOOR_Z + 0.34),
            dimensions=(CAR_WIDTH * 0.29, CAR_LENGTH * 0.27, 0.26),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.060,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_Backrest_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.10, FLOOR_Z + 0.59),
            dimensions=(CAR_WIDTH * 0.29, 0.105, 0.42),
            material=seat_mat,
            role="coaster.train.seat",
            bevel=0.060,
        ))
        authored.append(shape.add_rounded_box(
            f"{prefix}_Headrest_{col}",
            location=(x, seat_y - CAR_LENGTH * 0.105, FLOOR_Z + 0.82),
            dimensions=(CAR_WIDTH * 0.20, 0.095, 0.15),
            material=dark_mat,
            role="coaster.train.seat",
            bevel=0.045,
        ))

    # One broad restraint bar reads better in the final 2D sprite than complex harness geometry.
    authored.append(shape.add_rounded_box(
        f"{prefix}_LapBar",
        location=(0.0, seat_y + CAR_LENGTH * 0.09, FLOOR_Z + 0.51),
        dimensions=(CAR_WIDTH * 0.70, 0.070, 0.070),
        material=metal_mat,
        role="coaster.train.restraint",
        bevel=0.020,
    ))

    if lead:
        authored.append(shape.add_rounded_box(
            f"{prefix}_FrontBadge",
            location=(0.0, y_center + CAR_LENGTH * 0.475, FLOOR_Z + 0.31),
            dimensions=(CAR_WIDTH * 0.30, 0.040, 0.11),
            material=badge_mat,
            role="coaster.train.accent",
            bevel=0.020,
        ))

    authored.extend(add_flame_marks(prefix, y_center, orange_mat, yellow_mat))

    # Wheel hardware stays deliberately dark and mostly hidden under the hull.
    for local_y in (-CAR_LENGTH * 0.255, CAR_LENGTH * 0.255):
        for x in (-track.GAUGE * 0.49, track.GAUGE * 0.49):
            authored.append(add_wheel(
                f"{prefix}_Wheel_{local_y:+.3f}_{x:+.3f}",
                (x, y_center + local_y, track.RAIL_Z + 0.008),
                wheel_mat,
            ))

    return authored


def build_train():
    body_mat = bs.make_material("FlameV3Body", (0.57, 0.030, 0.022, 1.0), 0.44, 0.16)
    dark_mat = bs.make_material("FlameV3DarkTrim", (0.024, 0.029, 0.038, 1.0), 0.68)
    seat_mat = bs.make_material("FlameV3Seat", (0.017, 0.021, 0.028, 1.0), 0.74)
    metal_mat = bs.make_material("FlameV3Metal", (0.20, 0.23, 0.26, 1.0), 0.42, 0.32)
    wheel_mat = bs.make_material("FlameV3Wheel", (0.012, 0.016, 0.022, 1.0), 0.82)
    orange_mat = bs.make_material("FlameV3Orange", (0.94, 0.19, 0.020, 1.0), 0.52)
    yellow_mat = bs.make_material("FlameV3Yellow", (1.00, 0.56, 0.025, 1.0), 0.48)
    badge_mat = bs.make_material("FlameV3Badge", (0.78, 0.69, 0.48, 1.0), 0.54)
    materials = (body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat)

    authored = []
    pitch = CAR_LENGTH + CAR_GAP
    center_offset = (CAR_COUNT - 1) * pitch * 0.5
    centers = []
    for index in range(CAR_COUNT):
        y_center = center_offset - index * pitch
        centers.append(y_center)
        authored.extend(build_car(index, y_center, lead=(index == 0), materials=materials))

    # Compact couplers remain mechanically explicit but visually secondary.
    for index in range(CAR_COUNT - 1):
        y_mid = (centers[index] + centers[index + 1]) * 0.5
        authored.append(shape.add_rounded_box(
            f"FlameV3Coupler_{index}",
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
        "visualIntent": "integrated_tapered_flame_coaster_body",
        "detailPolicy": "silhouette_first_gameplay_readability",
        "prototypeStatus": "visual_review_v3_shape_tooling",
        "shapeStatus": shape_report.get("status"),
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
