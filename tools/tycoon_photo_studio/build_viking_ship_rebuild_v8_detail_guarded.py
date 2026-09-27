"""Guarded CH Blender review build for Viking ship V8 detail refinement."""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v5_guarded as v5gate
import viking_ship_rebuild_v8_detail_geometry as rebuild

v5gate.rebuild = rebuild
base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_for_gate_v8(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["hullRevision"] = "CH_VIKING_LONGSHIP_DETAIL_V8"
    root["revisionIntent"] = "preserve curved V7 hull and improve Viking ride identity/readability"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v8(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "viking_identity_detail_static_art_gate_v8"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v8_detail_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v8_detail_geometry.py"
    payload["hullRevision"] = "CH_VIKING_LONGSHIP_DETAIL_V8"
    payload["revisionIntent"] = "curved hull plus side shields, stronger bow/stern and deck ribs"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v8
base.write_metadata = _write_metadata_v8


if __name__ == "__main__":
    base.main()
