"""Guarded CH Blender review build for Viking ship V9 major ship overhaul."""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v5_guarded as v5gate
import viking_ship_rebuild_v9_ship_overhaul_geometry as rebuild

v5gate.rebuild = rebuild
base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_for_gate_v9(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["hullRevision"] = "CH_VIKING_SHIP_OVERHAUL_V9"
    root["revisionIntent"] = "major rebuild of suspended ship body: deeper hull, higher tapered ends, stronger Viking identity"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v9(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "viking_ship_body_overhaul_static_art_gate_v9"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v9_ship_overhaul_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v9_ship_overhaul_geometry.py"
    payload["hullRevision"] = "CH_VIKING_SHIP_OVERHAUL_V9"
    payload["revisionIntent"] = "deeper faceted clinker hull, pointed raised bow/stern, larger shields, denser passenger deck"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v9
base.write_metadata = _write_metadata_v9

if __name__ == "__main__":
    base.main()
