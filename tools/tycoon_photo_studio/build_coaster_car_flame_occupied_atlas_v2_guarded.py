"""Guarded occupied Flame coaster car atlas V2.

One source of truth for review and final bake.  It combines the approved Flame car
with the approved two-seat CHActor passenger recipe and applies the full
CH_COASTER_CAR_ORIENTATION_V2 yaw/pitch/roll transform around the rail anchor.
The legacy 40-frame atlas is not modified by this builder.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy

import build_scene as bs
import scene_gate
import shape_authoring as shape
import build_coaster_car_flame_orientation_v2_guarded as orientation
import build_coaster_car_flame_passenger_overlay_v1_guarded as passengers

ASSET_ID = "ride.coaster.car_flame_occupied_atlas_v2"
ATLAS_CONTRACT = "CH_COASTER_CAR_ATLAS_RUNTIME_V2"
ORIENTATION_CONTRACT = "CH_COASTER_CAR_ORIENTATION_V2"
TRACK_CONTRACT = "CH_COASTER_TRACK_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 1, "depthTiles": 1}
HEADING_COUNT = 16
HEADING_STEP = 22.5
PITCH_BINS = (-46.0, -30.0, -14.0, 0.0, 14.0, 30.0, 46.0)
VERTICAL_PITCHES = (-90.0, 90.0)
BANK_ROLLS = (-24.0, 24.0)
INVERTED_ROLL = 180.0

REVIEW_POSES = (
    {"id": "diagonal_slope", "heading": 45.0, "pitch": 30.0, "roll": 0.0},
    {"id": "vertical", "heading": 0.0, "pitch": 90.0, "roll": 0.0},
    {"id": "banked_curve", "heading": 45.0, "pitch": 0.0, "roll": 24.0},
    {"id": "loop_apex_inverted", "heading": 180.0, "pitch": 0.0, "roll": 180.0},
)
PRIMARY_PROXY_ID = "diagonal_slope"


def parse_args():
    argv = bpy.app.driver_namespace.get("argv_override")
    if argv is None:
        import sys
        argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def heading_index(deg: float) -> int:
    return int(round((deg % 360.0) / HEADING_STEP)) % HEADING_COUNT


def token(value: float) -> str:
    n = int(round(value))
    return f"p{n:03d}" if n >= 0 else f"m{abs(n):03d}"


def frame_name(h: float, p: float, r: float) -> str:
    return f"occupied_h{heading_index(h):02d}_{token(p)}_r{token(r)}.png"


def all_poses():
    poses = []
    headings = [i * HEADING_STEP for i in range(HEADING_COUNT)]
    # Every ordinary slope exists at every heading: no cardinal snap.
    for p in PITCH_BINS:
        for h in headings:
            poses.append({"heading": h, "pitch": p, "roll": 0.0, "family": "heading_pitch_16way"})
    # Full vertical entry/exit orientations for loops and steep elements.
    for p in VERTICAL_PITCHES:
        for h in headings:
            poses.append({"heading": h, "pitch": p, "roll": 0.0, "family": "vertical_16way"})
    # Banked horizontal curves used by the approved helix/banked vocabulary.
    for r in BANK_ROLLS:
        for h in headings:
            poses.append({"heading": h, "pitch": 0.0, "roll": r, "family": "banked_16way"})
    # Inverted horizontal apex.  Keeping all headings makes rotated modules safe.
    for h in headings:
        poses.append({"heading": h, "pitch": 0.0, "roll": INVERTED_ROLL, "family": "inverted_16way"})
    for index, pose in enumerate(poses):
        pose["frameIndex"] = index
        pose["headingIndex"] = heading_index(pose["heading"])
        pose["file"] = frame_name(pose["heading"], pose["pitch"], pose["roll"])
    return poses


def pose_by_id(pose_id: str):
    for p in REVIEW_POSES:
        if p["id"] == pose_id:
            return p
    raise KeyError(pose_id)


def render(scene, authored, profile, output: Path, pose, filename: str, direction: str):
    return scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / filename,
        profile=profile,
        asset_id=ASSET_ID,
        direction=direction,
    )


def write_manifest(output: Path, poses, slots, stage: str):
    payload = {
        "contract": ATLAS_CONTRACT,
        "assetId": ASSET_ID,
        "styleId": STYLE_ID,
        "trackContract": TRACK_CONTRACT,
        "orientationContract": ORIENTATION_CONTRACT,
        "cameraContract": "CH_CAMERA_V1",
        "baseForwardAxis": "+Y",
        "baseUpAxis": "+Z",
        "anchor": [0.0, 0.0, orientation.track.RAIL_Z],
        "headingCount": HEADING_COUNT,
        "headingStepDegrees": HEADING_STEP,
        "pitchBins": list(PITCH_BINS),
        "verticalPitchBins": list(VERTICAL_PITCHES),
        "bankRollBins": list(BANK_ROLLS),
        "invertedRollDegrees": INVERTED_ROLL,
        "frameCount": len(poses),
        "occupancy": {
            "mode": "blender_depth_correct_composite",
            "capacityPerCar": 2,
            "defaultOccupiedSeatsPerCar": 2,
            "seatSlots": slots,
            "visualRecipeSource": "CH_VIKING_PASSENGER_OVERLAY_V1",
        },
        "selectionPolicy": "nearest_heading_pitch_roll_without_cardinal_slope_snap",
        "stage": stage,
        "frames": poses,
    }
    (output / "occupied_pose_manifest_v2.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    shape.load_contract()
    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    car_meshes = orientation.build_generic_car()
    passenger_meshes, markers, slots = passengers.add_passengers()
    authored = car_meshes + passenger_meshes
    root = bs.create_asset_root(authored + markers)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["trackContract"] = TRACK_CONTRACT
    root["carContract"] = ORIENTATION_CONTRACT
    root["atlasContract"] = ATLAS_CONTRACT
    root["passengerOcclusionContract"] = "CH_COASTER_PASSENGER_OCCLUSION_V2"
    root["styleId"] = STYLE_ID
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    base = orientation.capture_base_matrices(authored)
    calibration = pose_by_id("vertical")
    orientation.apply_orientation(authored, base, calibration["heading"], calibration["pitch"], calibration["roll"])
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.34)
    bpy.context.view_layer.update()

    poses = all_poses()
    write_manifest(output, poses, slots, args.stage)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "preflight":
        return

    if args.stage == "proxy":
        auxiliary = []
        for p in REVIEW_POSES:
            orientation.apply_orientation(authored, base, p["heading"], p["pitch"], p["roll"])
            name = f"proxy_{p['id']}.png"
            render(scene, authored, profile, output, p, name,
                   f"{p['id']}_h{p['heading']:+.0f}_p{p['pitch']:+.0f}_r{p['roll']:+.0f}")
            auxiliary.append(name)
        primary = pose_by_id(PRIMARY_PROXY_ID)
        orientation.apply_orientation(authored, base, primary["heading"], primary["pitch"], primary["roll"])
        proxy = render(scene, authored, profile, output, primary, "proxy_south.png", "south")
        proxy["pose"] = primary
        proxy["atlasContract"] = ATLAS_CONTRACT
        proxy["plannedFinalFrameCount"] = len(poses)
        proxy["auxiliaryReviewImages"] = auxiliary
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
        return

    if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
        raise ValueError("Final occupied V2 atlas requires the reviewed proxy SHA-256")
    (output / "proxy_approval.json").write_text(json.dumps({
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": ASSET_ID,
        "reviewed": True,
        "proxySha256": args.approval_proxy_sha,
    }, indent=2), encoding="utf-8")
    (output / "studio_metadata.json").write_text(json.dumps({
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": "final",
        "runtimeRepresentation": "2D_RGBA_pre_rendered_occupied_pose_frames",
        "poseContract": ORIENTATION_CONTRACT,
        "atlasContract": ATLAS_CONTRACT,
        "frameCount": len(poses),
    }, indent=2), encoding="utf-8")

    for pose in poses:
        orientation.apply_orientation(authored, base, pose["heading"], pose["pitch"], pose["roll"])
        render(scene, authored, profile, output, pose, pose["file"],
               f"h{pose['headingIndex']:02d}_p{pose['pitch']:+.0f}_r{pose['roll']:+.0f}")


if __name__ == "__main__":
    main()
