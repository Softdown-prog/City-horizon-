"""Landmark-scale Ferris wheel geometry for City Horizon.

This is a structural rebuild of the approved procedural attraction, not a new
runtime system. CH Blender remains an offline authoring tool and the game still
consumes pre-rendered 2D RGBA sprites.

Design contract:
- two large parallel circular rims;
- cabins suspended between those rims;
- paired front/rear spoke systems with visibly denser radial structure;
- rim cross-members tying both circles together;
- existing loading platform, stairs, guard rails and support frame are preserved
  by the canonical base builder.
"""
from __future__ import annotations

import math


def build_wheel(root, g, mats, fw):
    radius = float(g["wheelRadius"])
    center_z = float(g["wheelCenterZ"])
    ring_r = float(g["ringTubeRadius"])
    spoke_r = float(g["spokeRadius"])
    hub_r = float(g["hubRadius"])
    axle_depth = float(g["axleDepth"])
    ring_half_depth = float(g.get("ringHalfDepth", 0.72))
    cross_member_r = float(g.get("rimCrossMemberRadius", max(0.035, spoke_r * 0.78)))

    rotor = fw.empty("WheelRotor", (0.0, 0.0, center_z), root)

    # Two actual side-by-side wheel circles, rather than concentric circles in
    # the same plane. This gives the attraction the broad mechanical silhouette
    # of a full-size Ferris wheel and leaves a real volume for cabins between.
    fw.torus(
        "WheelOuterRing",
        (0.0, -ring_half_depth, 0.0),
        radius,
        ring_r,
        mats["wheel"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=rotor,
    )
    fw.torus(
        "WheelInnerRing",
        (0.0, ring_half_depth, 0.0),
        radius,
        ring_r,
        mats["wheel"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=rotor,
    )

    # Axle spans beyond both rims so the support frame reads as carrying one
    # broad wheel assembly instead of a thin decorative disc.
    fw.cylinder(
        "WheelHub",
        (0.0, 0.0, 0.0),
        hub_r,
        max(axle_depth, ring_half_depth * 2.35),
        mats["hub"],
        rotation=(math.radians(90.0), 0.0, 0.0),
        parent=rotor,
        vertices=40,
    )

    gondola_pivots = []
    count = int(g["gondolaCount"])
    gondola_drop = float(g["gondolaDrop"])
    accent_cycle = ("accentA", "accentB", "accentC")

    for i in range(count):
        angle = math.tau * i / count
        x = math.sin(angle) * radius
        z = math.cos(angle) * radius

        # Paired spokes on both wheel planes make the radial structure much
        # denser while retaining clean 2D readability after downsample.
        for y, label in ((-ring_half_depth, "Front"), (ring_half_depth, "Rear")):
            fw.cylinder_between(
                f"Spoke_{label}_{i:02d}",
                (0.0, y, 0.0),
                (x, y, z),
                spoke_r,
                mats["wheel"],
                rotor,
                vertices=20,
            )
            fw.cylinder(
                f"RimNode_{label}_{i:02d}",
                (x, y, z),
                ring_r * 1.30,
                0.18,
                mats["hub"],
                rotation=(math.radians(90.0), 0.0, 0.0),
                parent=rotor,
                vertices=18,
            )

        # Cross-member physically ties the two circular rims at every cabin
        # station. This is intentionally chunky enough to survive gameplay scale.
        fw.cylinder_between(
            f"RimCrossMember_{i:02d}",
            (x, -ring_half_depth, z),
            (x, ring_half_depth, z),
            cross_member_r,
            mats["frame"],
            rotor,
            vertices=16,
        )

        # Cabin pivot sits halfway between the two rims. Its hanger drops from
        # the cross-member so the cabin visibly occupies the wheel's central bay.
        pivot = fw.empty(f"GondolaPivot_{i:02d}", (x, 0.0, z), rotor)
        gondola_pivots.append(pivot)
        fw.cylinder(
            f"GondolaHanger_{i:02d}",
            (0.0, 0.0, -gondola_drop * 0.5),
            float(g.get("gondolaHangerRadius", 0.052)),
            gondola_drop,
            mats["hub"],
            parent=pivot,
            vertices=18,
        )

        body_z = -gondola_drop - float(g["gondolaBodyHeight"]) * 0.48
        fw.build_gondola(pivot, i, body_z, g, mats, accent_cycle[i % len(accent_cycle)])

    return rotor, gondola_pivots
