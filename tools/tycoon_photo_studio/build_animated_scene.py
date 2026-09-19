"""Tycoon Animation Baker — N-frame, 4-direction pre-rendered sprite pipeline.

Extends the static build_scene.py pipeline to support animated props and buildings.
For each animation frame and each direction the baker renders two passes:
  • <asset_id>_<direction>_frame_<NN>_color_source.png
  • <asset_id>_<direction>_frame_<NN>_shadow_source.png

The studio metadata records frame count, FPS and loop mode so postprocess_animation.py
can compose direction spritesheets and a full animation atlas.

Asset config format (extend TYCOON_ASSET_SOURCE_V1 with an "animation" block)
-------------------------------------------------------------------------------
{
  "contract": "TYCOON_ASSET_SOURCE_V1",
  "assetId": "windmill_01",
  "assetType": "animated_prop",
  "studioPreset": "CH_TYCOON_STUDIO_V1",
  "footprint": {"widthTiles": 1, "depthTiles": 1, "occupiedCells": [[0, 0]]},
  "animation": {
    "enabled": true,
    "frameStart": 1,
    "frameEnd": 8,
    "fps": 12,
    "looping": true,
    "bladeObjectName": "MillBlade"   ← optional: name of a rotating sub-object
  },
  "materials": { ... },
  "parts": [ ... ]
}

Usage (via blender_bake_runner.py)
----------------------------------
    blender --background --python tools/tycoon_photo_studio/build_animated_scene.py -- \\
        --output out/bake/windmill_01/source \\
        --asset-config tools/tycoon_photo_studio/assets/windmill_01.json \\
        --studio-preset tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json

Or directly:
    python tools/blender_bake_runner.py \\
        --scene tools/tycoon_photo_studio/build_animated_scene.py \\
        --contract ... --output-dir out/bake/windmill_01
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector, Euler

# Reuse shared helpers from build_scene.py
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import build_scene as _bs  # noqa: E402 — imported after sys.path setup


DIRECTIONS = _bs.DIRECTIONS


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser(
        description="Tycoon Animation Baker — multi-frame, 4-direction bake"
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--source-resolution", default=None, metavar="WxH")
    parser.add_argument("--final-resolution", default=None, metavar="WxH")
    parser.add_argument("--ortho-safety", type=float, default=0.12)
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Animation-specific helpers
# ---------------------------------------------------------------------------


def _configure_animation(scene, anim: dict):
    """Set Blender scene frame range from the animation config."""
    frame_start = int(anim.get("frameStart", 1))
    frame_end = int(anim.get("frameEnd", 8))
    fps = int(anim.get("fps", 12))

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = fps
    scene.frame_set(frame_start)
    return frame_start, frame_end, fps


def _rotate_blade(authored, blade_name, frame, frame_start, frame_end):
    """Rotate a named sub-object continuously (e.g. a windmill blade).

    The rotation angle is computed so the object completes one full revolution
    per animation loop regardless of frame count.
    """
    total_frames = max(1, frame_end - frame_start + 1)
    angle = (2.0 * math.pi * (frame - frame_start)) / total_frames

    for obj in authored:
        if obj.name == blade_name:
            obj.rotation_euler = Euler((0.0, 0.0, angle), "XYZ")
            break


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    args = parse_args()
    output_dir = os.path.abspath(args.output)
    asset = _bs.load_json(args.asset_config)
    studio = _bs.load_json(args.studio_preset)

    if asset.get("studioPreset") != studio.get("id"):
        raise RuntimeError(
            f"Asset requests studio {asset.get('studioPreset')!r}, "
            f"but loaded {studio.get('id')!r}"
        )

    anim_spec = asset.get("animation", {})
    if not anim_spec.get("enabled", False):
        raise RuntimeError(
            "This baker is for animated assets. "
            "Set \"animation\": {\"enabled\": true, ...} in the asset config, "
            "or use build_scene.py for static assets."
        )

    # ── Resolution ────────────────────────────────────────────────────────
    src_res = _bs.parse_resolution(args.source_resolution) if args.source_resolution else None
    final_res = _bs.parse_resolution(args.final_resolution) if args.final_resolution else None
    auto_src, auto_final = _bs.compute_dynamic_resolution(asset, studio)
    src_res = src_res or auto_src
    final_res = final_res or auto_final

    # ── Build scene (static geometry + materials) ─────────────────────────
    _bs.clear_scene()
    scene = _bs.configure_scene(studio, src_res, output_dir)
    authored = _bs.build_asset(asset, asset_config_path=args.asset_config)
    root = _bs.create_asset_root(authored)

    _bs.validate_footprint_scale(asset, authored)

    receiver = studio["shadowReceiver"]
    ground_mat = _bs.make_material(
        "ShadowReceiver",
        receiver["materialColor"],
        float(receiver.get("roughness", 1.0)),
    )
    ground = _bs.add_box(
        "ShadowReceiverPlane",
        receiver["location"],
        receiver["dimensions"],
        ground_mat,
        0.0,
    )

    # ── Auto-fit camera ───────────────────────────────────────────────────
    calibrated_scale = _bs.calibrate_ortho_scale(
        scene, authored, safety_margin=args.ortho_safety
    )

    # ── Configure frame range ─────────────────────────────────────────────
    frame_start, frame_end, fps = _configure_animation(scene, anim_spec)
    blade_name = anim_spec.get("bladeObjectName")
    looping = bool(anim_spec.get("looping", True))
    frame_count = frame_end - frame_start + 1

    print(
        f"[anim_baker] Asset: {asset['assetId']}  "
        f"frames: {frame_start}–{frame_end} ({frame_count} frames)  "
        f"FPS: {fps}  looping: {looping}"
    )

    asset_id = asset["assetId"]
    direction_metadata = []

    # ── Render loop: directions × frames ─────────────────────────────────
    for direction in DIRECTIONS:
        direction_id = direction["id"]
        _bs.set_direction(root, direction)
        frame_records = []

        for frame in range(frame_start, frame_end + 1):
            scene.frame_set(frame)

            # Apply procedural sub-object animation (e.g. blade rotation)
            if blade_name:
                _rotate_blade(authored, blade_name, frame, frame_start, frame_end)

            bpy.context.view_layer.update()

            color_name = f"{asset_id}_{direction_id}_frame_{frame:02d}_color_source.png"
            shadow_name = f"{asset_id}_{direction_id}_frame_{frame:02d}_shadow_source.png"

            _bs.render_color_pass(
                scene, authored, ground,
                os.path.join(output_dir, color_name)
            )
            _bs.render_shadow_pass(
                scene, authored, ground,
                os.path.join(output_dir, shadow_name)
            )

            frame_records.append({
                "frame": frame,
                "colorSource": color_name,
                "shadowSource": shadow_name,
                "groundOriginSourcePx": _bs.ground_origin_source_px(scene),
            })

            print(
                f"  [{direction_id}] frame {frame}/{frame_end} "
                f"color+shadow rendered"
            )

        direction_metadata.append({
            **direction,
            "frameCount": frame_count,
            "frames": frame_records,
        })

    # Reset root and frame
    root.rotation_euler[2] = 0.0
    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    # ── Write studio_metadata.json ────────────────────────────────────────
    metadata = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "animationMode": True,
        "sourceContract": asset["contract"],
        "sourceObject": asset_id,
        "assetType": asset.get("assetType", "animated_prop"),
        "footprint": asset["footprint"],
        "assetConfig": os.path.basename(args.asset_config),
        "studioPreset": studio["id"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderDevice": studio["render"]["device"],
        "samples": scene.cycles.samples,
        "cameraContract": studio["camera"]["contract"],
        "gridContract": "CH_GRID_V1",
        "projection": studio["camera"]["projection"],
        "yawDegrees": studio["camera"]["yawDegrees"],
        "elevationDegrees": studio["camera"]["elevationDegrees"],
        "tileWidth": _bs.TILE_PX_W,
        "tileHeight": _bs.TILE_PX_H,
        "blenderUnitsPerTile": _bs.BLENDER_UNITS_PER_TILE,
        "renderResolution": list(src_res),
        "finalResolution": list(final_res),
        "orthoScaleCalibrated": calibrated_scale,
        "orthoScaleOriginal": studio["camera"]["orthoScale"],
        "animation": {
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "frameCount": frame_count,
            "fps": fps,
            "looping": looping,
        },
        "directionOrder": [d["id"] for d in DIRECTIONS],
        "directions": direction_metadata,
        "rotationPolicy": {
            "cameraRotates": False,
            "assetRootRotates": True,
            "lightsRotate": False,
        },
        "postProcess": studio["postProcess"],
        "note": (
            "Tycoon Animation Baker V1 output.  "
            f"Total renders: {len(DIRECTIONS)} directions × {frame_count} frames × 2 passes "
            f"= {len(DIRECTIONS) * frame_count * 2}.  "
            "Human visual approval required before production promotion."
        ),
    }

    with open(os.path.join(output_dir, "studio_metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    total_renders = len(DIRECTIONS) * frame_count * 2
    print(f"\n[anim_baker] Done: {total_renders} renders for '{asset_id}'")
    print(f"  source_resolution : {src_res[0]}×{src_res[1]}")
    print(f"  final_resolution  : {final_res[0]}×{final_res[1]}")
    print(f"  ortho_scale       : {calibrated_scale:.3f}")
    print(f"  directions        : {[d['id'] for d in DIRECTIONS]}")
    print(f"  frames/direction  : {frame_count} ({fps} FPS, looping={looping})")


if __name__ == "__main__":
    main()
