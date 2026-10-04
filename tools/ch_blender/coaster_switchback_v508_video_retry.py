#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V508_PATH = REPO / "tools/ch_blender/coaster_switchback_v508_pool.py"


def load_v508():
    spec = importlib.util.spec_from_file_location("ch_coaster_switchback_v508_retry", V508_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load V5.08 presentation pool")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    v508 = load_v508()

    # A GitHub Actions retry starts on a fresh filesystem. Recreate the three
    # deterministic presentation inputs locally only when they are absent;
    # these are fast source-generation steps, not expensive video renders.
    if not v508.TRACK_FILE.is_file():
        v508.task_track(v508.TRACK_OUT)
    if not v508.STATION_FILE.is_file():
        v508.task_station(v508.STATION_OUT)
    if not v508.TRAIN_FILE.is_file():
        v508.task_train(v508.TRAIN_OUT)

    # V5.structure writes its generated C++ file directly and therefore needs
    # its temporary output directory to exist. The first V5.08 integrator run
    # exposed this missing mkdir. Wrap only the imported V5 generator so the
    # original validated worker sources remain unchanged.
    original_load_module = v508.load_module

    def robust_load_module(path, name):
        module = original_load_module(path, name)
        if Path(path).resolve() == v508.V5.resolve():
            original_geometry = module.geometry
            original_structure = module.structure

            def geometry(source, out):
                Path(out).mkdir(parents=True, exist_ok=True)
                return original_geometry(source, out)

            def structure(out):
                Path(out).mkdir(parents=True, exist_ok=True)
                return original_structure(out)

            module.geometry = geometry
            module.structure = structure
        return module

    v508.load_module = robust_load_module
    project = v508.repo_path(args.project)
    output = v508.repo_path(args.output)
    v508.task_video(project, output)


if __name__ == "__main__":
    main()
