"""Guarded runtime pose-atlas builder for the approved City Horizon Flame coaster car.

The moving train is composed from individual pre-rendered car sprites. Flat curves use
16 yaw headings (22.5 degree steps). Current CH_COASTER_TRACK_V1 slopes and airtime
hills are longitudinal/cardinal, so only four cardinal headings need extra pitch poses.
This keeps curve articulation smooth without multiplying every heading by every pitch.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import shape_authoring as shape  # noqa: E402
import build_coaster_train_flame_v7_guarded as flame_v7  # noqa: E402

v5 = flame_v7.v5
track = v5.track

ASSET_ID = "ride.coaster.car_flame_pose_atlas_v1"
CAR_CONTRACT = "CH_COASTER_CAR_V1"
TRACK_CONTRACT = "CH_COASTER_TRACK_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 1, "depthTiles": 1}

HEADING_COUNT = 16
HEADING_STEP_DEG = 360.0 / HEADING_COUNT
FLAT_HEADINGS = [i * HEADING_STEP_DEG for i in range(HEADING_COUNT)]
CARDINAL_HEADINGS = [0.0, 90.0, 180.0, 270.0]
NONZERO_PITCH_BINS = [-46.0, -30.0, -14.0, 14.0, 30.0, 46.0]
PROXY_HEADING_DEG = 45.0
PROXY_PITCH_DEG = 0.0


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def make_materials():
    body_mat = bs.make_material("FlameAtlasBody", (0.56, 0.025, 0.018, 1.0), 0.44, 0.15)
    dark_mat = bs.make_material("FlameAtlasDarkTrim", (0.020, 0.025, 0.034, 1.0), 0.72)
    seat_mat = bs.make_material("FlameAtlasSeat", (0.014, 0.018, 0.024, 1.0), 0.78)
    metal_mat = bs.make_material("FlameAtlasMetal", (0.16, 0.18, 0.21, 1.0), 0.46, 0.34)
    wheel_mat = bs.make_material("FlameAtlasWheel", (0.010, 0.013, 0.018, 1.0), 0.86)
    orange_mat = bs.make_material("FlameAtlasOrange", (0.93, 0.15, 0.016, 1.0), 0.54)
    yellow_mat = bs.make_material("FlameAtlasYellow", (1.00, 0.50, 0.020, 1.0), 0.50)
    badge_mat = bs.make_material("FlameAtlasBadge", (0.80, 0.72, 0.54, 1.0), 0.58)
    return (body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat)


def build_generic_car():
    # One follower-style car is the runtime atom. The four-car hero render remains a
    # presentation asset; moving trains articulate by composing this car repeatedly.
    return v5.build_car(0, 0.0, lead=False, materials=make_materials())


def capture_base_matrices(authored):
    return {obj.name: obj.matrix_world.copy() for obj in authored}


def apply_pose(authored, base_matrices, heading_deg: float, pitch_deg: float):
    """Rotate around the rail-center anchor, with pitch in car-local X then world yaw."""
    anchor_z = track.RAIL_Z
    to_anchor = Matrix.Translation((0.0, 0.0, anchor_z))
    from_anchor = Matrix.Translation((0.0, 0.0, -anchor_z))
    yaw = Matrix.Rotation(math.radians(heading_deg), 4, "Z")
    pitch = Matrix.Rotation(math.radians(pitch_deg), 4, "X")
    pose = to_anchor @ yaw @ pitch @ from_anchor
    for obj in authored:
        obj.matrix_world = pose @ base_matrices[obj.name]
    bpy.context.view_layer.update()


def heading_index(degrees: float) -> int:
    return int(round((degrees % 360.0) / HEADING_STEP_DEG)) % HEADING_COUNT


def frame_name(heading_deg: float, pitch_deg: float) -> str:
    h = heading_index(heading_deg)
    if abs(pitch_deg) < 0.001:
        p = "p000"
    elif pitch_deg > 0:
        p = f"p{int(round(pitch_deg)):03d}"
    else:
        p = f"m{abs(int(round(pitch_deg))):03d}"
    return f"car_h{h:02d}_{p}.png"


def build_pose_manifest() -> dict:
    frames = []
    for heading in FLAT_HEADINGS:
        frames.append({
            "file": frame_name(heading, 0.0),
            "headingIndex": heading_index(heading),
            "headingDegrees": heading,
            "pitchDegrees": 0.0,
            "family": "flat_curve_16way",
            "trackUses": ["straight", "curve_left", "curve_right"],
        })
    for pitch in NONZERO_PITCH_BINS:
        for heading in CARDINAL_HEADINGS:
            frames.append({
                "file": frame_name(heading, pitch),
                "headingIndex": heading_index(heading),
                "headingDegrees": heading,
                "pitchDegrees": pitch,
                "family": "cardinal_vertical_supplement",
                "trackUses": [
                    "slope_up", "slope_down", "flat_to_slope_up", "slope_up_to_flat",
                    "flat_to_slope_down", "slope_down_to_flat", "airtime_hill_small",
                    "airtime_hill_large"
                ],
            })
    return {
        "contract": CAR_CONTRACT,
        "assetId": ASSET_ID,
        "styleId": STYLE_ID,
        "trackContract": TRACK_CONTRACT,
        "baseForwardAxis": "+Y",
        "anchor": [0.0, 0.0, track.RAIL_Z],
        "headingCount": HEADING_COUNT,
        "headingStepDegrees": HEADING_STEP_DEG,
        "flatCurveFrames": len(FLAT_HEADINGS),
        "verticalSupplementFrames": len(CARDINAL_HEADINGS) * len(NONZERO_PITCH_BINS),
        "totalFrames": len(frames),
        "rollDegrees": 0.0,
        "runtimeTrain": {
            "carCountDefault": 4,
            "composeCarsIndividually": True,
            "samplePoseFromLocalCenterlineTangent": True,
            "rigidWholeTrainSprite": False,
        },
        "frames": frames,
    }


def write_studio_metadata(output: Path, args):
    payload = {
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": ASSET_ID,
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": args.stage,
        "runtimeRepresentation": "2D_RGBA_pre_rendered_pose_atlas",
        "poseContract": CAR_CONTRACT,
        "frameCount": 40,
    }
    (output / "studio_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def render_frame(scene, authored, profile, output: Path, heading: float, pitch: float):
    return scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / frame_name(heading, pitch),
        profile=profile,
        asset_id=ASSET_ID,
        direction=f"h{heading_index(heading):02d}_pitch_{pitch:+.0f}",
    )


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

    authored = build_generic_car()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = TRACK_CONTRACT
    root["carContract"] = CAR_CONTRACT
    root["styleId"] = STYLE_ID
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    base_matrices = capture_base_matrices(authored)
    apply_pose(authored, base_matrices, PROXY_HEADING_DEG, PROXY_PITCH_DEG)
    # Extra framing margin covers the later +/-46 degree steep hill poses.
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.34)
    bpy.context.view_layer.update()

    pose_manifest = build_pose_manifest()
    (output / "pose_manifest.json").write_text(json.dumps(pose_manifest, indent=2), encoding="utf-8")

    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=ASSET_ID,
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / "proxy_south.png",
            profile=profile,
            asset_id=ASSET_ID,
            direction="curve_midpoint_heading_45",
        )
        proxy["pose"] = {"headingDegrees": PROXY_HEADING_DEG, "pitchDegrees": PROXY_PITCH_DEG}
        proxy["plannedFinalFrameCount"] = pose_manifest["totalFrames"]
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
            raise ValueError("The final atlas bake requires the reviewed proxy SHA-256")
        (output / "proxy_approval.json").write_text(json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": ASSET_ID,
            "reviewed": True,
            "proxySha256": args.approval_proxy_sha,
        }, indent=2), encoding="utf-8")
        write_studio_metadata(output, args)

        for heading in FLAT_HEADINGS:
            apply_pose(authored, base_matrices, heading, 0.0)
            render_frame(scene, authored, profile, output, heading, 0.0)
        for pitch in NONZERO_PITCH_BINS:
            for heading in CARDINAL_HEADINGS:
                apply_pose(authored, base_matrices, heading, pitch)
                render_frame(scene, authored, profile, output, heading, pitch)


if __name__ == "__main__":
    main()
