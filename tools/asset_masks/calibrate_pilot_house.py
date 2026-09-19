"""
CH_MASK_V1 — Pilot Visual Calibration Tool for house_small_01.
Generates:
1. mask_diagnostic_preview.png (R=Red, G=Green, B=Blue, unmasked=Black)
2. mask_diagnostic_extreme.png (Magenta Wall, Cyan Roof, Yellow Details)
3. Calibrated house_small_01_variants.json with clear visual differentiation
4. Calibrated side-by-side composite and runtime viewport preview renders.
"""

import os
import sys
import json
import colorsys
from PIL import Image, ImageDraw

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.asset_masks.apply_mask_variant import process_mask_manifest, apply_variant_to_image
from tools.asset_masks.mask_contract import MaskAssetManifest, VariantConfig, compute_file_sha256
from tools.map_forge.core.projection import tile_visual_top_world, world_to_screen, Camera


def calibrate_house_small_01():
    base_png_path = os.path.join(repo_root, "assets", "buildings", "house_suburban_01_lvl1.png")
    source_dir = os.path.join(repo_root, "assets", "source_masks", "house_small_01")
    generated_dir = os.path.join(repo_root, "assets", "generated", "variants", "house_small_01")
    artifact_dir = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"

    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(generated_dir, exist_ok=True)

    base_img = Image.open(base_png_path).convert("RGBA")
    w, h = base_img.size
    base_bytes = base_img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

    # High-coverage mask classification
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r = base_bytes[idx]
            g = base_bytes[idx + 1]
            b = base_bytes[idx + 2]
            a = base_bytes[idx + 3]

            if a == 0:
                continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

            # Details: windows, window frames, door, steps, foundation line
            is_detail = (
                (v_val < 0.32) or
                (s_val > 0.40 and r < 130) or
                (y > 248) or
                (175 <= y <= 215 and 65 <= x <= 112 and (v_val < 0.45 or s_val > 0.3)) # Door & front window
            )

            # Roof: top section up to roof eaves
            is_roof = (y < 164) and not is_detail

            # Wall: main building body
            is_wall = not is_roof and not is_detail

            if is_roof:
                color_bytes[idx + 1] = 255  # G channel = Roof
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B channel = Details
                color_bytes[idx + 3] = 255
            elif is_wall:
                color_bytes[idx] = 255      # R channel = Wall
                color_bytes[idx + 3] = 255

            # Wear mask: roof eaves, wall base, corners
            if is_roof and (y < 100 or y > 148 or x < 35 or x > 142):
                wear_bytes[idx] = 220
                wear_bytes[idx + 1] = 220
                wear_bytes[idx + 2] = 220
                wear_bytes[idx + 3] = 255
            elif is_wall and (y > 225 or x < 30 or x > 148):
                wear_bytes[idx] = 180
                wear_bytes[idx + 1] = 180
                wear_bytes[idx + 2] = 180
                wear_bytes[idx + 3] = 255

    color_mask_path = os.path.join(source_dir, "house_small_01_mask_color.png")
    wear_mask_path = os.path.join(source_dir, "house_small_01_mask_wear.png")

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(color_mask_path, format="PNG")
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(wear_mask_path, format="PNG")

    # 1. DIAGNOSTIC MASK PREVIEW IMAGE (R=Red, G=Green, B=Blue, Unmasked=Black)
    diag_mask_bytes = bytearray(w * h * 4)
    for i in range(w * h):
        idx = i * 4
        cR = color_bytes[idx]
        cG = color_bytes[idx + 1]
        cB = color_bytes[idx + 2]
        bA = base_bytes[idx + 3]

        if bA > 0:
            if cR > 0:
                diag_mask_bytes[idx] = 255     # Pure Red = Wall
                diag_mask_bytes[idx + 3] = 255
            elif cG > 0:
                diag_mask_bytes[idx + 1] = 255 # Pure Green = Roof
                diag_mask_bytes[idx + 3] = 255
            elif cB > 0:
                diag_mask_bytes[idx + 2] = 255 # Pure Blue = Details
                diag_mask_bytes[idx + 3] = 255
            else:
                diag_mask_bytes[idx + 3] = 255 # Black = Unmasked

    diag_mask_img = Image.frombytes("RGBA", (w, h), bytes(diag_mask_bytes))
    diag_mask_artifact = os.path.join(artifact_dir, "mask_diagnostic_preview.png")
    diag_mask_img.save(diag_mask_artifact, format="PNG")
    print(f"[1/4] Diagnostic mask preview saved to: {diag_mask_artifact}")

    # 2. DIAGNOSTIC EXTREME-COLOR VARIANT (Magenta Wall, Cyan Roof, Yellow Details)
    manifest_temp_dict = {
        "contract": "CH_MASK_V1",
        "assetId": "house_small_01",
        "base": "../../buildings/house_suburban_01_lvl1.png",
        "colorMask": "house_small_01_mask_color.png",
        "wearMask": "house_small_01_mask_wear.png",
        "channels": {
            "R": "wall",
            "G": "roof",
            "B": "details"
        },
        "variants": [
            {
                "id": "diagnostic_extreme",
                "wall": [255, 0, 255],     # Magenta
                "roof": [0, 255, 255],     # Cyan
                "details": [255, 255, 0],  # Yellow
                "wear": 0.0
            }
        ]
    }
    manifest_temp = MaskAssetManifest.from_dict(manifest_temp_dict, source_dir)
    color_img = Image.frombytes("RGBA", (w, h), bytes(color_bytes))
    wear_img = Image.frombytes("RGBA", (w, h), bytes(wear_bytes))

    diag_extreme_img = apply_variant_to_image(
        base_img, color_img, wear_img, manifest_temp, manifest_temp.variants[0]
    )
    diag_extreme_artifact = os.path.join(artifact_dir, "mask_diagnostic_extreme.png")
    diag_extreme_img.save(diag_extreme_artifact, format="PNG")
    print(f"[2/4] Diagnostic extreme variant saved to: {diag_extreme_artifact}")

    # 3. CALIBRATED CANONICAL VARIANTS MANIFEST
    manifest_calibrated_dict = {
        "contract": "CH_MASK_V1",
        "assetId": "house_small_01",
        "base": "../../buildings/house_suburban_01_lvl1.png",
        "colorMask": "house_small_01_mask_color.png",
        "wearMask": "house_small_01_mask_wear.png",
        "channels": {
            "R": "wall",
            "G": "roof",
            "B": "details"
        },
        "variants": [
            {
                "id": "coastal_blue",
                "wall": [235, 242, 250],    # Crisp white-blue plaster wall
                "roof": [35, 120, 195],     # Vibrant coastal ocean blue roof
                "details": [255, 255, 255], # Crisp white trim
                "wear": 0.08
            },
            {
                "id": "suburban_beige",
                "wall": [225, 190, 140],    # Warm ochre beige wall
                "roof": [185, 75, 45],      # Rich terracotta red roof
                "details": [245, 235, 210], # Cream trim
                "wear": 0.05
            },
            {
                "id": "aged",
                "wall": [135, 130, 120],    # Weathered slate plaster wall
                "roof": [70, 72, 75],       # Weathered dark slate roof
                "details": [105, 100, 95],  # Aged timber details
                "wear": 0.50                # Noticeable darkening, desaturation & dirt
            }
        ]
    }

    manifest_path = os.path.join(source_dir, "house_small_01_variants.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_calibrated_dict, f, indent=2)

    png_paths, json_paths = process_mask_manifest(manifest_path, generated_dir)

    print("\n--- CALIBRATED GENERATED VARIANTS ---")
    for p, j in zip(png_paths, json_paths):
        sha_p = compute_file_sha256(p)
        print(f"Variant PNG:  {os.path.basename(p)}")
        print(f"  SHA-256:    {sha_p}")

    # 4. COMPOSITE SIDE-BY-SIDE PREVIEW (Base | Coastal Blue | Suburban Beige | Aged)
    labels = ["Original Base", "Coastal Blue", "Suburban Beige", "Aged (Weathered)"]
    images = [base_img] + [Image.open(p).convert("RGBA") for p in png_paths]

    margin = 20
    header_h = 40
    comp_w = len(images) * w + (len(images) + 1) * margin
    comp_h = h + margin * 2 + header_h

    comp_img = Image.new("RGBA", (comp_w, comp_h), (24, 30, 38, 255))
    draw = ImageDraw.Draw(comp_img)

    for idx, (img_obj, label) in enumerate(zip(images, labels)):
        x_pos = margin + idx * (w + margin)
        y_pos = margin + header_h

        draw.rectangle(
            [x_pos - 4, y_pos - 4, x_pos + w + 4, y_pos + h + 4],
            fill=(34, 42, 54, 255),
            outline=(50, 70, 90, 255),
            width=1
        )
        comp_img.paste(img_obj, (x_pos, y_pos), img_obj)
        draw.text((x_pos, y_pos - header_h + 10), label, fill=(220, 240, 255))

    composite_artifact = os.path.join(artifact_dir, "mask_pilot_composite.png")
    comp_img.save(composite_artifact, format="PNG")
    print(f"[3/4] Calibrated composite preview saved to: {composite_artifact}")

    # 5. REAL RUNTIME ENGINE VIEWPORT RENDER
    tile_coords = [(-3, 0), (-1, 0), (1, 0), (3, 0)]
    canvas_w, canvas_h = 1280, 500
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (18, 24, 32, 255))
    draw_canvas = ImageDraw.Draw(canvas)
    cam = Camera(world_x=0.0, world_y=0.0, zoom=1.0, rotation=0)

    for tx, ty in tile_coords:
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)
        half_w = 64 * cam.zoom
        half_h = 32 * cam.zoom
        pts = [(sx, sy), (sx + half_w, sy + half_h), (sx, sy + 2 * half_h), (sx - half_w, sy + half_h)]
        draw_canvas.polygon(pts, fill=(35, 55, 40, 255), outline=(60, 90, 70, 255))

    anchor_x_ratio = 89.0 / 178.0
    anchor_y_ratio = 244.0 / 276.0

    for (label, sprite), (tx, ty) in zip(zip(labels, images), tile_coords):
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)
        sw, sh = sprite.size
        anc_x = int(sw * anchor_x_ratio)
        anc_y = int(sh * anchor_y_ratio)
        render_x = int(sx - anc_x)
        render_y = int(sy - anc_y + 32)

        canvas.paste(sprite, (render_x, render_y), sprite)
        draw_canvas.ellipse([sx - 3, sy + 32 - 3, sx + 3, sy + 32 + 3], fill=(255, 60, 60, 255))
        draw_canvas.text((render_x + (sw // 2) - 40, render_y - 25), label, fill=(230, 245, 255))
        draw_canvas.text((render_x + (sw // 2) - 40, render_y + sh + 5), f"Tile ({tx}, {ty})", fill=(140, 170, 190))

    draw_canvas.text((30, 20), "CH_MASK_V1 — CALIBRATED RUNTIME ENGINE VIEWPORT PREVIEW", fill=(80, 220, 255))
    draw_canvas.text((30, 42), "Identical Anchor (89, 244) | Identical Footprint 1x1 | Calibrated Visual Contrast", fill=(160, 190, 210))

    runtime_artifact = os.path.join(artifact_dir, "mask_pilot_runtime.png")
    canvas.save(runtime_artifact, format="PNG")
    print(f"[4/4] Calibrated runtime engine viewport preview saved to: {runtime_artifact}")

    print("\nCalibration completed successfully!")

if __name__ == "__main__":
    calibrate_house_small_01()
