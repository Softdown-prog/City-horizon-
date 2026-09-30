"""Deterministic differential-geometry helpers for City Horizon coaster authoring.

The solver is intentionally independent from rendering. It samples centerlines by
arc length, transports a stable local frame, applies curvature profiles with
clothoid-style linear ramps, and keeps track roll separate from the path itself.

Runtime is still pre-rendered 2D. These helpers are authoring-time geometry only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence, Tuple

from mathutils import Quaternion, Vector


EPS = 1.0e-8


@dataclass(frozen=True)
class CurveSample:
    s: float
    position: Vector
    tangent: Vector
    right: Vector
    up: Vector
    curvature: float
    curvature_plane_angle: float


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def linear_clothoid_envelope(u: float, ramp_fraction: float = 0.18) -> float:
    """0->1->0 curvature envelope with linear ramps in arc length.

    A linear curvature ramp is the defining useful property of a clothoid for
    our authoring purposes. The middle remains at full curvature and the two
    shoulders are symmetric.
    """
    u = _clamp(u, 0.0, 1.0)
    r = _clamp(ramp_fraction, 1.0e-4, 0.4999)
    if u < r:
        return u / r
    if u > 1.0 - r:
        return (1.0 - u) / r
    return 1.0


def smooth_roll_progress(u: float, ramp_fraction: float = 0.18) -> float:
    """Monotonic 0..1 roll schedule with zero-ish shoulder velocity."""
    u = _clamp(u, 0.0, 1.0)
    r = _clamp(ramp_fraction, 1.0e-4, 0.4999)
    total = 1.0 - r
    if u < r:
        q = u / r
        return (r * (q ** 3 - 0.5 * q ** 4)) / total
    if u > 1.0 - r:
        return 1.0 - smooth_roll_progress(1.0 - u, ramp_fraction)
    return (0.5 * r + (u - r)) / total


def _orthonormal_frame(tangent: Vector, preferred_up: Vector) -> Tuple[Vector, Vector, Vector]:
    tangent = tangent.normalized()
    up = preferred_up - tangent * preferred_up.dot(tangent)
    if up.length < EPS:
        fallback = Vector((1.0, 0.0, 0.0))
        up = fallback - tangent * fallback.dot(tangent)
    up.normalize()
    right = tangent.cross(up)
    if right.length < EPS:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(tangent).normalized()
    return tangent, right, up


def transport_frame(
    old_tangent: Vector,
    new_tangent: Vector,
    right: Vector,
    up: Vector,
) -> Tuple[Vector, Vector]:
    """Parallel-transport right/up from one tangent to the next.

    This avoids the Frenet-frame flip near zero curvature, which matters at
    straight connectors and clothoid shoulders.
    """
    a = old_tangent.normalized()
    b = new_tangent.normalized()
    axis = a.cross(b)
    axis_len = axis.length
    if axis_len < EPS:
        return right.copy(), up.copy()

    axis.normalize()
    angle = math.atan2(axis_len, _clamp(a.dot(b), -1.0, 1.0))
    q = Quaternion(axis, angle)
    new_right = q @ right
    new_up = q @ up

    # Remove accumulated numeric drift.
    new_right = new_right - b * new_right.dot(b)
    if new_right.length < EPS:
        new_right = b.cross(new_up)
    new_right.normalize()
    new_up = new_right.cross(b).normalized()
    return new_right, new_up


def integrate_curvature_curve(
    *,
    total_length: float,
    samples: int,
    curvature_fn: Callable[[float, float], float],
    curvature_plane_angle_fn: Callable[[float, float], float],
    initial_position: Vector,
    initial_tangent: Vector = Vector((0.0, 1.0, 0.0)),
    preferred_up: Vector = Vector((0.0, 0.0, 1.0)),
) -> List[CurveSample]:
    """Integrate a 3D centerline using arc length as the independent variable.

    `curvature_fn(s, u)` supplies kappa(s). `curvature_plane_angle_fn(s, u)`
    rotates the curvature vector around the transported tangent. This is a small
    deterministic Bishop-frame integrator rather than a graphics-only spline.
    """
    if total_length <= 0.0:
        raise ValueError("total_length must be > 0")
    if samples < 3:
        raise ValueError("samples must be >= 3")

    tangent, right, up = _orthonormal_frame(initial_tangent, preferred_up)
    position = initial_position.copy()
    ds = total_length / float(samples - 1)
    out: List[CurveSample] = []

    for i in range(samples):
        s = ds * i
        u = i / float(samples - 1)
        kappa = max(0.0, float(curvature_fn(s, u)))
        beta = float(curvature_plane_angle_fn(s, u))
        out.append(CurveSample(s, position.copy(), tangent.copy(), right.copy(), up.copy(), kappa, beta))
        if i == samples - 1:
            break

        # Midpoint estimate gives a stable tangent update without a heavy solver.
        sm = s + 0.5 * ds
        um = (i + 0.5) / float(samples - 1)
        km = max(0.0, float(curvature_fn(sm, um)))
        bm = float(curvature_plane_angle_fn(sm, um))
        curvature_dir = (right * math.cos(bm) + up * math.sin(bm)).normalized()
        next_tangent = tangent + curvature_dir * (km * ds)
        if next_tangent.length < EPS:
            next_tangent = tangent.copy()
        next_tangent.normalize()

        next_right, next_up = transport_frame(tangent, next_tangent, right, up)
        travel_dir = tangent + next_tangent
        if travel_dir.length < EPS:
            travel_dir = next_tangent.copy()
        travel_dir.normalize()
        position = position + travel_dir * ds
        tangent, right, up = next_tangent, next_right, next_up

    return out


def apply_roll(
    samples: Sequence[CurveSample],
    roll_fn: Callable[[float, float], float],
) -> List[CurveSample]:
    """Apply track roll around the already-solved tangent.

    Centerline geometry and rail/deck roll stay independent by design.
    """
    if not samples:
        return []
    total = samples[-1].s if samples[-1].s > 0.0 else 1.0
    out: List[CurveSample] = []
    for sample in samples:
        u = sample.s / total
        angle = float(roll_fn(sample.s, u))
        q = Quaternion(sample.tangent, angle)
        right = (q @ sample.right).normalized()
        up = (q @ sample.up).normalized()
        out.append(CurveSample(
            sample.s,
            sample.position.copy(),
            sample.tangent.copy(),
            right,
            up,
            sample.curvature,
            sample.curvature_plane_angle,
        ))
    return out


def helix_curvature_and_torsion(radius: float, pitch_per_turn: float) -> Tuple[float, float]:
    """Return constant curvature/torsion of an ideal circular helix."""
    if radius <= 0.0:
        raise ValueError("radius must be > 0")
    a = pitch_per_turn / math.tau
    denom = radius * radius + a * a
    return radius / denom, a / denom


def sample_engineering_corkscrew(
    *,
    total_length: float,
    samples: int,
    helix_radius: float,
    pitch_per_turn: float,
    handedness: float,
    base_z: float,
    transition_fraction: float = 0.18,
    roll_ramp_fraction: float = 0.18,
) -> Tuple[List[CurveSample], dict]:
    """Sample one engineering-inspired corkscrew element.

    The target helix supplies physical curvature/torsion values. Curvature is
    introduced/removed with clothoid-style linear ramps. A Bishop frame keeps
    straight connectors stable, while one independent 360-degree track roll is
    layered on top.
    """
    sign = 1.0 if handedness >= 0.0 else -1.0
    kappa, torsion = helix_curvature_and_torsion(helix_radius, pitch_per_turn)

    def curvature_fn(_s: float, u: float) -> float:
        return kappa * linear_clothoid_envelope(u, transition_fraction)

    def plane_angle_fn(s: float, _u: float) -> float:
        return sign * torsion * s

    raw = integrate_curvature_curve(
        total_length=total_length,
        samples=samples,
        curvature_fn=curvature_fn,
        curvature_plane_angle_fn=plane_angle_fn,
        initial_position=Vector((0.0, -0.5 * total_length, base_z)),
        initial_tangent=Vector((0.0, 1.0, 0.0)),
        preferred_up=Vector((0.0, 0.0, 1.0)),
    )

    rolled = apply_roll(
        raw,
        lambda _s, u: sign * math.tau * smooth_roll_progress(u, roll_ramp_fraction),
    )

    metadata = {
        "solverContract": "CH_COASTER_GEOMETRY_SOLVER_V1",
        "parameterization": "arc_length",
        "frame": "parallel_transport_bishop",
        "curvatureTransition": "linear_clothoid_ramp",
        "helixRadius": helix_radius,
        "pitchPerTurn": pitch_per_turn,
        "idealHelixCurvature": kappa,
        "idealHelixTorsion": torsion,
        "transitionFraction": transition_fraction,
        "rollRampFraction": roll_ramp_fraction,
        "rollDegrees": 360.0 * sign,
    }
    return rolled, metadata
