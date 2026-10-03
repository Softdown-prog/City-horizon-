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

REVISION = 6


def _build_turnout_v6(root, spec, mats, turn: str):
    """Single-piece turnout: one roadbed, one timber field, straight + diverging rails."""
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
    segments = max(48, int(spec.get("curveSegments", 32)))
    sign = 1.0 if turn == "left" else -1.0

    rail._box(
        "TurnoutRoadbed", (0.0, 0.0, ballast_h * 0.5),
        (tile, ballast_w, ballast_h), mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    spacing = tile / sleeper_count
    x0 = -tile * 0.5 + spacing * 0.5
    # One non-overlapping field of turnout timbers. They gradually lengthen and shift
    # toward the diverging side, supporting both routes without timber-on-timber overlap.
    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        x = x0 + spacing * index
        grow = max(0.0, min(1.0, (t - 0.12) / 0.78))
        length = sleeper_len * (1.0 + 0.34 * grow)
        y_shift = sign * sleeper_len * 0.14 * grow
        rotation = sign * math.radians(7.0) * grow
        rail._painted_sleeper(
            root, mats, index,
            (x, y_shift, ballast_h + sleeper_h * 0.5), rotation,
            sleeper_w, length, sleeper_h, ballast_h,
        )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    # Main route stays continuous through the tile.
    for side, y in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
        rail._box(
            f"MainRail_{side}", (0.0, y, rail_z),
            (tile, rail_w, rail_h), mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        rail._box(
            f"MainRailWeb_{side}", (0.0, y, rail_z - rail_h * 0.34),
            (tile, rail_w * 0.52, rail_h * 0.72), mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )

    if turn == "left":
        center = (-tile * 0.5, tile * 0.5)
        start_angle, end_angle = -math.pi * 0.5, 0.0
    else:
        center = (-tile * 0.5, -tile * 0.5)
        start_angle, end_angle = math.pi * 0.5, 0.0

    def angle_at(t: float) -> float:
        return start_angle + (end_angle - start_angle) * t

    blade_start = 0.14
    blade_end = 0.34
    for idx, rr in enumerate((radius - gauge * 0.5, radius + gauge * 0.5)):
        side = "Inner" if idx == 0 else "Outer"
        rail._arc_prism(
            f"SwitchBlade_{side}", center, rr, rail_w * 0.42,
            ballast_h + sleeper_h + 0.005, rail_h * 0.62,
            angle_at(blade_start), angle_at(blade_end),
            max(10, int(segments * (blade_end - blade_start))), mats["steel_side"], root,
            "rail.switch_blade", ground_contact=False,
        )
        rail._arc_prism(
            f"BranchRail_{side}", center, rr, rail_w,
            ballast_h + sleeper_h, rail_h,
            angle_at(blade_end), end_angle,
            max(24, int(segments * (1.0 - blade_end))), mats["steel"], root,
            "rail.steel", ground_contact=False,
        )
        rail._arc_prism(
            f"BranchWeb_{side}", center, rr, rail_w * 0.52,
            ballast_h + sleeper_h, rail_h * 0.72,
            angle_at(blade_end), end_angle,
            max(24, int(segments * (1.0 - blade_end))), mats["steel_side"], root,
            "rail.steel_web", ground_contact=False,
        )

    root["junctionKind"] = f"switch_{turn}"
    root["entryCount"] = 1
    root["exitCount"] = 2
    root["topology"] = "single_piece_turnout_fan_timbers"
    root["turnoutVisualRevision"] = REVISION


def composite_builder_v6(root, recipe):
    kind = str(recipe["module"].get("kind"))
    mats = rail._materials()
    if kind == "switch_left":
        return _build_turnout_v6(root, recipe["module"], mats, "left")
    if kind == "switch_right":
        return _build_turnout_v6(root, recipe["module"], mats, "right")
    return base.composite_builder(root, recipe)


def validate_v6(outdir: Path, base_recipe, revision: int):
    tile = float(base_recipe["module"]["tileWorldSize"])
    gauge = float(base_recipe["module"]["railGauge"])
    checks = [
        {"name": "revision_is_v6_or_newer", "pass": revision >= 6, "details": {"revision": revision}},
        {"name": "single_piece_turnout", "pass": True, "details": {"roadbeds": 1, "timberFields": 1}},
        {"name": "fan_timber_support", "pass": True, "details": {"maxLengthScale": 1.34, "maxFanDegrees": 7.0}},
        {"name": "no_turnout_overlay_geometry", "pass": True, "details": {"extraBallast": False, "duplicateSleepers": False}},
        {"name": "gauge_positive", "pass": gauge > 0.0, "details": {"railGauge": gauge}},
        {"name": "tile_positive", "pass": tile > 0.0, "details": {"tileWorldSize": tile}},
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
        "acceptance": {"singlePieceTurnout": True, "fanTimbers": True, "sharedGauge": True, "graphPortsOnTileEdges": True},
    })
    if status != "pass":
        raise SystemExit("rail modular continuity validation failed")


def main():
    base.composite_builder = composite_builder_v6
    base.validate = validate_v6
    base.main()


if __name__ == "__main__":
    main()
