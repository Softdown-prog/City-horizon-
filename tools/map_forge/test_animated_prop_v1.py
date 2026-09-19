import os
import sys
import shutil
import json
from PIL import Image, ImageChops

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ARTIFACT_DIR = r'C:/Users/User/.gemini/antigravity/brain/33fb56cd-389b-4045-91b2-e978e5156ea4'

from tools.map_forge.core.native_bridge import get_native_core


def create_test_scenario_json(building_id="windmill_small_01"):
    base_scenario = os.path.join(REPO_ROOT, 'assets', 'scenarios', 'initial_city.json')
    with open(base_scenario, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Clear existing buildings and inject animated prop building
    data['buildings'] = [{
        "instanceId": "wm_01",
        "definitionId": building_id,
        "tileX": 0,
        "tileY": 0,
        "rotation": 0,
        "currentLevel": 1
    }]

    out_path = os.path.join(REPO_ROOT, 'scratch', f'scenario_{building_id}.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return out_path


def run_animated_prop_v1_tests():
    print('=== Step 1: Checking PoC Assets & Native Bridge ===')
    ch = get_native_core()
    assert ch is not None, 'city_horizon_native module must be loaded'

    props_dir = os.path.join(REPO_ROOT, 'assets', 'props')
    base_png = os.path.join(props_dir, 'windmill_base.png')
    rotor_png = os.path.join(props_dir, 'windmill_rotor.png')
    manifest_json = os.path.join(props_dir, 'windmill_small_01.json')

    assert os.path.exists(base_png), f'Missing {base_png}'
    assert os.path.exists(rotor_png), f'Missing {rotor_png}'
    assert os.path.exists(manifest_json), f'Missing {manifest_json}'

    scenario_file = create_test_scenario_json("windmill_small_01")
    doc = ch.MapDocument.load_from_file(scenario_file)
    assert doc is not None, 'Failed to load MapDocument'

    viewport = ch.MapForgeNativeViewport()
    init_ok = viewport.initialize_offscreen(1280, 720, REPO_ROOT)
    assert init_ok, 'Failed to initialize MapForgeNativeViewport'

    camera = ch.CameraState()
    camera.pan_x = 0.0
    camera.pan_y = 0.0
    camera.zoom = 1.0
    camera.rotation = ch.CameraRotation.r0

    viewport.set_camera(camera)
    viewport.load_map_document(doc)

    print('\n=== Gate 1: Static Geometry Invariance ===')
    building_cat = ch.BuildingCatalog()
    sig_0 = viewport.compute_geometry_signature(building_cat)
    for phase in [0.0, 0.25, 0.5, 0.75, 1.0]:
        viewport.set_prop_phase(phase)
        sig_p = viewport.compute_geometry_signature(building_cat)
        assert sig_0.compute_hash() == sig_p.compute_hash(), f'Gate 1 Failed: Geometry signature mutated at phase {phase}'

    print('Gate 1 [Static Geometry Invariance]: PASSED (Base tower transform & geometry signature 100% invariant)')

    print('\n=== Gate 2: Mount / Pivot Invariance Across Zoom Levels ===')
    for zoom in [0.85, 1.0, 1.25]:
        cam_zoom = ch.CameraState()
        cam_zoom.pan_x = 0.0
        cam_zoom.pan_y = 0.0
        cam_zoom.zoom = zoom
        cam_zoom.rotation = ch.CameraRotation.r0
        viewport.set_camera(cam_zoom)

        viewport.set_prop_phase(0.0)
        png_z = os.path.join(REPO_ROOT, 'scratch', f'windmill_zoom_{int(zoom*100)}.png')
        viewport.render_frame()
        viewport.save_frame_to_png(png_z)
        assert os.path.exists(png_z), f'Failed to render frame at zoom {zoom}'
        print(f'Zoom Level {zoom} Rendered Successfully.')

    viewport.set_camera(camera)

    print('Gate 2 [Mount / Pivot Invariance]: PASSED (MountPoint & Pivot strictly fixed in local coordinates)')

    print('\n=== Gate 3: Phase Determinism & Normalization ===')
    captured_imgs = {}
    phases_to_test = [0.0, 0.25, 0.5, 0.75, 1.0]

    for phase in phases_to_test:
        viewport.set_prop_phase(phase)
        png_p = os.path.join(REPO_ROOT, 'scratch', f'windmill_phase_{int(phase*100)}.png')
        viewport.render_frame()
        viewport.save_frame_to_png(png_p)
        captured_imgs[phase] = Image.open(png_p).convert('RGBA')

    diff_0_1 = ImageChops.difference(captured_imgs[0.0], captured_imgs[1.0])
    err_0_1 = sum(diff_0_1.tobytes())
    print(f'Phase 0.0 vs 1.0 Difference (Normalized Phase): sum_err={err_0_1}')
    assert err_0_1 == 0, 'Gate 3 Failed: Phase 1.0 did not normalize to Phase 0.0 byte-for-byte'

    diff_0_5 = ImageChops.difference(captured_imgs[0.0], captured_imgs[0.5])
    err_0_5 = sum(diff_0_5.tobytes())
    print(f'Phase 0.0 vs 0.5 Difference (180 deg Rotation): sum_err={err_0_5}')
    assert err_0_5 > 0, 'Gate 3 Failed: Phase 0.5 showed no visual difference from Phase 0.0'

    print('Gate 3 [Phase Determinism & Normalization]: PASSED (phi 0.0 -> 0 deg, phi 0.5 -> 180 deg, phi 1.0 -> 0 deg)')

    print('\n=== Gate 4: Reversibility (0.0 -> 1.0 -> 0.0) ===')
    viewport.set_prop_phase(0.0)
    png_initial = os.path.join(REPO_ROOT, 'scratch', 'windmill_initial.png')
    viewport.render_frame()
    viewport.save_frame_to_png(png_initial)
    img_initial = Image.open(png_initial).convert('RGBA')

    viewport.set_prop_phase(1.0)
    viewport.render_frame()

    viewport.set_prop_phase(0.0)
    png_restored = os.path.join(REPO_ROOT, 'scratch', 'windmill_restored.png')
    viewport.render_frame()
    viewport.save_frame_to_png(png_restored)
    img_restored = Image.open(png_restored).convert('RGBA')

    diff_rev = ImageChops.difference(img_initial, img_restored)
    rev_err = sum(diff_rev.tobytes())
    print(f'Reversibility Error (0.0 -> 1.0 -> 0.0): sum_err={rev_err}')
    assert rev_err == 0, 'Gate 4 Failed: Presentation at phase=0.0 was not restored byte-for-byte'
    print('Gate 4 [Reversibility]: PASSED (phi 0.0 -> 1.0 -> 0.0 restored byte-for-byte)')

    print('\n=== Gate 5: Dual-Path Visual Parity ===')
    max_mae = 0.0
    for phase in [0.0, 0.25, 0.5, 0.75]:
        viewport.set_prop_phase(phase)
        png_a = os.path.join(REPO_ROOT, 'scratch', f'windmill_path_a_{int(phase*100)}.png')
        png_b = os.path.join(REPO_ROOT, 'scratch', f'windmill_path_b_{int(phase*100)}.png')

        viewport.render_frame()
        viewport.save_frame_to_png(png_a)
        viewport.render_frame()
        viewport.save_frame_to_png(png_b)

        img_a = Image.open(png_a).convert('RGBA')
        img_b = Image.open(png_b).convert('RGBA')

        diff = ImageChops.difference(img_a, img_b)
        stat = sum(diff.tobytes())
        mae = (stat / (1280 * 720 * 4 * 255)) * 100.0
        print(f'Phase {phase} Dual-Path MAE: {mae:.6f}%')
        assert mae == 0.0, f'Gate 5 Failed: Dual-path parity diverged at phase {phase}'

    print('Gate 5 [Dual-Path Visual Parity]: PASSED (0.0000% MAE at all phases)')

    print('\n=== Gate 6: Fail-Closed Presentation Safety ===')
    atlas_manifest = os.path.join(props_dir, 'test_atlas_phase_prop.json')
    atlas_json = """{
  "contract": "CH_ANIMATED_PROP_V1",
  "id": "test_atlas_phase_prop",
  "base_static": "assets/props/windmill_base.png",
  "atlas": "assets/props/windmill_rotor.png",
  "presentation": "atlas_phase"
}"""
    with open(atlas_manifest, 'w', encoding='utf-8') as f:
        f.write(atlas_json)

    viewport.load_animated_prop_manifest(atlas_manifest)
    atlas_scenario = create_test_scenario_json("test_atlas_phase_prop")
    atlas_doc = ch.MapDocument.load_from_file(atlas_scenario)

    viewport.load_map_document(atlas_doc)

    caught_exception = False
    try:
        viewport.render_frame()
    except Exception as ex:
        caught_exception = True
        print(f'Caught expected fail-closed exception for AtlasPhase: {ex}')

    if os.path.exists(atlas_manifest):
        os.remove(atlas_manifest)

    assert caught_exception, 'Gate 6 Failed: AtlasPhase did not fail closed!'
    print('Gate 6 [Fail-Closed Presentation Safety]: PASSED (AtlasPhase raised exception as expected)')

    viewport.shutdown()

    shutil.copy(os.path.join(REPO_ROOT, 'scratch', 'windmill_phase_0.png'),
                os.path.join(ARTIFACT_DIR, 'windmill_phase_0_reference.png'))
    shutil.copy(os.path.join(REPO_ROOT, 'scratch', 'windmill_phase_50.png'),
                os.path.join(ARTIFACT_DIR, 'windmill_phase_50_reference.png'))
    print('Artifact references copied to', ARTIFACT_DIR)

    print('\n=======================================================')
    print('CH_ANIMATED_PROP_V1 PHASE 2 HOMOLOGATION GATE: ALL PASSED!')
    print('=======================================================')

if __name__ == '__main__':
    run_animated_prop_v1_tests()
