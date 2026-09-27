"""Guarded V2 gate for the from-scratch anti-toy Viking ship rebuild.

V2 keeps the tall/open mechanical proportion but adds hard authoring checks against the
plastic/Lego/gumball-prize failure mode: restrained bevels, rough painted steel, rough
timber, square-ish structural members, bolted feet and explicit swing clearance.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import viking_ship_rebuild_v2_geometry as rebuild


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
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    primary_bevel = float(g["primaryBevel"])
    review_deg = float(g["clearanceReviewDegrees"])

    min_pivot = float(g["minimumPivotZ"])
    min_beam = float(g["minimumSupportBeamWidth"])
    min_ratio = float(g["minimumSupportHeightToBaseWidthRatio"])
    min_rest = float(g["minimumRestHullGapWorld"])
    min_swing = float(g["minimumSwingClearanceWorld"])
    max_bevel = float(g["maximumPrimaryBevel"])

    ratio = pivot_z / base_width
    beam_aspect = beam_w / max(beam_d, 1e-6)
    if pivot_z < min_pivot:
        raise RuntimeError(f"CH_VIKING_V2_HEIGHT_FAIL: pivotZ={pivot_z:.3f} < {min_pivot:.3f}")
    if beam_w < min_beam:
        raise RuntimeError(f"CH_VIKING_V2_BEAM_FAIL: supportBeamWidth={beam_w:.3f} < {min_beam:.3f}")
    if ratio < min_ratio:
        raise RuntimeError(f"CH_VIKING_V2_PROPORTION_FAIL: pivot/base={ratio:.3f} < {min_ratio:.3f}")
    if beam_aspect > 1.65:
        raise RuntimeError(f"CH_VIKING_V2_BLOCKY_BEAM_FAIL: width/depth={beam_aspect:.3f} > 1.650")
    if primary_bevel > max_bevel:
        raise RuntimeError(f"CH_VIKING_V2_TOY_BEVEL_FAIL: primaryBevel={primary_bevel:.3f} > {max_bevel:.3f}")

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
            world_z = pivot_z + (-x * s + local_z * c)
            if world_z < swing_lowest:
                swing_lowest = world_z
                swing_angle = degrees
                swing_x = x
    swing_gap = swing_lowest - platform_z
    if rest_gap < min_rest:
        raise RuntimeError(f"CH_VIKING_V2_REST_CLEARANCE_FAIL: gap={rest_gap:.3f} < {min_rest:.3f}")
    if swing_gap < min_swing:
        raise RuntimeError(
            f"CH_VIKING_V2_SWING_CLEARANCE_FAIL: gap={swing_gap:.3f} < {min_swing:.3f} at {swing_angle:.1f}deg"
        )

    mats = recipe["materials"]
    steel = mats["steelBlue"]
    wood = mats["wood"]
    yellow = mats["yellow"]
    if float(steel.get("roughness", 0.0)) < 0.50 or float(steel.get("metallic", 0.0)) < 0.50:
        raise RuntimeError("CH_VIKING_V2_PLASTIC_STEEL_FAIL: painted steel must remain rough and metallic")
    if float(wood.get("roughness", 0.0)) < 0.70:
        raise RuntimeError("CH_VIKING_V2_PLASTIC_WOOD_FAIL: hull timber roughness must be >= 0.70")
    if float(yellow.get("roughness", 0.0)) < 0.55:
        raise RuntimeError("CH_VIKING_V2_CANDY_PAINT_FAIL: secondary fairground paint is too glossy")

    return {
        "pivotZ": pivot_z,
        "boatDrop": boat_drop,
        "platformTopZ": platform_z,
        "supportBeamWidth": beam_w,
        "supportBeamDepth": beam_d,
        "supportBeamAspect": beam_aspect,
        "primaryBevel": primary_bevel,
        "supportHeightToBaseWidthRatio": ratio,
        "reviewDegrees": review_deg,
        "restPlatformGapWorld": rest_gap,
        "swingPlatformGapWorld": swing_gap,
        "swingWorstAngleDegrees": swing_angle,
        "swingWorstHullX": swing_x,
        "paintedSteelRoughness": steel["roughness"],
        "paintedSteelMetallic": steel["metallic"],
        "woodRoughness": wood["roughness"],
        "passed": True
    }


def _build_for_gate_v2(args):
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
    root["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V2"
    root["visualLanguage"] = "stylized_real_fairground_machine_not_toy"
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = report["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = report["swingPlatformGapWorld"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v2(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "from_scratch_rebuild_v2_anti_toy_gate"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v2.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v2_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v2_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V2"
    payload["fromScratch"] = True
    payload["mechanicalAndMaterialGate"] = _mechanical_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["visualLanguage"] = recipe.get("visualLanguage")
    payload["geometryReusedFromRejectedV9"] = False
    payload["firstGateFocus"] = [
        "very tall open A-frame",
        "long visibly mechanical hangers",
        "restrained edge bevels instead of rounded toy blocks",
        "bolted steel foot plates and compact bearing housings",
        "rough painted metal instead of glossy plastic",
        "faceted rough timber hull with plank separation",
        "segmented industrial loading deck",
        "explicit rejection of Lego/gumball-prize/cute-miniature read"
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v2
base.write_metadata = _write_metadata_v2

if __name__ == "__main__":
    base.main()
