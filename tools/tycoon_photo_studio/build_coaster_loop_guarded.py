"""Guarded CH Blender prototype for a vertical roller-coaster loop.

CH_COASTER_LOOP_V0 reuses the existing CH coaster rail/tie/support vocabulary,
while defining a deterministic vertical-plane centerline with flat approach and
exit connectors. Runtime remains pre-rendered 2D.
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
PIECE = "vertical_loop"
LOOP_RADIUS = base.TILE * 1.35
APPROACH_LENGTH = base.TILE * 0.85
FOOTPRINT = {"widthTiles": 3, "depthTiles": 4}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--piece", choices=(PIECE,), default=PIECE)
    parser.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    parser.add_argument("--preflight-profile", default=None)
    parser.add_argument("--approval-proxy-sha", default=None)
    return parser.parse_args(argv)


def sample_centerline(approach_samples: int = 25, loop_samples: int = 129):
    points = []

    # Flat approach into the bottom of the loop.
    for i in range(approach_samples):
        t = i / (approach_samples - 1)
        y = -APPROACH_LENGTH + APPROACH_LENGTH * t
        points.append(Vector((0.0, y, base.RAIL_Z)))

    # Vertical loop in the Y/Z plane. theta=0 starts at the bottom heading +Y.
    for i in range(1, loop_samples):
        t = i / (loop_samples - 1)
        theta = math.tau * t
        y = LOOP_RADIUS * math.sin(theta)
        z = base.RAIL_Z + LOOP_RADIUS * (1.0 - math.cos(theta))
        points.append(Vector((0.0, y, z)))

    # Flat exit continues forward from the same bottom tangent.
    for i in range(1, approach_samples):
        t = i / (approach_samples - 1)
        y = APPROACH_LENGTH * t
        points.append(Vector((0.0, y, base.RAIL_Z)))

    return points


def frame(points, index: int):
    tangent = base.tangent(points, index)
    # The loop lives in Y/Z, so a fixed X lateral axis prevents frame flipping
    # while tangent becomes vertical at the loop sides.
    right = Vector((1.0, 0.0, 0.0))
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


def build_piece():
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = sample_centerline()
    left = []
    right_rail = []
    frames = []

    for i, p in enumerate(centerline):
        tangent, right, up = frame(centerline, i)
        frames.append((tangent, right, up))
        left.append(p - right * (base.GAUGE * 0.5))
        right_rail.append(p + right * (base.GAUGE * 0.5))

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right_rail, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        tangent, right, up = frames[idx]
        p = centerline[idx] - up * 0.11
        authored.append(add_oriented_box(
            f"Tie_{n:03d}", p,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat, "coaster.tie", right, tangent, up,
        ))

    # V0 support proof: approach/exit frames plus two tall side supports.
    support_indices = sorted(set((0, len(centerline) - 1)))
    for n, idx in enumerate(support_indices):
        base.build_support_frame(
            authored,
            f"Support_Base_{n:03d}",
            centerline[idx],
            base.tangent(centerline, idx),
            support_mat,
        )

    side_points = [
        Vector((-base.GAUGE * 0.72, 0.0, LOOP_RADIUS)),
        Vector((base.GAUGE * 0.72, 0.0, LOOP_RADIUS)),
    ]
    for n, p in enumerate(side_points):
        height = max(0.2, p.z)
        authored.append(base.add_box(
            f"LoopSideSupport_{n:02d}",
            (p.x, p.y, height * 0.5),
            (base.SUPPORT_HALF_WIDTH * 1.25, base.SUPPORT_HALF_WIDTH * 1.25, height * 0.5),
            support_mat,
            "coaster.support.post",
        ))

    return authored, centerline


def write_metadata(output: Path, centerline):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": PIECE,
        "loopContract": "CH_COASTER_LOOP_V0",
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "radius": LOOP_RADIUS,
        "approachLength": APPROACH_LENGTH,
        "height": LOOP_RADIUS * 2.0,
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

    authored, centerline = build_piece()
    root = bs.create_asset_root(authored)
    root["assetId"] = f"{ASSET_ID}.{PIECE}"
    root["cameraContract"] = "CH_CAMERA_V1"
    root["studioPreset"] = "CH_TYCOON_STUDIO_V1"
    root["trackContract"] = "CH_COASTER_TRACK_V0"
    root["loopContract"] = "CH_COASTER_LOOP_V0"
    root["qualityGateContract"] = "CH_SCENE_PREFLIGHT_V1"

    bs.calibrate_ortho_scale(scene, authored, safety_margin=0.14)
    bs.set_direction(root, bs.DIRECTIONS[0])
    bpy.context.view_layer.update()

    write_metadata(output, centerline)
    report = scene_gate.run_preflight(
        scene=scene,
        authored=authored,
        footprint=FOOTPRINT,
        profile=profile,
        asset_id=f"{ASSET_ID}.{PIECE}",
        report_path=output / "preflight_report.json",
    )
    scene_gate.require_pass(report)

    if args.stage == "proxy":
        proxy = scene_gate.render_proxy(
            scene=scene,
            authored=authored,
            output_path=output / "proxy_south.png",
            profile=profile,
            asset_id=f"{ASSET_ID}.{PIECE}",
            direction="south",
        )
        (output / "proxy_report.json").write_text(json.dumps(proxy, indent=2), encoding="utf-8")
    elif args.stage == "final":
        if not args.approval_proxy_sha or len(args.approval_proxy_sha) != 64:
            raise ValueError("The final bake requires the reviewed SOUTH proxy SHA-256")
        (output / "proxy_approval.json").write_text(json.dumps({
            "contract": "CH_PROXY_APPROVAL_V1",
            "assetId": f"{ASSET_ID}.{PIECE}",
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
                asset_id=f"{ASSET_ID}.{PIECE}",
                direction=direction["id"],
            )


if __name__ == "__main__":
    main()
