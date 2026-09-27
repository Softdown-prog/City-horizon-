"""RCT-reference proportion pass for the City Horizon Viking ship ride.

The user reference is used for park-scale readability and site layout only.  This pass
intentionally moves away from the previous glossy/miniature machine language: slim open
A-frames, a low long timber ship, a thin ride pad, and queue rails that fill the 5x4 site.
No final swing timing or frame count is defined here.
"""
from __future__ import annotations

import math

import build_ferris_wheel as fw
import viking_ship_rebuild_v2_geometry as v2
import viking_ship_rebuild_v3_geometry as v3


beam_between = v2.beam_between
hull_sections = v2.hull_sections


def _rail_line(name, a, b, g, mats, root):
    radius = float(g.get("railingRadius", 0.038))
    fw.cylinder_between(name, a, b, radius, mats["steelMid"], root, vertices=10)


def build_base(root, g, mats):
    """Thin integrated ride pad; deliberately not a tall glossy pedestal."""
    base_h = float(g["baseHeight"])
    deck_h = float(g["deckHeight"])
    fw.box(
        "RCTRidePadFoundation",
        (0.0, 0.0, base_h * 0.5),
        (float(g["baseWidth"]), float(g["baseDepth"]), base_h),
        mats["steelDark"],
        0.008,
        root,
    )
    fw.box(
        "RCTRidePad",
        (0.0, 0.0, base_h + deck_h * 0.5),
        (float(g["deckWidth"]), float(g["deckDepth"]), deck_h),
        mats["platformWhite"],
        0.006,
        root,
    )

    # Sparse slab joints read at game scale without turning the floor into a shiny prop.
    top_z = base_h + deck_h + 0.008
    for i in (-2, -1, 0, 1, 2):
        y = i * float(g["deckDepth"]) / 6.0
        fw.box(
            f"RCTPadJoint_{i:+d}",
            (0.0, y, top_z),
            (float(g["deckWidth"]) - 0.45, 0.018, 0.012),
            mats["platform"],
            0.002,
            root,
        )
    return root


def build_supports(root, g, mats):
    """Open, slim A-frame inspired by classic Tycoon ride readability."""
    pivot_z = float(g["pivotZ"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    inner_w = float(g["innerBraceWidth"])
    inner_d = float(g["innerBraceDepth"])
    bevel = float(g["primaryBevel"])
    supports = []

    for y_sign, side in ((-1.0, "Front"), (1.0, "Back")):
        y = y_sign * half_y
        for x_sign, label in ((-1.0, "L"), (1.0, "R")):
            foot = (x_sign * half_x, y, 0.62)
            apex = (x_sign * 0.18, y, pivot_z - 0.20)
            supports.append(
                beam_between(
                    f"RCTV5MainLeg_{side}_{label}",
                    foot,
                    apex,
                    beam_w,
                    beam_d,
                    mats["steelDark"],
                    root,
                    bevel,
                )
            )
            # One restrained inner member gives the silhouette structure without candy trim.
            inner_foot = (x_sign * (half_x - 0.62), y, 0.78)
            inner_apex = (x_sign * 0.56, y, pivot_z * 0.78)
            beam_between(
                f"RCTV5InnerBrace_{side}_{label}",
                inner_foot,
                inner_apex,
                inner_w,
                inner_d,
                mats["steelMid"],
                root,
                max(0.006, bevel * 0.55),
            )

            # Flat foot plate + bolts, kept compact so the supports do not look like blocks.
            fw.box(
                f"RCTV5FootPlate_{side}_{label}",
                (foot[0], foot[1], 0.48),
                (0.78, 0.66, 0.10),
                mats["steelMid"],
                0.008,
                root,
            )
            for bx in (-0.25, 0.25):
                for by in (-0.19, 0.19):
                    fw.cylinder(
                        f"RCTV5FootBolt_{side}_{label}_{bx:+.2f}_{by:+.2f}",
                        (foot[0] + bx, foot[1] + by, 0.56),
                        0.045,
                        0.075,
                        mats["steelLight"],
                        parent=root,
                        vertices=10,
                    )

        # Low cross member only; upper opening stays visually clear.
        z = pivot_z * 0.28
        beam_between(
            f"RCTV5LowCross_{side}",
            (-half_x * 0.80, y, z),
            (half_x * 0.80, y, z),
            float(g["lowerCrossBraceWidth"]),
            float(g["lowerCrossBraceDepth"]),
            mats["steelMid"],
            root,
            0.008,
        )

    # Long top axle is exposed and functional, not hidden by a roof-like cap.
    fw.cylinder(
        "RCTV5MainAxle",
        (0.0, 0.0, pivot_z),
        float(g["axleRadius"]),
        float(g["axleDepth"]),
        mats["steelMid"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=root,
        vertices=16,
    )
    return supports


def build_loading_zone(root, g, mats):
    """Use the footprint as a park ride site: queue lanes + broad open boarding area."""
    top_z = float(g["baseHeight"]) + float(g["deckHeight"])
    rail_z = top_z + float(g["railingHeight"])
    half_w = float(g["loadingPlatformWidth"]) * 0.5
    half_d = float(g["loadingPlatformDepth"]) * 0.5

    # Low, matte boarding strip rather than a second raised white slab.
    fw.box(
        "RCTV5BoardingStrip",
        (0.0, -1.35, top_z + 0.055),
        (float(g["loadingPlatformWidth"]), float(g["loadingPlatformDepth"]), 0.11),
        mats["panelCream"],
        0.006,
        root,
    )

    # Perimeter rail along the public/front edge, with a generous entrance opening.
    front_y = -half_d
    for x0, x1, idx in ((-half_w, -2.0, 0), (2.0, half_w, 1)):
        _rail_line(f"RCTV5FrontRail_{idx}", (x0, front_y, rail_z), (x1, front_y, rail_z), g, mats, root)
        for x in (x0, x1):
            _rail_line(f"RCTV5FrontPost_{idx}_{x:+.2f}", (x, front_y, top_z), (x, front_y, rail_z), g, mats, root)

    # Three long queue dividers create the RCT-like site read and expose the ride scale.
    queue_y0 = front_y + 0.78
    queue_y1 = min(half_d - 0.55, queue_y0 + 3.0)
    for i, x in enumerate((-4.25, -1.42, 1.42, 4.25)):
        _rail_line(f"RCTV5QueueTop_{i}", (x, queue_y0, rail_z), (x, queue_y1, rail_z), g, mats, root)
        for y in (queue_y0, queue_y1):
            _rail_line(f"RCTV5QueuePost_{i}_{y:+.2f}", (x, y, top_z), (x, y, rail_z), g, mats, root)

    # Broad, shallow entrance steps centered on the opening.
    steps = int(g.get("stairSteps", 5))
    step_w = float(g["stairWidth"])
    step_d = float(g["stairDepth"]) / max(1, steps)
    for i in range(steps):
        h = (i + 1) * (top_z / max(1, steps))
        y = front_y - float(g["stairDepth"]) + (i + 0.5) * step_d
        fw.box(
            f"RCTV5EntryStep_{i:02d}",
            (0.0, y, h * 0.5),
            (step_w, step_d + 0.02, h),
            mats["platformWhite"],
            0.004,
            root,
        )
    return root


def build_swing_group(root, g, mats):
    # V3 already provides the mechanically connected pivot/clevis setup and the V2
    # faceted timber hull.  V5 changes its proportions/material palette in the recipe.
    return v3.build_swing_group(root, g, mats)
