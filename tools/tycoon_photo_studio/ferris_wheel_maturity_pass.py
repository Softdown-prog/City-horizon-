"""Visual maturity pass for the City Horizon Ferris wheel.

The runtime asset remains a 2D RGBA pre-render. This pass deliberately changes
only large, gameplay-readable forms: more open cabins, restrained bevels and a
slightly more fabricated/industrial silhouette. No micro-detail is added.
"""
from __future__ import annotations


def _set_bevel(obj, width):
    for modifier in obj.modifiers:
        if modifier.type == "BEVEL":
            modifier.width = float(width)
            modifier.segments = 2


def _open_gondola_bodies(gondola_pivots, g, mats, fw):
    """Turn the colored cube into a lower tub with an open passenger area."""
    w = float(g["gondolaWidth"])
    d = float(g["gondolaDepth"])
    h = float(g["gondolaBodyHeight"])
    drop = float(g["gondolaDrop"])
    body_z = -drop - h * 0.48

    tub_h = h * 0.62
    tub_z = body_z - h * 0.12
    post_h = h * 0.72
    post_z = body_z + h * 0.47

    for i, pivot in enumerate(gondola_pivots):
        body = fw.bpy.data.objects.get(f"GondolaBody_{i:02d}") if hasattr(fw, "bpy") else None
        if body is None:
            import bpy
            body = bpy.data.objects.get(f"GondolaBody_{i:02d}")
        if body is None:
            raise RuntimeError(f"FERRIS_MATURITY_MISSING_GONDOLA_BODY_{i:02d}")

        body.dimensions = (w, d, tub_h)
        body.location.z = tub_z
        _set_bevel(body, min(0.055, w * 0.065))

        # Rear roof posts complete the open-air cabin silhouette. The existing
        # front posts remain from the base builder, so the passenger area reads
        # as a framed cabin instead of a rounded toy block.
        rear_y = d * 0.44
        for side, x in (("L", -w * 0.39), ("R", w * 0.39)):
            fw.cylinder(
                f"GondolaRearPost_{i:02d}_{side}",
                (x, rear_y, post_z),
                0.028,
                post_h,
                mats["frame"],
                parent=pivot,
                vertices=12,
            )

        roof = None
        try:
            import bpy
            roof = bpy.data.objects.get(f"GondolaRoof_{i:02d}")
        except Exception:
            roof = None
        if roof is not None:
            _set_bevel(roof, min(0.040, w * 0.05))


def _restrain_soft_edges():
    """Reduce over-rounded edges on large manufactured pieces."""
    import bpy

    prefixes = (
        "LoadingPlatform",
        "BaseBeam_",
        "Foot_",
        "OperatorConsoleBody",
        "PlatformCurb_",
    )
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if obj.name.startswith(prefixes):
            _set_bevel(obj, 0.035)


def apply_maturity_pass(root, rotor, gondola_pivots, g, mats, fw):
    _open_gondola_bodies(gondola_pivots, g, mats, fw)
    _restrain_soft_edges()
    root["maturityPass"] = "FERRIS_2D_MATURITY_V1"
    root["maturityPolicy"] = "open_cabins_restrained_bevels_gameplay_readable"
