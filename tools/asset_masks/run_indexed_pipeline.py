"""
CH_MASK_V1 Pipeline Runner & Batch Visual Validation Suite.
Processes the 6 target assets through the 8-bit indexed mask pipeline, generates variant sidecars,
and renders:
1. mask_generic_batch_composite.png - Diagnostic Composite Matrix (Base, Mask, Extreme Test, Variants 1-3)
2. mask_terrain_seamless_test.png  - 6x6 Isometric 2:1 Seamless Repetition Test for Terrain Materials
3. mask_generic_batch_runtime.png    - Viewport Scene Preview with integrated variants
"""

import os
import sys
import json
import shutil
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.asset_masks.mask_contract import MaskAssetManifest, compute_file_sha256
from tools.asset_masks.validate_mask_asset import validate_mask_asset
from tools.asset_masks.apply_mask_variant import apply_variant_to_image, process_mask_manifest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACT_DIR = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"

TARGET_ASSET_IDS = [
    "house_small_02",
    "shop_cafe_01",
    "clinic_small_01",
    "decor_lighthouse",
    "commercial_building_01",
    "terrain_grass_base",
]

def make_extreme_variant(manifest: MaskAssetManifest) -> dict:
    # Assign vibrant false colors: Region 1 = Magenta, Region 2 = Cyan, Region 3 = Yellow
    colors = {
        1: [255, 0, 255], # Magenta
        2: [0, 255, 255], # Cyan
        3: [255, 255, 0], # Yellow
        4: [255, 128, 0], # Orange
    }
    recipes = {}
    for r_name, r_id in manifest.regions.items():
        recipes[r_name] = {
            "mode": "recolor",
            "targetRGB": colors.get(r_id, [255, 255, 255]),
            "saturation": 2.0,
            "brightness": 1.2
        }
    return {
        "id": "_diagnostic_extreme",
        "region_recipes": recipes,
        "wear": 0.0
    }

def render_mask_diagnostic(base_img: Image.Image, mask_img: Image.Image, regions: dict) -> Image.Image:
    # Render base sprite with region IDs highlighted in high-contrast diagnostic tint
    out = base_img.convert("RGBA")
    w, h = out.size
    out_pixels = out.load()
    mask_pixels = mask_img.load()

    palette = {
        1: (255, 50, 50, 220),   # Red
        2: (50, 255, 50, 220),   # Green
        3: (50, 100, 255, 220),  # Blue
        4: (255, 255, 50, 220),  # Yellow
    }

    for y in range(h):
        for x in range(w):
            r_id = mask_pixels[x, y]
            if r_id in palette:
                br, bg, bb, ba = out_pixels[x, y]
                if ba > 0:
                    pr, pg, pb, pa = palette[r_id]
                    # Blend 50% base with 50% false color
                    out_pixels[x, y] = (
                        int(br * 0.5 + pr * 0.5),
                        int(bg * 0.5 + pg * 0.5),
                        int(bb * 0.5 + pb * 0.5),
                        ba
                    )
    return out


def run_pipeline():
    source_masks_dir = os.path.join(REPO_ROOT, "assets", "source_masks")
    gen_output_dir = os.path.join(REPO_ROOT, "assets", "generated_variants")
    os.makedirs(gen_output_dir, exist_ok=True)

    pipeline_results = {}

    print("=== Step 1: Validating and Processing Assets ===")
    for asset_id in TARGET_ASSET_IDS:
        asset_dir = os.path.join(source_masks_dir, asset_id)
        manifest_path = os.path.join(asset_dir, f"{asset_id}_manifest.json")
        out_dir = os.path.join(gen_output_dir, asset_id)

        # 1. Validate manifest
        with open(manifest_path, "r", encoding="utf-8") as f:
            m_dict = json.load(f)
        manifest = MaskAssetManifest.from_dict(m_dict, asset_dir)
        validate_mask_asset(manifest)

        # 2. Process regular variants
        generated_pngs, sidecars = process_mask_manifest(manifest_path, out_dir)

        # 3. Generate extreme test variant image for diagnostic composite matrix
        base_img = Image.open(manifest.base).convert("RGBA")
        mask_img = Image.open(manifest.semantic_mask).convert("L")
        extreme_var_dict = make_extreme_variant(manifest)
        from tools.asset_masks.apply_mask_variant import VariantConfig
        extreme_config = VariantConfig.from_dict(extreme_var_dict, asset_dir, manifest.regions)
        extreme_img = apply_variant_to_image(base_img, mask_img, manifest, extreme_config)

        # 4. Generate mask diagnostic image
        mask_diag_img = render_mask_diagnostic(base_img, mask_img, manifest.regions)

        pipeline_results[asset_id] = {
            "manifest": manifest,
            "base_img": base_img,
            "mask_img": mask_img,
            "mask_diag_img": mask_diag_img,
            "extreme_img": extreme_img,
            "variant_pngs": generated_pngs,
            "sidecars": sidecars
        }
        print(f"PASS: {asset_id} ({len(generated_pngs)} variants generated)")

    print("\n=== Step 2: Rendering Diagnostic Composite Matrix ===")
    render_composite_matrix(pipeline_results)

    print("\n=== Step 3: Rendering 6x6 Isometric 2:1 Terrain Test ===")
    render_seamless_terrain_test(pipeline_results)

    print("\n=== Step 4: Rendering Viewport Scene Preview ===")
    render_runtime_viewport_preview(pipeline_results)


def render_composite_matrix(pipeline_results: dict):
    # Grid: 6 rows (assets) x 6 columns (Base, Mask Diag, Extreme Test, Variant 1, Variant 2, Variant 3)
    col_headers = ["Base Sprite", "Mask Diagnostic", "Extreme Color Test", "Variant 1", "Variant 2", "Variant 3"]
    cell_w, cell_h = 220, 240
    padding = 20
    header_h = 60

    grid_w = len(col_headers) * cell_w + (len(col_headers) + 1) * padding
    grid_h = header_h + len(TARGET_ASSET_IDS) * cell_h + (len(TARGET_ASSET_IDS) + 1) * padding

    composite = Image.new("RGBA", (grid_w, grid_h), (25, 30, 38, 255))
    draw = ImageDraw.Draw(composite)

    # Header labels
    for c_idx, title in enumerate(col_headers):
        x = padding + c_idx * (cell_w + padding) + cell_w // 2
        draw.text((x, padding + 15), title, fill=(240, 240, 245), anchor="mm")

    # Fill rows
    for r_idx, asset_id in enumerate(TARGET_ASSET_IDS):
        res = pipeline_results[asset_id]
        y_top = header_h + padding + r_idx * (cell_h + padding)

        cells = [
            res["base_img"],
            res["mask_diag_img"],
            res["extreme_img"],
        ]
        # Add variant images
        for v_png in res["variant_pngs"][:3]:
            cells.append(Image.open(v_png).convert("RGBA"))

        # Row label
        draw.text((padding + 10, y_top - 15), f"{asset_id}", fill=(180, 200, 220), anchor="lm")

        for c_idx, cell_img in enumerate(cells):
            x_left = padding + c_idx * (cell_w + padding)
            # Draw cell background card
            draw.rectangle([x_left, y_top, x_left + cell_w, y_top + cell_h], fill=(35, 42, 52, 255), outline=(60, 70, 85, 255))
            
            # Fit image nicely inside cell card
            w, h = cell_img.size
            scale = min((cell_w - 20) / w, (cell_h - 40) / h, 1.0)
            nw, nh = int(w * scale), int(h * scale)
            resized = cell_img.resize((nw, nh), Image.Resampling.LANCZOS)

            px = x_left + (cell_w - nw) // 2
            py = y_top + (cell_h - nh) // 2 + 10
            composite.alpha_composite(resized, (px, py))

    composite_path = os.path.join(REPO_ROOT, "mask_generic_batch_composite.png")
    composite.save(composite_path)
    shutil.copy(composite_path, os.path.join(ARTIFACT_DIR, "mask_generic_batch_composite.png"))
    print(f"Saved Diagnostic Composite Matrix to {composite_path}")


def render_seamless_terrain_test(pipeline_results: dict):
    # Render 6x6 isometric tile repetition test for terrain variants (e.g. stone_surface, dirt_surface)
    terrain_res = pipeline_results.get("terrain_grass_base")
    if not terrain_res:
        return

    # Load terrain base and variant tiles
    base_tile = terrain_res["base_img"]
    variant_pngs = terrain_res["variant_pngs"]
    stone_tile = Image.open(variant_pngs[1]).convert("RGBA") if len(variant_pngs) > 1 else base_tile

    tile_w, tile_h = base_tile.size
    rows, cols = 6, 6

    # Isometric 2:1 screen positioning bounds
    # Step X = tile_w / 2, Step Y = tile_h / 2
    canvas_w = int((cols + rows) * (tile_w / 2) + tile_w)
    canvas_h = int((cols + rows) * (tile_h / 4) + tile_h)

    test_canvas = Image.new("RGBA", (canvas_w, canvas_h), (20, 24, 30, 255))
    draw = ImageDraw.Draw(test_canvas)

    # Title label
    draw.text((canvas_w // 2, 25), "CH_MASK_V1 — 6x6 Isometric 2:1 Seamless Terrain Material Test (stone_surface)", fill=(240, 240, 245), anchor="mm")

    origin_x = canvas_w // 2 - tile_w // 2
    origin_y = 60

    # Draw 6x6 isometric grid in back-to-front painter order
    for row in range(rows):
        for col in range(cols):
            screen_x = origin_x + int((col - row) * (tile_w / 2))
            screen_y = origin_y + int((col + row) * (tile_h / 4))

            test_canvas.alpha_composite(stone_tile, (screen_x, screen_y))

    test_path = os.path.join(REPO_ROOT, "mask_terrain_seamless_test.png")
    test_canvas.save(test_path)
    shutil.copy(test_path, os.path.join(ARTIFACT_DIR, "mask_terrain_seamless_test.png"))
    print(f"Saved 6x6 Isometric Terrain Test to {test_path}")


def render_runtime_viewport_preview(pipeline_results: dict):
    # Render a viewport scene showcasing the custom variants in a neighborhood layout
    vw, vh = 1280, 720
    scene = Image.new("RGBA", (vw, vh), (30, 36, 44, 255))
    draw = ImageDraw.Draw(scene)

    draw.rectangle([0, 0, vw, vh], fill=(32, 40, 48, 255))
    draw.text((vw // 2, 30), "City Horizon — CH_MASK_V1 Runtime Viewport Preview", fill=(240, 245, 250), anchor="mm")

    # Render a ground layout of terrain tiles
    terrain_res = pipeline_results.get("terrain_grass_base")
    if terrain_res and terrain_res["variant_pngs"]:
        dirt_tile = Image.open(terrain_res["variant_pngs"][0]).convert("RGBA")
        stone_tile = Image.open(terrain_res["variant_pngs"][1]).convert("RGBA")

        tw, th = dirt_tile.size
        # Draw small 4x4 terrain area
        for r in range(4):
            for c in range(4):
                px = 250 + (c - r) * (tw // 4)
                py = 280 + (c + r) * (th // 8)
                tile = stone_tile if (r + c) % 2 == 0 else dirt_tile
                scene.alpha_composite(tile.resize((tw // 2, th // 2)), (px, py))

    # Place variant building sprites in viewport positions
    placements = [
        ("house_small_02", 0, 180, 200),
        ("shop_cafe_01", 0, 480, 180),
        ("clinic_small_01", 0, 780, 190),
        ("decor_lighthouse", 0, 1020, 170),
        ("commercial_building_01", 0, 320, 380),
        ("house_small_02", 1, 700, 390),
    ]

    for asset_id, v_idx, pos_x, pos_y in placements:
        res = pipeline_results.get(asset_id)
        if res and v_idx < len(res["variant_pngs"]):
            b_img = Image.open(res["variant_pngs"][v_idx]).convert("RGBA")
            bw, bh = b_img.size
            scale = min(220 / bw, 220 / bh, 1.0)
            nbw, nbh = int(bw * scale), int(bh * scale)
            b_resized = b_img.resize((nbw, nbh), Image.Resampling.LANCZOS)
            scene.alpha_composite(b_resized, (pos_x, pos_y))

    runtime_path = os.path.join(REPO_ROOT, "mask_generic_batch_runtime.png")
    scene.save(runtime_path)
    shutil.copy(runtime_path, os.path.join(ARTIFACT_DIR, "mask_generic_batch_runtime.png"))
    print(f"Saved Viewport Preview to {runtime_path}")


if __name__ == "__main__":
    run_pipeline()
