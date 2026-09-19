"""Compatibility launcher for the classic tree baker against the GAP2 scene API.

The generic baker now requires configure_scene(studio, src_resolution, output_dir).
The classic tree baker still calls the previous two-argument form.  This launcher
adapts that call without weakening the new generic baker API.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_scene
import build_classic_tree


def _arg_value(name: str) -> str:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    try:
        index = argv.index(name)
        return argv[index + 1]
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"Missing required argument {name}") from exc


_original_configure_scene = build_scene.configure_scene


def _configure_scene_compat(studio, output_dir):
    asset_path = _arg_value("--asset-config")
    asset = json.loads(Path(asset_path).read_text(encoding="utf-8"))
    src_resolution, final_resolution = build_scene.compute_dynamic_resolution(asset, studio)
    scene = _original_configure_scene(studio, src_resolution, output_dir)
    # Keep the resolved final size available to callers that still read the studio object.
    studio.setdefault("render", {})["finalResolution"] = list(final_resolution)
    return scene


build_classic_tree.studio_base.configure_scene = _configure_scene_compat


if __name__ == "__main__":
    build_classic_tree.main()
