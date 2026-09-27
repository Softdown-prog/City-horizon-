"""Guarded CH Blender review build for Viking ship V11 readability pass."""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v5_guarded as v5gate
import viking_ship_rebuild_v11_readability_geometry as rebuild

v5gate.rebuild = rebuild
base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group

_original_build_for_gate = base.build_for_gate
_original_write_metadata = base.write_metadata


def _build_for_gate_v11(args):
    result = _original_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["hullRevision"] = "CH_VIKING_READABILITY_V11"
    root["revisionIntent"] = "improve ride-cabin hierarchy and gameplay readability without copying reference geometry"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v11(recipe, scene, out):
    _original_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "viking_readability_static_art_gate_v11"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v11_readability_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v11_readability_geometry.py"
    payload["hullRevision"] = "CH_VIKING_READABILITY_V11"
    payload["revisionIntent"] = "raised compact seats, framed passenger well, stronger gunwale and clearer interior hierarchy"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v11
base.write_metadata = _write_metadata_v11

if __name__ == "__main__":
    base.main()
