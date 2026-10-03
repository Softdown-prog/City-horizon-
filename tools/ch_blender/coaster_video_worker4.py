#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import coaster_worker_task as base


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=("video",))
    p.add_argument("--project", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--samples", type=int, default=128)
    return p.parse_args(argv)


def main():
    args = parse_args()
    project_path = (base.REPO / args.project).resolve()
    outdir = (base.REPO / args.output).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    project = base.load_json(project_path)
    if project.get("contract") != "CH_MAPFORGE_COASTER_PROJECT_V1":
        raise SystemExit("unsupported coaster project contract")

    refined = base.REPO / "out/ch_blender_agent/coaster.flame.v3.02.track_refinement/coaster_flame_01_v3.mapforge.json"
    if not refined.is_file():
        print("Worker 2 artifact is not present in this runner; rebuilding deterministic Flame Coaster V3 locally.", flush=True)
        base.write_json(refined, base.improved_project(project))

    base.task_video(project_path, outdir)


if __name__ == "__main__":
    main()
