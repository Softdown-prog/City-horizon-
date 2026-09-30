#!/usr/bin/env python3
"""Fail closed when MapForge introduces a second CH_CAMERA_V1 projection formula.

This check is intentionally source based. Runtime/editor projection parity is covered by
mapforge_camera_parity_test.cpp; this script protects the authoring tools from quietly
re-introducing local 2:1 math after they have been migrated to canonical bridges.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAPFORGE_ROOT = Path(__file__).resolve().parents[1]
SRC = MAPFORGE_ROOT / "src"

MIGRATED_REQUIREMENTS = {
    "asset_grid_preview_widget.cpp": ("authoring_projection.h", "projectAuthoringGround"),
    "tile_surface_preview_widget.cpp": ("authoring_projection.h", "projectAuthoringGround"),
    "park_fence_renderer.cpp": ("authoring_projection.h", "projectAuthoringPixelElevation"),
    "building_block_preview_renderer.cpp": ("authoring_projection.h", "projectAuthoringGround"),
    "building_projected_shadow_renderer.cpp": ("authoring_projection.h", "projectAuthoringGround"),
    "building_composer.cpp": ("authoring_projection.h", "projectAuthoringPixelElevation"),
    "building_facade_renderer.cpp": ("authoring_projection.h", "projectAuthoringPixelElevation"),
    "building_roof_editor_renderer.cpp": ("authoring_projection.h", "projectAuthoringPixelElevation"),
    "map_capture_service.cpp": ("tilePolygonAtElevation", "world_to_screen_point"),
    "procedural_road_preview_main.cpp": ("world_to_screen_point", "screen_to_world_point"),
}

# Strong indicators of a local isometric projection implementation. Generic arithmetic
# remains legal; these patterns look for the paired coordinate expressions normally used
# to rebuild the CH 2:1 basis by hand.
DRIFT_PATTERNS = (
    re.compile(r"half_tile_w\s*=", re.IGNORECASE),
    re.compile(r"half_tile_h\s*=", re.IGNORECASE),
    re.compile(r"kTileWidth\s*=\s*128(?:\.0)?"),
    re.compile(r"kTileHeight\s*=\s*64(?:\.0)?"),
    re.compile(r"\(\s*tile_x\s*-\s*tile_y\s*\)\s*\*"),
    re.compile(r"\(\s*tile_x\s*\+\s*tile_y\s*\)\s*\*"),
    re.compile(r"\(\s*point\.x\s*-\s*point\.y\s*\)\s*\*"),
    re.compile(r"\(\s*point\.x\s*\+\s*point\.y\s*\)\s*\*"),
    re.compile(r"\(\s*rotated\.x\s*-\s*rotated\.y\s*\)\s*\*"),
    re.compile(r"\(\s*rotated\.x\s*\+\s*rotated\.y\s*\)\s*\*"),
)


def fail(message: str) -> None:
    print(f"FAIL CH_MAPFORGE_PROJECTION_DRIFT_GUARD_V1: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    missing = []
    for filename, required_tokens in MIGRATED_REQUIREMENTS.items():
        path = SRC / filename
        if not path.is_file():
            missing.append(f"{filename}: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        for token in required_tokens:
            if token not in text:
                missing.append(f"{filename}: missing {token!r}")
    if missing:
        fail("; ".join(missing))

    violations: list[str] = []
    for path in sorted(SRC.glob("*")):
        if path.suffix not in {".cpp", ".h", ".hpp"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in DRIFT_PATTERNS:
            if pattern.search(text):
                violations.append(f"{path.name}: {pattern.pattern}")

    if violations:
        fail("new local projection math detected: " + "; ".join(violations))

    print("PASS CH_MAPFORGE_PROJECTION_DRIFT_GUARD_V1")
    print("all tracked MapForge projection users are canonical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
