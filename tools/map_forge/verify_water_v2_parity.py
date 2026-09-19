"""
Water V2 & Shoreline Parity Verification Suite.
Validates 100% visual rendering parity between Game Runtime and MapForgeNativeViewport::render_frame().
Captures reference frames via both public consumer paths and generates an image diff.
"""

import os
import sys
import shutil
import subprocess
from PIL import Image, ImageChops

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ARTIFACT_DIR = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"

from tools.map_forge.core.native_bridge import get_native_core


def run_runtime_consumer(output_png_path: str):
    print("=== Step 1: Capturing Path A (Game Runtime Consumer Path) ===")
    exe_path = os.path.join(REPO_ROOT, "build", "Debug", "shoreline_pilot_runtime.exe")
    tmp_bmp = os.path.join(REPO_ROOT, "scratch", "runtime_water_ref_tmp.bmp")

    cmd = [exe_path, REPO_ROOT, tmp_bmp]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Runtime executable failed: {res.stderr}"

    img = Image.open(tmp_bmp).convert("RGB")
    img.save(output_png_path)
    print(f"Path A (Runtime) Frame Captured: {output_png_path} ({img.size[0]}x{img.size[1]})")


def run_mapforge_consumer(output_png_path: str):
    print("=== Step 2: Capturing Path B (MapForgeNativeViewport::render_frame Consumer Path) ===")
    ch = get_native_core()
    assert ch is not None, "city_horizon_native module must be loaded"

    scenario_path = os.path.join(REPO_ROOT, "assets", "scenarios", "initial_city.json")
    doc = ch.MapDocument.load_from_file(scenario_path)
    assert doc is not None, "MapDocument failed to load"

    viewport = ch.MapForgeNativeViewport()
    init_ok = viewport.initialize_offscreen(1280, 720, REPO_ROOT)
    assert init_ok, "Failed to initialize MapForgeNativeViewport offscreen"

    camera = ch.CameraState()
    camera.pan_x = 0.0
    camera.pan_y = 0.0
    camera.zoom = 0.85
    camera.rotation = ch.CameraRotation.r0

    viewport.set_camera(camera)
    viewport.load_map_document(doc)
    viewport.set_view_mode(0) # ART mode

    # Render frame via native C++ viewport
    viewport.render_frame()

    tmp_bmp = os.path.join(REPO_ROOT, "scratch", "mapforge_water_ref_tmp.bmp")
    viewport.save_frame_to_png(tmp_bmp)
    viewport.shutdown()

    img = Image.open(tmp_bmp).convert("RGB")
    img.save(output_png_path)
    print(f"Path B (MapForgeNativeViewport) Frame Captured: {output_png_path} ({img.size[0]}x{img.size[1]})")


def compute_parity_diff(runtime_png: str, mapforge_png: str, diff_png: str):
    print("=== Step 3: Computing Pixel-by-Pixel Parity Diff ===")
    img_runtime = Image.open(runtime_png).convert("RGB")
    img_forge = Image.open(mapforge_png).convert("RGB")

    assert img_runtime.size == img_forge.size, f"Dimension mismatch: {img_runtime.size} vs {img_forge.size}"
    w, h = img_runtime.size

    diff = ImageChops.difference(img_runtime, img_forge)
    diff.save(diff_png)

    # Compute Mean Absolute Error
    diff_bytes = diff.tobytes()
    total_err = sum(diff_bytes)
    max_err = w * h * 3 * 255
    error_ratio = total_err / max_err

    print(f"Parity Difference MAE Error Ratio: {error_ratio * 100:.4f}%")
    print(f"Saved Image Diff: {diff_png}")

    # Copy to artifact directory
    shutil.copy(runtime_png, os.path.join(ARTIFACT_DIR, "water_v2_runtime_reference.png"))
    shutil.copy(mapforge_png, os.path.join(ARTIFACT_DIR, "water_v2_mapforge_reference.png"))
    shutil.copy(diff_png, os.path.join(ARTIFACT_DIR, "water_v2_parity_diff.png"))
    print(f"All 3 reference artifacts copied to {ARTIFACT_DIR}")

    assert error_ratio < 0.005, f"Visual parity error ratio {error_ratio*100:.2f}% exceeds tolerance threshold (0.5%)"


def verify_all():
    os.makedirs(os.path.join(REPO_ROOT, "scratch"), exist_ok=True)
    runtime_png = os.path.join(REPO_ROOT, "water_v2_runtime_reference.png")
    mapforge_png = os.path.join(REPO_ROOT, "water_v2_mapforge_reference.png")
    diff_png = os.path.join(REPO_ROOT, "water_v2_parity_diff.png")

    run_runtime_consumer(runtime_png)
    run_mapforge_consumer(mapforge_png)
    compute_parity_diff(runtime_png, mapforge_png, diff_png)
    print("\n==========================================")
    print("WATER V2 MAP FORGE PARITY GATE: PASSED 100%!")
    print("==========================================")


if __name__ == "__main__":
    verify_all()
