"""Guarded CH Blender proof for the Flame coaster car full 3D orientation contract.

This is deliberately a proxy-first validation builder.  It proves that the approved
Flame car can be authored around its rail-center anchor with yaw + pitch + local
forward-axis roll before a larger runtime atlas is baked.  The existing 40-frame
CH_COASTER_CAR_ATLAS_RUNTIME_V1 remains untouched.
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

ASSET_ID = "ride.coaster.car_flame_orientation_v2"
CAR_CONTRACT = "CH_COASTER_CAR_ORIENTATION_V2"
TRACK_CONTRACT = "CH_COASTER_TRACK_V1"
STYLE_ID = "flame_01"
FOOTPRINT = {"widthTiles": 1, "depthTiles": 1}

# Three human-review poses.  The primary proxy is the loop apex because the
# previous heading+pitch atlas could not distinguish horizontal-upright from
# horizontal-inverted at that location.
REVIEW_POSES = (
    {"id": "normal", "heading": 45.0, "pitch": 0.0, "roll": 0.0},
    {"id": "vertical", "heading": 0.0, "pitch": 90.0, "roll": 0.0},
    {"id": "loop_apex_inverted", "heading": 180.0, "pitch": 0.0, "roll": 180.0},
)
PRIMARY_PROXY_ID = "loop_apex_inverted"


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
    body_mat = bs.make_material("FlameOrientationBody", (0.56, 0.025, 0.018, 1.0), 0.44, 0.15)
    dark_mat = bs.make_material("FlameOrientationDarkTrim", (0.020, 0.025, 0.034, 1.0), 0.72)
    seat_mat = bs.make_material("FlameOrientationSeat", (0.014, 0.018, 0.024, 1.0), 0.78)
    metal_mat = bs.make_material("FlameOrientationMetal", (0.16, 0.18, 0.21, 1.0), 0.46, 0.34)
    wheel_mat = bs.make_material("FlameOrientationWheel", (0.010, 0.013, 0.018, 1.0), 0.86)
    orange_mat = bs.make_material("FlameOrientationOrange", (0.93, 0.15, 0.016, 1.0), 0.54)
    yellow_mat = bs.make_material("FlameOrientationYellow", (1.00, 0.50, 0.020, 1.0), 0.50)
    badge_mat = bs.make_material("FlameOrientationBadge", (0.80, 0.72, 0.54, 1.0), 0.58)
    return (body_mat, dark_mat, seat_mat, metal_mat, wheel_mat, orange_mat, yellow_mat, badge_mat)


def build_generic_car():
    return v5.build_car(0, 0.0, lead=False, materials=make_materials())


def capture_base_matrices(authored):
    return {obj.name: obj.matrix_world.copy() for obj in authored}


def apply_orientation(authored, base_matrices, heading_deg: float, pitch_deg: float, roll_deg: float):
    """Apply local roll, local pitch, then world yaw around the rail-center anchor.

    Flame's authored forward axis is +Y.  Roll therefore rotates around local +Y;
    right-multiplication keeps that axis local before pitch/yaw transform it into
    the track frame.
    """
    anchor_z = track.RAIL_Z
    to_anchor = Matrix.Translation((0.0, 0.0, anchor_z))
    from_anchor = Matrix.Translation((0.0, 0.0, -anchor_z))
    yaw = Matrix.Rotation(math.radians(heading_deg), 4, "Z")
    pitch = Matrix.Rotation(math.radians(pitch_deg), 4, "X")
    roll = Matrix.Rotation(math.radians(roll_deg), 4, "Y")
    pose = to_anchor @ yaw @ pitch @ roll @ from_anchor
    for obj in authored:
        obj.matrix_world = pose @ base_matrices[obj.name]
    bpy.context.view_layer.update()


def pose_by_id(pose_id: str):
    for pose in REVIEW_POSES:
        if pose["id"] == pose_id:
            return pose
    raise KeyError(pose_id)


def render_pose(scene, authored, profile, output: Path, pose, filename: str):
    return scene_gate.render_proxy(
        scene=scene,
        authored=authored,
        output_path=output / filename,
        profile=profile,
        asset_id=ASSET_ID,
        direction=(
            f"{pose['id']}_h{pose['heading']:+.0f}_p{pose['pitch']:+.0f}_r{pose['roll']:+.0f}"
        ),
    )


def write_orientation_manifest(output: Path):
    payload = {
        "contract": CAR_CONTRACT,
        "assetId": ASSET_ID,
        "styleId": STYLE_ID,
        "trackContract": TRACK_CONTRACT,
        "baseForwardAxis": "+Y",
        "baseUpAxis": "+Z",
        "anchor": [0.0, 0.0, track.RAIL_Z],
        "rotationOrder": "yaw_Z @ pitch_local_X @ roll_local_Y",
        "runtimeInputs": ["headingDegrees", "pitchDegrees", "rollDegrees"],
        "replacesRuntimeAtlas": False,
        "purpose": "Proxy validation before expanding the Flame runtime atlas for inversions.",
        "reviewPoses": list(REVIEW_POSES),
        "primaryProxyPose": PRIMARY_PROXY_ID,
    }
    (output / "orientation_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
    # Calibrate against the vertical case, which is the tallest projected extent.
    calibration_pose = pose_by_id("vertical")
    apply_orientation(authored, base_matrices, calibration_pose["heading"], calibration_pose["pitch"], calibration_pose["roll"])
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.30)
    write_orientation_manifest(output)

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
        # Auxiliary references first.
        for pose in REVIEW_POSES:
            apply_orientation(authored, base_matrices, pose["heading"], pose["pitch"], pose["roll"])
            render_pose(scene, authored, profile, output, pose, f"proxy_{pose['id']}.png")

        primary = pose_by_id(PRIMARY_PROXY_ID)
        apply_orientation(authored, base_matrices, primary["heading"], primary["pitch"], primary["roll"])
        proxy = render_pose(scene, authored, profile, output, primary, "proxy_south.png")
        proxy["pose"] = primary
        proxy["orientationContract"] = CAR_CONTRACT
        proxy["auxiliaryReviewImages"] = [
            "proxy_normal.png", "proxy_vertical.png", "proxy_loop_apex_inverted.png"
        ]
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        raise RuntimeError(
            "CH_COASTER_CAR_ORIENTATION_V2 is proxy-first. Define and review the expanded pose lattice before final bake."
        )


if __name__ == "__main__":
    main()
