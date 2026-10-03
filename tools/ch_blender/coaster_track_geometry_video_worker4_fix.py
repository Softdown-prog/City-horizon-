#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKER = HERE / 'coaster_track_geometry_video_worker4.py'

spec = importlib.util.spec_from_file_location('ch_coaster_track_geometry_worker4_base', WORKER)
if spec is None or spec.loader is None:
    raise RuntimeError('cannot load coaster track geometry worker')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

base_loader = worker.load_v5_module

def load_v5_module_with_output_dirs():
    v5 = base_loader()
    original_structure = v5.structure
    original_motion = v5.motion

    def structure(out):
        out.mkdir(parents=True, exist_ok=True)
        return original_structure(out)

    def motion(out):
        out.mkdir(parents=True, exist_ok=True)
        return original_motion(out)

    v5.structure = structure
    v5.motion = motion
    return v5

worker.load_v5_module = load_v5_module_with_output_dirs
worker.main()
