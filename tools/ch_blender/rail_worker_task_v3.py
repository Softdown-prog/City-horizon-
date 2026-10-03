#!/usr/bin/env python3
from __future__ import annotations

import math

import rail_worker_task as base
import build_rail_track_guarded as rail


def _turnout_curve_overlay_v3(root, spec, mats, turn: str):
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    sleeper_len = float(spec["sleeperLength"])
    sleeper_w = float(spec["sleeperWidth"])
    sleeper_h = float(spec["sleeperHeight"])
    sleeper_count = int(spec["sleeperCount"])
    ballast_w = float(spec["ballastWidth"])
    ballast_h = float(spec["ballastHeight"])
    radius = tile * 0.5
    segments = int(spec.get("curveSegments", 32))

    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle = -math.pi * 0.5
        end_angle = 0.0
        tangent_sign = 1.0
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle = math.pi * 0.5
        end_angle = 0.0
        tangent_sign = -1.0

    # Keep the shared throat on the straight roadbed and only begin branch ballast
    # after the two routes have visibly separated.  This removes coplanar overlap/z-fighting.
    bed_t = 0.30
    bed_start = start_angle + (end_angle - start_angle) * bed_t
    rail._arc_prism(
        "DivergeBallast", center, radius, ballast_w, 0.0, ballast_h * 0.94,
        bed_start, end_angle, max(12, int(segments * (1.0 - bed_t))), mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        if t < 0.40:
            continue
        angle = start_angle + (end_angle - start_angle) * t
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        rotation_z = angle + tangent_sign * math.pi * 0.5
        rail._painted_sleeper(
            root, mats, 100 + index,
            (x, y, ballast_h + sleeper_h * 0.5), rotation_z,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_base = ballast_h + sleeper_h
    for index, rail_radius in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if index == 0 else "Outer"
        rail._arc_prism(
            f"DivergeRail_{side}", center, rail_radius, rail_w, rail_base, rail_h,
            start_angle, end_angle, segments, mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        rail._arc_prism(
            f"DivergeRailWeb_{side}", center, rail_radius, rail_w * 0.52,
            rail_base, rail_h * 0.72,
            start_angle, end_angle, segments, mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )

    # Small dark frog marker at the route crossing gives the 2D bake a deliberate junction
    # instead of two bright rails appearing to pass through one another.
    frog_x = -tile * 0.5 + tile * 0.42
    frog_y = (gauge * 0.5) * (1.0 if turn == "left" else -1.0)
    rail._box(
        "TurnoutFrog", (frog_x, frog_y, rail_base + rail_h + 0.006),
        (rail_w * 1.9, rail_w * 1.9, 0.012), mats["steel_side"], root,
        "rail.turnout_frog", ground_contact=False,
    )


def _rail_segment(root, mats, name, axis, offset, start, end, rail_w, rail_h, rail_z):
    length = end - start
    if length <= 1.0e-5:
        return
    center = (start + end) * 0.5
    if axis == 0:
        loc = (center, offset, rail_z)
        dims = (length, rail_w, rail_h)
        web_loc = (center, offset, rail_z - rail_h * 0.34)
        web_dims = (length, rail_w * 0.52, rail_h * 0.72)
    else:
        loc = (-offset, center, rail_z)
        dims = (rail_w, length, rail_h)
        web_loc = (-offset, center, rail_z - rail_h * 0.34)
        web_dims = (rail_w * 0.52, length, rail_h * 0.72)
    rail._box(name, loc, dims, mats["steel"], root, "rail.steel", ground_contact=False)
    rail._box(name + "Web", web_loc, web_dims, mats["steel_side"], root, "rail.steel_web", ground_contact=False)


def _build_clean_crossing_v3(root, spec, mats):
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    sleeper_len = float(spec["sleeperLength"])
    sleeper_w = float(spec["sleeperWidth"])
    sleeper_h = float(spec["sleeperHeight"])
    sleeper_count = int(spec["sleeperCount"])
    ballast_w = float(spec["ballastWidth"])
    ballast_h = float(spec["ballastHeight"])

    # Build a cross from five non-overlapping pieces.  Revision 2 used two coplanar full
    # rectangles, which created the large dark square visible in the proxy.
    arm = max(0.0, (tile - ballast_w) * 0.5)
    rail._box("BallastCenter", (0.0, 0.0, ballast_h * 0.5),
              (ballast_w, ballast_w, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)
    if arm > 0.0:
        c = ballast_w * 0.5 + arm * 0.5
        rail._box("BallastWest", (-c, 0.0, ballast_h * 0.5), (arm, ballast_w, ballast_h), mats["ballast"], root, "rail.ballast", ground_contact=True)
        rail._box("BallastEast", (c, 0.0, ballast_h * 0.5), (arm, ballast_w, ballast_h), mats["ballast"], root, "rail.ballast", ground_contact=True)
        rail._box("BallastSouth", (0.0, -c, ballast_h * 0.5), (ballast_w, arm, ballast_h), mats["ballast"], root, "rail.ballast", ground_contact=True)
        rail._box("BallastNorth", (0.0, c, ballast_h * 0.5), (ballast_w, arm, ballast_h), mats["ballast"], root, "rail.ballast", ground_contact=True)

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5
    center_clearance = ballast_w * 0.48
    for axis in (0, 1):
        rotation = 0.0 if axis == 0 else math.pi * 0.5
        for index in range(sleeper_count):
            pos = start + spacing * index
            if abs(pos) < center_clearance:
                continue
            loc = (pos, 0.0, ballast_h + sleeper_h * 0.5) if axis == 0 else (0.0, pos, ballast_h + sleeper_h * 0.5)
            rail._painted_sleeper(root, mats, axis * 100 + index, loc, rotation,
                                  sleeper_w, sleeper_len, sleeper_h, ballast_h)

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    half = tile * 0.5
    gap = max(rail_w * 1.8, 0.15)
    cuts = (-gauge * 0.5, gauge * 0.5)
    intervals = [(-half, cuts[0] - gap * 0.5),
                 (cuts[0] + gap * 0.5, cuts[1] - gap * 0.5),
                 (cuts[1] + gap * 0.5, half)]
    for axis in (0, 1):
        for side, offset in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
            for idx, (a, b) in enumerate(intervals):
                _rail_segment(root, mats, f"CrossRail_{axis}_{side}_{idx}", axis, offset, a, b, rail_w, rail_h, rail_z)

    joint_z = ballast_h + sleeper_h + rail_h + 0.006
    joint = max(rail_w * 1.7, 0.14)
    for x in (-gauge * 0.5, gauge * 0.5):
        for y in (-gauge * 0.5, gauge * 0.5):
            rail._box(
                f"CrossFrog_{'p' if x > 0 else 'm'}x_{'p' if y > 0 else 'm'}y",
                (x, y, joint_z), (joint, joint, 0.012), mats["steel_side"], root,
                "rail.crossing_frog", ground_contact=False,
            )


def main():
    base._turnout_curve_overlay = _turnout_curve_overlay_v3
    base._build_clean_crossing = _build_clean_crossing_v3
    base.main()


if __name__ == "__main__":
    main()
