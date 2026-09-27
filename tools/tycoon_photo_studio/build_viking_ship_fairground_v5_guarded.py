"""Guarded V5 entrypoint for the real-fairground Viking ship rebuild."""
from __future__ import annotations

import json
import bpy

import build_viking_ship_guarded as base
import viking_ship_imposing_geometry as legacy
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


def _build_for_gate_v5(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)
    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V5 requires IdleLightOverlay")

    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    root["runtimeLayerContract"] = "CH_ATTRACTION_MULTI_OVERLAY_V1"
    root["referenceGroundedGeometry"] = True
    root["fairgroundV5"] = True
    root["ticketBoothIncluded"] = False
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v5(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = out / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v5_real_fairground_rebuild"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_fairground_v5_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_fairground_v5_geometry.py"
    payload["v5Corrections"] = [
        "remove giant roof-like axle visual dominance",
        "use compact bearing housings and a narrow axle",
        "keep two clean tall open A-frames",
        "replace criss-cross web with leg-following yellow inner members",
        "lengthen and deepen the passenger ship",
        "raise bow and stern walls so seats sit inside the hull",
        "use long steep hanger pairs to widely spaced ship joints",
        "keep raised loading platform and idle-light overlay",
    ]
    payload["finalSwingFramesDefined"] = False
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v5
base.write_metadata = _write_metadata_v5

if __name__ == "__main__":
    base.main()
