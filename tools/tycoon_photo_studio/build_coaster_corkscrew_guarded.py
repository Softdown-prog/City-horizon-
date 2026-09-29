"""Guarded CH Blender prototype for roller-coaster corkscrew elements.

CH_COASTER_CORKSCREW_V0 reuses the existing CH coaster rail/tie/support
vocabulary while defining one deterministic corkscrew inversion with flat
approach/exit connectors. Runtime remains pre-rendered 2D; Blender is authoring
only.
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
CORKSCREW_LENGTH = base.TILE * 5.6
HORIZONTAL_RADIUS = base.TILE * 0.58
VERTICAL_RADIUS = base.TILE * 0.32
APPROACH_LENGTH = base.TILE * 1.10
ROLL_DEGREES = 360.0
PHASE_RAMP = 0.24
LONGITUDINAL_MID_BOOST = 0.45
FOOTPRINT = {"widthTiles": 3, "depthTiles": 8}


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


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def handedness(piece: str) -> float:
    return 1.0 if piece == "corkscrew_left" else -1.0


def phase_progress(t: float) -> float:
    """Nearly constant-speed phase with longer eased connector ramps."""
    t = max(0.0, min(1.0, t))
    r = PHASE_RAMP
    total = 1.0 - r
    if t < r:
        u = t / r
        return (r * (u ** 3 - 0.5 * u ** 4)) / total
    if t > 1.0 - r:
        return 1.0 - phase_progress(1.0 - t)
    return (0.5 * r + (t - r)) / total


def longitudinal_progress(t: float) -> float:
    """Advance farther along the track during the middle of the inversion.

    Endpoints remain exact while longitudinal speed is reduced near the two
    connector shoulders and increased around t=0.5. This prevents an isometric
    camera from compressing the middle of the helix into a narrow vertical wall.
    """
    t = max(0.0, min(1.0, t))
    k = LONGITUDINAL_MID_BOOST
    return t - (k / math.tau) * math.sin(math.tau * t)


def inversion_phase(piece: str, t: float) -> float:
    return handedness(piece) * math.tau * phase_progress(t)


def sample_centerline(piece: str, approach_samples: int = 37, body_samples: int = 241):
    """Build a low, stretched corkscrew with a longitudinally opened center.

    V7 keeps V6 height, lateral radius and total footprint, but warps body
    progress along Y so the middle of the 360-degree inversion advances farther
    longitudinally. The shoulders advance more gently while the center gets more
    front/back separation, reducing the vertical-wall read in isometric views.
    """
    points = []
    body_length = CORKSCREW_LENGTH - 2.0 * APPROACH_LENGTH
    body_start_y = -body_length * 0.5
    body_end_y = body_length * 0.5
    sign = handedness(piece)

    for i in range(approach_samples):
        t = i / (approach_samples - 1)
        y = -CORKSCREW_LENGTH * 0.5 + APPROACH_LENGTH * t
        points.append(Vector((0.0, y, base.RAIL_Z)))

    for i in range(1, body_samples):
        t = i / (body_samples - 1)
        phase = abs(inversion_phase(piece, t))
        y_t = longitudinal_progress(t)
        y = body_start_y + body_length * y_t
        x = sign * HORIZONTAL_RADIUS * math.sin(phase)
        z = base.RAIL_Z + VERTICAL_RADIUS * (1.0 - math.cos(phase))
        points.append(Vector((x, y, z)))

    for i in range(1, approach_samples):
        t = i / (approach_samples - 1)
        y = body_end_y + APPROACH_LENGTH * t
        points.append(Vector((0.0, y, base.RAIL_Z)))

    return points


def phase_for_centerline_index(piece: str, index: int) -> float:
    approach_samples = 37
    body_samples = 241
    body_first = approach_samples - 1
    body_last = body_first + body_samples - 1
    if index <= body_first:
        return 0.0
    if index >= body_last:
        return handedness(piece) * math.tau
    t = (index - body_first) / (body_samples - 1)
    return inversion_phase(piece, t)


def elliptical_track_frame(points, index: int, point: Vector):
    """Orient the deck from the elliptical helix geometry itself.

    The inward ellipse normal becomes track up. This keeps the rails parallel,
    naturally turns the deck upside-down once, and avoids reintroducing an
    independent 360-degree roll on top of the centerline geometry.
    """
    tangent = base.tangent(points, index)
    axis_z = base.RAIL_Z + VERTICAL_RADIUS
    x = point.x
    z = point.z - axis_z
    inward = Vector((
        -x / (HORIZONTAL_RADIUS * HORIZONTAL_RADIUS),
        0.0,
        -z / (VERTICAL_RADIUS * VERTICAL_RADIUS),
    ))
    up = inward - tangent * inward.dot(tangent)
    if up.length < 1e-6:
        up = Vector((0.0, 0.0, 1.0)) - tangent * tangent.z
    up.normalize()
    right = tangent.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(tangent).normalized()
    return tangent, right, up


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    centerline = sample_centerline(piece)
    frames = []
    left = []
    right_rail = []

    for i, point in enumerate(centerline):
        phase = phase_for_centerline_index(piece, i)
        tangent, right, up = elliptical_track_frame(centerline, i, point)
        frames.append((tangent, right, up, phase))
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

    last = len(centerline) - 1
    support_indices = sorted(set((
        0,
        len(centerline) // 8,
        len(centerline) // 4,
        (len(centerline) * 3) // 4,
        (len(centerline) * 7) // 8,
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

    return authored, centerline, frames


def write_metadata(output: Path, piece: str, centerline, frames):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "corkscrewContract": "CH_COASTER_CORKSCREW_V0",
        "profile": "single_inversion_v6_longitudinal_mid_boost",
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "length": CORKSCREW_LENGTH,
        "horizontalRadius": HORIZONTAL_RADIUS,
        "verticalRadius": VERTICAL_RADIUS,
        "approachLength": APPROACH_LENGTH,
        "rollDegrees": ROLL_DEGREES,
        "phaseRamp": PHASE_RAMP,
        "longitudinalMidBoost": LONGITUDINAL_MID_BOOST,
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
