"""V15 corkscrew: elliptic helical trajectory + rotation-minimizing frames.

This builder intentionally does not import any previous corkscrew recipe.  The
centerline is a true one-turn elliptic helix around the longitudinal +Y axis.
Track orientation is propagated with a Bishop/parallel-transport frame and a
single explicit 0..2*pi roll around the local tangent, eliminating world-UP
singularities at steep/vertical parts of the element.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

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

# Deliberately new calibration for the RMF architecture.  Radius X controls the
# lateral width, radius Z the inversion height, pitch the forward travel.
RADIUS_X = base.TILE * 0.72
RADIUS_Z = base.TILE * 0.92
PITCH = base.TILE * 3.60
TURNS = 1.0
ROLL_TURNS = 1.0
PHASE_DEG = 0.0
TRANSITION_LENGTH = base.TILE * 1.45
STRAIGHT_LENGTH = base.TILE * 0.80
CORE_SAMPLES = 321
TRANSITION_SAMPLES = 73
STRAIGHT_SAMPLES = 25
FOOTPRINT = {"widthTiles": 5, "depthTiles": 9}


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


def hermite_point_tangent(p0: Vector, p1: Vector, t0: Vector, t1: Vector, u: float, scale: float):
    u2 = u * u
    u3 = u2 * u
    h00 = 2.0 * u3 - 3.0 * u2 + 1.0
    h10 = u3 - 2.0 * u2 + u
    h01 = -2.0 * u3 + 3.0 * u2
    h11 = u3 - u2
    m0 = t0.normalized() * scale
    m1 = t1.normalized() * scale
    point = p0 * h00 + m0 * h10 + p1 * h01 + m1 * h11

    dh00 = 6.0 * u2 - 6.0 * u
    dh10 = 3.0 * u2 - 4.0 * u + 1.0
    dh01 = -6.0 * u2 + 6.0 * u
    dh11 = 3.0 * u2 - 2.0 * u
    deriv = p0 * dh00 + m0 * dh10 + p1 * dh01 + m1 * dh11
    if deriv.length < 1.0e-8:
        deriv = t0.lerp(t1, u)
    return point, deriv.normalized()


def init_rmf(tangent: Vector):
    tangent = tangent.normalized()
    preferred = Vector((0.0, 0.0, 1.0))
    up = preferred - tangent * preferred.dot(tangent)
    if up.length < 1.0e-8:
        preferred = Vector((1.0, 0.0, 0.0))
        up = preferred - tangent * preferred.dot(tangent)
    up.normalize()
    right = tangent.cross(up).normalized()
    up = right.cross(tangent).normalized()
    return right, up


def reframe_rmf(points, tangents, core_begin: int, core_end: int, sign: float):
    """Parallel transport over the entire piece, then add one tangent roll."""
    if len(points) != len(tangents) or not points:
        raise ValueError("RMF requires matching non-empty points/tangents")

    right, up = init_rmf(tangents[0])
    prev_tangent = tangents[0].normalized()
    frames = []
    min_basis = 1.0

    core_span = max(1, core_end - core_begin)
    for i, tangent_raw in enumerate(tangents):
        tangent = tangent_raw.normalized()
        if i:
            right, up = geometry.transport_frame(prev_tangent, tangent, right, up)

        if i <= core_begin:
            roll_u = 0.0
        elif i >= core_end:
            roll_u = 1.0
        else:
            roll_u = (i - core_begin) / float(core_span)

        roll = sign * math.tau * roll_u
        q = Quaternion(tangent, roll)
        rolled_right = q @ right
        rolled_right = rolled_right - tangent * rolled_right.dot(tangent)
        if rolled_right.length < 1.0e-8:
            raise ValueError(f"RMF right basis collapsed at sample {i}")
        rolled_right.normalize()
        rolled_up = rolled_right.cross(tangent)
        if rolled_up.length < 1.0e-8:
            raise ValueError(f"RMF up basis collapsed at sample {i}")
        rolled_up.normalize()
        min_basis = min(min_basis, rolled_right.length, rolled_up.length)
        frames.append((tangent.copy(), rolled_right, rolled_up, roll))
        prev_tangent = tangent

    return frames, min_basis


def sample_piece(piece: str):
    sign = handedness(piece)
    core, core_meta = geometry.sample_elliptic_helical_rmf(
        radius_x=RADIUS_X,
        radius_z=RADIUS_Z,
        pitch_per_turn=PITCH,
        turns=TURNS,
        samples=CORE_SAMPLES,
        handedness=sign,
        base_z=base.RAIL_Z,
        roll_turns=ROLL_TURNS,
        phase_rad=math.radians(PHASE_DEG * sign),
    )

    # Center the core longitudinally, then place entry/exit at the same ground
    # connector height.  Hermite shoulders match the helix tangents.
    shift = Vector((-core[0].position.x, -0.5 * PITCH, -core[0].position.z + base.RAIL_Z))
    core_points = [s.position + shift for s in core]
    core_tangents = [s.tangent.copy() for s in core]
    first_p, last_p = core_points[0], core_points[-1]
    first_t, last_t = core_tangents[0], core_tangents[-1]
    forward = Vector((0.0, 1.0, 0.0))

    entry_transition_start = Vector((0.0, first_p.y - TRANSITION_LENGTH, base.RAIL_Z))
    exit_transition_end = Vector((0.0, last_p.y + TRANSITION_LENGTH, base.RAIL_Z))
    entry_start = entry_transition_start - Vector((0.0, STRAIGHT_LENGTH, 0.0))
    exit_end = exit_transition_end + Vector((0.0, STRAIGHT_LENGTH, 0.0))

    points = []
    tangents = []
    for i in range(STRAIGHT_SAMPLES):
        u = i / float(STRAIGHT_SAMPLES - 1)
        points.append(entry_start.lerp(entry_transition_start, u))
        tangents.append(forward.copy())

    hermite_scale = TRANSITION_LENGTH * 1.10
    for i in range(1, TRANSITION_SAMPLES):
        u = i / float(TRANSITION_SAMPLES - 1)
        p, t = hermite_point_tangent(entry_transition_start, first_p, forward, first_t, u, hermite_scale)
        points.append(p)
        tangents.append(t)

    core_begin = len(points) - 1
    for i in range(1, len(core_points)):
        points.append(core_points[i])
        tangents.append(core_tangents[i])
    core_end = len(points) - 1

    for i in range(1, TRANSITION_SAMPLES):
        u = i / float(TRANSITION_SAMPLES - 1)
        p, t = hermite_point_tangent(last_p, exit_transition_end, last_t, forward, u, hermite_scale)
        points.append(p)
        tangents.append(t)

    for i in range(1, STRAIGHT_SAMPLES):
        u = i / float(STRAIGHT_SAMPLES - 1)
        points.append(exit_transition_end.lerp(exit_end, u))
        tangents.append(forward.copy())

    frames, min_basis = reframe_rmf(points, tangents, core_begin, core_end, sign)

    s_values = [0.0]
    for i in range(1, len(points)):
        s_values.append(s_values[-1] + (points[i] - points[i - 1]).length)

    solved = [
        geometry.CurveSample(
            s_values[i], points[i].copy(), frames[i][0].copy(), frames[i][1].copy(),
            frames[i][2].copy(), 0.0, frames[i][3]
        )
        for i in range(len(points))
    ]

    entry_dir_error = math.degrees(math.acos(max(-1.0, min(1.0, tangents[0].normalized().dot(forward)))))
    exit_dir_error = math.degrees(math.acos(max(-1.0, min(1.0, tangents[-1].normalized().dot(forward)))))
    connector_height_error = abs(points[-1].z - points[0].z)
    meta = dict(core_meta)
    meta.update({
        "profile": "elliptic_helical_rmf_corkscrew_v15",
        "trajectory": "elliptic_helix_360",
        "frame": "parallel_transport_rmf_bishop_plus_tangent_roll",
        "rollDegrees": 360.0 * sign,
        "worldUpUsedOnlyForInitialFrame": True,
        "legacyCorkscrewRecipeImported": False,
        "coreBeginIndex": core_begin,
        "coreEndIndex": core_end,
        "minimumBasisLength": min_basis,
        "entryDirectionErrorDegrees": entry_dir_error,
        "exitDirectionErrorDegrees": exit_dir_error,
        "connectorHeightError": connector_height_error,
        "validationPassedV15": min_basis > 0.999 and entry_dir_error < 0.01 and exit_dir_error < 0.01 and connector_height_error < 1.0e-5,
    })
    if not meta["validationPassedV15"]:
        raise ValueError(f"V15 RMF validation failed: {meta}")
    return solved, meta


def build_piece(piece: str):
    steel = bs.make_material("TrackSteel", (0.18, 0.22, 0.24, 1.0), 0.38, 0.34)
    ties_mat = bs.make_material("TrackTies", (0.23, 0.19, 0.16, 1.0), 0.72)
    support_mat = bs.make_material("TrackSupports", (0.31, 0.35, 0.36, 1.0), 0.52, 0.18)

    solved, solver_meta = sample_piece(piece)
    centerline = [s.position.copy() for s in solved]
    frames = [(s.tangent.copy(), s.right.copy(), s.up.copy()) for s in solved]
    left = [p - f[1] * (base.GAUGE * 0.5) for p, f in zip(centerline, frames)]
    right_rail = [p + f[1] * (base.GAUGE * 0.5) for p, f in zip(centerline, frames)]

    authored = [
        base.make_curve_tube("RailLeft", left, steel, base.RAIL_RADIUS, "coaster.rail.left"),
        base.make_curve_tube("RailRight", right_rail, steel, base.RAIL_RADIUS, "coaster.rail.right"),
    ]

    _, _, tie_indices = base.sampled_indices_by_distance(centerline, base.TIE_SPACING)
    for n, idx in enumerate(tie_indices):
        tangent, right, up = frames[idx]
        p = centerline[idx] - up * 0.11
        authored.append(banked.add_oriented_box(
            f"Tie_{n:03d}", p,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat, "coaster.tie", right, tangent, up,
        ))

    # Keep supports outside the inversion core until visual approval.
    for n, idx in enumerate((0, STRAIGHT_SAMPLES - 1, len(centerline) - STRAIGHT_SAMPLES, len(centerline) - 1)):
        base.build_support_frame(authored, f"Support_{n:03d}", centerline[idx], base.tangent(centerline, idx), support_mat)

    return authored, centerline, solved, solver_meta


def write_metadata(output: Path, piece: str, centerline, solver_meta):
    payload = {
        "contract": "CH_COASTER_TRACK_V0",
        "assetId": ASSET_ID,
        "piece": piece,
        "corkscrewContract": "CH_COASTER_CORKSCREW_V0",
        "profile": "single_inversion_v15_elliptic_helical_rmf",
        "geometrySolver": solver_meta,
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "radiusXTiles": RADIUS_X / base.TILE,
        "radiusZTiles": RADIUS_Z / base.TILE,
        "pitchTiles": PITCH / base.TILE,
        "turns": TURNS,
        "rollTurns": ROLL_TURNS,
        "transitionLengthTiles": TRANSITION_LENGTH / base.TILE,
        "straightLengthTiles": STRAIGHT_LENGTH / base.TILE,
        "legacyCorkscrewRecipeImported": False,
        "worldUpSingularityPath": False,
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
        "directions": [d["id"] for d in bs.DIRECTIONS],
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

    authored, centerline, _solved, solver_meta = build_piece(args.piece)
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

    write_metadata(output, args.piece, centerline, solver_meta)
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
