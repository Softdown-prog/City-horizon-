"""Guarded V8 entrypoint for Viking ship boat/platform micro-details."""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_fairground_v6_guarded as v6
import viking_ship_fairground_v8_geometry as v8


_original_build_for_gate = v6._original_build_for_gate
_original_write_metadata = v6._original_write_metadata


def _build_base(root, geometry, materials):
    return v8.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return v8.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return v8.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return v8.build_swing_group(root, geometry, materials, base)


base.hull_sections = v8.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _build_for_gate_v8(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V8 requires IdleLightOverlay")

    clearance = v6._clearance_report(recipe)
    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MULTI_OVERLAY_V1"
    root["referenceGroundedGeometry"] = True
    root["fairgroundV8"] = True
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = clearance["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = clearance["swingPlatformGapWorld"]
    root["clearanceReviewDegrees"] = clearance["reviewDegrees"]
    root["microDetailRecipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.microdetail_v8.json"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v8(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v8_boat_platform_microdetail"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_fairground_v8_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_fairground_v8_geometry.py"
    payload["microDetailRecipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_5x4.microdetail_v8.json"
    payload["clearance"] = v6._clearance_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["v8Corrections"] = [
        "preserve the approved V7/V6 height and mechanical clearance",
        "add wood plank seams, top rails, studs and gold rivets to the ship sides",
        "add small seat-end metallic caps without exposing the bench stack",
        "add platform deck seams, service hatches and fairground edge stripes",
        "add heavy bolted support base plates",
        "add anti-slip stair tread strips and boarding gate posts",
        "preserve separate idle-light and motion overlays",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v8
base.write_metadata = _write_metadata_v8

if __name__ == "__main__":
    base.main()
