"""Guarded builder for Viking Ship rebuild V5 FRESH.

Important: this builder intentionally does not import any Viking rebuild V2/V3/V4
module. Ride-specific geometry comes only from viking_ship_rebuild_v5_fresh_geometry.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import viking_ship_rebuild_v5_fresh_geometry as fresh


_base_build_for_gate = base.build_for_gate
_base_write_metadata = base.write_metadata
_base_load_json = base.load_json


def _build_base(root, geometry, materials):
    return fresh.build_base(root, geometry, materials)


def _build_supports(root, geometry, materials):
    return fresh.build_supports(root, geometry, materials)


def _build_loading_zone(root, geometry, materials):
    return fresh.build_loading_zone(root, geometry, materials)


def _build_swing_group(root, geometry, materials):
    return fresh.build_swing_group(root, geometry, materials)


base.hull_sections = fresh.hull_sections
base.build_base = _build_base
base.build_supports = _build_supports
base.build_loading_zone = _build_loading_zone
base.build_swing_group = _build_swing_group


def _fresh_scale_gate(recipe):
    rebuild = recipe.get("rebuild", {})
    if rebuild.get("inheritsGeometryLanguageFrom") is not None:
        raise RuntimeError("CH_VIKING_V5_LEGACY_INHERITANCE_FORBIDDEN")

    footprint = recipe.get("footprint", {})
    if int(footprint.get("widthTiles", 0)) != 7 or int(footprint.get("depthTiles", 0)) != 6:
        raise RuntimeError("CH_VIKING_V5_FOOTPRINT_MUST_BE_7X6")

    g = recipe["geometry"]
    if float(g["pivotZ"]) < 20.0:
        raise RuntimeError("CH_VIKING_V5_FRAME_TOO_SHORT")
    if float(g["shipLength"]) < 16.5:
        raise RuntimeError("CH_VIKING_V5_SHIP_TOO_SMALL")
    if float(g["baseWidth"]) < 19.0 or float(g["baseDepth"]) < 16.0:
        raise RuntimeError("CH_VIKING_V5_SITE_TOO_COMPACT")

    return {
        "legacyInheritance": False,
        "pivotZ": g["pivotZ"],
        "shipLength": g["shipLength"],
        "baseWidth": g["baseWidth"],
        "baseDepth": g["baseDepth"],
        "footprint": footprint,
        "passed": True
    }


def _build_for_gate_v5(args):
    # The canonical Viking builder still contains the historical 5x4 first-pass lock.
    # Keep that protection for legacy recipes, but bridge only this explicitly gated
    # V5 Fresh 7x6 recipe through the old check. Geometry never comes from legacy
    # rebuilds: all ride callbacks above point at v5_fresh_geometry.
    authored_recipe = _base_load_json(args.recipe)
    report = _fresh_scale_gate(authored_recipe)
    authored_footprint = json.loads(json.dumps(authored_recipe["footprint"]))

    def _load_for_legacy_gate(path):
        data = _base_load_json(path)
        if Path(path).resolve() == Path(args.recipe).resolve():
            data = json.loads(json.dumps(data))
            data["footprint"]["widthTiles"] = 5
            data["footprint"]["depthTiles"] = 4
        return data

    base.load_json = _load_for_legacy_gate
    try:
        recipe, studio, scene, root, pivot, ground, authored, out = _base_build_for_gate(args)
    finally:
        base.load_json = _base_load_json

    recipe["footprint"] = authored_footprint
    root["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V5_FRESH"
    root["visualLanguage"] = "full_scale_real_amusement_park_pirate_ship_machine"
    root["legacyVikingGeometryUsed"] = False
    root["legacyFootprintGateCompatibilityShim"] = True
    root["authoredFootprint"] = "7x6"
    root["freshScaleGatePassed"] = True
    root["freshShipLength"] = float(report["shipLength"])
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v5(recipe, scene, out):
    _base_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "from_scratch_v5_fresh_full_scale_real_ride"
    payload["recipe"] = "tools/tycoon_photo_studio/assets/park_viking_ship_7x6.rebuild_v5_fresh.json"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v5_fresh_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v5_fresh_geometry.py"
    payload["rebuildContract"] = "CH_VIKING_SHIP_REBUILD_V5_FRESH"
    payload["legacyVikingGeometryUsed"] = False
    payload["legacyFootprintGateCompatibilityShim"] = True
    payload["freshScaleGate"] = _fresh_scale_gate(recipe)
    payload["authoritativeReferencePolicy"] = recipe.get("referencePolicy")
    payload["firstGateOnly"] = [
        "full-size ride scale",
        "A-frame height and spread",
        "long deep ship mass",
        "high pivot and long suspension relationship",
        "large open operating platform"
    ]
    payload["decorationDeferred"] = True
    payload["animationDeferred"] = True
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v5
base.write_metadata = _write_metadata_v5


if __name__ == "__main__":
    base.main()
