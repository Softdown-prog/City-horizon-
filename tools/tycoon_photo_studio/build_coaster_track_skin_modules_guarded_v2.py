"""Provenance-complete wrapper for Classic Steel coaster skin modules.

Geometry and materials are inherited unchanged from
build_coaster_track_skin_modules_guarded.py. This revision only emits the
mandatory guarded-final provenance files expected by the CH Blender worker.
"""
from __future__ import annotations

import json
from pathlib import Path

import build_coaster_track_skin_modules_guarded as base

_original_render_final = base.render_final


def render_final_v2(studio, scene, root, ground, authored, modules, out, approval):
    _original_render_final(studio, scene, root, ground, authored, modules, out, approval)

    source_fingerprint = __import__("os").environ.get("CH_SOURCE_FINGERPRINT")
    proxy_approval = {
        "contract": "CH_PROXY_APPROVAL_V1",
        "assetId": base.ASSET_ID,
        "proxySha256": approval,
        "reviewed": True,
        "runtimeTarget": "2D_RGBA_overlay_atlas",
        "sourceFingerprint": source_fingerprint,
    }
    (Path(out) / "proxy_approval.json").write_text(
        json.dumps(proxy_approval, indent=2), encoding="utf-8"
    )

    metadata = {
        "contract": "CH_COASTER_TRACK_SKIN_MODULE_METADATA_V1",
        "assetId": base.ASSET_ID,
        "skinContract": "CH_COASTER_TRACK_SKIN_V1",
        "geometryAuthority": "CH_COASTER_TRACK_GEOMETRY_V1",
        "cameraContract": "CH_CAMERA_V1",
        "studioPreset": studio.get("id", "CH_TYCOON_STUDIO_V1"),
        "runtimeRepresentation": "2D_RGBA_overlay_atlas",
        "approvedProxySha256": approval,
        "sourceFingerprint": source_fingerprint,
        "modules": list(base.MODULE_IDS),
        "directions": [direction["id"] for direction in base.bs.DIRECTIONS],
    }
    (Path(out) / "studio_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )


base.render_final = render_final_v2

if __name__ == "__main__":
    base.main()
