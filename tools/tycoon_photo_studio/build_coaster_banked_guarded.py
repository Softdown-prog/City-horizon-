"""Guarded CH Blender prototype for banked roller-coaster curve pieces.

Builds on CH_COASTER_TRACK_V0 centerline geometry while adding a smooth roll
profile around the track tangent. Runtime remains pre-rendered 2D.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "tools" / "ch_blender"))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402
import build_coaster_track_guarded as base  # noqa: E402

ASSET_ID = "ride.coaster.track_v0"
VALID_PIECES = ("banked_curve_left", "banked_curve_right")
MAX_BANK_DEG = 24.0


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


def centerline_for(piece: str, samples: int = 49):
    mapped = "curve_left" if piece == "banked_curve_left" else "curve_right"
    return base.sample_centerline(mapped, samples=samples)


def bank_angle(piece: str, t: float) -> float:
    # Zero roll at both connectors, peak roll at curve midpoint.
    # Left curves raise the outer/right rail; right curves mirror that handedness.
    sign = 1.0 if piece == "banked_curve_left" else -1.0
    envelope = math.sin(math.pi * t)
    return math.radians(MAX_BANK_DEG) * sign * envelope


def track_frame(points, index: int, bank_rad: float):
    tangent = base.tangent(points, index)
    horizontal_right = Vector((tangent.y, -tangent.x, 0.0))
    if horizontal_right.length < 1e-6:
        horizontal_right = Vector((1.0, 0.0, 0.0))
    horizontal_right.normalize()

    natural_up = horizontal_right.cross(tangent).normalized()
    right = horizontal_right * math.cos(bank_rad) + natural_up * math.sin(bank_rad)
    right.normalize()
    up = right.cross(tangent).normalized()
    return tangent, right, up


def add_oriented_box(name, location, scale, material, role, right, forward, up):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    rotation = Matrix((right, forward, up)).transposed()
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = rotation.to_quaternion()
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = centerline_for(piece)
    last = len(centerline) - 1
    left = []
    right_rail = []
    frames = []

    for i, point in enumerate(centerline):
        normalized = i / last
        bank = bank_angle(piece, normalized)
        tangent, right, up = track_frame(centerline, i, bank)
        frames.append((tangent, right, up, bank))
        left.append(point - right * (base.GAUGE * 0.5))
        right_rail.append(point + right * (base.GAUGE * 0.5))

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right_rail, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        tangent, right, up, _ = frames[idx]
        point = centerline[idx] - up * 0.11
        tie = add_oriented_box(
            f"Tie_{n:03d}",
            point,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat,
            "coaster.tie",
            right,
            tangent,
            up,
        )
        authored.append(tie)

    # Supports stay world-vertical in V0; banking affects the track deck, not posts.
    support_indices = sorted(set((0, len(centerline) // 2, len(centerline) - 1)))
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
    bank_samples = [round(math.degrees(frame[3]), 6) for frame in frames]
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "blenderUnitsPerTile": base.TILE,
        "footprint": {"widthTiles": 1, "depthTiles": 1},
        "maxBankDegrees": MAX_BANK_DEG,
        "bankDegrees": bank_samples,
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

    authored, centerline, frames = build_piece(args.piece)
    root = bs.create_asset_root(authored)
    root["assetId"] = f"{ASSET_ID}.{args.piece}"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = "CH_COASTER_TRACK_V0"
    root["bankingContract"] = "CH_COASTER_BANK_V0"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, args.piece, centerline, frames)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint={"widthTiles": 1, "depthTiles": 1},
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
