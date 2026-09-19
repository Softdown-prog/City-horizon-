"""Native Map Forge smoke test for the CH_MASK_V1 concrete terrain pilot."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.core.map_model import MapModel
from tools.map_forge.core.validator import validate_map
from tools.map_forge.importers.map_importer import load_building_catalog, load_scenario


def main() -> None:
    asset_root = REPO_ROOT / "build" / "Debug"
    source = load_scenario(str(asset_root / "assets" / "scenarios" / "initial_city.json"))
    raw = copy.deepcopy(source.raw_data)
    pilot_texture = "assets/terrain/paths/grass_to_concrete_path_01_concrete_path.png"
    target = (0, 0)
    replaced = False
    for tile in raw.setdefault("terrain", []):
        if int(tile.get("tileX", 0)) == target[0] and int(tile.get("tileY", 0)) == target[1]:
            tile["texture"] = pilot_texture
            replaced = True
            break
    if not replaced:
        raw["terrain"].append({"tileX": target[0], "tileY": target[1], "texture": pilot_texture})

    model = MapModel(raw)
    report = validate_map(model, str(asset_root), load_building_catalog(str(asset_root)))
    if not report["valid"]:
        raise RuntimeError("Concrete path pilot rejected: " + "; ".join(report["errors"]))

    core = get_native_core()
    viewport = core.MapForgeNativeViewport()
    if not viewport.initialize_offscreen(1280, 720, str(asset_root)):
        raise RuntimeError("Could not initialize Map Forge native viewport")
    camera = core.CameraState()
    camera.pan_x = 0.0
    camera.pan_y = 0.0
    camera.zoom = 0.85
    camera.rotation = core.CameraRotation.r0
    viewport.set_camera(camera)
    viewport.load_map_document(core.MapDocument(json.dumps(raw)))
    viewport.render_frame()
    screenshot = REPO_ROOT / "scratch" / "mapforge_concrete_path_pilot.bmp"
    screenshot.parent.mkdir(exist_ok=True)
    if not viewport.save_frame_to_png(str(screenshot)):
        raise RuntimeError("Map Forge could not capture concrete path pilot")
    viewport.shutdown()
    print(json.dumps({"valid": True, "texture": pilot_texture, "screenshot": str(screenshot)}, indent=2))


if __name__ == "__main__":
    main()
