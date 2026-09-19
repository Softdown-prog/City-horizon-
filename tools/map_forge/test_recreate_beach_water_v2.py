import hashlib
import json
import os
import shutil
import subprocess
import sys
from PIL import Image, ImageChops

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ARTIFACT_DIR = r'C:/Users/User/.gemini/antigravity/brain/33fb56cd-389b-4045-91b2-e978e5156ea4'

from tools.map_forge.core.native_bridge import get_native_core
from tools.map_forge.recipes.recreate_beach_water_v2 import generate_recreated_beach_scenario, OBJECT_COMPATIBILITY_POLICIES
from tools.map_forge.core.terrain_semantics import load_terrain_semantic_catalog


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def run_beach_recreation_test():
    load_terrain_semantic_catalog(REPO_ROOT)
    print('=== Gate 1: Immutability Pre-Check ===')
    initial_city_path = os.path.join(REPO_ROOT, 'assets', 'scenarios', 'initial_city.json')
    sha_before = compute_sha256(initial_city_path)
    print(f'initial_city.json SHA-256 (before): {sha_before}')

    print('=== Gate 2: Generating Recreated Beach Scenario ===')
    scenario_path = generate_recreated_beach_scenario(REPO_ROOT)
    print('Generated Scenario:', scenario_path)

    sha_after = compute_sha256(initial_city_path)
    print(f'initial_city.json SHA-256 (after):  {sha_after}')
    assert sha_before == sha_after, 'CRITICAL GATE FAILED: initial_city.json was mutated!'
    print('Gate 1 [Immutability]: PASSED (initial_city.json untouched)')

    ch = get_native_core()
    assert ch is not None, 'city_horizon_native module must be loaded'

    doc = ch.MapDocument.load_from_file(scenario_path)
    assert doc is not None, 'Failed to load generated MapDocument'

    # 1. Validate Map Document Structure
    report = ch.validate_map_document(doc)
    assert report.valid, f'MapDocument validation failed: {getattr(report, "errors", report)}'
    print('Gate 2 [MapDocument Structure Validation]: PASSED [VALID]')

    # 2. Gate 3: Infrastructure Non-Encroachment Check
    with open(scenario_path, 'r', encoding='utf-8') as f:
        scen_json = json.load(f)

    encroachment_violations = []

    # Check land buildings
    for b in scen_json.get('buildings', []):
        def_id = b.get('definitionId', '')
        policy = OBJECT_COMPATIBILITY_POLICIES.get(def_id, 'requires_land')
        if policy == 'requires_land':
            bx = int(b['tileX'])
            by = int(b['tileY'])
            bw = int(b.get('footprintWidth', 1))
            bh = int(b.get('footprintDepth', 1))
            for dx in range(bw):
                for dy in range(bh):
                    tx, ty = bx + dx, by + dy
                    info = ch.inspect_tile_channels(doc, tx, ty)
                    if info.water_state == ch.SemanticState.VALID:
                        encroachment_violations.append(f'Building {def_id} at ({tx}, {ty}) has water')

    # Check roads & sidewalks
    for r in scen_json.get('roads', []):
        tx, ty = int(r['tileX']), int(r['tileY'])
        info = ch.inspect_tile_channels(doc, tx, ty)
        if info.water_state == ch.SemanticState.VALID:
            encroachment_violations.append(f'Road at ({tx}, {ty}) has water')

    for s in scen_json.get('sidewalks', []):
        tx, ty = int(s['tileX']), int(s['tileY'])
        info = ch.inspect_tile_channels(doc, tx, ty)
        if info.water_state == ch.SemanticState.VALID:
            encroachment_violations.append(f'Sidewalk at ({tx}, {ty}) has water')

    print(f'Infrastructure Non-Encroachment Violations: {len(encroachment_violations)}')
    assert len(encroachment_violations) == 0, f'Encroachment violations detected: {encroachment_violations}'
    print('Gate 3 [Infrastructure Non-Encroachment]: PASSED (0 land buildings/roads on water)')

    # 3. Gate 4: Semantic Channel Verification (inspect_tile_channels)
    terrain_tiles = doc.terrain_tiles()
    shallow_count = 0
    deep_count = 0
    sand_dry_count = 0
    sand_wet_count = 0

    for tile in terrain_tiles:
        info = ch.inspect_tile_channels(doc, tile.tile_x, tile.tile_y)
        tex = tile.texture

        if 'coast_water_shallow' in tex or 'ocean_shallow' in tex:
            assert info.water_state == ch.SemanticState.VALID, f'Tile at ({tile.tile_x}, {tile.tile_y}) must be valid water'
            assert info.buildable_state == ch.SemanticState.INVALID, f'Water tile at ({tile.tile_x}, {tile.tile_y}) must be non-buildable'
            shallow_count += 1
        elif 'coast_water_deep' in tex or 'ocean_deep' in tex:
            assert info.water_state == ch.SemanticState.VALID, f'Tile at ({tile.tile_x}, {tile.tile_y}) must be valid water'
            assert info.buildable_state == ch.SemanticState.INVALID, f'Water tile at ({tile.tile_x}, {tile.tile_y}) must be non-buildable'
            deep_count += 1
        elif 'coast_sand_center_01' in tex:
            assert info.water_state == ch.SemanticState.NOT_APPLICABLE, f'Sand tile at ({tile.tile_x}, {tile.tile_y}) must not be water'
            sand_dry_count += 1
        elif 'coast_sand_wet_01' in tex:
            assert info.water_state == ch.SemanticState.NOT_APPLICABLE, f'Wet sand tile at ({tile.tile_x}, {tile.tile_y}) must not be water'
            sand_wet_count += 1

    print(f'Semantic Channel Breakdown -> Shallow: {shallow_count}, Deep: {deep_count}, Dry Sand: {sand_dry_count}, Wet Sand: {sand_wet_count}')
    assert shallow_count > 0, 'Semantic gate failed: shallow water count must be positive'
    assert deep_count > 0, 'Semantic gate failed: deep water count must be positive'
    assert sand_dry_count > 0, 'Semantic gate failed: dry sand count must be positive'
    assert sand_wet_count > 0, 'Semantic gate failed: wet sand count must be positive'
    print('Gate 4 [Semantic Channel Verification]: PASSED')

    # 4. Gate 5: Shoreline Autotiler Execution & Topological breakdown
    autotile_res = ch.evaluate_shoreline(doc, -24, 10, 23, 23)
    assert autotile_res is not None, 'ShorelineAutotiler evaluation failed'
    assert len(autotile_res.edits) > 0, 'Topological assertion failed: shoreline edits count must be positive'
    print('Shoreline Autotiler Total Edits:', len(autotile_res.edits))

    straight_edges = 0
    outer_corners = 0
    inner_corners = 0

    border_pieces = {ch.ShorelinePiece.BORDER_NORTH, ch.ShorelinePiece.BORDER_EAST, ch.ShorelinePiece.BORDER_SOUTH, ch.ShorelinePiece.BORDER_WEST}
    outer_pieces = {ch.ShorelinePiece.OUTER_NE, ch.ShorelinePiece.OUTER_SE, ch.ShorelinePiece.OUTER_SW, ch.ShorelinePiece.OUTER_NW}
    inner_pieces = {ch.ShorelinePiece.INNER_NE, ch.ShorelinePiece.INNER_SE, ch.ShorelinePiece.INNER_SW, ch.ShorelinePiece.INNER_NW}

    for edit in autotile_res.edits:
        for piece in edit.recipe.pieces:
            if piece in border_pieces:
                straight_edges += 1
            elif piece in outer_pieces:
                outer_corners += 1
            elif piece in inner_pieces:
                inner_corners += 1

    print(f'Topology Autotile Breakdown -> Straight Edges: {straight_edges}, Outer Corners: {outer_corners}, Inner Corners: {inner_corners}')
    assert straight_edges > 0, 'Topological assertion failed: straight_edges must be positive'
    assert outer_corners > 0, 'Topological assertion failed: outer_corners must be positive'
    assert inner_corners > 0, 'Topological assertion failed: inner_corners must be positive'
    print('Gate 5 [Topological Shoreline Coverage]: PASSED')

    # 5. Gate 6: Dual-Path Parity Rendering & MAE Metrics
    print('=== Step 2: Capturing Path A (Game Runtime) ===')
    exe_path = os.path.join(REPO_ROOT, 'build', 'Debug', 'shoreline_pilot_runtime.exe')
    tmp_a_bmp = os.path.join(REPO_ROOT, 'scratch', 'recreated_beach_runtime_tmp.bmp')
    cmd = [exe_path, REPO_ROOT, tmp_a_bmp, scenario_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, 'Runtime executable failed: ' + str(res.stderr)

    png_a = os.path.join(REPO_ROOT, 'scratch', 'recreated_beach_water_v2.png')
    img_a = Image.open(tmp_a_bmp).convert('RGB')
    img_a.save(png_a)

    print('=== Step 3: Capturing Path B (MapForge Native Viewport) ===')
    viewport = ch.MapForgeNativeViewport()
    init_ok = viewport.initialize_offscreen(1280, 720, REPO_ROOT)
    assert init_ok, 'Failed to initialize MapForgeNativeViewport offscreen'

    camera = ch.CameraState()
    camera.pan_x = 0.0
    camera.pan_y = 0.0
    camera.zoom = 0.85
    camera.rotation = ch.CameraRotation.r0

    viewport.set_camera(camera)
    viewport.load_map_document(doc)
    viewport.set_view_mode(0)

    tmp_b_bmp = os.path.join(REPO_ROOT, 'scratch', 'recreated_beach_mapforge_tmp.bmp')
    viewport.save_frame_to_png(tmp_b_bmp)
    viewport.shutdown()

    png_b = os.path.join(REPO_ROOT, 'scratch', 'recreated_beach_mapforge.png')
    img_b = Image.open(tmp_b_bmp).convert('RGB')
    img_b.save(png_b)

    # Parity Diff Calculation
    diff = ImageChops.difference(img_a, img_b)
    diff_png = os.path.join(REPO_ROOT, 'scratch', 'recreated_beach_parity_diff.png')
    diff.save(diff_png)

    diff_bytes = diff.tobytes()
    total_err = sum(diff_bytes)
    max_err = 1280 * 720 * 3 * 255
    error_ratio = total_err / max_err

    print(f'Recreated Beach Visual Parity MAE Error Ratio: {error_ratio * 100:.4f}%')
    if error_ratio == 0.0:
        print('Gate 6 [Parity Metric]: PASSED (Perfect 0.0000% MAE)')
    elif error_ratio <= 0.005:
        print(f'Gate 6 [Parity Metric]: PASSED WITH WARNING (MAE = {error_ratio * 100:.4f}% <= threshold 0.5%)')
    else:
        raise AssertionError(f'Visual parity error ratio {error_ratio * 100:.4f}% exceeds 0.5% failure threshold!')

    # Copy reference artifacts
    shutil.copy(png_a, os.path.join(ARTIFACT_DIR, 'recreated_beach_water_v2.png'))
    shutil.copy(png_a, os.path.join(ARTIFACT_DIR, 'recreated_beach_runtime_reference.png'))
    shutil.copy(png_b, os.path.join(ARTIFACT_DIR, 'recreated_beach_mapforge_reference.png'))
    shutil.copy(diff_png, os.path.join(ARTIFACT_DIR, 'recreated_beach_parity_diff.png'))
    print('All reference artifacts copied to', ARTIFACT_DIR)

    print('\n=======================================================')
    print('MAP FORGE BEACH RECREATION HOMOLOGATION GATE: ALL PASSED!')
    print('=======================================================')

if __name__ == '__main__':
    run_beach_recreation_test()

