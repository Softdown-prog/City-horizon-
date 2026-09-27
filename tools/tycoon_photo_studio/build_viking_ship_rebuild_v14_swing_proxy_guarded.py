"""Guarded swing-animation proxy for the approved City Horizon Viking ship V12.

This pass is review-only. It keeps the approved static attraction geometry and
camera, animates only SwingPivot around its authored Y axis, and renders one
complete 12-frame pendulum cycle from the SOUTH view. No runtime sheets are
promoted here; four-direction final baking remains gated on human proxy review.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v12_hull_finish_guarded as v12gate  # noqa: F401
import scene_gate


ANIMATION_CONTRACT = "CH_VIKING_SWING_ANIMATION_PROXY_V1"
FRAME_COUNT = 12
FPS = 8
AMPLITUDE_DEGREES = 35.0


def _angles() -> list[float]:
    # One complete sinusoidal cycle. Frame 0 is the canonical neutral/static pose;
    # the last frame continues smoothly back into frame 0 without duplicating it.
    return [
        AMPLITUDE_DEGREES * math.sin((2.0 * math.pi * index) / FRAME_COUNT)
        for index in range(FRAME_COUNT)
    ]


def _write_animation_manifest(out: Path, frame_names: list[str]) -> None:
    payload = {
        "contract": "CH_ANIMATION_PREVIEW_V1",
        "id": "attraction.park_viking_ship.01.swing_proxy_v14",
        "reviewOnly": True,
        "frames": frame_names,
        "durationMs": int(round(1000.0 / FPS)),
        "loop": 0,
        "pingPong": False,
        "output": "viking_ship_swing_preview.gif",
        "contactSheet": "viking_ship_swing_contact_sheet.png",
        "background": [24, 30, 36],
    }
    (out / "animation_preview_manifest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _write_swing_report(out: Path, frame_reports: list[dict], angles: list[float]) -> None:
    payload = {
        "contract": ANIMATION_CONTRACT,
        "status": "ok",
        "assetId": "attraction.park_viking_ship.01",
        "sourceRevision": "CH_VIKING_HULL_FINISH_V12",
        "direction": "south",
        "rotationAxis": "Y",
        "motion": "pendulum_sinusoidal",
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "frameDurationMs": int(round(1000.0 / FPS)),
        "amplitudeDegrees": AMPLITUDE_DEGREES,
        "anglesDegrees": [round(value, 6) for value in angles],
        "looping": True,
        "runtimePromoted": False,
        "requiresHumanReviewBeforeFourDirectionBake": True,
        "frames": [
            {
                "index": index,
                "angleDegrees": round(angles[index], 6),
                "file": Path(report["path"]).name,
                "sha256": report["sha256"],
            }
            for index, report in enumerate(frame_reports)
        ],
    }
    (out / "swing_proxy_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def main() -> None:
    args = base.parse_args()
    profile = scene_gate.load_profile(args.preflight_profile)
    recipe, studio, scene, root, pivot, ground, authored, out = base.build_for_gate(args)
    out = Path(out)

    root["animationContract"] = ANIMATION_CONTRACT
    root["animationFramesDefined"] = True
    root["swingFramesBaked"] = False
    root["swingProxyFrameCount"] = FRAME_COUNT
    root["swingProxyFps"] = FPS
    root["swingAmplitudeDegrees"] = AMPLITUDE_DEGREES
    pivot["rotationAxis"] = "Y"
    pivot["motionProfile"] = "pendulum_sinusoidal"

    base.write_metadata(recipe, scene, out)
    metadata_path = out / "studio_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update({
        "stage": "viking_swing_animation_proxy_v14",
        "builder": "tools/tycoon_photo_studio/build_viking_ship_rebuild_v14_swing_proxy_guarded.py",
        "animationContract": ANIMATION_CONTRACT,
        "frameCount": FRAME_COUNT,
        "fps": FPS,
        "swingAmplitudeDegrees": AMPLITUDE_DEGREES,
        "swingAxis": "Y",
        "runtimePromoted": False,
    })
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # Structural gate is run in the approved neutral pose.
    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    preflight_path = out / "preflight_report.json"
    preflight = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=recipe["footprint"],
        profile=profile,
        asset_id=recipe["assetId"],
        report_path=preflight_path,
    )
    scene_gate.require_pass(preflight)

    if args.stage == "preflight":
        base.save_blend(args.save_blend)
        print(f"[CH_GATE] Viking V14 swing preflight PASS: {preflight_path}")
        return

    if args.stage != "proxy":
        raise RuntimeError(
            "CH_VIKING_V14_PROXY_ONLY: final four-direction swing bake requires human review of this animation proxy"
        )

    angles = _angles()
    frame_reports: list[dict] = []
    frame_names: list[str] = []
    for index, angle in enumerate(angles):
        pivot.rotation_euler[1] = math.radians(angle)
        bpy.context.view_layer.update()
        frame_name = f"swing_south_{index:02d}.png"
        report = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=out / frame_name,
            profile=profile,
            asset_id=recipe["assetId"],
            direction="south",
        )
        frame_reports.append(report)
        frame_names.append(frame_name)
        print(f"[CH_GATE] Viking swing frame {index:02d} angle={angle:+.2f} sha={report['sha256']}")

    # The CH Blender worker requires one canonical SOUTH proxy/report pair.
    # Use the neutral first frame byte-for-byte so the quality gate can validate it.
    neutral_path = out / frame_names[0]
    proxy_path = out / "proxy_south.png"
    proxy_path.write_bytes(neutral_path.read_bytes())
    canonical_proxy = dict(frame_reports[0])
    canonical_proxy["path"] = str(proxy_path)
    (out / "proxy_report.json").write_text(
        json.dumps(canonical_proxy, indent=2), encoding="utf-8"
    )

    _write_swing_report(out, frame_reports, angles)
    _write_animation_manifest(out, frame_names)

    # Save the authored file in the approved neutral pose. Animation frames remain
    # explicit deterministic outputs, not hidden keyframes in this proxy pass.
    pivot.rotation_euler[1] = 0.0
    bpy.context.view_layer.update()
    base.save_blend(args.save_blend)
    print("[CH_GATE] Viking V14 12-frame SOUTH swing proxy ready for human review")


if __name__ == "__main__":
    main()
