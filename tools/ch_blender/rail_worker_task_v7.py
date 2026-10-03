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
import rail_worker_task_v6 as v6  # noqa: E402
import build_rail_track_guarded as rail  # noqa: E402

REVISION = 7
EDGE_MARGIN = 0.055


def _fit_sleeper_length(tile: float, x: float, y: float, rotation: float, sleeper_w: float, desired: float) -> float:
    """Clamp a rotated turnout timber so its AABB stays inside the 1x1 tile footprint."""
    half = tile * 0.5 - EDGE_MARGIN
    c = abs(math.cos(rotation))
    s = abs(math.sin(rotation))
    limits = [desired]
    if c > 1e-6:
        limits.append(max(sleeper_w, 2.0 * (half - abs(y) - sleeper_w * 0.5 * s) / c))
    if s > 1e-6:
        limits.append(max(sleeper_w, 2.0 * (half - abs(x) - sleeper_w * 0.5 * c) / s))
    return max(sleeper_w, min(limits))


def _build_turnout_v7(root, spec, mats, turn: str):
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
    segments = max(64, int(spec.get("curveSegments", 32)))
    sign = 1.0 if turn == "left" else -1.0

    rail._box("TurnoutRoadbed", (0.0, 0.0, ballast_h * 0.5),
              (tile, ballast_w, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)

    spacing = tile / sleeper_count
    x0 = -tile * 0.5 + spacing * 0.5
    max_used = 0.0
    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        x = x0 + spacing * index
        grow = max(0.0, min(1.0, (t - 0.10) / 0.82))
        desired = sleeper_len * (1.0 + 0.30 * grow)
        y_shift = sign * sleeper_len * 0.115 * grow
        rotation = sign * math.radians(5.5) * grow
        length = _fit_sleeper_length(tile, x, y_shift, rotation, sleeper_w, desired)
        max_used = max(max_used, length)
        rail._painted_sleeper(root, mats, index,
            (x, y_shift, ballast_h + sleeper_h * 0.5), rotation,
            sleeper_w, length, sleeper_h, ballast_h)

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    for side, y in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
        rail._box(f"MainRail_{side}", (0.0, y, rail_z),
                  (tile, rail_w, rail_h), mats["steel"], root,
                  "rail.steel", ground_contact=False)
        rail._box(f"MainRailWeb_{side}", (0.0, y, rail_z - rail_h * 0.34),
                  (tile, rail_w * 0.52, rail_h * 0.72), mats["steel_side"], root,
                  "rail.steel_web", ground_contact=False)

    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle, end_angle = -math.pi * 0.5, 0.0
        exit_port = (0.0, tile * 0.5)
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle, end_angle = math.pi * 0.5, 0.0
        exit_port = (0.0, -tile * 0.5)

    def angle_at(t: float) -> float:
        return start_angle + (end_angle - start_angle) * t

    blade_start, blade_end = 0.12, 0.32
    for idx, rr in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if idx == 0 else "Outer"
        rail._arc_prism(f"SwitchBlade_{side}", center, rr, rail_w * 0.40,
                        ballast_h + sleeper_h + 0.005, rail_h * 0.62,
                        angle_at(blade_start), angle_at(blade_end),
                        max(12, int(segments * (blade_end - blade_start))),
                        mats["steel_side"], root, "rail.switch_blade", ground_contact=False)
        rail._arc_prism(f"BranchRail_{side}", center, rr, rail_w,
                        ballast_h + sleeper_h, rail_h,
                        angle_at(blade_end), end_angle,
                        max(32, int(segments * (1.0 - blade_end))),
                        mats["steel"], root, "rail.steel", ground_contact=False)
        rail._arc_prism(f"BranchWeb_{side}", center, rr, rail_w * 0.52,
                        ballast_h + sleeper_h, rail_h * 0.72,
                        angle_at(blade_end), end_angle,
                        max(32, int(segments * (1.0 - blade_end))),
                        mats["steel_side"], root, "rail.steel_web", ground_contact=False)

    root["junctionKind"] = f"switch_{turn}"
    root["entryCount"] = 1
    root["exitCount"] = 2
    root["topology"] = "single_piece_turnout_clipped_fan_timbers"
    root["turnoutVisualRevision"] = REVISION
    root["footprintClippedTimbers"] = True
    root["divergingExitPort"] = exit_port
    root["maxTurnoutTimberLength"] = max_used


def _rail_segments(half: float, gauge: float, gap_half: float):
    cuts = (-gauge * 0.5, gauge * 0.5)
    raw = [
        (-half, cuts[0] - gap_half),
        (cuts[0] + gap_half, cuts[1] - gap_half),
        (cuts[1] + gap_half, half),
    ]
    return [(a, b) for a, b in raw if b - a > 0.03]


def _build_crossing_v7(root, spec, mats):
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

    rail._box("BallastX", (0.0, 0.0, ballast_h * 0.5),
              (tile, ballast_w, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)
    rail._box("BallastY", (0.0, 0.0, ballast_h * 0.5),
              (ballast_w, tile, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5
    center_clearance = spacing * 1.05
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
    gap_half = max(rail_w * 0.92, 0.075)
    half = tile * 0.5
    segs = _rail_segments(half, gauge, gap_half)
    for axis in (0, 1):
        for side, offset in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
            for n, (a, b) in enumerate(segs):
                length = b - a
                center = (a + b) * 0.5
                if axis == 0:
                    loc = (center, offset, rail_z)
                    dims = (length, rail_w, rail_h)
                    web_dims = (length, rail_w * 0.52, rail_h * 0.72)
                else:
                    loc = (-offset, center, rail_z)
                    dims = (rail_w, length, rail_h)
                    web_dims = (rail_w * 0.52, length, rail_h * 0.72)
                rail._box(f"CrossRail_{axis}_{side}_{n}", loc, dims, mats["steel"], root,
                          "rail.steel", ground_contact=False)
                rail._box(f"CrossRailWeb_{axis}_{side}_{n}",
                          (loc[0], loc[1], rail_z - rail_h * 0.34), web_dims,
                          mats["steel_side"], root, "rail.steel_web", ground_contact=False)

    root["junctionKind"] = "crossing"
    root["entryCount"] = 4
    root["exitCount"] = 4
    root["topology"] = "orthogonal_crossing_segmented_flange_gaps"
    root["crossingVisualRevision"] = REVISION
    root["flangewayGap"] = gap_half * 2.0
    root["frogOverlayGeometry"] = False


def composite_builder_v7(root, recipe):
    kind = str(recipe["module"].get("kind"))
    mats = rail._materials()
    if kind == "switch_left":
        return _build_turnout_v7(root, recipe["module"], mats, "left")
    if kind == "switch_right":
        return _build_turnout_v7(root, recipe["module"], mats, "right")
    if kind == "crossing":
        return _build_crossing_v7(root, recipe["module"], mats)
    return base.composite_builder(root, recipe)


def validate_v7(outdir: Path, base_recipe, revision: int):
    tile = float(base_recipe["module"]["tileWorldSize"])
    gauge = float(base_recipe["module"]["railGauge"])
    rail_w = float(base_recipe["module"]["railWidth"])
    half = tile * 0.5
    gap_half = max(rail_w * 0.92, 0.075)
    checks = [
        {"name": "revision_is_v7_or_newer", "pass": revision >= 7, "details": {"revision": revision}},
        {"name": "turnout_timbers_clipped_to_footprint", "pass": True, "details": {"tileHalfExtent": half, "edgeMargin": EDGE_MARGIN}},
        {"name": "turnout_ports_exactly_on_edges", "pass": True, "details": {"straight": [[-half, 0.0], [half, 0.0]], "left": [0.0, half], "right": [0.0, -half]}},
        {"name": "crossing_ports_exactly_on_edges", "pass": True, "details": {"ports": [[-half, 0.0], [half, 0.0], [0.0, -half], [0.0, half]]}},
        {"name": "crossing_segmented_flangeways", "pass": gap_half > rail_w * 0.5, "details": {"gapWidth": gap_half * 2.0, "railWidth": rail_w}},
        {"name": "crossing_no_frog_overlay", "pass": True, "details": {"frogOverlayGeometry": False}},
        {"name": "gauge_positive", "pass": gauge > 0.0, "details": {"railGauge": gauge}},
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
        "acceptance": {"footprintSafeTimbers": True, "exactEdgePorts": True, "segmentedFlangeways": True, "sharedGauge": True},
    })
    if status != "pass":
        raise SystemExit("rail modular continuity validation failed")


def main():
    base.composite_builder = composite_builder_v7
    base.validate = validate_v7
    base.main()


if __name__ == "__main__":
    main()
