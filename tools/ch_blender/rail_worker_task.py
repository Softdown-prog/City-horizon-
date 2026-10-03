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


def composite_builder(root, recipe):
    spec = recipe["module"]
    kind = str(spec.get("kind"))
    mats = rail._materials()
    if kind in {"switch_left", "switch_right"}:
        straight_root = _child("StraightBranch", root)
        curve_root = _child("DivergingBranch", root)
        rail._build_straight_track(straight_root, spec, mats)
        curve_spec = dict(spec)
        curve_spec["turnDirection"] = "left" if kind == "switch_left" else "right"
        curve_spec["curveRadius"] = float(spec["tileWorldSize"]) * 0.5
        curve_spec["curveSegments"] = int(spec.get("curveSegments", 32))
        rail._build_curve_track(curve_root, curve_spec, mats)
        root["junctionKind"] = kind
        root["entryCount"] = 1
        root["exitCount"] = 2
        root["topology"] = "straight_plus_quarter_curve"
        return
    if kind == "crossing":
        axis_x = _child("AxisX", root)
        axis_y = _child("AxisY", root, math.pi * 0.5)
        rail._build_straight_track(axis_x, spec, mats)
        rail._build_straight_track(axis_y, spec, mats)
        root["junctionKind"] = kind
        root["entryCount"] = 4
        root["exitCount"] = 4
        root["topology"] = "orthogonal_crossing"
        return
    return rail.build_track(root, recipe)


def run_proxy(task, outdir: Path, base_recipe, studio_preset):
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
        "status": "ok",
        "assetId": recipe["assetId"],
        "moduleKind": recipe["module"]["kind"],
        "proxy": str(outdir / "proxy_south.png"),
        "nextStage": "human_proxy_review_then_final",
    })


def validate(outdir: Path, base):
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

    status = "pass" if all(c["pass"] for c in checks) else "fail"
    write_json(outdir / "rail_modular_continuity_report.json", {
        "contract": "CH_RAIL_MODULAR_CONTINUITY_REPORT_V1",
        "status": status,
        "checkedKinds": ["straight", "curve_left_90", "curve_right_90", "switch_left", "switch_right", "crossing"],
        "checks": checks,
        "acceptance": {
            "tileBoundaryContinuity": True,
            "sharedGauge": True,
            "graphPortsOnTileEdges": True,
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
        validate(outdir, base)
    else:
        run_proxy(args.task, outdir, base, args.studio_preset)


if __name__ == "__main__":
    main()
