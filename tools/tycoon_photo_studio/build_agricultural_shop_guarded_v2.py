"""Detail pass v2 for the guarded City Horizon agricultural shop.

This module deliberately layers readable 2D-city-builder detail on top of the
already validated agricultural shop scene. It keeps the exact CH Blender gate,
camera, lighting, footprint and runtime contracts from the base builder.
"""
from __future__ import annotations

import math

import build_agricultural_shop_guarded as base


_original_build_shop = base.build_shop


def _roof_z(x: float) -> float:
    # Base roof: eave z=2.58 at |x|=2.64, ridge z=3.43 at x=0.
    return 3.43 - (0.85 / 2.64) * abs(x)


def _add_side_window(root, mats, name, x, y, z=1.42, width=0.92, height=0.88):
    # Window mounted on the east/west wall; X is the wall-normal axis.
    base._box(name + "_Frame", (x, y, z), (0.12, width + 0.18, height + 0.18), mats["wood"], 0.025, root)
    face_x = x + (0.07 if x > 0 else -0.07)
    base._box(name + "_Glass", (face_x, y, z), (0.045, width, height), mats["glass"], 0.012, root)
    trim_x = x + (0.095 if x > 0 else -0.095)
    base._box(name + "_MullionV", (trim_x, y, z), (0.055, 0.07, height), mats["cream"], 0.010, root)
    base._box(name + "_MullionH", (trim_x, y, z), (0.055, width, 0.07), mats["cream"], 0.010, root)
    base._box(name + "_Sill", (trim_x, y, z - height * 0.55), (0.16, width + 0.24, 0.10), mats["stone"], 0.018, root)


def _add_roof_detail(root, mats):
    # Broad standing seams survive the 256 px gameplay sprite much better than
    # tiny tile/texture noise and make the roof read as authored material.
    for i, x in enumerate((-2.15, -1.62, -1.08, -0.54, 0.54, 1.08, 1.62, 2.15)):
        base._box(
            f"RoofStandingSeam_{i}",
            (x, 0.0, _roof_z(x) + 0.035),
            (0.055, 4.66, 0.065),
            mats["accent"],
            0.012,
            root,
        )

    # Small ridge vent / cupola gives a stronger silhouette without changing
    # the building's gameplay footprint.
    base._box("RoofVentBase", (0.0, 0.52, 3.50), (0.62, 0.62, 0.18), mats["wood"], 0.035, root)
    base._box("RoofVentBody", (0.0, 0.52, 3.72), (0.48, 0.48, 0.38), mats["cream"], 0.035, root)
    for side, sx in (("L", -0.255), ("R", 0.255)):
        base._box(f"RoofVentTrim_{side}", (sx, 0.52, 3.72), (0.055, 0.52, 0.42), mats["wood"], 0.012, root)
    vent_roof = base._box("RoofVentCap", (0.0, 0.52, 3.98), (0.76, 0.76, 0.13), mats["roof"], 0.025, root)
    vent_roof.rotation_euler[2] = math.radians(45.0)


def _add_front_architecture(root, mats):
    # Readable front-gable timbering and porch structure.
    base._box("GableVerticalTrim", (0.0, -2.17, 2.78), (0.13, 0.12, 0.92), mats["wood"], 0.018, root)
    base._box("PorchHeader", (0.0, -2.61, 1.96), (4.36, 0.16, 0.20), mats["wood"], 0.025, root)

    for side, x, tilt in (("L", -1.91, -37.0), ("R", 1.91, 37.0)):
        brace = base._box(f"PorchBrace_{side}", (x, -2.62, 1.72), (0.11, 0.14, 0.72), mats["wood_light"], 0.018, root)
        brace.rotation_euler[1] = math.radians(tilt)

    # Strong sills and planter boxes under the two front windows.
    for side, x in (("L", -1.52), ("R", 1.52)):
        base._box(f"FrontSill_{side}", (x, -2.245, 0.88), (1.44, 0.20, 0.13), mats["stone"], 0.020, root)
        base._box(f"WindowPlanter_{side}", (x, -2.40, 0.77), (1.12, 0.32, 0.23), mats["wood_light"], 0.025, root)
        for n, dx in enumerate((-0.36, -0.12, 0.14, 0.37)):
            leaf = base._sphere(
                f"PlanterLeaf_{side}_{n}",
                (x + dx, -2.44, 0.98 + (n % 2) * 0.05),
                0.13,
                mats["green"],
                parent=root,
                scale=(0.72, 0.52, 1.20),
            )
            leaf.rotation_euler[1] = math.radians((-18, 10, -8, 16)[n])


def _add_side_story(root, mats):
    # Side-wall features remain legible after rotation and prevent the asset
    # looking like a decorated facade pasted onto an empty box.
    _add_side_window(root, mats, "EastWindow", 2.50, 0.62)
    _add_side_window(root, mats, "WestWindow", -2.50, -0.42)

    # Feed/seed rack on east side.
    base._box("SeedRack", (2.58, -1.08, 0.58), (0.42, 1.10, 1.02), mats["wood"], 0.035, root)
    for i, (y, z, color) in enumerate(((-1.34, 0.43, "cream"), (-1.03, 0.61, "yellow"), (-0.77, 0.39, "green"))):
        sack = base._sphere(
            f"SeedBagSide_{i}",
            (2.82, y, z),
            0.25,
            mats[color],
            parent=root,
            scale=(0.66, 1.12, 0.84),
        )
        sack.rotation_euler[0] = math.radians(8.0 * (i - 1))

    # Large garden-tool silhouettes on west side.
    for name, y, height in (("Shovel", -1.18, 1.58), ("Rake", -0.82, 1.72)):
        base._cylinder(
            f"{name}Handle",
            (-2.62, y, 0.82),
            0.035,
            height,
            mats["wood_light"],
            parent=root,
            vertices=12,
        )
    base._box("ShovelBlade", (-2.62, -1.18, 0.16), (0.20, 0.28, 0.25), mats["dark"], 0.035, root)
    base._box("RakeHead", (-2.62, -0.82, 0.14), (0.18, 0.55, 0.12), mats["dark"], 0.025, root)


def build_shop_v2(root, mats):
    _original_build_shop(root, mats)
    _add_roof_detail(root, mats)
    _add_front_architecture(root, mats)
    _add_side_story(root, mats)


base.build_shop = build_shop_v2


if __name__ == "__main__":
    base.main()
