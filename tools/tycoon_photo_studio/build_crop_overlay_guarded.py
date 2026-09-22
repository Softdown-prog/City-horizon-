#!/usr/bin/env python3
"""Guarded CH Blender builder for crop overlays.

Builds one crop overlay stage from CH_CROP_OVERLAY_RECIPE_V1 via the procedural
expander, then delegates rendering to the canonical Tycoon Photo Studio scene
builder. Intended for CH Blender preflight/proxy/final jobs.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools" / "tycoon_photo_studio" / "generate_crop_overlay_asset.py"
BUILD_SCENE = ROOT / "tools" / "tycoon_photo_studio" / "build_scene.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--crop-stage", default="ripe")
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), required=True)
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args()


def run(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, cwd=ROOT)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    args = parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ch_crop_overlay_") as temp_dir:
        source = Path(temp_dir) / "crop_overlay.asset.json"
        run([
            sys.executable,
            str(GENERATOR),
            "--recipe", args.recipe,
            "--stage", args.crop_stage,
            "--output", str(source),
        ])

        # build_scene.py runs inside Blender in the CH Blender worker. Keep all
        # inputs repository-relative except this generated temporary source.
        sys.argv = [
            str(BUILD_SCENE), "--",
            "--output", str(output),
            "--asset-config", str(source),
            "--studio-preset", args.studio_preset,
        ]
        namespace = {"__name__": "__main__", "__file__": str(BUILD_SCENE)}
        exec(compile(BUILD_SCENE.read_text(encoding="utf-8"), str(BUILD_SCENE), "exec"), namespace)


if __name__ == "__main__":
    main()
