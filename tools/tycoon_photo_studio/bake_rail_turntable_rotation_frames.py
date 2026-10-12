#!/usr/bin/env python3
"""Author CH_CAMERA_V1 true-isometric moving-bridge frame sequence.

All frames share exactly the same Blender camera, lighting, orthographic scale,
origin pivot and deterministic source mesh as the approved 4-view layered bake.
The moving steel bridge rotates in WORLD XY; the renderer must never call SDL
2D sprite rotation to imitate perspective.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[2]
for module_dir in (REPO / "tools" / "tycoon_photo_studio",
                   REPO / "tools" / "ch_blender"):
    if str(module_dir) not in sys.path:
        sys.path.insert(0,str(module_dir))

import build_scene as bs  # noqa: E402
import build_rail_turntable_guarded as model  # noqa: E402
import scene_gate  # noqa: E402

FRAME_COUNT = 25
RESOLUTION = 512

def main() -> None:
    args=sys.argv
    args=args[args.index("--")+1:] if "--" in args else []
    cli=argparse.ArgumentParser()
    cli.add_argument("--recipe",required=True)
    cli.add_argument("--studio-preset",required=True)
    cli.add_argument("--output",required=True)
    settings=cli.parse_args(args)

    recipe=model.verified_recipe(settings.recipe)
    studio=bs.load_json(settings.studio_preset)
    dest=Path(settings.output).resolve()
    dest.mkdir(parents=True,exist_ok=True)

    bs.clear_scene()
    scene=bs.configure_scene(studio,
        tuple(map(int,studio["render"]["sourceResolution"])),str(dest))
    scene.render.film_transparent=True
    scene.render.image_settings.color_mode="RGBA"
    root=model.make_empty("AssetRoot")
    root["assetId"]=model.ASSET_ID
    root["cameraContract"]="CH_CAMERA_V1"
    root["gridContract"]="CH_GRID_V1"
    root["runtimeRepresentation"]="2D_RGBA_rotating_bridge"
    base,bridge=model.build_model(root,recipe)

    bs.calibrate_ortho_scale(scene,base+bridge,safety_margin=.12)
    bs.set_direction(root,bs.DIRECTIONS[0])
    preflight=scene_gate.run_preflight(
        scene=scene,authored=base+bridge,footprint=recipe["footprint"],
        asset_id=model.ASSET_ID,report_path=dest/"rotation_preflight.json")
    scene_gate.require_pass(preflight)

    for item in base:item.hide_render=True
    for item in bridge:item.hide_render=False

    scene.render.resolution_x=RESOLUTION
    scene.render.resolution_y=RESOLUTION
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=True
    if scene.render.engine=="CYCLES":
        scene.cycles.samples=12

    records={}
    for direction in bs.DIRECTIONS:
        name=direction["id"]
        for n in range(FRAME_COUNT):
            degrees=direction["rotationDegrees"]+180.0*n/(FRAME_COUNT-1)
            root.rotation_euler.z=math.radians(degrees)
            bpy.context.view_layer.update()
            filename=f"rail_turntable_bridge_{name}_phase_{n:02d}.png"
            image=dest/filename
            scene.render.filepath=str(image)
            bpy.ops.render.render(write_still=True)
            records[filename]=hashlib.sha256(image.read_bytes()).hexdigest()

    pivot=bs.ground_origin_source_px(scene)
    (dest/"rotation_manifest.json").write_text(json.dumps({
        "contract":"CH_RAIL_TURNTABLE_ROTATION_FRAMES_V1",
        "cameraContract":"CH_CAMERA_V1",
        "fixedCamera":True,
        "frameCount":FRAME_COUNT,
        "angleStartDegrees":0,
        "angleEndDegrees":180,
        "directions":["south","east","west","north"],
        "resolution":[RESOLUTION,RESOLUTION],
        "pivotPx":pivot,
        "files":records
    },indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("CH_RAIL_TURNTABLE_ROTATION_25x4_PASS")

if __name__=="__main__":
    main()
