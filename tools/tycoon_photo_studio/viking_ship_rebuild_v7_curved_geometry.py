"""Curved longship refinement for the City Horizon Viking ship ride.

V7 keeps the approved V5/V6 park-scale A-frame and site layout, but rebuilds the
ship silhouette around a stronger bow-to-stern arc.  The hull is longer, the
sheer and keel rise toward both ends, and the external timber bands follow the
same curve instead of reading as straight rectangular fascia.

This pass also opts into CH_PARAMETRIC_AUTHORING_V1 metadata so the authored
source remains deterministic and auditable while runtime stays 2D RGBA.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v5_geometry as v5

CH_BLENDER = Path(__file__).resolve().parents[1] / "ch_blender"
if str(CH_BLENDER) not in sys.path:
    sys.path.insert(0, str(CH_BLENDER))
import parametric_authoring as pa  # noqa: E402


# Keep the already approved site/frame/loading geometry.
build_base = v5.build_base
build_supports = v5.build_supports
build_loading_zone = v5.build_loading_zone
beam_between = v5.beam_between


def _ship_length(g) -> float:
    # V6 was 13.2 m.  Stretch just over twelve percent while staying compatible
    # with the canonical five-tile site and automatic orthographic calibration.
    return float(g.get("curvedShipLength", float(g["shipLength"]) * 1.125))


def hull_sections(g):
    """Return a visibly arched 13-station hull profile.

    x, half-width, gunwale-z, side-z, keel-z.  The stronger sheer line is what
    stops the body from reading as a flat canoe at gameplay scale.
    """
    half_len = _ship_length(g) * 0.5
    half_w = float(g["shipHalfWidth"])
    stations = (-1.0, -0.86, -0.69, -0.51, -0.33, -0.16, 0.0,
                0.16, 0.33, 0.51, 0.69, 0.86, 1.0)
    out = []
    for t in stations:
        a = abs(t)
        # Narrow, high ends and a broad center give the classic amusement-ride
        # "banana"/arc silhouette without turning the ship into a fantasy crescent.
        width_ratio = 0.075 + 0.955 * ((1.0 - a ** 2.15) ** 0.52)
        width = half_w * width_ratio
        gunwale_z = -1.18 + 2.02 * (a ** 2.05)
        side_z = gunwale_z - (0.72 + 0.28 * (1.0 - a))
        keel_z = -3.52 + 2.16 * (a ** 1.82)
        out.append((t * half_len, width, gunwale_z, side_z, keel_z))
    return out


def _build_curved_hull(boat_root, g, mats):
    sections = hull_sections(g)
    vertices = []
    ring_count = 6
    for x, width, top_z, mid_z, bottom_z in sections:
        vertices.extend([
            (x, -width, top_z),
            (x, -width * 0.90, mid_z),
            (x, -width * 0.28, bottom_z),
            (x,  width * 0.28, bottom_z),
            (x,  width * 0.90, mid_z),
            (x,  width, top_z),
        ])

    faces = []
    for s in range(len(sections) - 1):
        a = s * ring_count
        b = (s + 1) * ring_count
        for r in range(ring_count):
            n = (r + 1) % ring_count
            faces.append((a + r, a + n, b + n, b + r))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    last = (len(sections) - 1) * ring_count
    faces.append(tuple(last + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new("CityHorizonVikingHullCurvedV7Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("CityHorizonVikingHullCurvedV7", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    hull["hullProfile"] = "long_curved_arc_v7"

    bevel = pa.add_modifier_stage(
        hull,
        modifier_type="BEVEL",
        name="HullEdgeBreak",
        stage="surface",
    )
    bevel.width = 0.045
    bevel.segments = 2

    # Curved gunwale and clinker bands.  Unlike V6's long straight boxes, every
    # segment follows the local width and vertical arc of the hull stations.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for i in range(len(sections) - 1):
            x0, w0, top0, mid0, _ = sections[i]
            x1, w1, top1, mid1, _ = sections[i + 1]
            fw.cylinder_between(
                f"CHR_V7_Gunwale_{label}_{i:02d}",
                (x0, side * (w0 + 0.025), top0 + 0.055),
                (x1, side * (w1 + 0.025), top1 + 0.055),
                0.072,
                mats["red"],
                boat_root,
                vertices=12,
            )

            for band_index, fraction in enumerate((0.32, 0.58, 0.80)):
                z0 = top0 + (mid0 - top0) * fraction
                z1 = top1 + (mid1 - top1) * fraction
                inset = 1.0 - 0.055 * band_index
                fw.cylinder_between(
                    f"CHR_V7_HullBand_{label}_{band_index}_{i:02d}",
                    (x0, side * w0 * inset, z0),
                    (x1, side * w1 * inset, z1),
                    0.045 if band_index < 2 else 0.040,
                    mats["woodDark"],
                    boat_root,
                    vertices=10,
                )

    # Keep the passenger floor flatter than the shell, but shorten it so the
    # upward-curving ends remain visible instead of being hidden by one slab.
    length = _ship_length(g)
    half_w = float(g["shipHalfWidth"])
    deck_z = float(g["shipDeckZ"])
    deck_len = length * 0.58
    fw.box(
        "CHR_V7_ShipDeck",
        (0.0, 0.0, deck_z),
        (deck_len, half_w * 1.34, 0.13),
        mats["woodDark"],
        0.010,
        boat_root,
    )
    for i in range(11):
        x = -deck_len * 0.46 + deck_len * 0.92 * (i / 10.0)
        fw.box(
            f"CHR_V7_DeckCrossPlank_{i:02d}",
            (x, 0.0, deck_z + 0.078),
            (0.18, half_w * 1.29, 0.026),
            mats["woodLight"],
            0.003,
            boat_root,
        )
    return hull


def _build_curved_prows(boat_root, g, mats):
    half_len = _ship_length(g) * 0.5

    # Both stems continue the new sheer line upward so the body itself reads as
    # an arc, rather than looking like a straight canoe with ornaments attached.
    for sign, label in ((1.0, "Bow"), (-1.0, "Stern")):
        v5.beam_between(
            f"CHR_V7_{label}StemLower",
            (sign * half_len * 0.92, 0.0, 0.34),
            (sign * half_len * 1.015, 0.0, 1.10),
            0.20, 0.27, mats["woodLight"], boat_root, 0.016,
        )
        v5.beam_between(
            f"CHR_V7_{label}StemUpper",
            (sign * half_len * 1.015, 0.0, 1.10),
            (sign * half_len * 1.055, 0.0, 1.72 if sign > 0 else 1.48),
            0.16, 0.22, mats["woodDark"], boat_root, 0.012,
        )

    # Retain one restrained carved-head cue only on the bow for asymmetry.
    fw.box(
        "CHR_V7_BowCarvedHead",
        (half_len * 1.075, 0.0, 1.76),
        (0.46, 0.34, 0.26),
        mats["woodLight"],
        0.016,
        boat_root,
    )


def _build_curved_seating(boat_root, g, mats):
    rows = int(g.get("seatRows", 8)) + 1
    span = _ship_length(g) * 0.54
    half_w = float(g["shipHalfWidth"])
    for i in range(rows):
        x = -span * 0.5 + span * (i / max(1, rows - 1))
        fw.box(
            f"CHR_V7_SeatFrame_{i:02d}", (x, 0.0, -1.10),
            (0.50, half_w * 1.22, 0.08), mats["steelDark"], 0.009, boat_root,
        )
        fw.box(
            f"CHR_V7_SeatBench_{i:02d}", (x, 0.0, -1.01),
            (0.44, half_w * 1.16, 0.065), mats["seatRed"], 0.009, boat_root,
        )
        fw.box(
            f"CHR_V7_SeatBack_{i:02d}", (x + 0.15, 0.0, -0.80),
            (0.085, half_w * 1.14, 0.32), mats["woodLight"], 0.009, boat_root,
        )
        fw.cylinder_between(
            f"CHR_V7_SafetyBar_{i:02d}",
            (x - 0.07, -half_w * 0.53, -0.70),
            (x - 0.07,  half_w * 0.53, -0.70),
            0.028, mats["steelLight"], boat_root, vertices=10,
        )


# Patch V5's proven suspension constructor so only the ship geometry changes.
v5.hull_sections = hull_sections
v5._build_city_horizon_hull = _build_curved_hull
v5._build_city_horizon_prows = _build_curved_prows
v5._build_city_horizon_seating = _build_curved_seating


def build_swing_group(root, g, mats):
    pa.configure_metric_units(bpy.context.scene)
    pivot = v5.build_swing_group(root, g, mats)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V7_BOAT_ROOT_MISSING")
    pa.tag_procedural_generator(
        boat_root,
        generator_kind="CURVED_LONGSHIP_HULL",
        seed=7007,
        parameters={
            "revision": "v7",
            "shipLength": round(_ship_length(g), 4),
            "stations": len(hull_sections(g)),
            "arcProfile": "raised_sheer_and_keel",
            "curvedExternalBands": True,
        },
    )
    boat_root["hullRevision"] = "CH_VIKING_CURVED_LONGSHIP_V7"
    boat_root["visualCorrection"] = "longer_ship_stronger_arc_not_flat_canoe"
    return pivot
