"""V9 major ship-body overhaul for the City Horizon Viking ride.

Keeps the approved 5x4 ride frame/site, but substantially rebuilds the suspended
longship itself.  Goals: remove the flat/blunt canoe read, make both ends visibly
rise and taper, add a deeper faceted clinker hull, stronger gunwales, a readable
Viking prow/stern silhouette, larger shields and a denser passenger deck.
"""
from __future__ import annotations

import math

import bpy

import build_ferris_wheel as fw
import viking_ship_rebuild_v7_curved_geometry as v7

build_base = v7.build_base
build_supports = v7.build_supports
build_loading_zone = v7.build_loading_zone
beam_between = v7.beam_between


def _ship_length(g):
    return float(g.get("v9ShipLength", float(g["shipLength"]) * 1.16))


def hull_sections(g):
    """15-station high-sheer longship with narrow raised ends and deep centre."""
    half_len = _ship_length(g) * 0.5
    half_w = float(g["shipHalfWidth"]) * 1.06
    stations = (-1.00, -0.92, -0.80, -0.66, -0.50, -0.32, -0.16, 0.0,
                0.16, 0.32, 0.50, 0.66, 0.80, 0.92, 1.00)
    out = []
    for t in stations:
        a = abs(t)
        # Narrow tips, broad belly, pronounced sheer rise at both ends.
        width_ratio = 0.055 + 0.975 * ((1.0 - a ** 2.05) ** 0.47)
        width = half_w * width_ratio
        top_z = -1.23 + 2.48 * (a ** 2.32)
        mid_z = top_z - (0.86 + 0.30 * (1.0 - a))
        keel_z = -3.78 + 2.62 * (a ** 1.86)
        out.append((t * half_len, width, top_z, mid_z, keel_z))
    return out


def _build_hull(boat_root, g, mats):
    sections = hull_sections(g)
    ring_count = 8
    verts = []
    for x, w, top, mid, keel in sections:
        verts.extend([
            (x, -w, top),
            (x, -w * 0.96, top - 0.34),
            (x, -w * 0.82, mid),
            (x, -w * 0.28, keel),
            (x,  w * 0.28, keel),
            (x,  w * 0.82, mid),
            (x,  w * 0.96, top - 0.34),
            (x,  w, top),
        ])
    faces = []
    for s in range(len(sections) - 1):
        a, b = s * ring_count, (s + 1) * ring_count
        for r in range(ring_count):
            n = (r + 1) % ring_count
            faces.append((a + r, a + n, b + n, b + r))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    last = (len(sections) - 1) * ring_count
    faces.append(tuple(last + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new("CityHorizonVikingHullV9Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    hull = bpy.data.objects.new("CityHorizonVikingHullV9", mesh)
    bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats["wood"])
    hull.parent = boat_root
    bevel = hull.modifiers.new(name="HullEdgeBreakV9", type="BEVEL")
    bevel.width = 0.055
    bevel.segments = 2

    # Gunwale + four clinker strakes following the true local hull curve.
    for side, label in ((-1.0, "Near"), (1.0, "Far")):
        for i in range(len(sections)-1):
            x0,w0,t0,m0,k0 = sections[i]
            x1,w1,t1,m1,k1 = sections[i+1]
            fw.cylinder_between(f"CHR_V9_Gunwale_{label}_{i:02d}",
                (x0, side*(w0+0.035), t0+0.08), (x1, side*(w1+0.035), t1+0.08),
                0.085, mats["woodLight"], boat_root, vertices=12)
            for band, frac in enumerate((0.20, 0.42, 0.64, 0.82)):
                z0 = t0 + (m0-t0)*frac
                z1 = t1 + (m1-t1)*frac
                inset = 1.0 - 0.045*band
                fw.cylinder_between(f"CHR_V9_Strake_{label}_{band}_{i:02d}",
                    (x0, side*w0*inset, z0), (x1, side*w1*inset, z1),
                    0.050 if band < 2 else 0.042, mats["woodDark"], boat_root, vertices=10)

    # Red accent follows the sheer rather than forming a straight fascia.
    for side,label in ((-1.0,"Near"),(1.0,"Far")):
        for i in range(len(sections)-1):
            x0,w0,t0,_,_ = sections[i]; x1,w1,t1,_,_ = sections[i+1]
            fw.cylinder_between(f"CHR_V9_RedSheer_{label}_{i:02d}",
                (x0, side*(w0+0.05), t0-0.16), (x1, side*(w1+0.05), t1-0.16),
                0.055, mats["red"], boat_root, vertices=10)

    # Passenger floor remains level but no longer dominates the shell.
    length = _ship_length(g); half_w = float(g["shipHalfWidth"])
    deck_z = float(g["shipDeckZ"]) - 0.02
    fw.box("CHR_V9_Deck", (0,0,deck_z), (length*0.60, half_w*1.42, 0.14),
           mats["woodDark"], 0.012, boat_root)
    return hull


def _build_prow_and_stern(boat_root, g, mats):
    half = _ship_length(g)*0.5
    # Bow: continuous S-like stepped stem ending in an original angular beast head.
    pts = [
        (half*0.90,0,0.55), (half*0.99,0,1.35),
        (half*1.045,0,2.05), (half*1.105,0,2.58)
    ]
    for i in range(len(pts)-1):
        beam_between(f"CHR_V9_BowStem_{i}", pts[i], pts[i+1],
                     0.20-i*0.025, 0.26-i*0.02,
                     mats["woodLight"] if i<2 else mats["woodDark"], boat_root, 0.014)
    fw.box("CHR_V9_BowHead", (half*1.135,0,2.63), (0.58,0.42,0.34), mats["woodLight"], 0.020, boat_root)
    beam_between("CHR_V9_BowSnout", (half*1.15,0,2.61), (half*1.205,-0.02,2.48),
                 0.13,0.18,mats["gold"],boat_root,0.010)
    # Small horns make the prow readable without copying any reference model.
    for ys in (-1.0,1.0):
        beam_between(f"CHR_V9_BowHorn_{'N' if ys<0 else 'F'}",
                     (half*1.12,ys*0.16,2.78), (half*1.075,ys*0.30,3.08),
                     0.055,0.065,mats["white"],boat_root,0.006)

    # Stern: raised curling fork, clearly different from bow but equally tall.
    beam_between("CHR_V9_SternStemA", (-half*0.90,0,0.50), (-half*1.00,0,1.34),
                 0.20,0.26,mats["woodLight"],boat_root,0.014)
    beam_between("CHR_V9_SternStemB", (-half*1.00,0,1.34), (-half*1.055,0,2.15),
                 0.16,0.22,mats["woodDark"],boat_root,0.012)
    for ys in (-1.0,1.0):
        beam_between(f"CHR_V9_SternFork_{'N' if ys<0 else 'F'}",
                     (-half*1.05,0,2.08), (-half*1.10,ys*0.30,2.62),
                     0.105,0.12,mats["woodDark"],boat_root,0.009)


def _section_at(g, x):
    return min(hull_sections(g), key=lambda s: abs(s[0]-x))


def _build_shields(boat_root, g, mats):
    length = _ship_length(g)
    xs = [length*t for t in (-0.30,-0.20,-0.10,0.0,0.10,0.20,0.30)]
    palette = ("red","white","gold","red","white","gold","red")
    for side,label in ((-1.0,"Near"),(1.0,"Far")):
        for i,(x,key) in enumerate(zip(xs,palette)):
            _x,w,top,mid,_ = _section_at(g,x)
            y = side*(w+0.13); z = top + (mid-top)*0.48
            fw.cylinder(f"CHR_V9_Shield_{label}_{i:02d}", (x,y,z), 0.43,0.085,
                        mats[key], rotation=(math.radians(90),0,0), parent=boat_root, vertices=24)
            fw.cylinder(f"CHR_V9_ShieldBoss_{label}_{i:02d}", (x,y+side*0.065,z), 0.105,0.075,
                        mats["steelMid"], rotation=(math.radians(90),0,0), parent=boat_root, vertices=16)


def _build_seating(boat_root, g, mats):
    rows = 10
    length = _ship_length(g); half_w=float(g["shipHalfWidth"])
    span = length*0.55
    for i in range(rows):
        x = -span*0.5 + span*i/(rows-1)
        fw.box(f"CHR_V9_SeatFrame_{i:02d}",(x,0,-1.11),(0.44,half_w*1.30,0.08),mats["steelDark"],0.008,boat_root)
        fw.box(f"CHR_V9_Seat_{i:02d}",(x,0,-1.01),(0.39,half_w*1.22,0.075),mats["seatRed"],0.009,boat_root)
        fw.box(f"CHR_V9_Back_{i:02d}",(x+0.14,0,-0.79),(0.075,half_w*1.20,0.34),mats["woodLight"],0.008,boat_root)
        fw.cylinder_between(f"CHR_V9_Bar_{i:02d}",(x-0.06,-half_w*0.56,-0.68),(x-0.06,half_w*0.56,-0.68),
                            0.030,mats["steelLight"],boat_root,vertices=10)


# Reuse V5/V7 suspension but replace all ship-specific geometry.
import viking_ship_rebuild_v5_geometry as v5
v5.hull_sections = hull_sections
v5._build_city_horizon_hull = _build_hull
v5._build_city_horizon_prows = _build_prow_and_stern
v5._build_city_horizon_seating = _build_seating


def build_swing_group(root, g, mats):
    pivot = v5.build_swing_group(root,g,mats)
    boat_root = bpy.data.objects.get("BoatRoot")
    if boat_root is None:
        raise RuntimeError("CH_VIKING_V9_BOAT_ROOT_MISSING")
    _build_shields(boat_root,g,mats)
    boat_root["hullRevision"] = "CH_VIKING_SHIP_OVERHAUL_V9"
    boat_root["visualGoal"] = "deep_curved_longship_pointed_high_ends_dense_viking_detail"
    boat_root["shipBodyOverhaul"] = True
    return pivot
