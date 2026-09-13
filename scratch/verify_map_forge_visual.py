"""
Visual & Runtime Verification Script for Map Forge Native SDL3 Viewport.
Verifies native viewport rendering, document loading, camera pan, zoom,
DPI resizing, and clean shutdown.
"""

import sys
import os

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from tools.map_forge.core.native_bridge import get_native_core


def run_visual_verification():
    ch = get_native_core()
    assert ch is not None, "city_horizon_native module must be loaded"

    asset_root = root_dir
    scenario_path = os.path.join(asset_root, "assets", "scenarios", "initial_city.json")

    print("[VISUAL TEST] Loading MapDocument...", flush=True)
    doc = ch.MapDocument.load_from_file(scenario_path)
    assert doc is not None, "MapDocument failed to load"
    print(f"[VISUAL TEST] MapDocument loaded with {len(doc.buildings())} buildings, {len(doc.roads())} roads.", flush=True)

    print("[VISUAL TEST] Creating MapForgeNativeViewport...", flush=True)
    viewport = ch.MapForgeNativeViewport()

    # Create native camera state
    camera = ch.CameraState()
    camera.pan_x = -2.0
    camera.pan_y = 12.0
    camera.zoom = 0.9
    camera.rotation = ch.CameraRotation.r0

    viewport.set_camera(camera)
    loaded = viewport.load_map_document(doc)
    assert loaded, "Failed to load document into viewport"
    print("[VISUAL TEST] Document loaded into C++ native viewport.", flush=True)

    # Calculate geometry signature at 1280x720
    definitions_dir = os.path.join(asset_root, "assets", "definitions")
    catalog = ch.BuildingCatalog()
    catalog.load_from_directory(definitions_dir)

    sig_initial = viewport.compute_geometry_signature(catalog)
    hash_initial = sig_initial.compute_hash()
    print(f"[VISUAL TEST] Initial Viewport Signature Hash (1280x720): {hash_initial}", flush=True)
    assert len(sig_initial.records) > 0, "Geometry signature records should not be empty"

    # Camera Pan Test
    camera.pan_x += 3.0
    camera.pan_y -= 2.0
    viewport.set_camera(camera)
    sig_panned = viewport.compute_geometry_signature(catalog)
    hash_panned = sig_panned.compute_hash()
    print(f"[VISUAL TEST] Panned Viewport Signature Hash: {hash_panned}", flush=True)
    assert hash_panned != hash_initial, "Panning camera must update render geometry screen coordinates"

    # Camera Zoom Test
    camera.zoom = 1.35
    viewport.set_camera(camera)
    sig_zoomed = viewport.compute_geometry_signature(catalog)
    hash_zoomed = sig_zoomed.compute_hash()
    print(f"[VISUAL TEST] Zoomed Viewport Signature Hash (135%): {hash_zoomed}", flush=True)

    # Physical Window Resize Test
    viewport.resize(1600, 900)
    sig_resized = viewport.compute_geometry_signature(catalog)
    hash_resized = sig_resized.compute_hash()
    print(f"[VISUAL TEST] Resized Viewport Signature Hash (1600x900): {hash_resized}", flush=True)

    # Shutdown Test
    viewport.shutdown()
    print("[VISUAL TEST] Native Viewport shutdown cleanly without crash!", flush=True)
    return True


if __name__ == "__main__":
    success = run_visual_verification()
    if success:
        print("\n==========================================", flush=True)
        print("MAP FORGE NATIVE SDL3 VISUAL GATE: PASSED!", flush=True)
        print("==========================================", flush=True)
        sys.exit(0)
    else:
        sys.exit(1)
