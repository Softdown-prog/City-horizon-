"""Guarded V3 gate for the open-footprint Viking ship rebuild.

V3 inherits the V2 anti-toy mechanical/material checks, then adds explicit 5x4 site
utilization gates.  It rejects the asset if the front/rear A-frame planes collapse back
toward the boat or if the boarding zone becomes visually cramped.  Ride-specific
geometry is supplied by viking_ship_rebuild_v3_geometry; CH Blender camera/render setup
continues to come from the canonical guarded builder.
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v2_guarded as v2guard  # installs V2 anti-toy gates
import viking_ship_rebuild_v3_geometry as rebuild


_v2_build_for_gate = base.build_for_gate
_v2_write_metadata = base.write_metadata


# Replace only the ride-specific geometry callbacks.  V2's anti-toy material/mechanical
# checks remain active around the canonical scene/preflight pipeline.
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


def _site_utilization_report(recipe):
    g = recipe["geometry"]
    base_width = float(g["baseWidth"])
    base_depth = float(g["baseDepth"])
    half_x = float(g["supportHalfWidth"])
    half_y = float(g["supportHalfDepth"])
    loading_depth = float(g["loadingPlatformDepth"])
    joint_y = float(g.get("boatJointHalfDepth", 0.0))
    ship_half_w = float(g["shipHalfWidth"])

    width_util = (2.0 * half_x) / base_width
    depth_util = (2.0 * half_y) / base_depth
    loading_depth_util = loading_depth / base_depth
    joint_depth_util = joint_y / max(ship_half_w, 1e-6)

    min_depth = float(g["minimumSupportDepthUtilization"])
    min_loading = float(g["minimumLoadingDepthUtilization"])

    if depth_util < min_depth:
        raise RuntimeError(
            f"CH_VIKING_V3_CRAMPED_DEPTH_FAIL: support depth utilization={depth_util:.3f} < {min_depth:.3f}"
        )
    if loading_depth_util < min_loading:
        raise RuntimeError(
            f"CH_VIKING_V3_CRAMPED_LOADING_FAIL: loading depth utilization={loading_depth_util:.3f} < {min_loading:.3f}"
        )
    if joint_depth_util < 0.80:
        raise RuntimeError(
            f"CH_VIKING_V3_NARROW_HANGER_FAIL: joint/boat half-depth={joint_depth_util:.3f} < 0.800"
        )

    return {
        "baseWidth": base_width,
        "baseDepth": base_depth,
        "supportWidthUtilization": width_util,
        "supportDepthUtilization": depth_util,
        "loadingDepthUtilization": loading_depth_util,
        "boatJointDepthUtilization": joint_depth_util,
        "minimumSupportDepthUtilization": min_depth,
        "minimumLoadingDepthUtilization": min_loading,
        "passed": True,
    }


def _build_for_gate_v3(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _v2_build_for_gate(args)
    site = _site_utilization_report(recipe)

    root["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V3"
    root["visualLanguage"] = "stylized_real_fairground_machine_open_5x4_not_cramped"
    root["supportDepthUtilization"] = site["supportDepthUtilization"]
    root["loadingDepthUtilization"] = site["loadingDepthUtilization"]
    root["fullHeightLightingReview"] = True
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v3(recipe, scene, out):
    _v2_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "from_scratch_rebuild_v3_open_site_lighting_gate"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.rebuild_v3.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v3_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v3_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V3"
    payload["siteUtilizationGate"] = _site_utilization_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["visualLanguage"] = recipe.get("visualLanguage")
    payload["v3Focus"] = [
        "use most of the four-tile depth with separated front/rear A-frame planes",
        "widen hanger attachment depth so the boat has visible breathing room",
        "lower cross bracing to preserve an open upper silhouette",
        "expand the loading/boarding zone across the available site",
        "retain V2 anti-toy rough metal and timber language",
        "review with full-height lighting aimed at the upper bearing and hanger system",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v3
base.write_metadata = _write_metadata_v3


if __name__ == "__main__":
    base.main()
