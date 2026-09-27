"""Guarded CH Blender review build for the curved Viking ship V7 refinement."""
from __future__ import annotations

import json
from pathlib import Path

import build_viking_ship_guarded as base
import build_viking_ship_rebuild_v5_guarded as v5gate
import viking_ship_rebuild_v7_curved_geometry as rebuild


# Reuse the approved V5/V6 static quality gate, but point every geometry lookup to
# the new curved longship pass.  This keeps site/frame/material constraints intact.
v5gate.rebuild = rebuild
base.hull_sections = rebuild.hull_sections
base.build_base = rebuild.build_base
base.build_supports = rebuild.build_supports
base.build_loading_zone = rebuild.build_loading_zone
base.build_swing_group = rebuild.build_swing_group

_original_v5_build_for_gate = base.build_for_gate
_original_v5_write_metadata = base.write_metadata


def _build_for_gate_v7(args):
    result = _original_v5_build_for_gate(args)
    recipe, studio, scene, root, pivot, ground, authored, out = result
    root["hullRevision"] = "CH_VIKING_CURVED_LONGSHIP_V7"
    root["revisionIntent"] = "stretch hull and strengthen bow-to-stern arc"
    root["parametricAuthoring"] = "CH_PARAMETRIC_AUTHORING_V1"
    return recipe, studio, scene, root, pivot, ground, authored, out


def _write_metadata_v7(recipe, scene, out):
    _original_v5_write_metadata(recipe, scene, out)
    path = Path(out) / "studio_metadata.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["stage"] = "curved_longship_static_art_gate_v7"
    payload["builder"] = "tools/tycoon_photo_studio/build_viking_ship_rebuild_v7_curved_guarded.py"
    payload["geometryPass"] = "tools/tycoon_photo_studio/viking_ship_rebuild_v7_curved_geometry.py"
    payload["hullRevision"] = "CH_VIKING_CURVED_LONGSHIP_V7"
    payload["revisionIntent"] = "longer hull, stronger sheer/keel arc, curved external bands"
    payload["parametricAuthoring"] = {
        "contract": "CH_PARAMETRIC_AUTHORING_V1",
        "nonDestructiveHullSurfaceStage": true,
        "deterministicGeneratorSeed": 7007,
        "runtimeRepresentation": "2D_RGBA_pre_rendered"
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


base.build_for_gate = _build_for_gate_v7
base.write_metadata = _write_metadata_v7


if __name__ == "__main__":
    base.main()
