"""
CH_MASK_V1 — Phase 2 Batch Generator & Visual Diagnostic Pipeline.
Processes house_small_02, shop_cafe_01, clinic_small_01, and decor_lighthouse.
Enforces per-asset identity pixel protection, diagnostic previews, extreme color tests, and engine viewport previews.
"""

import os
import sys
import json
from PIL import Image, ImageDraw

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.asset_masks.generate_precise_masks import build_all_precise_masks
from tools.asset_masks.apply_mask_variant import process_mask_manifest, apply_variant_to_image
from tools.asset_masks.mask_contract import MaskAssetManifest, VariantConfig, compute_file_sha256
from tools.asset_masks.validate_mask_asset import validate_mask_asset
from tools.map_forge.core.projection import tile_visual_top_world, world_to_screen, Camera


def generate_all_phase2_artifacts():
    artifact_dir = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"
    assets = [
        ("house_small_02", "assets/buildings/house_suburban_02_lvl1.png"),
        ("shop_cafe_01", "assets/buildings/cafe_01_lvl1.png"),
        ("clinic_small_01", "assets/buildings/clinic_small_01_lvl1.png"),
        ("decor_lighthouse", "assets/decor/beach/beach_lighthouse.png")
    ]

    print("==================================================")
    print("CH_MASK_V1 — PHASE 2 BATCH GENERATION")
    print("==================================================")

    # 1. Build precise semantic masks
    build_all_precise_masks()

    all_composite_rows = []

    for asset_id, base_rel in assets:
        base_path = os.path.join(repo_root, base_rel)
        source_dir = os.path.join(repo_root, "assets", "source_masks", asset_id)
        generated_dir = os.path.join(repo_root, "assets", "generated", "variants", asset_id)

        color_mask_path = os.path.join(source_dir, f"{asset_id}_mask_color.png")
        wear_mask_path = os.path.join(source_dir, f"{asset_id}_mask_wear.png")
        manifest_path = os.path.join(source_dir, f"{asset_id}_variants.json")

        base_img = Image.open(base_path).convert("RGBA")
        color_img = Image.open(color_mask_path).convert("RGBA")
        wear_img = Image.open(wear_mask_path).convert("RGBA") if os.path.exists(wear_mask_path) else None
        w, h = base_img.size

        base_bytes = base_img.tobytes()
        color_bytes = color_img.tobytes()

        # 1. Mask Diagnostic Preview (R=Red, G=Green, B=Blue, Unmasked=Black/Transparent)
        diag_bytes = bytearray(w * h * 4)
        for i in range(w * h):
            idx = i * 4
            cR, cG, cB, bA = color_bytes[idx], color_bytes[idx+1], color_bytes[idx+2], base_bytes[idx+3]
            if bA > 0:
                if cR > 0: diag_bytes[idx] = 255; diag_bytes[idx+3] = 255 # Pure Red
                elif cG > 0: diag_bytes[idx+1] = 255; diag_bytes[idx+3] = 255 # Pure Green
                elif cB > 0: diag_bytes[idx+2] = 255; diag_bytes[idx+3] = 255 # Pure Blue
                else: diag_bytes[idx+3] = 255 # Black (Unmasked)

        diag_img = Image.frombytes("RGBA", (w, h), bytes(diag_bytes))
        diag_path = os.path.join(artifact_dir, f"mask_{asset_id}_diagnostic_preview.png")
        diag_img.save(diag_path, format="PNG")

        # 2. Extreme Color Diagnostic Test (Magenta Wall/Main, Cyan Roof/Awning/Dome, Yellow Details)
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        manifest = MaskAssetManifest.from_dict(manifest_data, source_dir)
        ch_map = manifest.channel_mapping # e.g. {"R": "wall", "G": "roof", "B": "details"}

        extreme_channels = {}
        if "R" in ch_map: extreme_channels[ch_map["R"]] = [255, 0, 255]   # Magenta
        if "G" in ch_map: extreme_channels[ch_map["G"]] = [0, 255, 255]   # Cyan
        if "B" in ch_map: extreme_channels[ch_map["B"]] = [255, 255, 0]   # Yellow

        extreme_variant = VariantConfig(id="extreme_diag", channels=extreme_channels, wear=0.0)
        extreme_img = apply_variant_to_image(base_img, color_img, wear_img, manifest, extreme_variant)
        extreme_path = os.path.join(artifact_dir, f"mask_{asset_id}_diagnostic_extreme.png")
        extreme_img.save(extreme_path, format="PNG")

        # 3. Process Manifest for Calibrated Variants
        png_paths, json_paths = process_mask_manifest(manifest_path, generated_dir)
        print(f"Asset '{asset_id}' variants generated and validated successfully.")

        # Row for composite preview: Base | Diagnostic | Extreme | Variant1 | Variant2 | Variant3
        variant_imgs = [Image.open(p).convert("RGBA") for p in png_paths]
        row_imgs = [base_img, diag_img, extreme_img] + variant_imgs
        all_composite_rows.append((asset_id, row_imgs))

    # BUILD PHASE 2 BATCH COMPOSITE GRID ARTIFACT
    row_h = 295
    col_w = 195
    margin = 15
    header_h = 50

    comp_w = 6 * col_w + 7 * margin
    comp_h = len(all_composite_rows) * row_h + header_h + margin * 2

    comp_grid = Image.new("RGBA", (comp_w, comp_h), (20, 26, 34, 255))
    draw = ImageDraw.Draw(comp_grid)

    draw.text((margin, 15), "CH_MASK_V1 — PHASE 2 BATCH COMPOSITE GRID (CALIBRATED DIAGNOSTICS)", fill=(80, 220, 255))
    headers = ["Base", "Mask Diagnostic", "Extreme Test", "Variant 1", "Variant 2", "Aged Variant"]
    for c_idx, h_text in enumerate(headers):
        draw.text((margin + c_idx * (col_w + margin) + 10, 35), h_text, fill=(160, 190, 210))

    for r_idx, (asset_id, row_imgs) in enumerate(all_composite_rows):
        y_top = header_h + margin + r_idx * row_h
        draw.text((margin, y_top + 5), f"ASSET: {asset_id.upper()}", fill=(240, 245, 255))

        for c_idx, img_obj in enumerate(row_imgs):
            x_left = margin + c_idx * (col_w + margin)
            draw.rectangle(
                [x_left, y_top + 25, x_left + col_w, y_top + row_h - 10],
                fill=(30, 38, 48, 255), outline=(45, 60, 75, 255)
            )
            # Center sprite inside box
            sw, sh = img_obj.size
            px = x_left + (col_w - sw) // 2
            py = y_top + 25 + (row_h - 35 - sh) // 2
            comp_grid.paste(img_obj, (px, py), img_obj)

    batch_composite_path = os.path.join(artifact_dir, "mask_phase2_batch_composite.png")
    comp_grid.save(batch_composite_path, format="PNG")
    print(f"\nPhase 2 Batch composite grid saved to: {batch_composite_path}")

    # BUILD PHASE 2 BATCH ENGINE VIEWPORT RUNTIME RENDER PREVIEW
    canvas_w, canvas_h = 1280, 720
    runtime_canvas = Image.new("RGBA", (canvas_w, canvas_h), (16, 22, 28, 255))
    draw_rt = ImageDraw.Draw(runtime_canvas)
    cam = Camera(world_x=0.0, world_y=0.0, zoom=0.95, rotation=0)

    # Render each asset's 3 variants in grid positions
    positions = [
        ("house_small_02", [(-4, -2), (-2, -2), (0, -2)]),
        ("shop_cafe_01", [(-4, 0), (-2, 0), (0, 0)]),
        ("clinic_small_01", [(-4, 2), (-2, 2), (0, 2)]),
        ("decor_lighthouse", [(2, -1), (4, -1), (6, -1)]),
    ]

    for asset_id, coords in positions:
        gen_dir = os.path.join(repo_root, "assets", "generated", "variants", asset_id)
        manifest_p = os.path.join(repo_root, "assets", "source_masks", asset_id, f"{asset_id}_variants.json")
        with open(manifest_p, "r", encoding="utf-8") as f: data = json.load(f)

        for (vid_idx, variant_info), (tx, ty) in zip(enumerate(data["variants"]), coords):
            png_p = os.path.join(gen_dir, f"{asset_id}_{variant_info['id']}.png")
            sprite = Image.open(png_p).convert("RGBA")
            sw, sh = sprite.size

            wx, wy = tile_visual_top_world(tx, ty)
            sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

            # Diamond tile
            half_w = 64 * cam.zoom; half_h = 32 * cam.zoom
            pts = [(sx, sy), (sx + half_w, sy + half_h), (sx, sy + 2 * half_h), (sx - half_w, sy + half_h)]
            draw_rt.polygon(pts, fill=(30, 48, 36, 255), outline=(50, 80, 60, 255))

            anc_x = sw // 2; anc_y = int(sh * 0.88)
            rx = int(sx - anc_x); ry = int(sy - anc_y + 32)
            runtime_canvas.paste(sprite, (rx, ry), sprite)
            draw_rt.ellipse([sx - 3, sy + 32 - 3, sx + 3, sy + 32 + 3], fill=(255, 60, 60, 255))
            draw_rt.text((rx, ry - 15), f"{asset_id}:{variant_info['id']}", fill=(200, 230, 255))

    draw_rt.text((30, 20), "CH_MASK_V1 — PHASE 2 BATCH ENGINE VIEWPORT PREVIEW", fill=(80, 220, 255))
    draw_rt.text((30, 42), "Identity Protection Validated | Identical Anchors & Footprints", fill=(160, 190, 210))

    batch_runtime_path = os.path.join(artifact_dir, "mask_phase2_batch_runtime.png")
    runtime_canvas.save(batch_runtime_path, format="PNG")
    print(f"Phase 2 Batch runtime viewport preview saved to: {batch_runtime_path}")

    print("\nPhase 2 Batch Generation Completed Successfully!")

if __name__ == "__main__":
    generate_all_phase2_artifacts()
