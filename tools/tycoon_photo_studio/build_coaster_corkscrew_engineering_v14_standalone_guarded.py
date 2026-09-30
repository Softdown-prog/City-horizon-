"""Standalone V14 corkscrew authoring.

This builder intentionally does NOT import any previous corkscrew recipe.  It
uses only the shared coaster primitives plus the validated analytic helix solver
fixture, then applies an explicit phase rotation and tangent-matched Hermite
shoulders.  This removes accidental inheritance from rejected V0-V13 recipes.
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

# V14 is deliberately self-contained and calibrated from the technical plan +
# SOUTH proxy review, not from a previous corkscrew wrapper.
HELIX_RADIUS = base.TILE * 0.60
HELIX_PITCH = base.TILE * 4.10
HELIX_PHASE_DEG = 55.0
ENTRY_ELEVATION = base.TILE * 0.42
TRANSITION_LENGTH = base.TILE * 1.70
STRAIGHT_LENGTH = base.TILE * 0.85
HELIX_SAMPLES = 301
TRANSITION_SAMPLES = 73
STRAIGHT_SAMPLES = 25
FOOTPRINT = {"widthTiles": 5, "depthTiles": 10}


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


def rotate_y(v: Vector, angle_rad: float) -> Vector:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return Vector((c * v.x + s * v.z, v.y, -s * v.x + c * v.z))


def frame_from_tangent(tangent: Vector):
    tangent = tangent.normalized()
    up = Vector((0.0, 0.0, 1.0))
    up = up - tangent * up.dot(tangent)
    if up.length < 1.0e-8:
        up = Vector((1.0, 0.0, 0.0))
        up = up - tangent * up.dot(tangent)
    up.normalize()
    right = tangent.cross(up).normalized()
    up = right.cross(tangent).normalized()
    return tangent, right, up


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


def append_flat_sample(samples, point: Vector, tangent: Vector):
    tangent, right, up = frame_from_tangent(tangent)
    samples.append(geometry.CurveSample(0.0, point, tangent, right, up, 0.0, 0.0))


def reparameterize(samples):
    out = []
    s = 0.0
    prev = None
    for sample in samples:
        if prev is not None:
            s += (sample.position - prev).length
        prev = sample.position
        out.append(geometry.CurveSample(
            s,
            sample.position.copy(),
            sample.tangent.copy(),
            sample.right.copy(),
            sample.up.copy(),
            sample.curvature,
            sample.curvature_plane_angle,
        ))
    return out


def phased_analytic_core(piece: str):
    sign = handedness(piece)
    raw, meta = geometry.sample_analytic_helix_reference(
        radius=HELIX_RADIUS,
        pitch_per_turn=HELIX_PITCH,
        turns=1.0,
        samples=HELIX_SAMPLES,
        handedness=sign,
        base_z=base.RAIL_Z,
    )

    # The analytic fixture's circle centre is at z=base.RAIL_Z + HELIX_RADIUS.
    # Rotate around the longitudinal +Y axis to choose a more coaster-like phase
    # without adding any independent 360-degree roll.
    phase = math.radians(HELIX_PHASE_DEG * sign)
    centre_z = base.RAIL_Z + HELIX_RADIUS
    phased = []
    for sample in raw:
        rel = sample.position - Vector((0.0, 0.0, centre_z))
        p = rotate_y(rel, phase) + Vector((0.0, 0.0, centre_z))
        t = rotate_y(sample.tangent, phase).normalized()
        r = rotate_y(sample.right, phase).normalized()
        u = rotate_y(sample.up, phase).normalized()
        phased.append(geometry.CurveSample(
            sample.s, p, t, r, u, sample.curvature, sample.curvature_plane_angle
        ))

    # Full-turn helix closes in X/Z.  Translate the shared entry/exit point to
    # x=0 and a controlled elevated connector level, then center Y around zero.
    entry = phased[0].position
    target_z = base.RAIL_Z + ENTRY_ELEVATION
    shift = Vector((-entry.x, -0.5 * HELIX_PITCH, target_z - entry.z))
    phased = [geometry.CurveSample(
        sample.s,
        sample.position + shift,
        sample.tangent.copy(),
        sample.right.copy(),
        sample.up.copy(),
        sample.curvature,
        sample.curvature_plane_angle,
    ) for sample in phased]

    meta = dict(meta)
    meta.update({
        "profile": "analytic_helix_phase_controlled_standalone_v14",
        "helixIsSoleInversionSource": True,
        "independentRollDegrees": 0.0,
        "helixPhaseDegrees": HELIX_PHASE_DEG * sign,
        "entryElevation": ENTRY_ELEVATION,
    })
    return phased, meta


def sample_centerline(piece: str):
    core, core_meta = phased_analytic_core(piece)
    first = core[0]
    last = core[-1]
    forward = Vector((0.0, 1.0, 0.0))

    entry_transition_start = Vector((0.0, first.position.y - TRANSITION_LENGTH, base.RAIL_Z))
    exit_transition_end = Vector((0.0, last.position.y + TRANSITION_LENGTH, base.RAIL_Z))
    entry_straight_start = entry_transition_start - Vector((0.0, STRAIGHT_LENGTH, 0.0))
    exit_straight_end = exit_transition_end + Vector((0.0, STRAIGHT_LENGTH, 0.0))

    samples = []
    for i in range(STRAIGHT_SAMPLES):
        u = i / float(STRAIGHT_SAMPLES - 1)
        append_flat_sample(samples, entry_straight_start.lerp(entry_transition_start, u), forward)

    hermite_scale = TRANSITION_LENGTH * 1.10
    for i in range(1, TRANSITION_SAMPLES):
        u = i / float(TRANSITION_SAMPLES - 1)
        p, tangent = hermite_point_tangent(
            entry_transition_start, first.position, forward, first.tangent, u, hermite_scale
        )
        append_flat_sample(samples, p, tangent)

    samples.extend(core[1:])

    for i in range(1, TRANSITION_SAMPLES):
        u = i / float(TRANSITION_SAMPLES - 1)
        p, tangent = hermite_point_tangent(
            last.position, exit_transition_end, last.tangent, forward, u, hermite_scale
        )
        append_flat_sample(samples, p, tangent)

    for i in range(1, STRAIGHT_SAMPLES):
        u = i / float(STRAIGHT_SAMPLES - 1)
        append_flat_sample(samples, exit_transition_end.lerp(exit_straight_end, u), forward)

    solved = reparameterize(samples)
    core_meta.update({
        "transitionType": "cubic_hermite_tangent_match",
        "transitionLength": TRANSITION_LENGTH,
        "straightLength": STRAIGHT_LENGTH,
        "helixSamples": HELIX_SAMPLES,
        "transitionSamples": TRANSITION_SAMPLES,
        "straightSamples": STRAIGHT_SAMPLES,
        "totalSampledArcLength": solved[-1].s,
        "legacyCorkscrewRecipeImported": False,
    })
    return solved, core_meta


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
            f"Tie_{n:03d}", p,
            (base.TIE_HALF_WIDTH, base.TIE_HALF_DEPTH, base.TIE_HALF_HEIGHT),
            ties_mat, "coaster.tie", right, tangent, up,
        ))

    # Keep supports conservative until SOUTH visual approval.
    last = len(centerline) - 1
    support_indices = sorted(set((0, STRAIGHT_SAMPLES - 1, last - STRAIGHT_SAMPLES + 1, last)))
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
        "profile": "single_inversion_v14_standalone_phase_controlled",
        "geometrySolver": solver_meta,
        "blenderUnitsPerTile": base.TILE,
        "footprint": FOOTPRINT,
        "helixRadiusTiles": 0.60,
        "helixPitchTiles": 4.10,
        "helixPhaseDegrees": HELIX_PHASE_DEG * handedness(piece),
        "entryElevationTiles": 0.42,
        "transitionLengthTiles": 1.70,
        "straightLengthTiles": 0.85,
        "independentRollDegrees": 0.0,
        "legacyCorkscrewRecipeImported": False,
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
