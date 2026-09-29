"""Guarded CH Blender prototype for roller-coaster corkscrew elements.

CH_COASTER_CORKSCREW_V0 reuses the existing CH coaster rail/tie/support
vocabulary while adding a deterministic 360-degree roll around a smooth 3D
centerline. Runtime remains pre-rendered 2D; Blender is authoring only.
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

ASSET_ID = "ride.coaster.track_v0"
VALID_PIECES = ("corkscrew_left", "corkscrew_right")
CORKSCREW_LENGTH = base.TILE * 3.0
CORKSCREW_RADIUS = base.TILE * 0.65
ROLL_DEGREES = 360.0
FOOTPRINT = {"widthTiles": 3, "depthTiles": 4}


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


def smootherstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def handedness(piece: str) -> float:
    return 1.0 if piece == "corkscrew_left" else -1.0


def sample_centerline(piece: str, samples: int = 193):
    """Sample a forward-moving corkscrew with flat/tangent-safe connectors.

    The transverse excursion fades to zero at both connectors.  This keeps the
    entry and exit centered and tangent to +Y while the middle of the element
    traces a full spatial roll around the forward axis.
    """
    sign = handedness(piece)
    points = []
    for i in range(samples):
        t = i / (samples - 1)
        phase = sign * math.tau * t
        envelope = math.sin(math.pi * t) ** 2
        y = -CORKSCREW_LENGTH * 0.5 + CORKSCREW_LENGTH * t
        x = CORKSCREW_RADIUS * envelope * math.sin(phase)
        z = base.RAIL_Z + CORKSCREW_RADIUS * envelope * (1.0 - math.cos(phase))
        points.append(Vector((x, y, z)))
    return points


def roll_angle(piece: str, t: float) -> float:
    # A full 360-degree roll with zero angular velocity at both connectors.
    return math.radians(ROLL_DEGREES * handedness(piece) * smootherstep(t))


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = sample_centerline(piece)
    last = len(centerline) - 1
    frames = []
    left = []
    right_rail = []

    for i, point in enumerate(centerline):
        t = i / last
        roll = roll_angle(piece, t)
        tangent, right, up = banked.track_frame(centerline, i, roll)
        frames.append((tangent, right, up, roll))
        left.append(point - right * (base.GAUGE * 0.5))
        right_rail.append(point + right * (base.GAUGE * 0.5))

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right_rail, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        tangent, right, up, _ = frames[idx]
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

    # Keep supports world-vertical and out of the central inversion envelope.
    support_indices = sorted(set((0, last // 4, (last * 3) // 4, last)))
    for n, idx in enumerate(support_indices):
        base.build_support_frame(
            authored,
            f"Support_{n:03d}",
            centerline[idx],
            base.tangent(centerline, idx),
            support_mat,
        )

    return authored, centerline, frames


def write_metadata(output: Path, piece: str, centerline, frames):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "corkscrewContract": "CH_COASTER_CORKSCREW_V0",
        "profile": "single_roll_v0",
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "length": CORKSCREW_LENGTH,
        "radius": CORKSCREW_RADIUS,
        "rollDegrees": ROLL_DEGREES,
        "rollSamplesDegrees": [round(math.degrees(frame[3]), 6) for frame in frames],
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

    authored, centerline, frames = build_piece(args.piece)
    root = bs.create_asset_root(authored)
    root["assetId"] = f"{ASSET_ID}.{args.piece}"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = "CH_COASTER_TRACK_V0"
    root["corkscrewContract"] = "CH_COASTER_CORKSCREW_V0"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, args.piece, centerline, frames)
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
