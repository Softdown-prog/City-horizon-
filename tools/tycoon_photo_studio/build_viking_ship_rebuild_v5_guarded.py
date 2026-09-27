"""Guarded static review build for the RCT-reference Viking ship V5.

This is intentionally independent of the older V2/V3/V4 proportion gates.  Those gates
were useful for mechanical clearance, but they also encoded the thick-beam miniature
language now rejected by the user.  V5 keeps only the canonical CH Blender scene and
adds new park-scale/readability gates.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import build_viking_ship_guarded as base
import viking_ship_rebuild_v5_geometry as rebuild


_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group


def _v5_report(recipe):
    if recipe.get("styleContract") != "CH_STYLIZED_PRERENDER_V1":
        raise RuntimeError("CH_VIKING_V5_LEGACY_STYLE_FAIL: miniature style contract is forbidden")

    g = recipe["geometry"]
    mats = recipe["materials"]
    beam_w = float(g["supportBeamWidth"])
    beam_d = float(g["supportBeamDepth"])
    max_beam = float(g["maximumSupportBeamWidth"])
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    pivot_z = float(g["pivotZ"])
    boat_drop = float(g["boatDrop"])
    platform_z = float(g["platformTopZ"])
    review_deg = float(g["clearanceReviewDegrees"])

    if beam_w > max_beam:
        raise RuntimeError(f"CH_VIKING_V5_CHUNKY_FRAME_FAIL: {beam_w:.3f} > {max_beam:.3f}")
    if beam_w / max(beam_d, 1e-6) > 1.60:
        raise RuntimeError("CH_VIKING_V5_BLOCK_PROFILE_FAIL: support profile is too blocky")
    if float(g["primaryBevel"]) > float(g["maximumPrimaryBevel"]):
        raise RuntimeError("CH_VIKING_V5_ROUNDED_TOY_EDGE_FAIL")
    if (2.0 * half_x) / base_w < 0.78:
        raise RuntimeError("CH_VIKING_V5_SITE_WIDTH_FAIL: frame is too compact")
    if (2.0 * half_y) / base_d < float(g["minimumSupportDepthUtilization"]):
        raise RuntimeError("CH_VIKING_V5_SITE_DEPTH_FAIL: frame is too compact")
    if float(g["loadingPlatformDepth"]) / base_d < float(g["minimumLoadingDepthUtilization"]):
        raise RuntimeError("CH_VIKING_V5_QUEUE_DEPTH_FAIL: site does not read as a park ride")

    for key in ("steelDark", "steelMid", "wood", "platformWhite", "panelCream"):
        if float(mats[key].get("roughness", 0.0)) < 0.78:
            raise RuntimeError(f"CH_VIKING_V5_GLOSS_FAIL:{key}")
    if mats["steelDark"]["rgba"][2] > 0.16 or mats["yellow"]["rgba"][0] > 0.45:
        raise RuntimeError("CH_VIKING_V5_CANDY_PALETTE_FAIL")

    points = [(float(x), float(bottom_z)) for x, _w, _top, _mid, bottom_z in rebuild.hull_sections(g)]
    rest_low = min(pivot_z - boat_drop + z for _x, z in points)
    rest_gap = rest_low - platform_z
    if rest_gap < float(g["minimumRestHullGapWorld"]):
        raise RuntimeError(f"CH_VIKING_V5_REST_CLEARANCE_FAIL:{rest_gap:.3f}")
    if rest_gap > float(g["maximumRestHullGapWorld"]):
        raise RuntimeError(f"CH_VIKING_V5_SHIP_TOO_HIGH_FAIL:{rest_gap:.3f}")

    swing_low = float("inf")
    for degrees in (-review_deg, review_deg):
        angle = math.radians(degrees)
        s = math.sin(angle)
        c = math.cos(angle)
        for x, z in points:
            local_z = z - boat_drop
            world_z = pivot_z + (-x * s + local_z * c)
            swing_low = min(swing_low, world_z)
    swing_gap = swing_low - platform_z
    if swing_gap < float(g["minimumSwingClearanceWorld"]):
        raise RuntimeError(f"CH_VIKING_V5_SWING_CLEARANCE_FAIL:{swing_gap:.3f}")

    return {
        "supportBeamWidth": beam_w,
        "supportBeamDepth": beam_d,
        "supportWidthUtilization": (2.0 * half_x) / base_w,
        "supportDepthUtilization": (2.0 * half_y) / base_d,
        "queueDepthUtilization": float(g["loadingPlatformDepth"]) / base_d,
        "restPlatformGapWorld": rest_gap,
        "swingPlatformGapWorld": swing_gap,
        "styleContract": recipe["styleContract"],
        "legacyMiniatureContractPresent": False,
        "passed": True,
    }


def _build_for_gate_v5(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)

    # V5's procedural build_base returns the asset root for composition, while the
    # generic Viking gate expects the returned object itself to be the ground-contact
    # mesh.  Explicitly tag the actual thin foundation so preflight measures Z=0
    # against the ride pad rather than only the elevated A-frame members.
    foundation = base.bpy.data.objects.get("CHR_VikingPadFoundation")
    if foundation is None:
        raise RuntimeError("CH_VIKING_V5_FOUNDATION_MISSING")
    base.scene_gate.tag(foundation, "attraction.base", ground_contact=True)

    report = _v5_report(recipe)
    root["rebuildContract"] = "CH_VIKING_SHIP_RCT_REFERENCE_V1"
    root["visualLanguage"] = "classic_tycoon_park_scale_not_toy"
    root["referenceUse"] = "proportion_site_layout_readability_only"
    root["legacyMiniatureContractPresent"] = False
    root["finalSwingFramesDefined"] = False
    root["restPlatformGapWorld"] = report["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = report["swingPlatformGapWorld"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v5(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "rct_reference_static_art_gate_v5"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v5.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v5_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v5_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_RCT_REFERENCE_V1"
    payload["gate"] = _v5_report(recipe)
    payload["referencePolicy"] = recipe.get("referencePolicy")
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v5
base.write_metadata = _write_metadata_v5


if __name__ == "__main__":
    base.main()
