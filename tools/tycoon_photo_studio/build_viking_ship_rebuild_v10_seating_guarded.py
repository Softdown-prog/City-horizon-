"""Guarded CH Blender review build for Viking ship V10 seating realism."""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v5_guarded as v5gate
import viking_ship_rebuild_v10_seating_geometry as rebuild

v5gate.rebuild = rebuild
base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_for_gate_v10(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["hullRevision"] = "CH_VIKING_SEATING_REALISM_V10"
    root["revisionIntent"] = "preserve V9 ship overhaul and substantially improve passenger seating realism"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v10(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "viking_seating_realism_static_art_gate_v10"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v10_seating_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v10_seating_geometry.py"
    payload["hullRevision"] = "CH_VIKING_SEATING_REALISM_V10"
    payload["revisionIntent"] = "paired padded seats, structural mounts, lap bars, foot rails and centre aisle"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v10
base.write_metadata = _write_metadata_v10

if __name__ == "__main__":
    base.main()
