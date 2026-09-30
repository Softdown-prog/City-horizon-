"""Guarded visual fixture for exact analytic coaster helix geometry.

This is not a production track piece. It exists to prove that
CH_COASTER_GEOMETRY_SOLVER_V1 reproduces a known circular helix exactly before
transition/clothoid logic is allowed back into corkscrew authoring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_coaster_track_guarded as base  # noqa: E402
import build_coaster_banked_guarded as banked  # noqa: E402
import coaster_geometry_solver as geometry  # noqa: E402

ASSET_ID = "validation.coaster.analytic_helix_v1"
RADIUS = base.TILE * 0.75
PITCH_PER_TURN = base.TILE * 3.2
TURNS = 1.0
SAMPLES = 241
FOOTPRINT = {"widthTiles": 3, "depthTiles": 5}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def build_reference():
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    samples, metadata = geometry.sample_analytic_helix_reference(
        radius=RADIUS,
        pitch_per_turn=PITCH_PER_TURN,
        turns=TURNS,
        samples=SAMPLES,
        handedness=1.0,
        base_z=base.RAIL_Z,
    )
    centerline = [s.position.copy() for s in samples]
    left = [s.position - s.right * (base.GAUGE * 0.5) for s in samples]
    right = [s.position + s.right * (base.GAUGE * 0.5) for s in samples]
    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]
    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        sample = samples[idx]
        authored.append(banked.add_oriented_box(
            f"Tie_{n:03d}", sample.position - sample.up * 0.11,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat, "coaster.tie", sample.right, sample.tangent, sample.up,
        ))
    return authored, centerline, metadata


def write_metadata(output: Path, centerline, metadata):
    payload = {
        "contract": "CH_COASTER_GEOMETRY_REFERENCE_V1",
        "assetId": ASSET_ID,
        "geometrySolver": metadata,
        "centerline": [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] for p in centerline],
        "entry": base.payload_endpoint(centerline, 0),
        "exit": base.payload_endpoint(centerline, -1),
    }
    (output / "track_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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

    authored, centerline, metadata = build_reference()
    root = bs.create_asset_root(authored)
    root["assetId"] = ASSET_ID
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["geometrySolverContract"] = "CH_COASTER_GEOMETRY_SOLVER_V1"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, centerline, metadata)
    report = scene_gate.run_preflight(
        scene=scene, authored=authored, footprint=FOOTPRINT, profile=profile,
        asset_id=ASSET_ID, report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene, authored=authored, output_path=output / "proxy_south.png",
            profile=profile, asset_id=ASSET_ID, direction="south",
        )
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        raise ValueError("analytic helix reference is validation-only; final bake is forbidden")


if __name__ == "__main__":
    main()
