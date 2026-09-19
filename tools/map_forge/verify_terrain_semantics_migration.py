"""Native Map Forge proof for the active CH_TERRAIN_SEMANTICS_V1 migration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.core.terrain_semantics import load_terrain_semantic_catalog, native_catalog_json


def main() -> None:
    asset_root = ROOT / "build" / "Debug"
    scenario = asset_root / "assets" / "scenarios" / "initial_city_terrain_semantics_v1.json"
    catalog = load_terrain_semantic_catalog(str(asset_root))
    raw = json.loads(scenario.read_text(encoding="utf-8"))
    core = get_native_core()
    doc = core.MapDocument(json.dumps(raw))
    water = next(tile for tile in raw["terrain"] if tile["terrainDefinition"] == "water_deep")
    info = core.inspect_tile_channels_with_terrain_catalog(doc, water["tileX"], water["tileY"], native_catalog_json(catalog))
    assert info.water_state == core.SemanticState.VALID
    assert info.buildable_state == core.SemanticState.INVALID

    viewport = core.MapForgeNativeViewport()
    assert viewport.initialize_offscreen(1280, 720, str(asset_root))
    camera = core.CameraState(); camera.zoom = 0.85; camera.rotation = core.CameraRotation.r0
    viewport.set_camera(camera); viewport.load_map_document(doc); viewport.render_frame()
    output = ROOT / "scratch" / "mapforge_terrain_semantics_v1.bmp"
    assert viewport.save_frame_to_png(str(output))
    viewport.shutdown()
    print(json.dumps({"valid": True, "scenario": str(scenario), "screenshot": str(output)}, indent=2))


if __name__ == "__main__":
    main()
