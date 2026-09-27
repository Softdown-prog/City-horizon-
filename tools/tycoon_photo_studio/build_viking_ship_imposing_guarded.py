"""Guarded V3 entrypoint for the reference-grounded City Park Viking ship.

The proven V1 gate remains canonical. This wrapper substitutes only the current
reference-grounded geometry/base/loading pass and enriches metadata for the three
runtime layers: static structure, swinging boat and idle blinking lights.
"""
from __future__ import annotations

import json

import bpy

import build_viking_ship_guarded as base
import viking_ship_imposing_geometry as imposing


_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_base(root, geometry, materials):
    return imposing.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return imposing.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return imposing.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return imposing.build_swing_group(root, geometry, materials, base)


base.hull_sections = imposing.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _build_for_gate_v3(args):
    recipe, studio, scene, root, pivot, ground, authored, out = _original_build_for_gate(args)

    overlay = bpy.data.objects.get("IdleLightOverlay")
    if overlay is None:
        raise RuntimeError("CH_VIKING_IDLE_OVERLAY_MISSING: V3 requires IdleLightOverlay")

    for obj in authored:
        if base._is_descendant_of(obj, overlay):
            obj["runtimeLayer"] = "idle_light_overlay"
        elif base._is_descendant_of(obj, pivot):
            obj["runtimeLayer"] = "motion_overlay"
        else:
            obj["runtimeLayer"] = "static_base"

    layers = recipe.get("runtimeLayers") or {}
    root["runtimeLayerContract"] = layers.get("contract", "CH_ATTRACTION_MULTI_OVERLAY_V1")
    root["motionOverlayRole"] = layers.get("motionOverlay", {}).get(
        "role", "attraction_motion_overlay"
    )
    root["idleLightOverlayRole"] = layers.get("idleLightOverlay", {}).get(
        "role", "attraction_idle_light_overlay"
    )
    root["idleLightOverlayPrepared"] = True
    root["idleLightActiveWhen"] = layers.get("idleLightOverlay", {}).get(
        "activeWhen", "ride_idle"
    )
    root["idleLightDisabledWhen"] = layers.get("idleLightOverlay", {}).get(
        "disabledWhen", "ride_running"
    )
    root["idleLightPattern"] = layers.get("idleLightOverlay", {}).get(
        "pattern", "alternating_groups_a_b"
    )
    root["referenceGroundedGeometry"] = True
    root["ticketBoothIncluded"] = False

    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v3(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = out / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "geometry_proxy_v3_real_ride_reference"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_imposing_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_imposing_geometry.py"
    payload["runtimeLayers"] = recipe.get("runtimeLayers")
    payload["referenceGrounding"] = {
        "source": "user_supplied_real_amusement_park_ship_photos",
        "copiedLiterally": False,
        "ticketBoothIncluded": False,
        "keyReads": [
            "tall_open_A_frame_without_roof_like_crossbeam",
            "blue_square_outer_steel",
            "yellow_inner_truss_bracing",
            "raised_white_loading_platform_with_side_stairs",
            "long_hangers_and_low_boat_rest_position",
            "illuminated_apex_sign_and_leg_bulbs",
            "large_side_decorative_backdrop",
        ],
    }
    payload["v3ReviewGate"] = {
        "silhouette": "travelling_fair_pirate_viking_ship_machine",
        "structure": "tall_A_frame_square_steel_exposed_axle",
        "ship": "deep_brown_longship_with_compartmented_side_fascia",
        "loading": "raised_platform_side_stair_white_railings",
        "idleLights": "separate_cyan_pink_overlay_groups",
        "finalSwingFramesDefined": False,
        "finalBlinkFramesDefined": False,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v3
base.write_metadata = _write_metadata_v3


if __name__ == "__main__":
    base.main()
