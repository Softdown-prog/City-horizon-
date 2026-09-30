"""Contract-complete wrapper for the approved steam-train vapor overlay bake.

Keeps the approved vapor authoring untouched and adds the canonical
studio_metadata.json required by the CH Blender guarded worker.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_steam_train_vapor_guarded as base

_ORIGINAL_RENDER_OVERLAY_ONLY = base.render_overlay_only


def _write_studio_metadata(scene, recipe: dict, out: Path) -> None:
    source_metadata_path = out / "steam_vapor_overlay_metadata.json"
    source_metadata = json.loads(source_metadata_path.read_text(encoding="utf-8"))

    metadata = {
        "sourceObject": base.ASSET_ID,
        "assetType": "animated_effect_overlay",
        "sourceContract": "DIRECT_CH_BLENDER_GUARDED_V1",
        "assetConfig": "tools/tycoon_photo_studio/build_steam_train_vapor_guarded_v2.py",
        "recipe": "tools/tycoon_photo_studio/assets/steam_train_vapor_overlay_v1.json",
        "studioPreset": "CH_TYCOON_STUDIO_V1",
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": "4.2.3 LTS",
        "renderEngine": scene.render.engine,
        "renderResolution": [int(scene.render.resolution_x), int(scene.render.resolution_y)],
        "runtimeRepresentation": "2D_RGBA_animated_overlay",
        "parentAssetId": base.PARENT_ASSET_ID,
        "transparentBackground": True,
        "animation": source_metadata["animation"],
        "directionOrder": source_metadata["directionOrder"],
        "anchorPolicy": source_metadata["anchorPolicy"],
        "directions": source_metadata["directions"],
    }
    (out / "studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


def render_overlay_only(scene, root, train_authored, vapor_authored, ground, recipe, puffs, out):
    _ORIGINAL_RENDER_OVERLAY_ONLY(
        scene, root, train_authored, vapor_authored, ground, recipe, puffs, out
    )
    _write_studio_metadata(scene, recipe, Path(out))


base.render_overlay_only = render_overlay_only


if __name__ == "__main__":
    base.main()
