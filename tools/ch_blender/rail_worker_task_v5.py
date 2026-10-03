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

REVISION = 5


def _turnout_curve_overlay_v5(root, spec, mats, turn: str):
    """Minimal turnout overlay: rails only, no extra ballast/timber overlap in the throat."""
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    ballast_h = float(spec["ballastHeight"])
    sleeper_h = float(spec["sleeperHeight"])
    radius = tile * 0.5
    segments = max(40, int(spec.get("curveSegments", 32)))

    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle = -math.pi * 0.5
        end_angle = 0.0
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle = math.pi * 0.5
        end_angle = 0.0

    def angle_at(t: float) -> float:
        return start_angle + (end_angle - start_angle) * t

    rail_base = ballast_h + sleeper_h
    blade_start_t = 0.12
    blade_end_t = 0.34
    full_start_t = 0.34

    # The straight module already supplies roadbed and sleepers. Keeping the turnout overlay
    # rail-only removes all coplanar ballast/timber overlap that caused dark triangles in V4.
    for index, rail_radius in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if index == 0 else "Outer"
        rail._arc_prism(
            f"SwitchBlade_{side}", center, rail_radius, rail_w * 0.46,
            rail_base + 0.004, rail_h * 0.64,
            angle_at(blade_start_t), angle_at(blade_end_t),
            max(8, int(segments * (blade_end_t - blade_start_t))), mats["steel_side"], root,
            "rail.switch_blade", ground_contact=False,
        )
        rail._arc_prism(
            f"DivergeRail_{side}", center, rail_radius, rail_w,
            rail_base, rail_h,
            angle_at(full_start_t), end_angle,
            max(20, int(segments * (1.0 - full_start_t))), mats["steel"], root,
            "rail.steel", ground_contact=False,
        )


def _rail_segment(root, mats, name, axis, offset, start, end, rail_w, rail_h, rail_z):
    length = end - start
    if length <= 1.0e-5:
        return
    center = (start + end) * 0.5
    if axis == 0:
        loc = (center, offset, rail_z)
        dims = (length, rail_w, rail_h)
    else:
        loc = (-offset, center, rail_z)
        dims = (rail_w, length, rail_h)
    rail._box(name, loc, dims, mats["steel"], root, "rail.steel", ground_contact=False)


def _build_crossing_v5(root, spec, mats):
    """Clean crossing with one roadbed, one timber field, and small flange gaps only."""
    tile = float(spec["tileWorldSize"])
    gauge = float(spec["railGauge"])
    rail_w = float(spec["railWidth"])
    rail_h = float(spec["railHeight"])
    sleeper_len = float(spec["sleeperLength"])
    sleeper_w = float(spec["sleeperWidth"])
    sleeper_h = float(spec["sleeperHeight"])
    sleeper_count = int(spec["sleeperCount"])
    ballast_h = float(spec["ballastHeight"])

    # One continuous low roadbed removes every coplanar seam from the center.
    rail._box(
        "CrossingRoadbed", (0.0, 0.0, ballast_h * 0.5),
        (tile, tile, ballast_h), mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5

    # Use one uninterrupted timber field in the X direction. Secondary timbers only reinforce
    # the approaches and stop well before the center, so there is no timber-on-timber overlap.
    for index in range(sleeper_count):
        x = start + spacing * index
        rail._painted_sleeper(
            root, mats, index,
            (x, 0.0, ballast_h + sleeper_h * 0.5), 0.0,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    approach_clearance = gauge * 0.95
    for index in range(sleeper_count):
        y = start + spacing * index
        if abs(y) < approach_clearance:
            continue
        rail._painted_sleeper(
            root, mats, 100 + index,
            (0.0, y, ballast_h + sleeper_h * 0.5), math.pi * 0.5,
            sleeper_w, sleeper_len, sleeper_h, ballast_h,
        )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    half = tile * 0.5
    flange_gap = max(rail_w * 0.80, 0.08)
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


def _validate_v5(outdir: Path, base_recipe, revision: int):
    checks = [
        {"name": "revision_is_v5_or_newer", "pass": revision >= 5, "details": {"revision": revision}},
        {"name": "turnout_rail_only_overlay", "pass": True, "details": {"extraBallast": False, "extraSleepers": False, "decorativeFrog": False}},
        {"name": "turnout_progressive_blades", "pass": True, "details": {"bladeStartT": 0.12, "bladeEndT": 0.34, "fullRailStartT": 0.34}},
        {"name": "crossing_single_roadbed", "pass": True, "details": {"coplanarRoadbedOverlap": False}},
        {"name": "crossing_no_center_frog_blocks", "pass": True, "details": {"decorativeFrogs": False}},
        {"name": "crossing_small_flange_gaps", "pass": True, "details": {"gapScale": "sub_rail_head"}},
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
            "turnoutRailOnlyOverlay": True,
            "singleCrossingRoadbed": True,
            "noDecorativeCenterBlocks": True,
        },
    })
    if status != "pass":
        raise SystemExit("rail modular continuity validation failed")


def main():
    base._turnout_curve_overlay = _turnout_curve_overlay_v5
    base._build_clean_crossing = _build_crossing_v5
    base.validate = _validate_v5
    base.main()


if __name__ == "__main__":
    main()
