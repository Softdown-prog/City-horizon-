"""Procedural detail pass for the City Horizon Ferris wheel.

This module deliberately adds only chunky, gameplay-readable geometry. The game
runtime remains 2D RGBA sprites; CH Blender is the offline 3D authoring source.
Fine details that would disappear in the final downsample are intentionally
avoided.
"""
from __future__ import annotations

import math


def _build_support_finishing(root, g, mats, fw):
    """Add engineered ties and a compact loading/control zone."""
    half_x = float(g["supportBaseHalfWidth"])
    half_y = float(g["supportBaseHalfDepth"])
    center_z = float(g["wheelCenterZ"])
    support_r = float(g["supportRadius"])

    # Mid-height ties make the A-frame read as a real fabricated structure after
    # downsample without filling the silhouette with tiny truss noise.
    tie_z = center_z * 0.43
    tie_half_x = half_x * 0.58
    for side_y, label in ((-half_y, "South"), (half_y, "North")):
        fw.cylinder_between(
            f"SupportTie_{label}",
            (-tie_half_x, side_y * 0.63, tie_z),
            (tie_half_x, side_y * 0.63, tie_z),
            support_r * 0.72,
            mats["frame"],
            root,
            vertices=20,
        )

    platform_w = float(g["entryPlatformWidth"])
    platform_d = float(g["entryPlatformDepth"])
    platform_h = float(g["entryPlatformHeight"])
    platform_y = -half_y - platform_d * 0.48

    # Thick edge curb gives the platform a finished manufactured read.
    curb_h = max(0.07, platform_h * 0.42)
    front_y = platform_y - platform_d * 0.5 + 0.035
    back_y = platform_y + platform_d * 0.5 - 0.035
    for y, label in ((front_y, "Front"), (back_y, "Back")):
        fw.box(
            f"PlatformCurb_{label}",
            (0.0, y, platform_h + curb_h * 0.5),
            (platform_w * 0.94, 0.07, curb_h),
            mats["dark"],
            0.025,
            root,
        )

    # Compact operator console: large enough to read in the 2D sprite, small
    # enough not to turn into a separate building.
    console_x = platform_w * 0.34
    console_y = platform_y + platform_d * 0.08
    fw.box(
        "OperatorConsoleBody",
        (console_x, console_y, platform_h + 0.30),
        (0.38, 0.32, 0.52),
        mats["dark"],
        0.055,
        root,
    )
    fw.box(
        "OperatorConsolePanel",
        (console_x, console_y - 0.17, platform_h + 0.43),
        (0.30, 0.055, 0.18),
        mats["accentC"],
        0.025,
        root,
    )

    # Entry gate arms frame the stair opening and make boarding direction clear.
    stair_w = float(g.get("stairWidth", 0.92))
    gate_x = stair_w * 0.62
    gate_y = platform_y - platform_d * 0.5 + 0.04
    gate_h = platform_h + 0.62
    for side, x in (("L", -gate_x), ("R", gate_x)):
        fw.cylinder(
            f"EntryGatePost_{side}",
            (x, gate_y, platform_h + 0.31),
            0.045,
            0.62,
            mats["frame"],
            parent=root,
            vertices=16,
        )
    fw.cylinder_between(
        "EntryGateHeader",
        (-gate_x, gate_y, gate_h),
        (gate_x, gate_y, gate_h),
        0.045,
        mats["frame"],
        root,
        vertices=16,
    )


def _build_wheel_finishing(rotor, g, mats, fw):
    """Add hub collars and restrained secondary bracing for a stronger 2D read."""
    radius = float(g["wheelRadius"])
    hub_r = float(g["hubRadius"])
    axle_depth = float(g["axleDepth"])
    spoke_r = float(g["spokeRadius"])

    # Hub caps on both visible sides add depth when the asset rotates to E/W.
    for y, label in ((-axle_depth * 0.58, "Front"), (axle_depth * 0.58, "Rear")):
        fw.cylinder(
            f"WheelHubCap_{label}",
            (0.0, y, 0.0),
            hub_r * 1.22,
            0.10,
            mats["frame"],
            rotation=(math.radians(90.0), 0.0, 0.0),
            parent=rotor,
            vertices=28,
        )

    # Six diagonal chords give the wheel a professional truss rhythm while
    # remaining broad enough to survive the gameplay downsample.
    chord_r = max(0.025, spoke_r * 0.78)
    inner_r = radius * 0.46
    outer_r = radius * 0.88
    for i in range(6):
        a0 = math.tau * i / 6.0
        a1 = a0 + math.tau / 12.0
        start = (math.sin(a0) * inner_r, 0.0, math.cos(a0) * inner_r)
        end = (math.sin(a1) * outer_r, 0.0, math.cos(a1) * outer_r)
        fw.cylinder_between(
            f"WheelChord_{i:02d}",
            start,
            end,
            chord_r,
            mats["frame"],
            rotor,
            vertices=16,
        )


def _build_gondola_finishing(gondola_pivots, g, mats, fw):
    """Give each cabin an interior/trim read instead of a plain rounded box."""
    w = float(g["gondolaWidth"])
    d = float(g["gondolaDepth"])
    h = float(g["gondolaBodyHeight"])
    drop = float(g["gondolaDrop"])
    body_z = -drop - h * 0.48

    for i, pivot in enumerate(gondola_pivots):
        # Dark recessed backrest suggests a usable cabin interior in a single
        # chunky shape that remains visible at 256px proxy/gameplay scale.
        fw.box(
            f"GondolaBackrest_{i:02d}",
            (0.0, d * 0.34, body_z + h * 0.10),
            (w * 0.72, 0.08, h * 0.42),
            mats["dark"],
            0.035,
            pivot,
        )
        fw.box(
            f"GondolaSeat_{i:02d}",
            (0.0, d * 0.18, body_z - h * 0.12),
            (w * 0.72, d * 0.42, 0.09),
            mats["frame"],
            0.035,
            pivot,
        )

        # A broad contrasting front trim band breaks the remaining cube read.
        fw.box(
            f"GondolaFrontTrim_{i:02d}",
            (0.0, -d * 0.505, body_z - h * 0.06),
            (w * 0.76, 0.055, h * 0.16),
            mats["frame"],
            0.025,
            pivot,
        )

        # Short side rails connect the roof posts visually and make the cabin
        # look assembled rather than carved from one block.
        rail_z = body_z + h * 0.35
        for side, x in (("L", -w * 0.43), ("R", w * 0.43)):
            fw.cylinder_between(
                f"GondolaSideRail_{i:02d}_{side}",
                (x, -d * 0.39, rail_z),
                (x, d * 0.30, rail_z),
                0.025,
                mats["hub"],
                pivot,
                vertices=12,
            )


def apply_detail_pass(root, rotor, gondola_pivots, g, mats, fw):
    """Apply the restrained professional-detail pass used by CH Blender."""
    _build_support_finishing(root, g, mats, fw)
    _build_wheel_finishing(rotor, g, mats, fw)
    _build_gondola_finishing(gondola_pivots, g, mats, fw)
    root["detailPass"] = "FERRIS_2D_READABILITY_V1"
    root["detailPolicy"] = "chunky_gameplay_readable_no_microdetail"
