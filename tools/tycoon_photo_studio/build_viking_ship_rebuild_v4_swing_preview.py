"""Render a review-only swing sequence for Viking Ship Rebuild V4.

This does NOT define the runtime animation contract. The temporary angles/cadence exist
only to judge silhouette, clearances, scale and motion before final frame count/arc/FPS
are approved. Camera, lighting and V4 geometry remain authoritative from CH Blender.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v4_guarded  # noqa: F401 - installs V4 callbacks/gates


REVIEW_ANGLES = [-40, -30, -20, -10, 0, 10, 20, 30, 40, 30, 20, 10, 0, -10, -20, -30]
REVIEW_DURATION_MS = 90
REVIEW_RESOLUTION = 640


def _render_frame(scene, pivot, path: Path, degrees: float) -> None:
    pivot.rotation_euler[1] = math.radians(float(degrees))
    bpy.context.view_layer.update()
    scene.render.resolution_x = REVIEW_RESOLUTION
    scene.render.resolution_y = REVIEW_RESOLUTION
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = min(int(scene.cycles.samples), 12)
        scene.cycles.use_denoising = True
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    args = base.parse_args()
    profile = base.scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = base.build_for_gate(args)
    base.write_metadata(recipe, scene, out)

    preflight_path = out / "preflight_report.json"
    preflight = base.scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    base.scene_gate.require_pass(preflight)

    preview_dir = out / "animation_preview"
    frames_dir = preview_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_names: list[str] = []
    frame_records: list[dict] = []
    for index, degrees in enumerate(REVIEW_ANGLES):
        frame = frames_dir / f"frame_{index:03d}.png"
        _render_frame(scene, pivot, frame, degrees)
        frame_names.append(f"frames/{frame.name}")
        frame_records.append({"index": index, "swingDegrees": degrees, "file": frame_names[-1]})

    manifest = {
        "contract": "CH_ANIMATION_PREVIEW_V1",
        "id": "attraction.park_viking_ship.01.rebuild_v4.swing_review",
        "reviewOnly": True,
        "runtimeAnimationDefined": False,
        "note": "Temporary review motion only; do not infer final runtime frame count, arc or FPS.",
        "frames": frame_names,
        "durationMs": REVIEW_DURATION_MS,
        "loop": 0,
        "pingPong": False,
        "background": [24, 30, 36],
        "output": "viking_ship_rebuild_v4_swing_review.gif",
        "contactSheet": "viking_ship_rebuild_v4_swing_contact_sheet.png",
        "capture": {
            "cameraContract": "CH_CAMERA_V1",
            "resolution": [REVIEW_RESOLUTION, REVIEW_RESOLUTION],
            "angles": REVIEW_ANGLES,
            "sourceRecipe": "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v4.json",
            "builder": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v4_swing_preview.py",
        },
    }
    (preview_dir / "animation_preview_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (preview_dir / "frame_sequence.json").write_text(
        json.dumps({"reviewOnly": True, "frames": frame_records}, indent=2), encoding="utf-8"
    )

    # Restore rest position before saving the authoring file.
    pivot.rotation_euler[1] = math.radians(float(recipe["geometry"].get("previewSwingDegrees", 0.0)))
    bpy.context.view_layer.update()
    base.save_blend(args.save_blend)
    print(f"[CH_ANIMATION_PREVIEW] Captured {len(frame_names)} V4 review frames in {preview_dir}")


if __name__ == "__main__":
    main()
