"""Guarded CH Blender entry point for the landmark Ferris wheel rebuild.

This keeps the proven Ferris wheel gate/bake pipeline intact while swapping only
the wheel geometry builder. The original builder and previous recipes remain
available for regression/reference.
"""
from __future__ import annotations

import build_ferris_wheel as fw
import build_ferris_wheel_guarded as guarded
import ferris_wheel_landmark_geometry as landmark


def _landmark_build_wheel(root, geometry, materials):
    return landmark.build_wheel(root, geometry, materials, fw)


# build_ferris_wheel_guarded imports the same module object as `fw`, so this
# targeted substitution is visible inside its existing build_for_gate flow.
fw.build_wheel = _landmark_build_wheel


if __name__ == "__main__":
    guarded.main()
