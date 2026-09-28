"""Final 4-direction runtime bake for the approved Viking V16 motion.

V17 preserves the approved V15 geometry/passenger placement and V16 timing.
The runtime sheet adds one idle frame (neutral boat, no riders) followed by the
28 approved active frames (boat + seated riders). This lets the SDL runtime keep
the attraction empty while idle and loop only the action range while running.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import bpy

import build_scene as bs
import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v15_passenger_overlay_proxy_guarded as v15
import build_viking_ship_rebuild_v16_physics_proxy_guarded as v16
import scene_gate

FINAL_CONTRACT = "CH_VIKING_RUNTIME_ANIMATION_FINAL_V1"
IDLE_FRAME = 0
ACTION_START_FRAME = 1
ACTION_FRAME_COUNT = v16.FRAME_COUNT
TOTAL_FRAME_COUNT = ACTION_FRAME_COUNT + 1
FPS = v16.FPS


def _set_passengers_visible(visible: bool) -> None:
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name.startswith("CHR_V15_CHActor_"):
            obj.hide_render = not visible


def _frame_metadata(recipe, studio, scene, frame: int, directions_meta, *, active: bool):
    source_res = tuple(map(int, studio["render"]["sourceResolution"]))
    final_res = tuple(map(int, studio["render"]["finalResolution"]))
    return {
        "sourceObject": recipe["assetId"],
        "assetType": "animated_attraction",
        "sourceContract": FINAL_CONTRACT,
        "assetConfig": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v17_runtime_final_guarded.py",
        "studioPreset": studio["id"],
        "styleContract": recipe.get("styleContract", "CH_STYLIZED_PRERENDER_V1"),
        "cameraContract": "CH_CAMERA_V1",
        "gridContract": "CH_GRID_V1",
        "projection": "orthographic_dimetric_2_to_1",
        "yawDegrees": 45.0,
        "elevationDegrees": 30.0,
        "tileWidth": 128,
        "tileHeight": 64,
        "footprint": recipe["footprint"],
        "blenderVersion": bpy.app.version_string,
        "renderEngine": scene.render.engine,
        "renderResolution": list(source_res),
        "finalResolution": list(final_res),
        "directionOrder": [direction["id"] for direction in bs.DIRECTIONS],
        "rotationPolicy": {
            "assetRootRotates": True,
            "cameraRemainsFixed": True,
            "lightsRemainWorldFixed": True,
        },
        "animation": {
            "frame": frame,
            "idleFrame": IDLE_FRAME,
            "actionStartFrame": ACTION_START_FRAME,
            "actionFrameCount": ACTION_FRAME_COUNT,
            "frameCount": TOTAL_FRAME_COUNT,
            "fps": FPS,
            "looping": True,
            "activeRideFrame": active,
            "motionProfile": "slow_ascent_peak_dwell_fast_descent_v1",
            "amplitudeDegrees": v16.AMPLITUDE_DEGREES,
        },
        "passengers": {
            "contract": v15.PASSENGER_CONTRACT,
            "capacity": v15.CAPACITY,
            "visible": active,
            "actorSource": "assets/characters/ch_actor_green_01",
            "paletteMode": "stable_per_visitor",
        },
        "sourceSummary": {
            "groundIncludedInAsset": False,
            "runtimeRepresentation": "2D_RGBA_pre_rendered_sprite",
            "revision": "V17_RUNTIME_FINAL",
            "geometryRevision": "V15",
            "motionRevision": "V16",
        },
        "directions": directions_meta,
    }


def _render_source_frame(recipe, studio, scene, root, pivot, ground, authored, frame_dir: Path,
                         frame: int, angle: float, *, active: bool) -> None:
    frame_dir.mkdir(parents=True, exist_ok=True)
    pivot.rotation_euler[1] = math.radians(angle)
    _set_passengers_visible(active)
    directions_meta = []
    for direction in bs.DIRECTIONS:
        bs.set_direction(root, direction)
        bpy.context.view_layer.update()
        color_name = f"{recipe['assetId']}_{direction['id']}_color_source.png"
        shadow_name = f"{recipe['assetId']}_{direction['id']}_shadow_source.png"
        bs.render_color_pass(scene, authored, ground, str(frame_dir / color_name))
        origin_px = bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene, authored, ground, str(frame_dir / shadow_name))
        directions_meta.append({
            "id": direction["id"],
            "quarterTurns": direction["quarterTurns"],
            "rotationDegrees": direction["rotationDegrees"],
            "colorSource": color_name,
            "shadowSource": shadow_name,
            "groundOriginSourcePx": origin_px,
        })
    metadata = _frame_metadata(recipe, studio, scene, frame, directions_meta, active=active)
    (frame_dir / "studio_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def _postprocess(out: Path, studio_preset: str, asset_id: str, approval_sha: str) -> None:
    python_exe = shutil.which("python")
    if not python_exe:
        raise RuntimeError("CH_VIKING_POSTPROCESS_PYTHON_NOT_FOUND")
    script = Path(__file__).resolve().with_name("postprocess_ferris_animation.py")
    cmd = [
        python_exe, str(script),
        "--input", str(out / "final_source"),
        "--output", str(out / "runtime"),
        "--studio-preset", str(Path(studio_preset).resolve()),
        "--asset-id", asset_id,
        "--frame-start", str(IDLE_FRAME),
        "--frame-end", str(TOTAL_FRAME_COUNT - 1),
        "--fps", str(FPS),
        "--approved-proxy-sha", approval_sha,
    ]
    subprocess.run(cmd, check=True, cwd=str(Path(__file__).resolve().parents[2]))


def main() -> None:
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored_before_passengers, out = base.build_for_gate(args)
    out = Path(out)
    _, slots = v15._add_passengers(recipe["geometry"])

    # Recompute authored meshes after adding the passenger overlay so the final
    # render includes the reviewed riders. Hidden riders are excluded by Blender
    # for the dedicated idle frame.
    authored = [obj for obj in scene.objects if obj.type == "MESH" and obj != ground]
    angles = v16._physics_angles()

    root["animationContract"] = FINAL_CONTRACT
    root["passengerOverlayContract"] = v15.PASSENGER_CONTRACT
    root["rideCapacity"] = v15.CAPACITY
    root["runtimeFrameCount"] = TOTAL_FRAME_COUNT
    root["runtimeIdleFrame"] = IDLE_FRAME
    root["runtimeActionStartFrame"] = ACTION_START_FRAME
    root["runtimeActionFrameCount"] = ACTION_FRAME_COUNT
    root["runtimeFps"] = FPS
    root["swingAmplitudeDegrees"] = v16.AMPLITUDE_DEGREES
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "slow_ascent_peak_dwell_fast_descent_v1"

    base.write_metadata(recipe, scene, out)
    metadata_path = out / "studio_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "stage": "viking_runtime_final_v17",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v17_runtime_final_guarded.py",
        "animationContract": FINAL_CONTRACT,
        "capacity": v15.CAPACITY,
        "seatSlots": slots,
        "frameCount": TOTAL_FRAME_COUNT,
        "idleFrame": IDLE_FRAME,
        "actionStartFrame": ACTION_START_FRAME,
        "actionFrameCount": ACTION_FRAME_COUNT,
        "fps": FPS,
        "activeCycleDurationMs": int(round(1000.0 * ACTION_FRAME_COUNT / FPS)),
        "amplitudeDegrees": v16.AMPLITUDE_DEGREES,
        "motionProfile": "slow_ascent_peak_dwell_fast_descent_v1",
        "runtimePromoted": False,
    })
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    _set_passengers_visible(False)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    preflight = scene_gate.run_preflight(
        scene=scene, authored=None, footprint=recipe["footprint"], profile=profile,
        asset_id=recipe["assetId"], report_path=out / "preflight_report.json")
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        base.save_blend(args.save_blend)
        return
    if args.stage == "proxy":
        raise RuntimeError("CH_VIKING_V17_FINAL_ONLY: V16 proxy timing is already human-approved")

    approval = (args.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY")

    (out / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": recipe["assetId"],
        "proxySha256": approval,
        "reviewed": True,
        "reviewedRevision": "V16",
        "runtimeTarget": "2D_RGBA_pre_rendered_sprite",
    }, indent=2), encoding="utf-8")

    source_root = out / "final_source"
    source_root.mkdir(parents=True, exist_ok=True)

    # Frame 0 is the idle attraction: neutral boat, no passengers.
    _render_source_frame(recipe, studio, scene, root, pivot, ground, authored,
                         source_root / "frame_000", 0, 0.0, active=False)

    # Frames 1..28 are the approved V16 passenger motion.
    for index, angle in enumerate(angles, start=ACTION_START_FRAME):
        _render_source_frame(recipe, studio, scene, root, pivot, ground, authored,
                             source_root / f"frame_{index:03d}", index, angle, active=True)

    _postprocess(out, args.studio_preset, recipe["assetId"], approval)

    final_report = {
        "contract": FINAL_CONTRACT,
        "status": "ok",
        "assetId": recipe["assetId"],
        "approvedProxySha256": approval,
        "directions": [direction["id"] for direction in bs.DIRECTIONS],
        "frameCount": TOTAL_FRAME_COUNT,
        "idleFrame": IDLE_FRAME,
        "actionStartFrame": ACTION_START_FRAME,
        "actionFrameCount": ACTION_FRAME_COUNT,
        "fps": FPS,
        "activeCycleDurationMs": int(round(1000.0 * ACTION_FRAME_COUNT / FPS)),
        "amplitudeDegrees": v16.AMPLITUDE_DEGREES,
        "motionProfile": "slow_ascent_peak_dwell_fast_descent_v1",
        "passengerCapacity": v15.CAPACITY,
        "runtimeDir": "runtime",
        "runtimePromoted": False,
    }
    (out / "final_bake_report.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    _set_passengers_visible(False)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()
    base.save_blend(args.save_blend)
    print("[CH_GATE] Viking V17 final 4-direction runtime animation bake complete")


if __name__ == "__main__":
    main()
