#!/usr/bin/env python3
from __future__ import annotations

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
import rail_worker_task_v5 as v5  # noqa: E402
import build_rail_track_guarded as rail  # noqa: E402

APPROVED_PROXY_SHA = "d3824d17f4f8bd553685752c925ca711508e0e79b3d998840f89deefbfe14264"
STUDIO_PRESET = "tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"
BASE_RECIPE = "tools/tycoon_photo_studio/assets/rail_track_classic_01.track.json"


def main():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    out_arg = "out/ch_blender_agent/rail.classic.v5.03.crossing.final"
    if "--output" in argv:
        out_arg = argv[argv.index("--output") + 1]

    base_recipe = json.loads((REPO_ROOT / BASE_RECIPE).read_text(encoding="utf-8"))
    recipe = base.recipe_for(base_recipe, "crossing")
    outdir = (REPO_ROOT / out_arg).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    recipe_path = outdir / "rail_crossing.track.json"
    base.write_json(recipe_path, recipe)

    original_build = rail.build_track
    original_argv = list(sys.argv)
    try:
        base._build_clean_crossing = v5._build_crossing_v5
        rail.build_track = base.composite_builder
        sys.argv = [
            str(Path(__file__)), "--",
            "--recipe", str(recipe_path),
            "--studio-preset", str(REPO_ROOT / STUDIO_PRESET),
            "--output", str(outdir),
            "--stage", "final",
            "--approval-proxy-sha", APPROVED_PROXY_SHA,
        ]
        rail.main()
    finally:
        rail.build_track = original_build
        sys.argv = original_argv

    base.write_json(outdir / "worker_summary.json", {
        "contract": "CH_RAIL_WORKER_TASK_V1",
        "task": "crossing_final",
        "revision": 5,
        "status": "ok",
        "assetId": recipe["assetId"],
        "approvedProxySha256": APPROVED_PROXY_SHA,
        "nextStage": "promote_to_runtime_assets",
    })


if __name__ == "__main__":
    main()
