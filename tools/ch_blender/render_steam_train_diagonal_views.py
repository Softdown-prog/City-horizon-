#!/usr/bin/env python3
"""Render only four new diagonal views of an approved CH Blender steam-train unit.

The existing south/east/west/north PNGs and runtime manifests are never edited.
This is authoring/QA evidence, not an automatic runtime promotion.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
STUDIO_ROOT = ROOT / "tools" / "tycoon_photo_studio"
sys.path.insert(0, str(STUDIO_ROOT))
sys.path.insert(0, str(ROOT / "tools" / "ch_blender"))
DIR_ANGLES = {
    "north_east": 135.0,
    "east_south": 45.0,
    "south_west": 315.0,
    "west_north": 225.0,
}

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--unit", required=True, choices=("locomotive", "coach"))
    p.add_argument("--output", required=True)
    return p.parse_args(argv)

def main():
    args = parse_args()
    out = (ROOT / args.output).resolve()
    if not out.is_relative_to(ROOT):
        raise RuntimeError("CH Blender output must remain within the repo")
    out.mkdir(parents=True, exist_ok=True)

    # The approved V3 authoring entrypoint already centers individual units.
    # Import it with its original --unit contract, without altering its source.
    original_argv = list(sys.argv)
    try:
        sys.argv = [str(STUDIO_ROOT / "build_steam_train_articulated_unit_v1.py"), "--", "--unit", args.unit]
        import build_steam_train_articulated_unit_v1 as unit_builder
    finally:
        sys.argv = original_argv

    recipe_path = ROOT / "tools/tycoon_photo_studio/assets/steam_train_cab_7coaches_v1.train.json"
    preset_path = ROOT / "tools/tycoon_photo_studio/render_pipelines/large_asset/studio_1024.json"
    build_args = argparse.Namespace(recipe=str(recipe_path), studio_preset=str(preset_path), output=str(out))
    base = unit_builder.base
    recipe, studio, scene, root, ground, authored, _ = base.build_for_gate(build_args)
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.cycles.samples = 20
    # The 4-view V3 framing did not include side-on projections at +45 degree
    # angles. The old renders touched and visibly clipped the image borders.
    # Give the new eight-view shots a verified clear margin. Retain this ratio
    # in the QA metadata for runtime world-scale compensation at promotion time.
    source_ortho_scale = float(scene.camera.data.ortho_scale)
    pixel_scale_compensation = 1.28
    scene.camera.data.ortho_scale = source_ortho_scale * pixel_scale_compensation
    # Preserve the approved camera yaw/pitch and scene materials/light rig.
    # Only orthographic framing expands; all approved 4 cardinal PNGs stay put.
    bpy.context.view_layer.update()
    directions = []
    for direction, degrees in DIR_ANGLES.items():
        base.bs.set_direction(root, {"id": direction, "rotationDegrees": degrees})
        bpy.context.view_layer.update()
        prefix = "steam_train_" + args.unit + "_" + direction
        color_name = prefix + "_color_source.png"
        shadow_name = prefix + "_shadow_source.png"
        base.bs.render_color_pass(scene, authored, ground, str(out / color_name))
        pivot = base.bs.ground_origin_source_px(scene)
        base.bs.render_shadow_pass(scene, authored, ground, str(out / shadow_name))
        directions.append({
            "direction": direction,
            "blenderRootRotationDegrees": degrees,
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": pivot,
        })

    info = {
        "contract": "CH_RAIL_DIAGONAL_BAKE_V1",
        "stage": "human_review_required",
        "unit": args.unit,
        "assetId": "vehicle.steam_train." + args.unit + ".01",
        "cameraContract": "CH_CAMERA_V1",
        "visualContract": "CH_STYLIZED_PRERENDER_V1",
        "studio": studio["id"],
        "sourceResolution": list(studio["render"]["sourceResolution"]),
        "finalResolution": list(studio["render"]["finalResolution"]),
        "approvedCardinalSpritesIntact": True,
        "originalOrthoScale": source_ortho_scale,
        "bakeOrthoScale": float(scene.camera.data.ortho_scale),
        "runtimePixelScaleCompensation": pixel_scale_compensation,
        "quality": {"cyclesSamples": 20, "denoising": True},
        "views": directions,
    }
    (out / "diagonal_bake_metadata.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print("[CH_RAIL_DIAGONAL_BAKE_V1] Produced 4 review-only diagonal views of", args.unit)

if __name__ == "__main__":
    main()
