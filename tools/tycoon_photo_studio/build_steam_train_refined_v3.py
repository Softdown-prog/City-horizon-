"""Third visual refinement pass for the City Horizon guarded steam train.

Builds on build_steam_train_refined.py and keeps the same guarded quality flow.
This pass improves gameplay-scale readability without changing the consist:
1 steam locomotive with driver cab + exactly 7 passenger coaches.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_steam_train_refined as refined  # noqa: E402

base = refined.base

_original_build_locomotive = base.build_locomotive
_original_build_coach = base.build_coach
_original_build_for_gate = base.build_for_gate


def _wheel_face(name, x, y, z, radius, mats, parent, accent=False):
    """Thin outer wheel face that remains readable after 256px downsampling."""
    return base._cylinder(
        name,
        (x, y, z),
        radius,
        0.045,
        mats["red"] if accent else mats["frame"],
        parent=parent,
        vertices=28,
        rotation=(math.radians(90.0), 0.0, 0.0),
        bevel=0.010,
    )


def build_locomotive_v3(root, mats, recipe):
    trailing = _original_build_locomotive(root, mats, recipe)
    unit = bpy.data.objects.get("LocomotiveRoot")
    if unit is None:
        raise RuntimeError("Steam train v3 expected LocomotiveRoot")

    x0 = -16.0
    wheel_r = float(recipe["geometry"]["wheelRadius"])

    # Make the locomotive read immediately as the hero vehicle of the consist.
    # A warm smokebox badge and broad boiler handrail survive final downsampling.
    base._cylinder(
        "Loco_SmokeboxBadge_V3",
        (x0 - 2.505, -0.02, 1.72),
        0.27,
        0.055,
        mats["brass"],
        parent=unit,
        vertices=24,
        rotation=(0.0, math.radians(90.0), 0.0),
        bevel=0.010,
    )
    for side_y in (-0.735, 0.735):
        base._box(
            f"Loco_BoilerHandrail_{'N' if side_y < 0 else 'F'}_V3",
            (x0 - 0.45, side_y, 1.88),
            (3.25, 0.045, 0.055),
            mats["brass"],
            0.010,
            unit,
        )

    # Slightly taller stack cap and cab cornice sharpen the silhouette.
    base._cylinder(
        "Loco_StackTopRing_V3",
        (x0 - 1.62, 0.0, 3.31),
        0.47,
        0.10,
        mats["brass"],
        parent=unit,
        vertices=28,
        bevel=0.018,
    )
    cab_x = x0 + 1.72
    base._box(
        "Loco_CabCornice_V3",
        (cab_x, -0.01, 2.78),
        (1.72, 2.00, 0.10),
        mats["cream"],
        0.025,
        unit,
    )

    # Stronger visible wheel faces and a heavier coupling rod.
    for side_y in (-1.105, 1.105):
        for idx, wx in enumerate((x0 - 1.05, x0 - 0.10, x0 + 0.85)):
            _wheel_face(
                f"Loco_DriveWheelFace_{idx}_{'L' if side_y < 0 else 'R'}_V3",
                wx,
                side_y,
                wheel_r,
                wheel_r * 0.91,
                mats,
                unit,
                accent=True,
            )
        base._box(
            f"Loco_MainRod_{'L' if side_y < 0 else 'R'}_V3",
            (x0 - 0.10, side_y + (-0.025 if side_y < 0 else 0.025), wheel_r + 0.02),
            (2.82, 0.085, 0.13),
            mats["brass"],
            0.020,
            unit,
        )

    # Front pilot rails help the nose read at a glance.
    for side_y in (-0.92, 0.92):
        rail = base._box(
            f"Loco_PilotRail_{'L' if side_y < 0 else 'R'}_V3",
            (x0 - 3.02, side_y, 0.67),
            (0.72, 0.08, 0.09),
            mats["brass"],
            0.012,
            unit,
        )
        rail.rotation_euler[1] = math.radians(-12.0)

    return trailing


def build_coach_v3(root, mats, index, center_x, recipe):
    coach = _original_build_coach(root, mats, index, center_x, recipe)
    g = recipe["geometry"]
    length = float(g["coachLength"])
    width = float(g["coachWidth"])

    # Rounded roof shell: the lower half intersects the existing roof/body,
    # leaving a classic arched passenger-car crown visible from the CH camera.
    roof = base._cylinder(
        f"Coach_{index:02d}_ArchedRoof_V3",
        (center_x, 0.0, 2.26),
        width * 0.54,
        length + 0.12,
        mats["roof"],
        parent=coach,
        vertices=32,
        rotation=(0.0, math.radians(90.0), 0.0),
        bevel=0.020,
    )
    roof.scale.z = 0.34
    bpy.context.view_layer.objects.active = roof
    roof.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    roof.select_set(False)

    # Roof edge rails separate the crown from the green body at gameplay scale.
    for side_y in (-width * 0.54, width * 0.54):
        base._box(
            f"Coach_{index:02d}_RoofEdge_{'N' if side_y < 0 else 'F'}_V3",
            (center_x, side_y, 2.23),
            (length + 0.04, 0.055, 0.07),
            mats["cream"],
            0.012,
            coach,
        )

    # Wheel faces are intentionally brighter/larger than the base undercarriage.
    for side_y in (-width * 0.555, width * 0.555):
        for axle, wx in enumerate((center_x - 1.18, center_x + 1.18)):
            _wheel_face(
                f"Coach_{index:02d}_WheelFace_{axle}_{'L' if side_y < 0 else 'R'}_V3",
                wx,
                side_y,
                0.34,
                0.30,
                mats,
                coach,
                accent=False,
            )

    # Dark vestibule blocks make each car boundary obvious without widening gaps.
    for end, ex in (("A", center_x - length * 0.5 + 0.02), ("B", center_x + length * 0.5 - 0.02)):
        base._box(
            f"Coach_{index:02d}_Vestibule_{end}_V3",
            (ex, 0.0, 1.47),
            (0.13, width * 0.76, 1.02),
            mats["coach_dark"],
            0.018,
            coach,
        )

    return coach


def build_for_gate_v3(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, ground, authored, out = result

    # The seven-car consist was visually conservative in v2. Tighten framing a
    # little while preserving enough alpha margin for every direction.
    base.bs.calibrate_ortho_scale(scene, authored, safety_margin=0.09)
    base.bs.set_direction(root, base.bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    return recipe, studio, scene, root, ground, authored, out


# Keep all existing preflight/proxy/final logic and only replace visual authoring.
base.build_locomotive = build_locomotive_v3
base.build_coach = build_coach_v3
base.build_for_gate = build_for_gate_v3


if __name__ == "__main__":
    base.main()
