"""Deterministic differential-geometry helpers for City Horizon coaster authoring.

The solver is intentionally independent from rendering. It samples centerlines by
arc length, transports a stable local frame, applies curvature profiles with
clothoid-style linear ramps, and keeps track roll separate from the path itself.

Runtime is still pre-rendered 2D. These helpers are authoring-time geometry only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Sequence, Tuple

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
    u = _clamp(u, 0.0, 1.0)
    r = _clamp(ramp_fraction, 1.0e-4, 0.4999)
    if u < r:
        return u / r
    if u > 1.0 - r:
        return (1.0 - u) / r
    return 1.0


def smooth_roll_progress(u: float, ramp_fraction: float = 0.18) -> float:
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


def transport_frame(old_tangent: Vector, new_tangent: Vector, right: Vector, up: Vector) -> Tuple[Vector, Vector]:
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
    new_right = new_right - b * new_right.dot(b)
    if new_right.length < EPS:
        new_right = b.cross(new_up)
    new_right.normalize()
    new_up = new_right.cross(b).normalized()
    return new_right, new_up


def integrate_curvature_curve(*, total_length: float, samples: int,
                              curvature_fn: Callable[[float, float], float],
                              curvature_plane_angle_fn: Callable[[float, float], float],
                              initial_position: Vector,
                              initial_tangent: Vector = Vector((0.0, 1.0, 0.0)),
                              preferred_up: Vector = Vector((0.0, 0.0, 1.0))) -> List[CurveSample]:
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


def apply_roll(samples: Sequence[CurveSample], roll_fn: Callable[[float, float], float]) -> List[CurveSample]:
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
        out.append(CurveSample(sample.s, sample.position.copy(), sample.tangent.copy(), right, up,
                               sample.curvature, sample.curvature_plane_angle))
    return out


def helix_curvature_and_torsion(radius: float, pitch_per_turn: float) -> Tuple[float, float]:
    if radius <= 0.0:
        raise ValueError("radius must be > 0")
    a = pitch_per_turn / math.tau
    denom = radius * radius + a * a
    return radius / denom, a / denom


def sample_elliptic_helical_rmf(*, radius_x: float, radius_z: float,
                                pitch_per_turn: float, turns: float,
                                samples: int, handedness: float,
                                base_z: float, roll_turns: float = 1.0,
                                phase_rad: float = 0.0) -> Tuple[List[CurveSample], dict]:
    """Sample an elliptic helix around +Y using a rotation-minimizing frame.

    The trajectory itself is a true 3D elliptic helix.  A Bishop/parallel-
    transport frame is propagated from sample to sample, avoiding the singular
    world-UP projection that collapses near vertical tangents.  Explicit track
    roll is then accumulated about each local tangent.  ``roll_turns=1`` means
    one full 2*pi roll over the element.
    """
    if radius_x <= 0.0 or radius_z <= 0.0 or pitch_per_turn <= 0.0:
        raise ValueError("elliptic helix radii and pitch must be > 0")
    if turns <= 0.0 or samples < 3:
        raise ValueError("turns must be > 0 and samples >= 3")

    sign = 1.0 if handedness >= 0.0 else -1.0
    theta_total = math.tau * turns
    a = pitch_per_turn / math.tau
    positions: List[Vector] = []
    tangents: List[Vector] = []

    for i in range(samples):
        u = i / float(samples - 1)
        theta = phase_rad + sign * theta_total * u
        x = radius_x * math.sin(theta)
        y = pitch_per_turn * turns * u
        z = base_z + radius_z * (1.0 - math.cos(theta))
        dtheta_du = sign * theta_total
        deriv = Vector((
            radius_x * math.cos(theta) * dtheta_du,
            pitch_per_turn * turns,
            radius_z * math.sin(theta) * dtheta_du,
        ))
        if deriv.length < EPS:
            raise ValueError("elliptic helix produced zero tangent")
        positions.append(Vector((x, y, z)))
        tangents.append(deriv.normalized())

    # Arc-length parameterization from the exact sampled polyline.
    arc = [0.0]
    for i in range(1, samples):
        arc.append(arc[-1] + (positions[i] - positions[i - 1]).length)
    total_length = arc[-1]
    if total_length <= EPS:
        raise ValueError("elliptic helix has zero arc length")

    # RMF/Bishop frame.  No repeated world-UP projection after initialization.
    t0, right, up = _orthonormal_frame(tangents[0], Vector((0.0, 0.0, 1.0)))
    out: List[CurveSample] = []
    prev_tangent = t0
    min_right = float("inf")
    min_up = float("inf")

    for i in range(samples):
        tangent = tangents[i]
        if i:
            right, up = transport_frame(prev_tangent, tangent, right, up)
        u_arc = arc[i] / total_length
        roll = sign * math.tau * roll_turns * u_arc
        q = Quaternion(tangent, roll)
        rolled_right = q @ right
        rolled_right = rolled_right - tangent * rolled_right.dot(tangent)
        if rolled_right.length < EPS:
            raise ValueError(f"RMF right vector collapsed at sample {i}")
        rolled_right.normalize()
        rolled_up = rolled_right.cross(tangent)
        if rolled_up.length < EPS:
            raise ValueError(f"RMF up vector collapsed at sample {i}")
        rolled_up.normalize()
        min_right = min(min_right, rolled_right.length)
        min_up = min(min_up, rolled_up.length)
        out.append(CurveSample(
            arc[i], positions[i].copy(), tangent.copy(), rolled_right, rolled_up,
            0.0, roll,
        ))
        prev_tangent = tangent

    closure_xz = math.hypot(out[-1].position.x - out[0].position.x,
                            out[-1].position.z - out[0].position.z)
    y_advance = out[-1].position.y - out[0].position.y
    expected_y = pitch_per_turn * turns
    metadata = {
        "solverContract": "CH_COASTER_GEOMETRY_SOLVER_V1",
        "fixture": "elliptic_helical_rmf",
        "axis": "+Y",
        "frame": "parallel_transport_rmf_bishop",
        "radiusX": radius_x,
        "radiusZ": radius_z,
        "pitchPerTurn": pitch_per_turn,
        "turns": turns,
        "rollTurns": roll_turns,
        "rollDegrees": 360.0 * roll_turns * sign,
        "phaseRadians": phase_rad,
        "arcLength": total_length,
        "closureXZError": closure_xz,
        "longitudinalAdvanceError": abs(y_advance - expected_y),
        "frameCollapseDetected": False,
        "minimumRightLength": min_right,
        "minimumUpLength": min_up,
        "validationPassed": closure_xz <= 1.0e-4 and abs(y_advance - expected_y) <= 1.0e-4,
    }
    if not metadata["validationPassed"]:
        raise ValueError(f"elliptic helix invariant failed: {metadata}")
    return out, metadata


def sample_analytic_helix_reference(*, radius: float, pitch_per_turn: float,
                                    turns: float, samples: int, handedness: float,
                                    base_z: float) -> Tuple[List[CurveSample], dict]:
    """Exact circular helix used as the geometry solver's ground-truth fixture.

    Axis is +Y. For one full turn the endpoint must have the same X/Z as the
    start and advance exactly ``pitch_per_turn`` along Y. The local up vector is
    the inward radial normal projected perpendicular to the tangent, so the deck
    orientation comes from helix geometry itself; no independent 360-degree roll
    is applied here.
    """
    if radius <= 0.0 or samples < 3 or turns <= 0.0:
        raise ValueError("radius/turns must be > 0 and samples >= 3")
    sign = 1.0 if handedness >= 0.0 else -1.0
    a = pitch_per_turn / math.tau
    kappa, torsion = helix_curvature_and_torsion(radius, pitch_per_turn)
    theta_max = math.tau * turns
    arc_per_rad = math.sqrt(radius * radius + a * a)
    total_length = arc_per_rad * theta_max
    out: List[CurveSample] = []

    for i in range(samples):
        u = i / float(samples - 1)
        theta = sign * theta_max * u
        x = radius * math.sin(theta)
        y = a * abs(theta)
        z = base_z + radius * (1.0 - math.cos(theta))
        d = Vector((sign * radius * math.cos(theta), a, sign * radius * math.sin(theta)))
        tangent = d.normalized()
        inward = Vector((-math.sin(theta), 0.0, math.cos(theta)))
        up = inward - tangent * inward.dot(tangent)
        up.normalize()
        right = tangent.cross(up).normalized()
        up = right.cross(tangent).normalized()
        s = total_length * u
        out.append(CurveSample(s, Vector((x, y, z)), tangent, right, up, kappa, sign * torsion * s))

    start = out[0].position
    end = out[-1].position
    expected_y = pitch_per_turn * turns
    closure_xz = math.hypot(end.x - start.x, end.z - start.z)
    y_error = abs((end.y - start.y) - expected_y)
    tolerance = 1.0e-5
    metadata = {
        "solverContract": "CH_COASTER_GEOMETRY_SOLVER_V1",
        "fixture": "analytic_circular_helix",
        "axis": "+Y",
        "radius": radius,
        "pitchPerTurn": pitch_per_turn,
        "turns": turns,
        "arcLength": total_length,
        "idealHelixCurvature": kappa,
        "idealHelixTorsion": torsion * sign,
        "closureXZError": closure_xz,
        "longitudinalAdvanceError": y_error,
        "analyticValidationPassed": closure_xz <= tolerance and y_error <= tolerance,
    }
    if not metadata["analyticValidationPassed"]:
        raise ValueError(f"analytic helix invariant failed: {metadata}")
    return out, metadata


def sample_engineering_corkscrew(*, total_length: float, samples: int,
                                 helix_radius: float, pitch_per_turn: float,
                                 handedness: float, base_z: float,
                                 transition_fraction: float = 0.18,
                                 roll_ramp_fraction: float = 0.18) -> Tuple[List[CurveSample], dict]:
    sign = 1.0 if handedness >= 0.0 else -1.0
    kappa, torsion = helix_curvature_and_torsion(helix_radius, pitch_per_turn)

    def curvature_fn(_s: float, u: float) -> float:
        return kappa * linear_clothoid_envelope(u, transition_fraction)

    def plane_angle_fn(s: float, _u: float) -> float:
        return sign * torsion * s

    raw = integrate_curvature_curve(
        total_length=total_length, samples=samples,
        curvature_fn=curvature_fn, curvature_plane_angle_fn=plane_angle_fn,
        initial_position=Vector((0.0, -0.5 * total_length, base_z)),
        initial_tangent=Vector((0.0, 1.0, 0.0)), preferred_up=Vector((0.0, 0.0, 1.0)),
    )
    rolled = apply_roll(raw, lambda _s, u: sign * math.tau * smooth_roll_progress(u, roll_ramp_fraction))
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
