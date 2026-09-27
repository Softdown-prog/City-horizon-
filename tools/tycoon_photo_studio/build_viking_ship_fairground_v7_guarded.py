"""Guarded V7 entrypoint for the tall fairground Viking ship detail pass."""
from __future__ import annotations

import json
from pathlib import Path

import bpy

import build_viking_ship_guarded as base
import build_viking_ship_fairground_v6_guarded as v6
import viking_ship_fairground_v7_geometry as v7


_original_build_for_gate = v6._original_build_for_gate
_original_write_metadata = v6._original_write_metadata


def _build_base(root, geometry, materials):
    return v7.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return v7.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return v7.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return v7.build_swing_group(root, geometry, materials, base)


base.hull_sections = v7.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _build_for_gate_v7(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V7 requires IdleLightOverlay")

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
    root["fairgroundV7"] = True
    root["ticketBoothIncluded"] = False
    root["restPlatformGapWorld"] = clearance["restPlatformGapWorld"]
    root["swingPlatformGapWorld"] = clearance["swingPlatformGapWorld"]
    root["clearanceReviewDegrees"] = clearance["reviewDegrees"]
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v7(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v7_fairground_detail"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_fairground_v7_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_fairground_v7_geometry.py"
    payload["clearance"] = v6._clearance_report(recipe)
    payload["reviewTargets"] = recipe.get("reviewTargets")
    payload["v7Corrections"] = [
        "keep the V6 tall heavy support proportions and clearance gate",
        "add rear travelling-fair artwork panel behind the swing plane",
        "add stronger lower support gussets so the frame reads as engineered machinery",
        "add taller Viking bow and stern ornaments",
        "add broad red white black amusement-ride hull fascia and larger side shields",
        "preserve separate idle-light and motion overlays",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v7
base.write_metadata = _write_metadata_v7

if __name__ == "__main__":
    base.main()
