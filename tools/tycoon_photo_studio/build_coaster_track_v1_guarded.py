"""Production-scope simple coaster builder for City Horizon.

CH_COASTER_TRACK_V1 intentionally excludes inversions. It reuses only the
validated generic rail/tie/support primitives from build_coaster_track_guarded
and adds two deterministic airtime-hill centerlines.
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

ASSET_ID = "ride.coaster.track_v1"
TRACK_CONTRACT = "CH_COASTER_TRACK_V1"

VALID_PIECES = (
    "straight",
    "curve_left",
    "curve_right",
    "slope_up",
    "slope_down",
    "flat_to_slope_up",
    "slope_up_to_flat",
    "flat_to_slope_down",
    "slope_down_to_flat",
    "airtime_hill_small",
    "airtime_hill_large",
)

HILL_SPECS = {
    "airtime_hill_small": {
        "length_tiles": 2.0,
        "peak_height": base.HEIGHT_STEP * 2.0,
        "samples": 81,
        "footprint": {"widthTiles": 1, "depthTiles": 2},
    },
    "airtime_hill_large": {
        "length_tiles": 3.0,
        "peak_height": base.HEIGHT_STEP * 4.0,
        "samples": 121,
        "footprint": {"widthTiles": 1, "depthTiles": 3},
    },
}


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


def sample_airtime_hill(piece: str):
    spec = HILL_SPECS[piece]
    length = base.TILE * spec["length_tiles"]
    half = 0.5 * length
    points = []
    for i in range(spec["samples"]):
        u = i / float(spec["samples"] - 1)
        y = -half + length * u
        # 0 at both connectors, smooth horizontal tangent at both ends, one peak.
        z = base.RAIL_Z + spec["peak_height"] * 0.5 * (1.0 - math.cos(math.tau * u))
        points.append(Vector((0.0, y, z)))
    return points


def sample_centerline(piece: str):
    if piece in HILL_SPECS:
        return sample_airtime_hill(piece)
    return base.sample_centerline(piece)


def piece_footprint(piece: str):
    if piece in HILL_SPECS:
        return HILL_SPECS[piece]["footprint"]
    return {"widthTiles": 1, "depthTiles": 1}


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = sample_centerline(piece)
    left = []
    right = []
    for i, p in enumerate(centerline):
        lat = base.lateral_from_tangent(base.tangent(centerline, i))
        left.append(p + lat * (base.GAUGE * 0.5))
        right.append(p - lat * (base.GAUGE * 0.5))

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        p = centerline[idx]
        t = base.tangent(centerline, idx)
        yaw = math.atan2(t.y, t.x) - math.pi * 0.5
        pitch = math.atan2(t.z, math.hypot(t.x, t.y))
        tie = base.add_box(
            f"Tie_{n:03d}",
            (p.x, p.y, p.z - 0.11),
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat,
            "coaster.tie",
            yaw=yaw,
            pitch=pitch,
        )
        authored.append(tie)

    # Support frequency follows track length. Hills receive more intermediate
    # frames so the elevated crest does not look unsupported.
    support_spacing = base.TILE * (0.65 if piece in HILL_SPECS else 0.95)
    _, _, support_indices = base.sampled_indices_by_distance(centerline, support_spacing)
    for n, idx in enumerate(support_indices):
        base.build_support_frame(
            authored,
            f"Support_{n:03d}",
            centerline[idx],
            base.tangent(centerline, idx),
            support_mat,
        )

    return authored, centerline


def write_metadata(output: Path, piece: str, centerline):
    payload = {
        "contract": TRACK_CONTRACT,
        "assetId": ASSET_ID,
        "piece": piece,
        "productionScope": "simple_no_inversions",
        "blenderUnitsPerTile": base.TILE,
        "heightStep": base.HEIGHT_STEP,
        "footprint": piece_footprint(piece),
        "centerline": [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] for p in centerline],
        "entry": base.payload_endpoint(centerline, 0),
        "exit": base.payload_endpoint(centerline, -1),
        "inversion": False,
    }
    if piece in HILL_SPECS:
        spec = HILL_SPECS[piece]
        payload["hill"] = {
            "profile": "cosine_ease",
            "lengthTiles": spec["length_tiles"],
            "peakHeight": spec["peak_height"],
            "entryExitHeightMatched": True,
            "entryExitTangentHorizontal": True,
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

    authored, centerline = build_piece(args.piece)
    root = bs.create_asset_root(authored)
    root["assetId"] = f"{ASSET_ID}.{args.piece}"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = TRACK_CONTRACT
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    root["inversion"] = False

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, args.piece, centerline)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=piece_footprint(args.piece),
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
