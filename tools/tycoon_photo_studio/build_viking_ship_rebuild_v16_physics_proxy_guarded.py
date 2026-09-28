"""V16 Viking ship passenger swing timing review.

Keeps the approved V15 geometry/passenger placement untouched and changes only
the temporal sampling of SwingPivot. The motion intentionally spends more frames
climbing, dwells briefly at each extreme, and uses fewer frames on the descent.
This is a SOUTH review proxy; four-direction final bake remains gated on human
approval of this revised timing.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v15_passenger_overlay_proxy_guarded as v15
import scene_gate

ANIMATION_CONTRACT = "CH_VIKING_SWING_PHYSICS_PROXY_V2"
FRAME_COUNT = 28
FPS = 8
AMPLITUDE_DEGREES = 35.0


def _physics_angles() -> list[float]:
    """One loop: slow climb, 250 ms crest dwell, faster fall, repeat opposite side."""
    values: list[float] = [0.0]

    # Slow climb from center to +peak: 8 frames, sinusoidal ease-out.
    for i in range(1, 9):
        t = i / 8.0
        values.append(AMPLITUDE_DEGREES * math.sin(0.5 * math.pi * t))
    # Two extra peak frames = 250 ms visible dwell at 8 fps.
    values.extend([AMPLITUDE_DEGREES, AMPLITUDE_DEGREES])

    # Faster descent +peak -> center: only 4 frames, accelerating naturally.
    for i in range(1, 5):
        t = i / 4.0
        values.append(AMPLITUDE_DEGREES * math.cos(0.5 * math.pi * t))

    # Slow climb center -> -peak: 8 frames.
    for i in range(1, 9):
        t = i / 8.0
        values.append(-AMPLITUDE_DEGREES * math.sin(0.5 * math.pi * t))
    # Two extra peak frames on the opposite side.
    values.extend([-AMPLITUDE_DEGREES, -AMPLITUDE_DEGREES])

    # Faster descent -peak toward center. Omit the final zero because frame 0 is
    # already neutral and closes the loop without a duplicate center pause.
    for i in range(1, 4):
        t = i / 4.0
        values.append(-AMPLITUDE_DEGREES * math.cos(0.5 * math.pi * t))

    if len(values) != FRAME_COUNT:
        raise RuntimeError(f"CH_VIKING_V16_FRAME_COUNT_MISMATCH:{len(values)}!={FRAME_COUNT}")
    return values


def main() -> None:
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = base.build_for_gate(args)
    out = Path(out)
    _, slots = v15._add_passengers(recipe["geometry"])

    angles = _physics_angles()
    root["animationContract"] = ANIMATION_CONTRACT
    root["passengerOverlayContract"] = v15.PASSENGER_CONTRACT
    root["rideCapacity"] = v15.CAPACITY
    root["swingProxyFrameCount"] = FRAME_COUNT
    root["swingProxyFps"] = FPS
    root["swingAmplitudeDegrees"] = AMPLITUDE_DEGREES
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "slow_ascent_peak_dwell_fast_descent_v1"

    base.write_metadata(recipe, scene, out)
    metadata_path = out / "studio_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "stage": "viking_swing_physics_proxy_v16",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v16_physics_proxy_guarded.py",
        "animationContract": ANIMATION_CONTRACT,
        "passengerOverlayContract": v15.PASSENGER_CONTRACT,
        "capacity": v15.CAPACITY,
        "seatSlots": slots,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "cycleDurationMs": int(round(1000.0 * FRAME_COUNT / FPS)),
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "motionProfile": "slow_ascent_peak_dwell_fast_descent_v1",
        "timingNotes": "8-frame climb, 2-frame crest dwell, 4-frame descent per half-cycle",
        "runtimePromoted": False,
    })
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    preflight = scene_gate.run_preflight(
        scene=scene, authored=None, footprint=recipe["footprint"], profile=profile,
        asset_id=recipe["assetId"], report_path=out / "preflight_report.json")
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        base.save_blend(args.save_blend)
        return
    if args.stage != "proxy":
        raise RuntimeError("CH_VIKING_V16_PROXY_ONLY: revised motion requires human timing review before final four-direction bake")

    frame_names: list[str] = []
    reports = []
    for index, angle in enumerate(angles):
        pivot.rotation_euler[1] = math.radians(angle)
        bpy.context.view_layer.update()
        frame_name = f"occupied_south_{index:02d}.png"
        report = scene_gate.render_proxy(
            scene=scene, authored=None, output_path=out / frame_name,
            profile=profile, asset_id=recipe["assetId"], direction="south")
        reports.append(report)
        frame_names.append(frame_name)

    (out / "proxy_south.png").write_bytes((out / frame_names[0]).read_bytes())
    canonical = dict(reports[0])
    canonical["path"] = str(out / "proxy_south.png")
    (out / "proxy_report.json").write_text(json.dumps(canonical, indent=2), encoding="utf-8")

    (out / "swing_physics_proxy_report.json").write_text(json.dumps({
        "contract": ANIMATION_CONTRACT,
        "status": "ok",
        "capacity": v15.CAPACITY,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "cycleDurationMs": int(round(1000.0 * FRAME_COUNT / FPS)),
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "motionProfile": "slow_ascent_peak_dwell_fast_descent_v1",
        "anglesDegrees": [round(value, 6) for value in angles],
        "frames": frame_names,
        "runtimePromoted": False,
    }, indent=2), encoding="utf-8")

    (out / "animation_preview_manifest.json").write_text(json.dumps({
        "contract": "CH_ANIMATION_PREVIEW_V1",
        "id": "attraction.park_viking_ship.01.swing_physics_passengers_v16",
        "reviewOnly": True,
        "frames": frame_names,
        "durationMs": int(round(1000.0 / FPS)),
        "loop": 0,
        "pingPong": False,
        "output": "viking_ship_physics_passengers_v16_preview.gif",
        "contactSheet": "viking_ship_physics_passengers_v16_contact_sheet.png",
        "background": [24, 30, 36],
    }, indent=2), encoding="utf-8")

    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    base.save_blend(args.save_blend)
    print("[CH_GATE] Viking V16 slower pendulum timing proxy ready")


if __name__ == "__main__":
    main()
