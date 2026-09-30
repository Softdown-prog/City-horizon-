"""Guarded CH Blender authoring for roller-coaster corkscrew elements.

This builder now uses CH_COASTER_GEOMETRY_SOLVER_V1: arc-length sampling,
clothoid-style curvature ramps, parallel-transport frames, and independent
track roll. Runtime remains pre-rendered 2D; Blender is authoring only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_coaster_track_guarded as base  # noqa: E402
import build_coaster_banked_guarded as banked  # noqa: E402
import coaster_geometry_solver as geometry  # noqa: E402

ASSET_ID = "ride.coaster.track_v0"
VALID_PIECES = ("corkscrew_left", "corkscrew_right")
CORKSCREW_LENGTH = base.TILE * 5.8
APPROACH_LENGTH = base.TILE * 0.90
HELIX_RADIUS = base.TILE * 0.58
TRANSITION_FRACTION = 0.18
ROLL_RAMP_FRACTION = 0.20
BODY_SAMPLES = 281
APPROACH_SAMPLES = 33
FOOTPRINT = {"widthTiles": 4, "depthTiles": 8}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--piece", choices=VALID_PIECES, required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def handedness(piece: str) -> float:
    return 1.0 if piece == "corkscrew_left" else -1.0


def _shift_sample(sample: geometry.CurveSample, offset: Vector) -> geometry.CurveSample:
    return geometry.CurveSample(
        sample.s,
        sample.position + offset,
        sample.tangent.copy(),
        sample.right.copy(),
        sample.up.copy(),
        sample.curvature,
        sample.curvature_plane_angle,
    )


def sample_centerline(piece: str):
    """Build straight connectors plus one solver-driven corkscrew body."""
    body_length = CORKSCREW_LENGTH - 2.0 * APPROACH_LENGTH
    pitch_per_turn = body_length
    sign = handedness(piece)

    body, solver_meta = geometry.sample_engineering_corkscrew(
        total_length=body_length,
        samples=BODY_SAMPLES,
        helix_radius=HELIX_RADIUS,
        pitch_per_turn=pitch_per_turn,
        handedness=sign,
        base_z=base.RAIL_Z,
        transition_fraction=TRANSITION_FRACTION,
        roll_ramp_fraction=ROLL_RAMP_FRACTION,
    )

    # The solver starts its body centered around Y=0. Add deterministic straight
    # connectors using the exact solved endpoint tangent/frame.
    first = body[0]
    last = body[-1]
    samples = []

    for i in range(APPROACH_SAMPLES):
        u = i / float(APPROACH_SAMPLES - 1)
        distance = APPROACH_LENGTH * (1.0 - u)
        pos = first.position - first.tangent * distance
        samples.append(geometry.CurveSample(
            -distance,
            pos,
            first.tangent.copy(),
            first.right.copy(),
            first.up.copy(),
            0.0,
            first.curvature_plane_angle,
        ))

    # Avoid duplicating the first body sample.
    samples.extend(body[1:])

    base_s = samples[-1].s if samples else body_length
    for i in range(1, APPROACH_SAMPLES):
        u = i / float(APPROACH_SAMPLES - 1)
        distance = APPROACH_LENGTH * u
        pos = last.position + last.tangent * distance
        samples.append(geometry.CurveSample(
            body_length + distance,
            pos,
            last.tangent.copy(),
            last.right.copy(),
            last.up.copy(),
            0.0,
            last.curvature_plane_angle,
        ))

    solver_meta.update({
        "elementLength": CORKSCREW_LENGTH,
        "bodyLength": body_length,
        "approachLength": APPROACH_LENGTH,
        "bodySamples": BODY_SAMPLES,
        "approachSamples": APPROACH_SAMPLES,
    })
    return samples, solver_meta


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    solved, solver_meta = sample_centerline(piece)
    centerline = [sample.position.copy() for sample in solved]
    frames = [(sample.tangent.copy(), sample.right.copy(), sample.up.copy()) for sample in solved]
    left = []
    right_rail = []

    for point, (_tangent, right, _up) in zip(centerline, frames):
        left.append(point - right * (base.GAUGE * 0.5))
        right_rail.append(point + right * (base.GAUGE * 0.5))

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right_rail, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        tangent, right, up = frames[idx]
        p = centerline[idx] - up * 0.11
        authored.append(banked.add_oriented_box(
            f"Tie_{n:03d}",
            p,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat,
            "coaster.tie",
            right,
            tangent,
            up,
        ))

    last = len(centerline) - 1
    support_indices = sorted(set((
        0,
        len(centerline) // 10,
        len(centerline) // 5,
        (len(centerline) * 4) // 5,
        (len(centerline) * 9) // 10,
        last,
    )))
    for n, idx in enumerate(support_indices):
        base.build_support_frame(
            authored,
            f"Support_{n:03d}",
            centerline[idx],
            base.tangent(centerline, idx),
            support_mat,
        )

    return authored, centerline, solved, solver_meta


def write_metadata(output: Path, piece: str, centerline, solved, solver_meta):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "corkscrewContract": "CH_COASTER_CORKSCREW_V0",
        "profile": "single_inversion_v10_geometry_solver_v1",
        "geometrySolver": solver_meta,
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "length": CORKSCREW_LENGTH,
        "helixRadius": HELIX_RADIUS,
        "transitionFraction": TRANSITION_FRACTION,
        "rollRampFraction": ROLL_RAMP_FRACTION,
        "curvatureSamples": [round(sample.curvature, 8) for sample in solved],
        "centerline": [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] for p in centerline],
        "entry": base.payload_endpoint(centerline, 0),
        "exit": base.payload_endpoint(centerline, -1),
    }
    (output / "track_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_studio_metadata(output: Path, args):
    payload = {
        "contract": "CH_STUDIO_METADATA_V1",
        "assetId": f"{ASSET_ID}.{args.piece}",
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": str(args.studio_preset),
        "qualityStage": args.stage,
        "directions": [direction["id"] for direction in bs.DIRECTIONS],
        "runtimeRepresentation": "2D_RGBA_pre_rendered",
    }
    (output / "studio_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    studio = bs.load_json(args.studio_preset)
    profile = scene_gate.load_profile(args.preflight_profile)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    bs.clear_scene()
    scene = bs.configure_scene(studio, (512, 512), str(output))
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"

    authored, centerline, solved, solver_meta = build_piece(args.piece)
    root = bs.create_asset_root(authored)
    root["assetId"] = f"{ASSET_ID}.{args.piece}"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = "CH_COASTER_TRACK_V0"
    root["corkscrewContract"] = "CH_COASTER_CORKSCREW_V0"
    root["geometrySolverContract"] = "CH_COASTER_GEOMETRY_SOLVER_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, args.piece, centerline, solved, solver_meta)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=f"{ASSET_ID}.{args.piece}",
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / "proxy_south.png",
            profile=profile,
            asset_id=f"{ASSET_ID}.{args.piece}",
            direction="south",
        )
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
            raise ValueError("The final bake requires the reviewed SOUTH proxy SHA-256")
        (output / "proxy_approval.json").write_text(json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": f"{ASSET_ID}.{args.piece}",
            "reviewed": True,
            "proxySha256": args.approval_proxy_sha,
        }, indent=2), encoding="utf-8")
        write_studio_metadata(output, args)
        for direction in bs.DIRECTIONS:
            bs.set_direction(root, direction)
            scene_gate.render_proxy(
                scene=scene,
                authored=authored,
                output_path=output / f"track_{direction['id']}.png",
                profile=profile,
                asset_id=f"{ASSET_ID}.{args.piece}",
                direction=direction["id"],
            )


if __name__ == "__main__":
    main()
