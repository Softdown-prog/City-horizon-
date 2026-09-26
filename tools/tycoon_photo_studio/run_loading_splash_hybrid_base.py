"""Compatibility entrypoint for the hybrid loading-splash 3D foundation.

Keeps the new hybrid palette independent from the older storybook helper while
reusing its ferris-wheel geometry.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_loading_splash_hybrid_base as hybrid  # noqa: E402

_original_add_ferris_wheel = hybrid.add_ferris_wheel


def add_ferris_wheel_compat(center, radius, mats):
    palette = dict(mats)
    if "purple" not in palette and "violet" in palette:
        palette["purple"] = palette["violet"]
    return _original_add_ferris_wheel(center, radius, palette)


hybrid.add_ferris_wheel = add_ferris_wheel_compat

if __name__ == "__main__":
    hybrid.main()
