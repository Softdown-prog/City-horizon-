"""Guarded V2 entrypoint for the taller City Park Viking ship.

The V1 builder remains the proven quality-gate implementation. This entrypoint swaps
only the authored geometry/detail pass and then enriches runtime-layer metadata for the
separate idle blinking-light overlay.
"""
from __future__ import annotations

import json

import bpy

import build_viking_ship_guarded as base
import viking_ship_imposing_geometry as imposing


_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_supports(root, geometry, materials):
    return imposing.build_supports(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return imposing.build_swing_group(root, geometry, materials, base)


# Keep V1 quality gates, loading zone, base and established ship detail functions,
# while substituting the requested taller square-steel authoring pass.
base.hull_sections = imposing.hull_sections
base.build_supports = _build_supports
base.build_swing_group = _build_swing_group


def _build_for_gate_v2(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)

    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V2 requires IdleLightOverlay")

    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    layers = recipe.get("runtimeLayers") or {}
    root["runtimeLayerContract"] = layers.get("contract", "CH_ATTRACTION_MULTI_OVERLAY_V1")
    root["motionOverlayRole"] = layers.get("motionOverlay", {}).get("role", "attraction_motion_overlay")
    root["idleLightOverlayRole"] = layers.get("idleLightOverlay", {}).get(
        "role", "attraction_idle_light_overlay"
    )
    root["idleLightOverlayPrepared"] = True
    root["idleLightActiveWhen"] = layers.get("idleLightOverlay", {}).get("activeWhen", "ride_idle")
    root["idleLightDisabledWhen"] = layers.get("idleLightOverlay", {}).get(
        "disabledWhen", "ride_running"
    )
    root["idleLightPattern"] = layers.get("idleLightOverlay", {}).get(
        "pattern", "alternating_groups_a_b"
    )

    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v2(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = out / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v2_imposing_square_steel_idle_lights"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_imposing_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_imposing_geometry.py"
    payload["runtimeLayers"] = recipe.get("runtimeLayers")
    payload["v2ReviewGate"] = {
        "height": "raised_pivot_and_longer_square_hangers",
        "structure": "square_rectangular_steel_primary_members",
        "ship": "deeper_taller_hull",
        "idleLights": "authored_as_separate_runtime_overlay",
        "finalSwingFramesDefined": False,
        "finalBlinkFramesDefined": False,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v2
base.write_metadata = _write_metadata_v2


if __name__ == "__main__":
    base.main()
