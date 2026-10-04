#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
STUDIO = REPO_ROOT / "tools" / "tycoon_photo_studio"
for path in (HERE, STUDIO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import rail_worker_task as base  # noqa: E402
import rail_worker_task_v7 as v7  # noqa: E402
import build_rail_track_guarded as rail  # noqa: E402

STUDIO_PRESET = "tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"
BASE_RECIPE = "tools/tycoon_photo_studio/assets/rail_track_classic_01.track.json"
APPROVED = {
    "switch_left": "285912fc837c71271db5c26fdc461638a46e8a197ce35fc6c3371a5f5a42633b",
    "switch_right": "6b9026b970d9ce3a25d76357f203a247ea517fba00dfa99a80630545621799eb",
}


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=tuple(APPROVED))
    p.add_argument("--output", required=True)
    return p.parse_args(argv)


def build_frozen_turnout(root, recipe):
    kind = str(recipe["module"].get("kind"))
    mats = rail._materials()
    if kind == "switch_left":
        return v7._build_turnout_v7(root, recipe["module"], mats, "left")
    if kind == "switch_right":
        return v7._build_turnout_v7(root, recipe["module"], mats, "right")
    raise RuntimeError(f"unsupported frozen turnout kind: {kind}")


def main():
    args = parse_args()
    outdir = (REPO_ROOT / args.output).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    base_recipe = json.loads((REPO_ROOT / BASE_RECIPE).read_text(encoding="utf-8"))
    recipe = base.recipe_for(base_recipe, args.task)
    recipe_path = outdir / f"rail_{args.task}.track.json"
    base.write_json(recipe_path, recipe)

    original_build = rail.build_track
    original_argv = list(sys.argv)
    try:
        rail.build_track = build_frozen_turnout
        sys.argv = [
            str(Path(__file__)), "--",
            "--recipe", str(recipe_path),
            "--studio-preset", str(REPO_ROOT / STUDIO_PRESET),
            "--output", str(outdir),
            "--stage", "final",
            "--approval-proxy-sha", APPROVED[args.task],
        ]
        rail.main()
    finally:
        rail.build_track = original_build
        sys.argv = original_argv

    base.write_json(outdir / "worker_summary.json", {
        "contract": "CH_RAIL_WORKER_TASK_V1",
        "task": f"{args.task}_final",
        "revision": 7,
        "status": "ok",
        "assetId": recipe["assetId"],
        "approvedProxySha256": APPROVED[args.task],
        "geometryState": "frozen_approved_v7",
        "nextStage": "promote_to_runtime_assets",
    })


if __name__ == "__main__":
    main()
