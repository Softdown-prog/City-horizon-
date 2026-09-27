"""Guarded V4 gate for the City Horizon Viking ship rebuild.

V4 keeps V3's open 5x4 geometry and V2's anti-toy material checks, then adds the
specific visual corrections requested after the V3 review: larger yellow structural
members, a lower resting ship, and a broader/deeper boarding platform.  Animation
frames remain undefined until this proportion pass is approved.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v3_guarded as v3guard  # installs V3 geometry + gates


_v3_build_for_gate = base.build_for_gate
_v3_write_metadata = base.write_metadata


def _v4_proportion_report(recipe, root):
    g = recipe["geometry"]
    base_w = float(g["baseWidth"])
    base_d = float(g["baseDepth"])
    loading_w = float(g["loadingPlatformWidth"])
    loading_d = float(g["loadingPlatformDepth"])
    inner_w = float(g["innerBraceWidth"])
    swing_w = float(g["swingArmWidth"])
    rest_gap = float(root.get("restPlatformGapWorld", -1.0))
    swing_gap = float(root.get("swingPlatformGapWorld", -1.0))

    min_loading_w = float(g["minimumLoadingWidthUtilization"])
    min_loading_d = float(g["minimumLoadingDepthUtilization"])
    min_inner = float(g["minimumInnerBraceWidth"])
    min_swing = float(g["minimumSwingArmWidth"])
    max_rest = float(g["maximumRestHullGapWorld"])
    min_rest = float(g["minimumRestHullGapWorld"])
    min_swing_clearance = float(g["minimumSwingClearanceWorld"])

    loading_w_util = loading_w / base_w
    loading_d_util = loading_d / base_d

    if inner_w < min_inner:
        raise RuntimeError(
            f"CH_VIKING_V4_YELLOW_INNER_BRACE_TOO_SMALL: {inner_w:.3f} < {min_inner:.3f}"
        )
    if swing_w < min_swing:
        raise RuntimeError(
            f"CH_VIKING_V4_YELLOW_SWING_ARM_TOO_SMALL: {swing_w:.3f} < {min_swing:.3f}"
        )
    if loading_w_util < min_loading_w:
        raise RuntimeError(
            f"CH_VIKING_V4_PLATFORM_WIDTH_FAIL: {loading_w_util:.3f} < {min_loading_w:.3f}"
        )
    if loading_d_util < min_loading_d:
        raise RuntimeError(
            f"CH_VIKING_V4_PLATFORM_DEPTH_FAIL: {loading_d_util:.3f} < {min_loading_d:.3f}"
        )
    if rest_gap < min_rest:
        raise RuntimeError(
            f"CH_VIKING_V4_REST_CLEARANCE_FAIL: {rest_gap:.3f} < {min_rest:.3f}"
        )
    if rest_gap > max_rest:
        raise RuntimeError(
            f"CH_VIKING_V4_BOAT_STILL_TOO_HIGH: {rest_gap:.3f} > {max_rest:.3f}"
        )
    if swing_gap < min_swing_clearance:
        raise RuntimeError(
            f"CH_VIKING_V4_SWING_CLEARANCE_FAIL: {swing_gap:.3f} < {min_swing_clearance:.3f}"
        )

    return {
        "innerBraceWidth": inner_w,
        "minimumInnerBraceWidth": min_inner,
        "swingArmWidth": swing_w,
        "minimumSwingArmWidth": min_swing,
        "loadingWidthUtilization": loading_w_util,
        "minimumLoadingWidthUtilization": min_loading_w,
        "loadingDepthUtilization": loading_d_util,
        "minimumLoadingDepthUtilization": min_loading_d,
        "restPlatformGapWorld": rest_gap,
        "minimumRestHullGapWorld": min_rest,
        "maximumRestHullGapWorld": max_rest,
        "swingPlatformGapWorld": swing_gap,
        "minimumSwingClearanceWorld": min_swing_clearance,
        "passed": True,
    }


def _build_for_gate_v4(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _v3_build_for_gate(args)
    report = _v4_proportion_report(recipe, root)

    root["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V4"
    root["visualLanguage"] = "full_scale_open_5x4_large_yellow_members_lower_ship"
    root["v4LargerYellowMembers"] = True
    root["v4LowerRestingShip"] = True
    root["v4OpenPlatform"] = True
    root["loadingWidthUtilization"] = report["loadingWidthUtilization"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v4(recipe, scene, out):
    _v3_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "from_scratch_rebuild_v4_large_yellow_lower_boat_open_platform"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v4.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v4_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v3_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V4"
    # Reconstruct the root-independent review values from the configured recipe.
    payload["v4Targets"] = {
        "largerYellowInnerBraceWidth": recipe["geometry"]["innerBraceWidth"],
        "largerYellowSwingArmWidth": recipe["geometry"]["swingArmWidth"],
        "boatDrop": recipe["geometry"]["boatDrop"],
        "loadingPlatformWidth": recipe["geometry"]["loadingPlatformWidth"],
        "loadingPlatformDepth": recipe["geometry"]["loadingPlatformDepth"],
        "reviewTargets": recipe.get("reviewTargets"),
    }
    payload["v4Focus"] = [
        "make yellow inner braces visibly larger and structural",
        "make yellow suspension arms visibly larger and structural",
        "lower the boat closer to the deck while preserving positive swing clearance",
        "open the loading platform across most of the 5x4 site",
        "retain V3 full-height illumination and V2 anti-toy material language",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v4
base.write_metadata = _write_metadata_v4


if __name__ == "__main__":
    base.main()
