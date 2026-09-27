"""Guarded V9 entrypoint for Viking ship fairground finish detail."""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_fairground_v6_guarded as v6
import viking_ship_fairground_v9_geometry as v9


_original_build_for_gate = v6._original_build_for_gate
_original_write_metadata = v6._original_write_metadata


def _build_base(root, geometry, materials):
    return v9.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return v9.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return v9.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return v9.build_swing_group(root, geometry, materials, base)


base.hull_sections = v9.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _build_for_gate_v9(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V9 requires IdleLightOverlay")

    clearance = v6._clearance_report(recipe)
    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MULTI_OVERLAY_V1"
    root["fairgroundV9"] = True
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = clearance["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = clearance["swingPlatformGapWorld"]
    root["clearanceReviewDegrees"] = clearance["reviewDegrees"]
    root["microDetailRecipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.microdetail_v9.json"
    root["minimumReviewDimensionPx"] = 1280
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v9(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v9_fairground_finish_detail"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_fairground_v9_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_fairground_v9_geometry.py"
    payload["microDetailRecipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.microdetail_v9.json"
    payload["clearance"] = v6._clearance_report(recipe)
    payload["v9Corrections"] = [
        "preserve approved height, boat drop, footprint and swing clearance",
        "make rear fairground artwork panel visibly decorated instead of blank",
        "add stronger pivot-hub hardware and visible fasteners",
        "add platform safety, maintenance and perimeter trim details",
        "add additional hull strakes, gold rail, shield rings and seat hardware",
        "preserve separate idle-light and motion overlays",
        "retain 1280px minimum review master and 2048px source rendering"
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v9
base.write_metadata = _write_metadata_v9

if __name__ == "__main__":
    base.main()
