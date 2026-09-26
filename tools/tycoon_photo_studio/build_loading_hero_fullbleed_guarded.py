"""Full-bleed 16:9 presentation adapter for the City Horizon loading hero.

Background ground/road/scenery are allowed to continue beyond the review frame,
while the actual focal content remains inside CH_PREFLIGHT_CAMERA_CROP. This is
specific to static loading-screen presentation and does not change CH_CAMERA_V1.
"""
from __future__ import annotations

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

import build_loading_hero_guarded as hero


_base_build_scene = hero.build_scene

_BACKGROUND_ROLES = {
    "loading.ground",
    "loading.road",
    "loading.sidewalk",
    "loading.road_marking",
    "background.massing",
    "background.massing_roof",
    "scenery.tree_trunk",
    "scenery.tree_canopy",
    "scenery.lamp",
}


def _fit_exact(scene, authored, margin=0.045):
    camera = scene.camera
    # Start from the first-pass scale, then solve against Blender's own camera
    # projection rather than weakening the crop gate.
    for _ in range(4):
        bpy.context.view_layer.update()
        projected = [
            world_to_camera_view(scene, camera, obj.matrix_world @ Vector(corner))
            for obj in authored
            for corner in obj.bound_box
        ]
        min_x = min(p.x for p in projected)
        max_x = max(p.x for p in projected)
        min_y = min(p.y for p in projected)
        max_y = max(p.y for p in projected)
        extent_x = max(abs(min_x - 0.5), abs(max_x - 0.5)) * 2.0
        extent_y = max(abs(min_y - 0.5), abs(max_y - 0.5)) * 2.0
        usable = 1.0 - margin * 2.0
        factor = max(extent_x / usable, extent_y / usable)
        camera.data.ortho_scale *= max(0.25, factor * 1.025)
    bpy.context.view_layer.update()


def _build_fullbleed(args):
    ctx = _base_build_scene(args)
    scene = ctx["scene"]

    # Presentation background: make the terrain effectively full bleed. It is
    # still rendered, but it is intentionally not part of the crop/footprint
    # proof because a loading background is supposed to continue off screen.
    ground = bpy.data.objects.get("HeroGround")
    if ground is not None:
        ground.scale.x *= 18.0
        ground.scale.y *= 18.0

    for name in ("HeroRoad", "HeroSidewalkWest", "HeroSidewalkEast"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            obj.scale.y *= 6.0

    focal = []
    for obj in ctx["authored"]:
        role = str(obj.get("ch.semanticRole", ""))
        if role in {"background.massing", "background.massing_roof"}:
            obj.hide_render = True
            continue
        if role in _BACKGROUND_ROLES:
            continue
        focal.append(obj)

    if not focal:
        raise RuntimeError("CH_LOADING_HERO_NO_FOCAL_CONTENT")

    # Keep the frozen CH camera direction and lens language, but bias the 16:9
    # presentation slightly downward so the title field has breathing room.
    scene.camera.data.shift_y = 0.10
    ctx["authored"] = focal
    _fit_exact(scene, focal)
    return ctx


hero.build_scene = _build_fullbleed


if __name__ == "__main__":
    hero.main()
