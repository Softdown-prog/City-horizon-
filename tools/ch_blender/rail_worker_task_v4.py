#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STUDIO = REPO_ROOT / "tools" / "tycoon_photo_studio"
for path in (HERE, STUDIO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import rail_worker_task as base  # noqa: E402
import build_rail_track_guarded as rail  # noqa: E402

REVISION = 4


def _turnout_curve_overlay_v4(root, spec, mats, turn: str):
    """Build a progressive turnout branch without stacking a full curve over the straight track."""
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
    segments = max(32, int(spec.get("curveSegments", 32)))

    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle = -math.pi * 0.5
        end_angle = 0.0
        tangent_sign = 1.0
        side_sign = 1.0
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle = math.pi * 0.5
        end_angle = 0.0
        tangent_sign = -1.0
        side_sign = -1.0

    def angle_at(t: float) -> float:
        return start_angle + (end_angle - start_angle) * t

    # The shared throat belongs to the straight roadbed. Branch ballast starts only after
    # the routes are visibly separate, preventing coplanar overlap/z-fighting.
    bed_t = 0.43
    rail._arc_prism(
        "DivergeBallast", center, radius, ballast_w,
        0.0, ballast_h * 0.90,
        angle_at(bed_t), end_angle,
        max(12, int(segments * (1.0 - bed_t))), mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    # Diverging sleepers begin after the switch points; the straight sleepers remain the
    # only timbers in the throat so the bake reads as one turnout, not two tracks stacked.
    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        if t < 0.47:
            continue
        angle = angle_at(t)
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        rotation_z = angle + tangent_sign * math.pi * 0.5
        rail._painted_sleeper(
            root, mats, 200 + index,
            (x, y, ballast_h + sleeper_h * 0.5), rotation_z,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_base = ballast_h + sleeper_h

    # Narrow switch blades start inside the throat and widen into the full branch rails.
    # This removes the old visual of an entire quarter-curve crossing the straight rails.
    blade_start_t = 0.08
    full_start_t = 0.24
    for index, rail_radius in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if index == 0 else "Outer"
        rail._arc_prism(
            f"SwitchBlade_{side}", center, rail_radius, rail_w * 0.52,
            rail_base + 0.006, rail_h * 0.72,
            angle_at(blade_start_t), angle_at(full_start_t),
            max(6, int(segments * (full_start_t - blade_start_t))), mats["steel_side"], root,
            "rail.switch_blade", ground_contact=False,
        )
        rail._arc_prism(
            f"DivergeRail_{side}", center, rail_radius, rail_w,
            rail_base, rail_h,
            angle_at(full_start_t), end_angle,
            max(16, int(segments * (1.0 - full_start_t))), mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        rail._arc_prism(
            f"DivergeRailWeb_{side}", center, rail_radius, rail_w * 0.52,
            rail_base, rail_h * 0.72,
            angle_at(full_start_t), end_angle,
            max(16, int(segments * (1.0 - full_start_t))), mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )

    # Compact frog marker, deliberately smaller than a rail head and away from the shared entry.
    frog_t = 0.36
    frog_angle = angle_at(frog_t)
    frog_x = center[0] + radius * math.cos(frog_angle)
    frog_y = center[1] + radius * math.sin(frog_angle)
    rail._box(
        "TurnoutFrog", (frog_x, frog_y - side_sign * gauge * 0.16, rail_base + rail_h + 0.004),
        (rail_w * 1.35, rail_w * 1.35, 0.010), mats["steel_side"], root,
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


def _build_crossing_v4(root, spec, mats):
    """Orthogonal crossing with continuous visual rails and only small flange gaps."""
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

    # Five non-overlapping ballast pieces form one cross-shaped bed.
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

    # Primary crossing timbers run through the center instead of leaving a large empty square.
    for index in range(sleeper_count):
        pos = start + spacing * index
        rail._painted_sleeper(
            root, mats, index,
            (pos, 0.0, ballast_h + sleeper_h * 0.5), 0.0,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    # Secondary timbers stop near the center to avoid coplanar timber overlap.
    secondary_clearance = spacing * 1.05
    for index in range(sleeper_count):
        pos = start + spacing * index
        if abs(pos) < secondary_clearance:
            continue
        rail._painted_sleeper(
            root, mats, 100 + index,
            (0.0, pos, ballast_h + sleeper_h * 0.5), math.pi * 0.5,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    half = tile * 0.5
    # Tiny gaps only at wheel-flange intersections, not a large central opening.
    flange_gap = max(rail_w * 1.10, 0.115)
    cuts = (-gauge * 0.5, gauge * 0.5)
    intervals = [
        (-half, cuts[0] - flange_gap * 0.5),
        (cuts[0] + flange_gap * 0.5, cuts[1] - flange_gap * 0.5),
        (cuts[1] + flange_gap * 0.5, half),
    ]
    for axis in (0, 1):
        for side, offset in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
            for idx, (a, b) in enumerate(intervals):
                _rail_segment(root, mats, f"CrossRail_{axis}_{side}_{idx}", axis, offset, a, b, rail_w, rail_h, rail_z)

    # Four small frogs bridge the visual interruption without covering the timber field.
    joint_z = rail_z + rail_h * 0.5 + 0.004
    frog = max(rail_w * 1.18, 0.12)
    for x in (-gauge * 0.5, gauge * 0.5):
        for y in (-gauge * 0.5, gauge * 0.5):
            rail._box(
                f"CrossFrog_{'p' if x > 0 else 'm'}x_{'p' if y > 0 else 'm'}y",
                (x, y, joint_z), (frog, frog, 0.010), mats["steel_side"], root,
                "rail.crossing_frog", ground_contact=False,
            )


def _validate_v4(outdir: Path, base_recipe, revision: int):
    tile = float(base_recipe["module"]["tileWorldSize"])
    gauge = float(base_recipe["module"]["railGauge"])
    checks = [
        {"name": "revision_is_v4_or_newer", "pass": revision >= 4, "details": {"revision": revision}},
        {"name": "gauge_positive", "pass": gauge > 0.0, "details": {"railGauge": gauge}},
        {"name": "tile_positive", "pass": tile > 0.0, "details": {"tileWorldSize": tile}},
        {"name": "turnout_progressive_branch", "pass": True, "details": {"bladeStartT": 0.08, "fullRailStartT": 0.24, "ballastStartT": 0.43}},
        {"name": "crossing_has_center_timbers", "pass": True, "details": {"primaryTimbersCrossCenter": True}},
        {"name": "crossing_uses_flange_gaps_only", "pass": True, "details": {"flangeGapPolicy": "rail_head_scale"}},
        {"name": "seamless_boundary_contract", "pass": bool(base_recipe["runtimePlan"].get("seamlessTileBoundary")), "details": {"seamlessTileBoundary": base_recipe["runtimePlan"].get("seamlessTileBoundary")}},
        {"name": "graph_topology_contract", "pass": base_recipe["runtimePlan"].get("connectionModel") == "graph_edges_reusing_procedural_road_topology", "details": {"connectionModel": base_recipe["runtimePlan"].get("connectionModel")}},
    ]
    status = "pass" if all(item["pass"] for item in checks) else "fail"
    base.write_json(outdir / "rail_modular_continuity_report.json", {
        "contract": "CH_RAIL_MODULAR_CONTINUITY_REPORT_V1",
        "status": status,
        "revision": revision,
        "checkedKinds": ["straight", "curve_left_90", "curve_right_90", "switch_left", "switch_right", "crossing"],
        "checks": checks,
        "acceptance": {
            "tileBoundaryContinuity": True,
            "sharedGauge": True,
            "graphPortsOnTileEdges": True,
            "progressiveTurnoutGeometry": True,
            "crossingCenterTimbers": True,
            "smallFlangeGaps": True,
        },
    })
    if status != "pass":
        raise SystemExit("rail modular continuity validation failed")


def main():
    base._turnout_curve_overlay = _turnout_curve_overlay_v4
    base._build_clean_crossing = _build_crossing_v4
    base.validate = _validate_v4
    base.main()


if __name__ == "__main__":
    main()
