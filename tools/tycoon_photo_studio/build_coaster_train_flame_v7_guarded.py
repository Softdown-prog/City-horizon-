"""V7 paint-finish pass for the City Horizon Flame coaster train.

Geometry is intentionally inherited unchanged from the human-approved V6 silhouette.
This pass only improves the flame livery: large mirrored orange/yellow side graphics
are moved onto the true outside face of the raised shoulder shell so they remain
visible at gameplay scale without z-fighting or adding texture/UV complexity.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_coaster_train_flame_v6_guarded as v6  # noqa: E402

v5 = v6.v5
v5.ASSET_ID = "ride.coaster.train_flame_v7"


def add_flame_marks(prefix, y_center, material_orange, material_yellow):
    """Paint-like layered flames on the outside faces of both side cowls.

    V5/V6 placed the decal close enough to the cowl center that much of it could be
    hidden by the body. V7 derives the actual outer cowl face and offsets each layer
    slightly outward. The polygons stay deliberately broad and low-frequency so the
    livery reads in the compact isometric render instead of becoming noisy detail.
    """
    authored = []

    # Cowl geometry is centered at 0.455*width with 0.13*width thickness.
    # Put the orange layer just beyond the outer face and the yellow layer a hair
    # farther out so both survive rasterization without z-fighting.
    cowl_outer_x = v5.CAR_WIDTH * (0.455 + 0.13 * 0.5)
    orange_x = cowl_outer_x + 0.010
    yellow_x = cowl_outer_x + 0.020

    # Broad outer flame: long low base with three readable tongues.
    orange_profile = [
        (-v5.CAR_LENGTH * 0.34, v5.FLOOR_Z + 0.245),
        (-v5.CAR_LENGTH * 0.31, v5.FLOOR_Z + 0.345),
        (-v5.CAR_LENGTH * 0.18, v5.FLOOR_Z + 0.390),
        (-v5.CAR_LENGTH * 0.07, v5.FLOOR_Z + 0.530),
        ( v5.CAR_LENGTH * 0.00, v5.FLOOR_Z + 0.655),
        ( v5.CAR_LENGTH * 0.025, v5.FLOOR_Z + 0.430),
        ( v5.CAR_LENGTH * 0.14, v5.FLOOR_Z + 0.535),
        ( v5.CAR_LENGTH * 0.115, v5.FLOOR_Z + 0.405),
        ( v5.CAR_LENGTH * 0.315, v5.FLOOR_Z + 0.440),
        ( v5.CAR_LENGTH * 0.235, v5.FLOOR_Z + 0.315),
        ( v5.CAR_LENGTH * 0.075, v5.FLOOR_Z + 0.275),
        (-v5.CAR_LENGTH * 0.11, v5.FLOOR_Z + 0.260),
    ]

    # Inner hot-yellow flame follows the same motion but leaves an orange border.
    yellow_profile = [
        (-v5.CAR_LENGTH * 0.18, v5.FLOOR_Z + 0.295),
        (-v5.CAR_LENGTH * 0.12, v5.FLOOR_Z + 0.350),
        (-v5.CAR_LENGTH * 0.035, v5.FLOOR_Z + 0.455),
        ( v5.CAR_LENGTH * 0.005, v5.FLOOR_Z + 0.545),
        ( v5.CAR_LENGTH * 0.035, v5.FLOOR_Z + 0.395),
        ( v5.CAR_LENGTH * 0.115, v5.FLOOR_Z + 0.455),
        ( v5.CAR_LENGTH * 0.105, v5.FLOOR_Z + 0.365),
        ( v5.CAR_LENGTH * 0.230, v5.FLOOR_Z + 0.390),
        ( v5.CAR_LENGTH * 0.170, v5.FLOOR_Z + 0.325),
        ( v5.CAR_LENGTH * 0.035, v5.FLOOR_Z + 0.305),
    ]

    for side, label in ((-1, "L"), (1, "R")):
        authored.append(v5.shape.add_profile_prism(
            f"{prefix}_FlameOrangeV7_{label}",
            x_center=side * orange_x,
            thickness=0.014,
            y_center=y_center,
            profile_yz=orange_profile,
            material=material_orange,
            role="coaster.train.decal",
            bevel=0.0,
        ))
        authored.append(v5.shape.add_profile_prism(
            f"{prefix}_FlameYellowV7_{label}",
            x_center=side * yellow_x,
            thickness=0.010,
            y_center=y_center,
            profile_yz=yellow_profile,
            material=material_yellow,
            role="coaster.train.decal",
            bevel=0.0,
        ))
    return authored


_v6_write_metadata = v6.write_metadata


def write_metadata(output: Path, shape_report: dict):
    _v6_write_metadata(output, shape_report)
    metadata_path = output / "train_metadata.json"
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    payload["assetId"] = v5.ASSET_ID
    payload["visualIntent"] = "approved_v6_silhouette_with_readable_two_layer_flame_livery"
    payload["prototypeStatus"] = "visual_review_v7_flame_paint_finish"
    payload["paintFinish"] = {
        "base": "deep_red",
        "outerFlame": "orange",
        "innerFlame": "hot_yellow",
        "decalMethod": "mirrored_profile_prisms_surface_offset",
        "geometryChangedFromV6": False,
        "gameplayReadabilityFirst": True,
    }
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# Keep every V6 geometry decision; replace only the livery authoring hook and metadata.
v5.add_flame_marks = add_flame_marks
v5.write_metadata = write_metadata


if __name__ == "__main__":
    v5.main()
