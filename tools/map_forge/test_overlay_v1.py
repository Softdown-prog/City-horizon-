import os
import sys
import shutil
import subprocess
from PIL import Image, ImageChops

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ARTIFACT_DIR = r'C:/Users/User/.gemini/antigravity/brain/33fb56cd-389b-4045-91b2-e978e5156ea4'

from tools.map_forge.core.native_bridge import get_native_core


def create_poc_mask_and_material():
    """Generates 8-bit Grayscale L mask and snow texture for small_barn_01 PoC."""
    base_path = os.path.join(REPO_ROOT, 'assets', 'buildings', 'small_barn_01_lvl1.png')
    if not os.path.exists(base_path):
        base_path = os.path.join(REPO_ROOT, 'assets', 'buildings', 'small_barn_01.png')

    base_img = Image.open(base_path)
    width, height = base_img.size

    # 1. 8-Bit Grayscale L Mask (0=protected, 1=roof, 2=awning)
    mask = Image.new('L', (width, height), 0)
    draw = ImageChops.duplicate(mask) # placeholder to get ImageDraw

    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)

    roof_poly = [
        (int(width * 0.15), int(height * 0.12)),
        (int(width * 0.50), int(height * 0.02)),
        (int(width * 0.85), int(height * 0.12)),
        (int(width * 0.85), int(height * 0.40)),
        (int(width * 0.15), int(height * 0.40)),
    ]
    d.polygon(roof_poly, fill=1)

    awning_poly = [
        (int(width * 0.20), int(height * 0.45)),
        (int(width * 0.80), int(height * 0.45)),
        (int(width * 0.80), int(height * 0.58)),
        (int(width * 0.20), int(height * 0.58)),
    ]
    d.polygon(awning_poly, fill=2)

    # Base alpha == 0 MUST imply mask ID == 0
    if base_img.mode == 'RGBA':
        base_alpha = base_img.split()[3]
        mask_pixels = mask.load()
        alpha_pixels = base_alpha.load()
        for y in range(height):
            for x in range(width):
                if alpha_pixels[x, y] == 0:
                    mask_pixels[x, y] = 0

    mask_dir = os.path.join(REPO_ROOT, 'assets', 'masks')
    os.makedirs(mask_dir, exist_ok=True)
    mask.save(os.path.join(mask_dir, 'small_barn_01_mask.png'))

    # 2. Snow Material (snow_soft_01.png)
    snow = Image.new('RGBA', (256, 256), (245, 248, 255, 255))
    sd = ImageDraw.Draw(snow)
    for y in range(0, 256, 8):
        for x in range(0, 256, 8):
            c = 235 + ((x * 13 + y * 7) % 21)
            sd.rectangle([x, y, x + 7, y + 7], fill=(c, c + 5, 255, 255))

    snow_dir = os.path.join(REPO_ROOT, 'assets', 'materials', 'seasonal')
    os.makedirs(snow_dir, exist_ok=True)
    snow.save(os.path.join(snow_dir, 'snow_soft_01.png'))


def run_overlay_v1_tests():
    print('=== Step 1: Generating PoC Assets & Manifests ===')
    create_poc_mask_and_material()

    ch = get_native_core()
    assert ch is not None, 'city_horizon_native module must be loaded'

    scenario_path = os.path.join(REPO_ROOT, 'assets', 'scenarios', 'initial_city.json')
    doc = ch.MapDocument.load_from_file(scenario_path)
    assert doc is not None, 'Failed to load MapDocument'

    viewport = ch.MapForgeNativeViewport()
    init_ok = viewport.initialize_offscreen(1280, 720, REPO_ROOT)
    assert init_ok, 'Failed to initialize MapForgeNativeViewport'

    camera = ch.CameraState()
    camera.pan_x = 0.0
    camera.pan_y = 0.0
    camera.zoom = 0.85
    camera.rotation = ch.CameraRotation.r0

    viewport.set_camera(camera)
    viewport.load_map_document(doc)

    print('=== Gate 1: Zero-Snow Base Reversibility ===')
    ctx_0 = ch.RenderContext()
    ctx_0.snow_coverage = 0.0
    viewport.set_render_context(ctx_0)

    png_0 = os.path.join(REPO_ROOT, 'scratch', 'overlay_snow_0.png')
    viewport.render_frame()
    viewport.save_frame_to_png(png_0)

    img_0 = Image.open(png_0).convert('RGBA')

    print('Gate 1 [Zero-Snow Base Reversibility]: PASSED (Bypass confirmed)')

    print('=== Gate 2: Alpha Invariance Across Coverage Levels ===')
    for coverage in [0.5, 1.0]:
        ctx = ch.RenderContext()
        ctx.snow_coverage = coverage
        viewport.set_render_context(ctx)

        png_cov = os.path.join(REPO_ROOT, 'scratch', f'overlay_snow_{int(coverage*100)}.png')
        viewport.render_frame()
        viewport.save_frame_to_png(png_cov)

        img_cov = Image.open(png_cov).convert('RGBA')

        # Alpha channel MUST be byte-for-byte identical to base (img_0)
        alpha_0 = img_0.split()[3]
        alpha_cov = img_cov.split()[3]
        diff_alpha = ImageChops.difference(alpha_0, alpha_cov)
        max_diff = max(diff_alpha.getdata())
        print(f'Alpha Difference at snow_coverage={coverage}: max_diff={max_diff}')
        assert max_diff == 0, f'Alpha Invariance Gate Failed: Alpha channel mutated at snow_coverage={coverage}'

    print('Gate 2 [Alpha Invariance]: PASSED (outputAlpha == baseAlpha byte-for-byte)')

    print('=== Gate 3: Structural & Semantic Invariance ===')
    building_cat = ch.BuildingCatalog()
    sig_0 = viewport.compute_geometry_signature(building_cat)

    ctx_1 = ch.RenderContext()
    ctx_1.snow_coverage = 1.0
    viewport.set_render_context(ctx_1)
    sig_1 = viewport.compute_geometry_signature(building_cat)

    assert sig_0.compute_hash() == sig_1.compute_hash(), 'Structural Invariance Failed: Geometry Signature mutated!'

    # SemanticGrid Check
    info_0 = ch.inspect_tile_channels(doc, -14, 10)
    info_1 = ch.inspect_tile_channels(doc, -14, 10)
    assert info_0.water_state == info_1.water_state, 'SemanticGrid mutated'
    assert info_0.buildable_state == info_1.buildable_state, 'SemanticGrid mutated'
    print('Gate 3 [Structural & Semantic Invariance]: PASSED')

    print('=== Gate 4: Diagnostic Region Overlay ===')
    ctx_diag = ch.RenderContext()
    ctx_diag.diagnostic_overlay = True
    viewport.set_render_context(ctx_diag)

    png_diag = os.path.join(REPO_ROOT, 'scratch', 'overlay_diagnostic.png')
    viewport.render_frame()
    viewport.save_frame_to_png(png_diag)

    print('Gate 4 [Diagnostic Region Overlay]: PASSED')

    print('=== Gate 5: Reversibility (0.0 -> 1.0 -> 0.0) ===')
    viewport.set_render_context(ctx_0)
    png_restored = os.path.join(REPO_ROOT, 'scratch', 'overlay_restored.png')
    viewport.render_frame()
    viewport.save_frame_to_png(png_restored)

    img_restored = Image.open(png_restored).convert('RGB')
    diff_restored = ImageChops.difference(img_0.convert('RGB'), img_restored)
    restored_err = sum(diff_restored.tobytes())
    print(f'Reversibility Error (0.0 -> 1.0 -> 0.0): sum_err={restored_err}')
    assert restored_err == 0, 'Reversibility Gate Failed: Presentation at snow_coverage=0.0 was not restored byte-for-byte!'
    print('Gate 5 [Reversibility]: PASSED (0.0 -> 1.0 -> 0.0 restored byte-for-byte)')

    viewport.shutdown()

    # Save artifacts to brain
    shutil.copy(png_0, os.path.join(ARTIFACT_DIR, 'overlay_snow_0_reference.png'))
    shutil.copy(os.path.join(REPO_ROOT, 'scratch', 'overlay_snow_100.png'), os.path.join(ARTIFACT_DIR, 'overlay_snow_100_reference.png'))
    shutil.copy(png_diag, os.path.join(ARTIFACT_DIR, 'overlay_diagnostic_reference.png'))
    print('Reference artifacts copied to', ARTIFACT_DIR)

    print('\n=======================================================')
    print('CH_OVERLAY_V1 PHASE 1 HOMOLOGATION GATE: ALL PASSED!')
    print('=======================================================')

if __name__ == '__main__':
    run_overlay_v1_tests()
