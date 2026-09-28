"""Guarded CH Blender prototype for modular roller-coaster track pieces.

CH_COASTER_TRACK_V0 separates logical centerline data from rendered geometry.
The runtime remains 2D; Blender is only the deterministic authoring/render tool.
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

ASSET_ID = "ride.coaster.track_v0"
TILE = 3.0
HEIGHT_STEP = 0.75
GAUGE = 0.95
RAIL_RADIUS = 0.06
RAIL_Z = 0.48
TIE_SPACING = 0.36
TIE_HALF_WIDTH = 0.62
TIE_HALF_DEPTH = 0.055
TIE_HALF_HEIGHT = 0.04
SUPPORT_LATERAL = 0.42
SUPPORT_HALF_WIDTH = 0.055
SUPPORT_BEAM_Z_OFFSET = 0.22
VALID_PIECES = ("straight", "curve_left", "curve_right", "slope_up", "slope_down")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--piece", choices=VALID_PIECES, default="straight")
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def sample_centerline(piece: str, samples: int = 33):
    half = TILE * 0.5
    points = []
    for i in range(samples):
        t = i / (samples - 1)
        if piece == "straight":
            p = Vector((0.0, -half + TILE * t, RAIL_Z))
        elif piece == "slope_up":
            p = Vector((0.0, -half + TILE * t, RAIL_Z + HEIGHT_STEP * t))
        elif piece == "slope_down":
            p = Vector((0.0, -half + TILE * t, RAIL_Z + HEIGHT_STEP * (1.0 - t)))
        else:
            # Quarter circle. South entry is tangent north; exits west/east.
            radius = half
            if piece == "curve_left":
                center = Vector((-half, -half, RAIL_Z))
                angle = -0.0 + (math.pi * 0.5) * t
                p = center + Vector((radius * math.cos(angle), radius * math.sin(angle), 0.0))
            else:
                center = Vector((half, -half, RAIL_Z))
                angle = math.pi - (math.pi * 0.5) * t
                p = center + Vector((radius * math.cos(angle), radius * math.sin(angle), 0.0))
        points.append(p)
    return points


def tangent(points, index):
    if index == 0:
        return (points[1] - points[0]).normalized()
    if index == len(points) - 1:
        return (points[-1] - points[-2]).normalized()
    return (points[index + 1] - points[index - 1]).normalized()


def lateral_from_tangent(t):
    lateral = Vector((-t.y, t.x, 0.0))
    return lateral.normalized() if lateral.length > 1e-6 else Vector((1.0, 0.0, 0.0))


def make_curve_tube(name, points, material, radius, role):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, xyz in zip(spline.points, points):
        point.co = (*xyz, 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.object
    scene_gate.tag(obj, role)
    return obj


def add_box(name, location, scale, material, role, yaw=0.0, pitch=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=(pitch, 0.0, yaw))
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(material)
    scene_gate.tag(obj, role)
    return obj


def build_support_frame(authored, name_prefix, point, track_tangent, material):
    lateral = lateral_from_tangent(track_tangent)
    yaw = math.atan2(track_tangent.y, track_tangent.x) - math.pi * 0.5
    beam_z = max(0.18, point.z - SUPPORT_BEAM_Z_OFFSET)

    beam = add_box(
        f"{name_prefix}_Beam",
        (point.x, point.y, beam_z),
        (TIE_HALF_WIDTH * 0.92, SUPPORT_HALF_WIDTH, 0.045),
        material,
        "coaster.support.beam",
        yaw=yaw,
    )
    authored.append(beam)

    for side, sign in (("L", 1.0), ("R", -1.0)):
        foot = point + lateral * (SUPPORT_LATERAL * sign)
        post_height = max(0.12, beam_z)
        post = add_box(
            f"{name_prefix}_Post_{side}",
            (foot.x, foot.y, post_height * 0.5),
            (SUPPORT_HALF_WIDTH, SUPPORT_HALF_WIDTH, post_height * 0.5),
            material,
            "coaster.support.post",
        )
        authored.append(post)


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = sample_centerline(piece)
    left = []
    right = []
    for i, p in enumerate(centerline):
        lat = lateral_from_tangent(tangent(centerline, i))
        left.append(p + lat * (GAUGE * 0.5))
        right.append(p - lat * (GAUGE * 0.5))

    authored = [
        make_curve_tube("RailLeft", left, steel, RAIL_RADIUS, "coaster.rail.left"),
        make_curve_tube("RailRight", right, steel, RAIL_RADIUS, "coaster.rail.right"),
    ]

    # Ties and supports are sampled by arc length approximately; V0 intentionally
    # favors deterministic simple geometry over perfect engineering detail.
    cumulative = [0.0]
    for a, b in zip(centerline, centerline[1:]):
        cumulative.append(cumulative[-1] + (b - a).length)
    total = cumulative[-1]
    tie_count = max(2, int(total / TIE_SPACING) + 1)
    for n in range(tie_count):
        target = total * n / (tie_count - 1)
        idx = min(range(len(cumulative)), key=lambda i: abs(cumulative[i] - target))
        p = centerline[idx]
        t = tangent(centerline, idx)
        yaw = math.atan2(t.y, t.x) - math.pi * 0.5
        pitch = math.atan2(t.z, math.hypot(t.x, t.y))
        tie = add_box(
            f"Tie_{n:02d}",
            (p.x, p.y, p.z - 0.11),
            (TIE_HALF_WIDTH, TIE_HALF_DEPTH, TIE_HALF_HEIGHT),
            ties_mat,
            "coaster.tie",
            yaw=yaw,
            pitch=pitch,
        )
        authored.append(tie)

    support_indices = sorted(set((0, len(centerline) // 2, len(centerline) - 1)))
    for n, idx in enumerate(support_indices):
        build_support_frame(
            authored,
            f"Support_{n:02d}",
            centerline[idx],
            tangent(centerline, idx),
            support_mat,
        )

    return authored, centerline


def write_metadata(output: Path, piece: str, centerline):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "blenderUnitsPerTile": TILE,
        "heightStep": HEIGHT_STEP,
        "centerline": [[round(p.x, 6), round(p.y, 6), round(p.z, 6)] for p in centerline],
        "entry": payload_endpoint(centerline, 0),
        "exit": payload_endpoint(centerline, -1),
    }
    (output / "track_metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def payload_endpoint(points, index):
    actual = index if index >= 0 else len(points) - 1
    t = tangent(points, actual)
    p = points[actual]
    return {
        "position": [round(p.x, 6), round(p.y, 6), round(p.z, 6)],
        "tangent": [round(t.x, 6), round(t.y, 6), round(t.z, 6)],
    }


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
    root["trackContract"] = "CH_COASTER_TRACK_V0"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"
    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, args.piece, centerline)
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
