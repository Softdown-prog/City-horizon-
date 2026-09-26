"""16:9 framing adapter for the guarded City Horizon loading hero builder.

The loading composition uses the frozen CH camera direction/light setup, but its
wide presentation frame needs more breathing room than the square-ish sprite
asset calibration. Keep this adjustment local to loading presentation art.
"""
from __future__ import annotations

import bpy

import build_loading_hero_guarded as hero


_base_fit = hero._fit_camera_current


def _fit_loading_frame(scene, authored, safety_margin=0.075):
    scale = _base_fit(scene, authored, safety_margin)
    # The project preflight projects against the full 16:9 render frame. The
    # first deterministic preflight measured a 1.63x horizontal overflow after
    # the generic fit, so use a stable 1.70 presentation margin rather than
    # weakening CH_PREFLIGHT_CAMERA_CROP.
    scene.camera.data.ortho_scale = scale * 1.70
    bpy.context.view_layer.update()
    return float(scene.camera.data.ortho_scale)


hero._fit_camera_current = _fit_loading_frame


if __name__ == "__main__":
    hero.main()
