"""Render one articulated steam-train unit from the approved City Horizon V3 recipe.

This deliberately reuses the existing refined locomotive/coach builders instead of
forking their geometry.  CH Blender remains authoring-only; runtime consumes 2D
RGBA sprites under CH_CAMERA_V1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_steam_train_refined_v3 as refined_v3  # noqa: E402

base = refined_v3.base


def _take_unit_arg() -> str:
    if "--" not in sys.argv:
        raise RuntimeError("Expected Blender '--' argument separator")
    tail = sys.argv[sys.argv.index("--") + 1 :]
    if "--unit" not in tail:
        raise RuntimeError("Expected --unit locomotive|coach")
    index = tail.index("--unit")
    if index + 1 >= len(tail):
        raise RuntimeError("Missing --unit value")
    unit = tail[index + 1]
    if unit not in {"locomotive", "coach"}:
        raise RuntimeError("--unit must be locomotive or coach")
    # The guarded base parser must not see our extension argument.
    absolute = sys.argv.index("--") + 1 + index
    del sys.argv[absolute : absolute + 2]
    return unit


UNIT = _take_unit_arg()


def build_unit(root, mats, recipe):
    if UNIT == "locomotive":
        base.build_locomotive(root, mats, recipe)
        locomotive = bpy.data.objects.get("LocomotiveRoot")
        if locomotive is None:
            raise RuntimeError("Approved V3 locomotive builder did not create LocomotiveRoot")
        # The approved consist recipe authors the locomotive around x=-16.0.
        # Translate only its unit root so the independent sprite is centered.
        locomotive.location.x += 16.0
        base.ASSET_ID = "vehicle.steam_train.locomotive.01"
        return

    base.build_coach(root, mats, 1, 0.0, recipe)
    length = float(recipe["geometry"]["coachLength"])
    gap = float(recipe["geometry"]["coachGap"])
    base.add_coupler(root, mats, "Coach_Articulated_FrontCoupler", -(length * 0.5 + gap * 0.5))
    base.add_coupler(root, mats, "Coach_Articulated_RearCoupler", +(length * 0.5 + gap * 0.5))
    base.ASSET_ID = "vehicle.steam_train.coach.01"


# Keep V3 materials/details, scene gate, proxy/final flow and CH_CAMERA_V1.
base.build_train = build_unit


if __name__ == "__main__":
    base.main()
