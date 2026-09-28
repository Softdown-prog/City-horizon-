"""Compatibility launcher for the classic tree baker against the GAP2 scene API.

Historical classic-tree revisions called ``configure_scene(studio, output_dir)`` while
newer revisions call ``configure_scene(studio, src_resolution, output_dir)``.  This
launcher accepts both shapes and resolves the dynamic source/final resolution from the
asset before delegating to the current generic scene API.
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


def _configure_scene_compat(studio, *args):
    """Accept both classic 2-arg and current 3-arg configure_scene call shapes."""
    if len(args) == 1:
        output_dir = args[0]
    elif len(args) == 2:
        # Newer classic baker already supplies a source resolution.  We deliberately
        # recompute it here from the asset so GAP2 dynamic sizing remains authoritative.
        _legacy_src_resolution, output_dir = args
    else:
        raise TypeError(
            "classic configure_scene compatibility expects "
            "(studio, output_dir) or (studio, src_resolution, output_dir)"
        )

    asset_path = _arg_value("--asset-config")
    asset = json.loads(Path(asset_path).read_text(encoding="utf-8"))
    src_resolution, final_resolution = build_scene.compute_dynamic_resolution(asset, studio)
    scene = _original_configure_scene(studio, src_resolution, output_dir)

    # Keep the resolved sizes available to classic callers and metadata writers.
    studio.setdefault("render", {})["srcResolution"] = list(src_resolution)
    studio["render"]["sourceResolution"] = list(src_resolution)
    studio["render"]["finalResolution"] = list(final_resolution)
    return scene


build_classic_tree.studio_base.configure_scene = _configure_scene_compat


if __name__ == "__main__":
    build_classic_tree.main()
