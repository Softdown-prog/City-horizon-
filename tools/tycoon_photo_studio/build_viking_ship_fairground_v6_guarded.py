"""Guarded V6 entrypoint for the tall heavy fairground Viking ship.

V6 fixes the specific failure from earlier passes: pivot height and boat drop were
previously increased together, so the ship stayed visually too low. This gate raises
the structure substantially, keeps the boat visibly suspended, and rejects geometry
that would approach the platform at the configured swing-review angle.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import viking_ship_fairground_v5_geometry as v5

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_base(root, geometry, materials):
    return v5.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return v5.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return v5.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return v5.build_swing_group(root, geometry, materials, base)


base.hull_sections = v5.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _clearance_report(recipe):
    g = recipe["geometry"]
    pivot_z = float(g["pivotZ"])
    boat_drop = float(g["boatDrop"])
    platform_z = float(g.get("platformTopZ", 0.0))
    review_deg = float(g.get("clearanceReviewDegrees", 55.0))
    min_rest = float(g.get("minimumRestHullGapWorld", 0.0))
    min_swing = float(g.get("minimumSwingClearanceWorld", 0.0))

    sections = v5.hull_sections(g)
    bottom_points = [(float(x), float(bottom_z)) for x, _half_w, _top_z, _mid_z, bottom_z in sections]

    rest_lowest = min(pivot_z - boat_drop + z for _x, z in bottom_points)
    rest_gap = rest_lowest - platform_z

    swing_lowest = float("inf")
    swing_angle = 0.0
    swing_x = 0.0
    for degrees in (-review_deg, review_deg):
        angle = math.radians(degrees)
        s = math.sin(angle)
        c = math.cos(angle)
        for x, z in bottom_points:
            local_z = z - boat_drop
            rotated_z = -x * s + local_z * c
            world_z = pivot_z + rotated_z
            if world_z < swing_lowest:
                swing_lowest = world_z
                swing_angle = degrees
                swing_x = x

    swing_gap = swing_lowest - platform_z
    report = {
        "pivotZ": pivot_z,
        "boatDrop": boat_drop,
        "platformTopZ": platform_z,
        "reviewDegrees": review_deg,
        "restLowestHullZ": rest_lowest,
        "restPlatformGapWorld": rest_gap,
        "swingLowestHullZ": swing_lowest,
        "swingPlatformGapWorld": swing_gap,
        "swingWorstAngleDegrees": swing_angle,
        "swingWorstHullX": swing_x,
        "minimumRestHullGapWorld": min_rest,
        "minimumSwingClearanceWorld": min_swing,
        "passed": rest_gap >= min_rest and swing_gap >= min_swing,
    }
    if rest_gap < min_rest:
        raise RuntimeError(
            f"CH_VIKING_REST_CLEARANCE_FAIL: gap={rest_gap:.3f} < required={min_rest:.3f}"
        )
    if swing_gap < min_swing:
        raise RuntimeError(
            f"CH_VIKING_SWING_CLEARANCE_FAIL: gap={swing_gap:.3f} < required={min_swing:.3f} "
            f"at {swing_angle:.1f}deg"
        )
    return report


def _build_for_gate_v6(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V6 requires IdleLightOverlay")

    clearance = _clearance_report(recipe)
    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MULTI_OVERLAY_V1"
    root["referenceGroundedGeometry"] = True
    root["fairgroundV6"] = True
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = clearance["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = clearance["swingPlatformGapWorld"]
    root["clearanceReviewDegrees"] = clearance["reviewDegrees"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v6(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v6_tall_heavy_clearance"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_fairground_v6_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_fairground_v5_geometry.py"
    payload["clearance"] = _clearance_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["v6Corrections"] = [
        "raise pivot without preserving the old low boat height",
        "make primary A-frame square steel substantially thicker",
        "keep the ship visibly suspended above the platform at rest",
        "hard-fail rest and +/- review-angle platform clearance",
        "retain the clean real-fairground V5 boat and bearing silhouette",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v6
base.write_metadata = _write_metadata_v6

if __name__ == "__main__":
    base.main()
