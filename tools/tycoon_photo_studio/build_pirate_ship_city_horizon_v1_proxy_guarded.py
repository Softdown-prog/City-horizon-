#!/usr/bin/env python3
"""Guarded CH Blender SOUTH proxy for the new City Horizon Pirate Ship.

This is intentionally an art gate, not a runtime promotion.  It reuses the
mature Viking-ship authoring harness only for camera/preflight/render mechanics,
while replacing the visible ride geometry with the original Pirate Ship V1
pass.  Final four-direction and swing-frame baking remains blocked until the
SOUTH proxy is reviewed.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import pirate_ship_city_horizon_v1_geometry as design


DESIGN_CONTRACT = "CH_PIRATE_SHIP_CITY_HORIZON_V1"
AUTHORING_ASSET_ID = "attraction.park_pirate_ship.city_horizon_01"

base.hull_sections = design.hull_sections
base.build_base = design.build_base
base.build_supports = design.build_supports
base.build_loading_zone = design.build_loading_zone
base.build_swing_group = design.build_swing_group

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata
_original_parse_args = base.parse_args


def _parse_args_proxy_only():
    args = _original_parse_args()
    if args.stage == "final":
        raise RuntimeError(
            "CH_PIRATE_SHIP_V1_REVIEW_GATE: final bake is blocked until the SOUTH proxy is approved"
        )
    return args


def _build_for_gate_v1(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["designContract"] = DESIGN_CONTRACT
    root["authoringAssetId"] = AUTHORING_ASSET_ID
    root["artGate"] = "south_proxy_before_four_direction_bake"
    root["legacyVikingGeometryReused"] = False
    root["mechanicsHarnessReused"] = True
    root["referencePolicy"] = "photos_for_mechanical_readability_only_no_geometry_copy"
    root["runtimePromoted"] = False
    pivot["movingAssembly"] = "ship_suspension_passengers_future_overlay"
    pivot["fixedAssemblySeparated"] = True
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v1(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update({
        "stage": "pirate_ship_city_horizon_v1_south_art_gate",
        "builder": "tools/tycoon_photo_studio/build_pirate_ship_city_horizon_v1_proxy_guarded.py",
        "geometryPass": "tools/tycoon_photo_studio/pirate_ship_city_horizon_v1_geometry.py",
        "designContract": DESIGN_CONTRACT,
        "authoringAssetId": AUTHORING_ASSET_ID,
        "reviewOnly": True,
        "proxyDirection": "south",
        "finalFourDirectionBake": False,
        "runtimePromoted": False,
        "requiresHumanApproval": True,
        "designNotes": [
            "open continuous passenger hull",
            "raised bow and stern without Viking dragon/shield language",
            "eight transverse seat rows with restraints",
            "large A-frame and visible transverse axle",
            "fixed support assembly separated from SwingPivot moving assembly",
            "dark timber, deep red and restrained gold/metal accents",
        ],
    })
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.parse_args = _parse_args_proxy_only
base.build_for_gate = _build_for_gate_v1
base.write_metadata = _write_metadata_v1

if __name__ == "__main__":
    base.main()
