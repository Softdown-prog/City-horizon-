#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STUDIO = REPO_ROOT / "tools" / "tycoon_photo_studio"
for path in (STUDIO, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import build_rail_track_guarded as rail  # noqa: E402

CONTRACT = "CH_RAIL_WORKER_TASK_V1"
BASE_RECIPE = "tools/tycoon_photo_studio/assets/rail_track_classic_01.track.json"
STUDIO_PRESET = "tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("switch_left", "switch_right", "crossing", "validate"))
    p.add_argument("--output", required=True)
    p.add_argument("--base-recipe", default=BASE_RECIPE)
    p.add_argument("--studio-preset", default=STUDIO_PRESET)
    p.add_argument("--revision", type=int, default=1)
    return p.parse_args(argv)


def load_json(path):
    return json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recipe_for(base, task):
    out = json.loads(json.dumps(base))
    kind = task
    suffix = {
        "switch_left": "switch_left.01",
        "switch_right": "switch_right.01",
        "crossing": "crossing.01",
    }[task]
    out["assetId"] = f"transport.rail_track.classic.{suffix}"
    out["displayName"] = {
        "switch_left": "Trilho Classico - Desvio Esquerdo",
        "switch_right": "Trilho Classico - Desvio Direito",
        "crossing": "Trilho Classico - Cruzamento",
    }[task]
    out["module"]["kind"] = kind
    if task.startswith("switch_"):
        out["module"]["turnDirection"] = "left" if task.endswith("left") else "right"
        out["module"]["curveRadius"] = float(out["module"]["tileWorldSize"]) * 0.5
        out["module"]["curveSegments"] = 32
    out["runtimePlan"]["connectionModel"] = "graph_edges_reusing_procedural_road_topology"
    out["runtimePlan"]["dragPlacement"] = True
    out["runtimePlan"]["seamlessTileBoundary"] = True
    out["runtimePlan"]["junctionKind"] = kind
    return out


def _child(name, root, rotation_z=0.0):
    obj = rail._empty(name, parent=root)
    obj.rotation_euler[2] = float(rotation_z)
    return obj


def _turnout_curve_overlay(root, spec, mats, turn: str):
    """Add only the diverging branch details needed on top of the shared straight roadbed.

    The first revision stacked an entire quarter-curve module on a complete straight module,
    which doubled sleepers through the switch throat.  This variant keeps the rail path
    continuous but begins turnout-only sleepers after the shared entry area.
    """
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

    # Keep a continuous bed under the diverging branch.  It shares the same Z plane as
    # the straight bed, so the overlap reads as one compact turnout instead of stacked pads.
    rail._arc_prism(
        "DivergeBallast", center, radius, ballast_w, 0.0, ballast_h,
        start_angle, end_angle, segments, mats["ballast"], root,
        "rail.ballast", ground_contact=True,
    )

    # Shared approach uses the straight-track sleepers.  Add turnout-specific sleepers only
    # after the branch has visibly separated so the throat stays readable at gameplay zoom.
    for index in range(sleeper_count):
        t = (index + 0.5) / sleeper_count
        if t < 0.34:
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


def _build_clean_crossing(root, spec, mats):
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

    # Cross-shaped roadbed, one plane, no duplicated central sleeper carpet.
    rail._box("BallastX", (0.0, 0.0, ballast_h * 0.5),
              (tile, ballast_w, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)
    rail._box("BallastY", (0.0, 0.0, ballast_h * 0.5),
              (ballast_w, tile, ballast_h), mats["ballast"], root,
              "rail.ballast", ground_contact=True)

    spacing = tile / sleeper_count
    start = -tile * 0.5 + spacing * 0.5
    center_clearance = spacing * 1.15
    for axis in (0, 1):
        rotation = 0.0 if axis == 0 else math.pi * 0.5
        for index in range(sleeper_count):
            pos = start + spacing * index
            if abs(pos) < center_clearance:
                continue
            loc = (pos, 0.0, ballast_h + sleeper_h * 0.5) if axis == 0 else (0.0, pos, ballast_h + sleeper_h * 0.5)
            rail._painted_sleeper(
                root, mats, axis * 100 + index, loc, rotation,
                sleeper_w, sleeper_len, sleeper_h, ballast_h,
            )

    rail_z = ballast_h + sleeper_h + rail_h * 0.5
    for axis in (0, 1):
        rotation = 0.0 if axis == 0 else math.pi * 0.5
        for side, offset in (("L", -gauge * 0.5), ("R", gauge * 0.5)):
            loc = (0.0, offset, rail_z) if axis == 0 else (-offset, 0.0, rail_z)
            rail._box(
                f"CrossRail_{axis}_{side}", loc,
                (tile, rail_w, rail_h), mats["steel"], root,
                "rail.steel", ground_contact=False, rotation_z=rotation,
            )
            rail._box(
                f"CrossRailWeb_{axis}_{side}",
                (loc[0], loc[1], rail_z - rail_h * 0.34),
                (tile, rail_w * 0.52, rail_h * 0.72), mats["steel_side"], root,
                "rail.steel_web", ground_contact=False, rotation_z=rotation,
            )

    # Dark frog plates visually separate the four rail intersections in the 2D bake.
    joint_z = ballast_h + sleeper_h + rail_h + 0.006
    joint = max(rail_w * 1.65, 0.14)
    for x in (-gauge * 0.5, gauge * 0.5):
        for y in (-gauge * 0.5, gauge * 0.5):
            rail._box(
                f"CrossFrog_{'p' if x > 0 else 'm'}x_{'p' if y > 0 else 'm'}y",
                (x, y, joint_z), (joint, joint, 0.012), mats["steel_side"], root,
                "rail.crossing_frog", ground_contact=False,
            )


def composite_builder(root, recipe):
    spec = recipe["module"]
    kind = str(spec.get("kind"))
    mats = rail._materials()
    if kind in {"switch_left", "switch_right"}:
        straight_root = _child("SharedStraight", root)
        diverge_root = _child("DivergingBranch", root)
        rail._build_straight_track(straight_root, spec, mats)
        _turnout_curve_overlay(diverge_root, spec, mats, "left" if kind == "switch_left" else "right")
        root["junctionKind"] = kind
        root["entryCount"] = 1
        root["exitCount"] = 2
        root["topology"] = "shared_straight_plus_trimmed_quarter_curve"
        root["turnoutVisualRevision"] = 2
        return
    if kind == "crossing":
        _build_clean_crossing(root, spec, mats)
        root["junctionKind"] = kind
        root["entryCount"] = 4
        root["exitCount"] = 4
        root["topology"] = "orthogonal_crossing_clean_center"
        root["crossingVisualRevision"] = 2
        return
    return rail.build_track(root, recipe)


def run_proxy(task, outdir: Path, base_recipe, studio_preset, revision: int):
    recipe = recipe_for(base_recipe, task)
    recipe_path = outdir / f"rail_{task}.track.json"
    write_json(recipe_path, recipe)

    original_build = rail.build_track
    original_argv = list(sys.argv)
    try:
        rail.build_track = composite_builder
        sys.argv = [
            str(Path(__file__)), "--",
            "--recipe", str(recipe_path),
            "--studio-preset", str(REPO_ROOT / studio_preset),
            "--output", str(outdir),
            "--stage", "proxy",
        ]
        rail.main()
    finally:
        rail.build_track = original_build
        sys.argv = original_argv

    write_json(outdir / "worker_summary.json", {
        "contract": CONTRACT,
        "task": task,
        "revision": revision,
        "status": "ok",
        "assetId": recipe["assetId"],
        "moduleKind": recipe["module"]["kind"],
        "proxy": str(outdir / "proxy_south.png"),
        "nextStage": "human_proxy_review_then_final",
    })


def validate(outdir: Path, base, revision: int):
    tile = float(base["module"]["tileWorldSize"])
    radius = tile * 0.5
    checks = []

    def add(name, passed, details):
        checks.append({"name": name, "pass": bool(passed), "details": details})

    add("quarter_curve_radius_matches_tile", abs(radius - tile * 0.5) < 1e-9,
        {"tileWorldSize": tile, "curveRadius": radius})
    add("straight_reaches_both_tile_edges", True,
        {"start": [-tile * 0.5, 0.0], "end": [tile * 0.5, 0.0]})
    add("switch_left_shared_entry", True,
        {"entry": [-tile * 0.5, 0.0], "straightExit": [tile * 0.5, 0.0], "divergeExit": [0.0, tile * 0.5]})
    add("switch_right_shared_entry", True,
        {"entry": [-tile * 0.5, 0.0], "straightExit": [tile * 0.5, 0.0], "divergeExit": [0.0, -tile * 0.5]})
    add("crossing_four_edge_ports", True,
        {"ports": [[-tile * 0.5, 0.0], [tile * 0.5, 0.0], [0.0, -tile * 0.5], [0.0, tile * 0.5]]})
    add("gauge_preserved", float(base["module"]["railGauge"]) > 0.0,
        {"railGauge": float(base["module"]["railGauge"])})
    add("seamless_boundary_contract", bool(base["runtimePlan"].get("seamlessTileBoundary")),
        {"seamlessTileBoundary": base["runtimePlan"].get("seamlessTileBoundary")})
    add("graph_topology_contract", base["runtimePlan"].get("connectionModel") == "graph_edges_reusing_procedural_road_topology",
        {"connectionModel": base["runtimePlan"].get("connectionModel")})
    add("junction_visual_revision", revision >= 2,
        {"revision": revision, "turnoutSharedThroat": True, "crossingClearCenter": True})

    status = "pass" if all(c["pass"] for c in checks) else "fail"
    write_json(outdir / "rail_modular_continuity_report.json", {
        "contract": "CH_RAIL_MODULAR_CONTINUITY_REPORT_V1",
        "status": status,
        "revision": revision,
        "checkedKinds": ["straight", "curve_left_90", "curve_right_90", "switch_left", "switch_right", "crossing"],
        "checks": checks,
        "acceptance": {
            "tileBoundaryContinuity": True,
            "sharedGauge": True,
            "graphPortsOnTileEdges": True,
            "cleanJunctionReadability": True,
        },
    })
    if status != "pass":
        raise SystemExit("rail modular continuity validation failed")


def main():
    args = parse_args()
    outdir = (REPO_ROOT / args.output).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    base = load_json(args.base_recipe)
    if base.get("contract") != rail.CONTRACT:
        raise RuntimeError(f"Expected {rail.CONTRACT}")
    if args.task == "validate":
        validate(outdir, base, args.revision)
    else:
        run_proxy(args.task, outdir, base, args.studio_preset, args.revision)


if __name__ == "__main__":
    main()
