"""Guarded first gate for the from-scratch Viking ship rebuild.

This entrypoint intentionally replaces every ride-specific geometry callback from the
legacy Viking-ship builder with viking_ship_rebuild_v1_geometry.  The shared builder
is kept only for CH Blender scene setup, materials, preflight and proxy export.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import viking_ship_rebuild_v1_geometry as rebuild


_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_base(root, geometry, materials):
    return rebuild.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return rebuild.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return rebuild.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return rebuild.build_swing_group(root, geometry, materials)


base.hull_sections = rebuild.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _mechanical_report(recipe):
    g = recipe["geometry"]
    pivot_z = float(g["pivotZ"])
    boat_drop = float(g["boatDrop"])
    platform_z = float(g["platformTopZ"])
    base_width = float(g["baseWidth"])
    support_width = float(g["supportBeamWidth"])
    review_deg = float(g["clearanceReviewDegrees"])

    min_pivot = float(g["minimumPivotZ"])
    min_beam = float(g["minimumSupportBeamWidth"])
    min_ratio = float(g["minimumSupportHeightToBaseWidthRatio"])
    min_rest = float(g["minimumRestHullGapWorld"])
    min_swing = float(g["minimumSwingClearanceWorld"])

    ratio = pivot_z / base_width
    if pivot_z < min_pivot:
        raise RuntimeError(
            f"CH_VIKING_REBUILD_HEIGHT_FAIL: pivotZ={pivot_z:.3f} < required={min_pivot:.3f}"
        )
    if support_width < min_beam:
        raise RuntimeError(
            f"CH_VIKING_REBUILD_BEAM_FAIL: supportBeamWidth={support_width:.3f} < required={min_beam:.3f}"
        )
    if ratio < min_ratio:
        raise RuntimeError(
            f"CH_VIKING_REBUILD_PROPORTION_FAIL: pivot/base ratio={ratio:.3f} < required={min_ratio:.3f}"
        )

    sections = rebuild.hull_sections(g)
    bottom_points = [(float(x), float(bottom_z)) for x, _w, _top, _mid, bottom_z in sections]
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
    if rest_gap < min_rest:
        raise RuntimeError(
            f"CH_VIKING_REBUILD_REST_CLEARANCE_FAIL: gap={rest_gap:.3f} < required={min_rest:.3f}"
        )
    if swing_gap < min_swing:
        raise RuntimeError(
            f"CH_VIKING_REBUILD_SWING_CLEARANCE_FAIL: gap={swing_gap:.3f} < required={min_swing:.3f} "
            f"at {swing_angle:.1f}deg"
        )

    return {
        "pivotZ": pivot_z,
        "boatDrop": boat_drop,
        "platformTopZ": platform_z,
        "supportBeamWidth": support_width,
        "supportHeightToBaseWidthRatio": ratio,
        "reviewDegrees": review_deg,
        "restLowestHullZ": rest_lowest,
        "restPlatformGapWorld": rest_gap,
        "swingLowestHullZ": swing_lowest,
        "swingPlatformGapWorld": swing_gap,
        "swingWorstAngleDegrees": swing_angle,
        "swingWorstHullX": swing_x,
        "minimumPivotZ": min_pivot,
        "minimumSupportBeamWidth": min_beam,
        "minimumSupportHeightToBaseWidthRatio": min_ratio,
        "minimumRestHullGapWorld": min_rest,
        "minimumSwingClearanceWorld": min_swing,
        "passed": True,
    }


def _build_for_gate_rebuild(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    report = _mechanical_report(recipe)
    overlay = bpy.data.objects.get("IdleLightOverlay")

    for obj in authored:
        if overlay is not None and base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MULTI_OVERLAY_V1"
    root["fromScratchRebuild"] = True
    root["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V1"
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = report["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = report["swingPlatformGapWorld"]
    root["clearanceReviewDegrees"] = report["reviewDegrees"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_rebuild(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "from_scratch_rebuild_v1_structural_gate"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v1.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v1_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v1_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V1"
    payload["fromScratch"] = True
    payload["mechanicalGate"] = _mechanical_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["geometryReusedFromV9"] = False
    payload["firstGateFocus"] = [
        "much taller open A-frame",
        "larger square primary support steel",
        "long rectangular suspension arms",
        "ship visibly suspended above platform",
        "wide heavy support stance",
        "5x4 footprint retained",
        "no dense micro-detail until proportion approval"
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_rebuild
base.write_metadata = _write_metadata_rebuild

if __name__ == "__main__":
    base.main()
