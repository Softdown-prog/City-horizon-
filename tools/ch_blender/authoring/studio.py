"""Stylized preview studio presets for CH Blender authoring.

These presets affect only authoring/review renders. Canonical camera, anchors,
landmarks and runtime contracts remain untouched.
"""
from __future__ import annotations

import bpy

CONTRACT = "CH_CHARACTER_STYLIZED_PREVIEW_V1"


def apply_character_preview_style(scene: bpy.types.Scene) -> dict:
    """Bias EEVEE preview toward saturated classic pre-render sprite readability.

    AgX is excellent for broad dynamic range but can make tiny stylized sprites
    look pastel/washed after downsampling. Character authoring review instead uses
    Standard color management with restrained light energy and matte materials.
    """
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -0.15
    scene.view_settings.gamma = 1.0

    world = scene.world
    if world is not None:
        world.color = (0.018, 0.022, 0.028)

    key = bpy.data.objects.get("CH_KEY_LIGHT")
    if key is not None and getattr(key, "data", None) is not None:
        key.data.energy = 390.0
        key.data.size = 4.5

    fill = bpy.data.objects.get("CH_FILL_LIGHT")
    if fill is not None and getattr(fill, "data", None) is not None:
        fill.data.energy = 85.0
        fill.data.size = 3.8

    return {
        "contract": CONTRACT,
        "viewTransform": "Standard",
        "look": "None",
        "exposure": -0.15,
        "gamma": 1.0,
        "keyEnergy": 390.0,
        "fillEnergy": 85.0,
        "purpose": "saturated_classic_tycoon_prerender_review",
        "canonicalCameraModified": False,
        "runtimeExportAuthority": False,
    }
