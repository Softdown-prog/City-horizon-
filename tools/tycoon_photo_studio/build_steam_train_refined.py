"""Visual refinement pass for the guarded City Horizon steam train.

Keeps the original guarded authoring contract and quality gate, while adding
larger, higher-contrast details that survive the long 7-coach proxy and final
2D downsampling.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_steam_train_guarded as base  # noqa: E402


_original_materials = base.materials
_original_build_locomotive = base.build_locomotive
_original_build_coach = base.build_coach


def materials_refined():
    mats = _original_materials()

    # Lift the train away from near-black values. At the complete consist scale,
    # tiny dark details collapse quickly, so the refined palette intentionally
    # keeps broad surfaces one or two value steps brighter.
    mats["boiler"] = base.bs.make_material(
        "Train_Boiler_Refined", (0.075, 0.105, 0.090, 1.0), roughness=0.60, metallic=0.42
    )
    mats["black"] = base.bs.make_material(
        "Train_BlackMetal_Refined", (0.055, 0.065, 0.068, 1.0), roughness=0.68, metallic=0.42
    )
    mats["frame"] = base.bs.make_material(
        "Train_Frame_Refined", (0.11, 0.125, 0.12, 1.0), roughness=0.72, metallic=0.34
    )
    mats["red"] = base.bs.make_material(
        "Train_RedAccent_Refined", (0.62, 0.075, 0.045, 1.0), roughness=0.66, metallic=0.16
    )
    mats["brass"] = base.bs.make_material(
        "Train_Brass_Refined", (0.84, 0.58, 0.18, 1.0), roughness=0.39, metallic=0.60
    )
    mats["coach"] = base.bs.make_material(
        "Train_CoachBody_Refined", (0.095, 0.36, 0.235, 1.0), roughness=0.69, metallic=0.08
    )
    mats["coach_dark"] = base.bs.make_material(
        "Train_CoachLower_Refined", (0.055, 0.15, 0.10, 1.0), roughness=0.74, metallic=0.14
    )
    mats["cream"] = base.bs.make_material(
        "Train_CreamTrim_Refined", (0.93, 0.83, 0.61, 1.0), roughness=0.70
    )
    mats["roof"] = base.bs.make_material(
        "Train_Roof_Refined", (0.16, 0.17, 0.17, 1.0), roughness=0.74, metallic=0.12
    )
    mats["glass"] = base.bs.make_material(
        "Train_Glass_Refined", (0.14, 0.40, 0.48, 1.0), roughness=0.22, recipe="glass", seed=17, strength=0.12
    )
    mats["lamp"] = base.bs.make_material(
        "Train_Lamp_Refined", (1.0, 0.76, 0.28, 1.0), roughness=0.30, metallic=0.18
    )
    return mats


def _add_loco_readability_details(unit, mats):
    x0 = -16.0

    # Boiler bands: large enough to remain visible after downsampling.
    for idx, bx in enumerate((x0 - 1.38, x0 - 0.48, x0 + 0.42)):
        base._cylinder(
            f"Loco_BoilerBand_{idx}",
            (bx, 0.0, 1.72),
            0.715,
            0.075,
            mats["brass"],
            parent=unit,
            vertices=32,
            rotation=(0.0, math.radians(90.0), 0.0),
            bevel=0.010,
        )

    # Strong stack crown and dome collar sharpen the classic steam silhouette.
    base._cylinder(
        "Loco_StackCrown",
        (x0 - 1.62, 0.0, 3.22),
        0.43,
        0.12,
        mats["black"],
        parent=unit,
        vertices=24,
        bevel=0.025,
    )
    base._cylinder(
        "Loco_DomeCollar",
        (x0 - 0.55, 0.0, 2.30),
        0.36,
        0.10,
        mats["brass"],
        parent=unit,
        vertices=24,
        bevel=0.015,
    )

    # Cab cream framing makes the locomotive immediately distinct from coaches.
    cab_x = x0 + 1.72
    for side_y in (-0.965, 0.965):
        base._box(
            f"Loco_CabCreamRail_{'N' if side_y < 0 else 'F'}",
            (cab_x, side_y, 2.60),
            (1.35, 0.055, 0.10),
            mats["cream"],
            0.015,
            unit,
        )

    # Oversized front pilot/cowcatcher. Individual bars survive the 256px proxy.
    front_x = x0 - 2.92
    base._box("Loco_PilotBeam", (front_x, 0.0, 0.64), (0.16, 2.12, 0.18), mats["red"], 0.025, unit)
    for idx, py in enumerate((-0.72, -0.36, 0.0, 0.36, 0.72)):
        slat = base._box(
            f"Loco_PilotSlat_{idx}",
            (front_x - 0.30, py, 0.43),
            (0.72, 0.10, 0.10),
            mats["frame"],
            0.018,
            unit,
        )
        slat.rotation_euler[1] = math.radians(-22.0)

    # Large visible wheel counterweights and red rod anchor points.
    for side_y in (-1.075, 1.075):
        for idx, wx in enumerate((x0 - 1.05, x0 - 0.10, x0 + 0.85)):
            base._cylinder(
                f"Loco_DriveCounterweight_{idx}_{'L' if side_y < 0 else 'R'}",
                (wx, side_y, 0.46),
                0.16,
                0.08,
                mats["red"],
                parent=unit,
                vertices=20,
                rotation=(math.radians(90.0), 0.0, 0.0),
                bevel=0.010,
            )

    # Two whistles add a readable brass highlight behind the dome.
    for idx, wy in enumerate((-0.11, 0.11)):
        base._cylinder(
            f"Loco_Whistle_{idx}",
            (x0 + 0.34, wy, 2.72),
            0.055,
            0.28,
            mats["brass"],
            parent=unit,
            vertices=16,
            bevel=0.010,
        )


def build_locomotive_refined(root, mats, recipe):
    trailing = _original_build_locomotive(root, mats, recipe)
    unit = bpy.data.objects.get("LocomotiveRoot")
    if unit is None:
        raise RuntimeError("Refined steam train expected LocomotiveRoot from base builder")
    _add_loco_readability_details(unit, mats)
    return trailing


def build_coach_refined(root, mats, index, center_x, recipe):
    coach = _original_build_coach(root, mats, index, center_x, recipe)
    g = recipe["geometry"]
    length = float(g["coachLength"])
    width = float(g["coachWidth"])

    # Classic clerestory: a raised roof strip breaks the repeated flat-box shape.
    base._box(
        f"Coach_{index:02d}_Clerestory",
        (center_x, 0.0, 2.39),
        (length - 0.72, width * 0.52, 0.16),
        mats["roof"],
        0.055,
        coach,
    )

    # Bright upper belt and end posts increase separation between all seven cars.
    for side_y in (-width * 0.52, width * 0.52):
        base._box(
            f"Coach_{index:02d}_UpperRail_{'N' if side_y < 0 else 'F'}",
            (center_x, side_y, 2.03),
            (length - 0.34, 0.055, 0.095),
            mats["cream"],
            0.014,
            coach,
        )
    for ex in (center_x - length * 0.5 + 0.12, center_x + length * 0.5 - 0.12):
        base._box(
            f"Coach_{index:02d}_EndPost_{'A' if ex < center_x else 'B'}",
            (ex, -width * 0.52, 1.60),
            (0.10, 0.055, 1.08),
            mats["cream"],
            0.014,
            coach,
        )

    # A compact brass nameplate gives a strong mid-body highlight at gameplay scale.
    base._box(
        f"Coach_{index:02d}_Nameplate",
        (center_x, -width * 0.545, 1.13),
        (0.74, 0.035, 0.16),
        mats["brass"],
        0.012,
        coach,
    )
    return coach


# Monkey-patch the guarded v1 module so its existing preflight/proxy/final flow,
# metadata, approval SHA check and runtime contracts remain unchanged.
base.materials = materials_refined
base.build_locomotive = build_locomotive_refined
base.build_coach = build_coach_refined


if __name__ == "__main__":
    base.main()
