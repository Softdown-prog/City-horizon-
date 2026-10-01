"""V6 refinement of the City Horizon Flame coaster train.

This keeps the validated V5 open-tub architecture but pushes the silhouette toward a
classic compact coaster car: taller rear shoulder shell, stronger seat/harness read,
tighter car spacing and a more substantial front/rear body structure. It remains an
original CH design; the external image is used only for broad structural traits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_coaster_train_flame_v5_guarded as v5  # noqa: E402

# Preserve the V5 implementation and override only the structural recipe.
_v5_build_car = v5.build_car

v5.ASSET_ID = "ride.coaster.train_flame_v6"
v5.CAR_LENGTH = v5.track.TILE * 0.73
v5.CAR_WIDTH = v5.track.TILE * 0.61
v5.CAR_GAP = v5.track.TILE * 0.045
v5.FLOOR_Z = v5.track.RAIL_Z + 0.22


def tub_sections(y_center: float, lead: bool) -> list[dict]:
    """Lower, tighter passenger tub so the shoulder shell—not the bathtub—defines the car."""
    front_outer = 0.42 if lead else 0.45
    return [
        {"y": y_center - v5.CAR_LENGTH * 0.47, "outerHalfWidth": v5.CAR_WIDTH * 0.48,
         "innerHalfWidth": v5.CAR_WIDTH * 0.36, "outerBottomZ": v5.track.RAIL_Z + 0.08,
         "innerFloorZ": v5.FLOOR_Z + 0.08, "rimZ": v5.FLOOR_Z + 0.39, "innerRimZ": v5.FLOOR_Z + 0.35},
        {"y": y_center - v5.CAR_LENGTH * 0.28, "outerHalfWidth": v5.CAR_WIDTH * 0.50,
         "innerHalfWidth": v5.CAR_WIDTH * 0.37, "outerBottomZ": v5.track.RAIL_Z + 0.07,
         "innerFloorZ": v5.FLOOR_Z + 0.08, "rimZ": v5.FLOOR_Z + 0.36, "innerRimZ": v5.FLOOR_Z + 0.32},
        {"y": y_center + v5.CAR_LENGTH * 0.02, "outerHalfWidth": v5.CAR_WIDTH * 0.50,
         "innerHalfWidth": v5.CAR_WIDTH * 0.38, "outerBottomZ": v5.track.RAIL_Z + 0.07,
         "innerFloorZ": v5.FLOOR_Z + 0.08, "rimZ": v5.FLOOR_Z + 0.30, "innerRimZ": v5.FLOOR_Z + 0.27},
        {"y": y_center + v5.CAR_LENGTH * 0.26, "outerHalfWidth": v5.CAR_WIDTH * 0.48,
         "innerHalfWidth": v5.CAR_WIDTH * 0.36, "outerBottomZ": v5.track.RAIL_Z + 0.09,
         "innerFloorZ": v5.FLOOR_Z + 0.10, "rimZ": v5.FLOOR_Z + 0.30, "innerRimZ": v5.FLOOR_Z + 0.27},
        {"y": y_center + v5.CAR_LENGTH * 0.47, "outerHalfWidth": v5.CAR_WIDTH * front_outer,
         "innerHalfWidth": v5.CAR_WIDTH * 0.30, "outerBottomZ": v5.track.RAIL_Z + 0.12,
         "innerFloorZ": v5.FLOOR_Z + 0.12, "rimZ": v5.FLOOR_Z + 0.38, "innerRimZ": v5.FLOOR_Z + 0.34},
    ]


def shoulder_cowl_profile() -> list[tuple[float, float]]:
    """High rear shoulder that sweeps down toward the front opening."""
    return [
        (-v5.CAR_LENGTH * 0.45, v5.FLOOR_Z + 0.21),
        (-v5.CAR_LENGTH * 0.45, v5.FLOOR_Z + 0.95),
        (-v5.CAR_LENGTH * 0.37, v5.FLOOR_Z + 1.06),
        (-v5.CAR_LENGTH * 0.23, v5.FLOOR_Z + 1.08),
        (-v5.CAR_LENGTH * 0.09, v5.FLOOR_Z + 0.98),
        ( v5.CAR_LENGTH * 0.05, v5.FLOOR_Z + 0.76),
        ( v5.CAR_LENGTH * 0.18, v5.FLOOR_Z + 0.55),
        ( v5.CAR_LENGTH * 0.31, v5.FLOOR_Z + 0.40),
        ( v5.CAR_LENGTH * 0.42, v5.FLOOR_Z + 0.32),
        ( v5.CAR_LENGTH * 0.42, v5.FLOOR_Z + 0.20),
        ( v5.CAR_LENGTH * 0.13, v5.FLOOR_Z + 0.16),
        (-v5.CAR_LENGTH * 0.18, v5.FLOOR_Z + 0.16),
    ]


def add_restraint(prefix, seat_x, seat_y, material, authored):
    """Thicker four-segment over-shoulder restraint that survives the gameplay proxy."""
    half = v5.CAR_WIDTH * 0.075
    rear_y = seat_y - v5.CAR_LENGTH * 0.085
    shoulder_y = seat_y - v5.CAR_LENGTH * 0.015
    front_y = seat_y + v5.CAR_LENGTH * 0.10
    top_z = v5.FLOOR_Z + 0.90
    shoulder_z = v5.FLOOR_Z + 0.73
    lap_z = v5.FLOOR_Z + 0.44
    for side_index, dx in enumerate((-half, half)):
        authored.append(v5.add_bar_between(
            f"{prefix}_HarnessRear_{side_index}",
            (seat_x + dx, rear_y, top_z),
            (seat_x + dx, shoulder_y, shoulder_z),
            0.047, material, "coaster.train.restraint"))
        authored.append(v5.add_bar_between(
            f"{prefix}_HarnessFront_{side_index}",
            (seat_x + dx, shoulder_y, shoulder_z),
            (seat_x + dx, front_y, lap_z),
            0.047, material, "coaster.train.restraint"))
    authored.append(v5.add_bar_between(
        f"{prefix}_HarnessTop",
        (seat_x - half, rear_y, top_z),
        (seat_x + half, rear_y, top_z),
        0.050, material, "coaster.train.restraint"))


def build_car(index, y_center, lead, materials):
    authored = _v5_build_car(index, y_center, lead, materials)
    body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat = materials
    prefix = f"FlameV6Car{index:02d}"

    # Rear bridge ties the two high side shoulders together around the seat backs.
    authored.append(v5.shape.add_rounded_box(
        f"{prefix}_RearBridge",
        location=(0.0, y_center - v5.CAR_LENGTH * 0.405, v5.FLOOR_Z + 0.68),
        dimensions=(v5.CAR_WIDTH * 0.80, 0.105, 0.42),
        material=body_mat,
        role="coaster.train.body",
        bevel=0.055,
    ))

    # Two dark seat-surround towers improve the two-passenger read from isometric distance.
    for col, x in enumerate((-v5.CAR_WIDTH * 0.19, v5.CAR_WIDTH * 0.19)):
        authored.append(v5.shape.add_rounded_box(
            f"{prefix}_SeatSurround_{col}",
            location=(x, y_center - v5.CAR_LENGTH * 0.31, v5.FLOOR_Z + 0.72),
            dimensions=(v5.CAR_WIDTH * 0.28, 0.115, 0.46),
            material=dark_mat,
            role="coaster.train.seat",
            bevel=0.060,
        ))

    # A dark mechanical sill visually separates the red body from the bogie/wheels.
    authored.append(v5.shape.add_rounded_box(
        f"{prefix}_MechanicalSill",
        location=(0.0, y_center + v5.CAR_LENGTH * 0.01, v5.track.RAIL_Z + 0.20),
        dimensions=(v5.CAR_WIDTH * 0.86, v5.CAR_LENGTH * 0.80, 0.075),
        material=dark_mat,
        role="coaster.train.chassis",
        bevel=0.020,
    ))
    return authored


def write_metadata(output: Path, shape_report: dict):
    payload = {
        "contract": v5.TRAIN_CONTRACT,
        "assetId": v5.ASSET_ID,
        "styleId": v5.STYLE_ID,
        "trackContract": "CH_COASTER_TRACK_V1",
        "shapeContract": v5.shape.CONTRACT_ID,
        "shapeReportContract": v5.shape.REPORT_CONTRACT,
        "pose": "flat_south",
        "carCount": v5.CAR_COUNT,
        "passengerCapacityPerCar": 2,
        "passengerCapacityTotal": v5.CAR_COUNT * 2,
        "rowsPerCar": 1,
        "seatsPerRow": 2,
        "trackGauge": v5.track.GAUGE,
        "carLength": v5.CAR_LENGTH,
        "carWidth": v5.CAR_WIDTH,
        "carGap": v5.CAR_GAP,
        "anchor": [0.0, 0.0, v5.track.RAIL_Z],
        "visualIntent": "classic_compact_open_coaster_car_high_rear_shoulders",
        "detailPolicy": "silhouette_first_gameplay_readability",
        "prototypeStatus": "visual_review_v6_classic_shoulder",
        "shapeStatus": shape_report.get("status"),
        "requiredShapePrimitive": "open_tub_loft",
        "referenceTraits": [
            "low_open_body", "high_rear_side_shoulders", "rear_bridge",
            "two_exposed_seats", "thick_over_shoulder_restraints",
            "short_front_fascia", "visible_bogie_hardware", "side_flame_graphics"
        ]
    }
    (output / "train_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


v5.tub_sections = tub_sections
v5.shoulder_cowl_profile = shoulder_cowl_profile
v5.add_restraint = add_restraint
v5.build_car = build_car
v5.write_metadata = write_metadata


if __name__ == "__main__":
    v5.main()
