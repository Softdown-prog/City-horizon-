"""
Helper script to generate canonical source masks and variants manifest for house_small_01 pilot asset.
"""

import os
import json
import colorsys
from PIL import Image

def generate_house_small_01_masks(base_png_path: str, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    img = Image.open(base_png_path).convert("RGBA")
    w, h = img.size

    base_bytes = img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

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

            # Region Classification:
            # 1. Roof: upper section (y < 165) with warm/terracotta or darker roof hues
            is_roof = (y < 165) and (r > g + 5) and (v_val > 0.25)
            # 2. Details: dark trims, window frames, door, steps
            is_detail = (v_val < 0.35) or (s_val > 0.45 and r < 140) or (y > 240 and v_val < 0.5)

            if is_roof:
                color_bytes[idx + 1] = 255  # G channel = roof
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B channel = details
                color_bytes[idx + 3] = 255
            else:
                color_bytes[idx] = 255      # R channel = wall
                color_bytes[idx + 3] = 255

            # Wear mask: higher intensity on roof edges (y in 80..160) and lower wall base (y > 230)
            if is_roof and (y < 110 or y > 150 or x < 35 or x > 140):
                wear_bytes[idx] = 200
                wear_bytes[idx + 1] = 200
                wear_bytes[idx + 2] = 200
                wear_bytes[idx + 3] = 255
            elif not is_roof and y > 235:
                wear_bytes[idx] = 160
                wear_bytes[idx + 1] = 160
                wear_bytes[idx + 2] = 160
                wear_bytes[idx + 3] = 255

    color_mask_path = os.path.join(output_dir, "house_small_01_mask_color.png")
    wear_mask_path = os.path.join(output_dir, "house_small_01_mask_wear.png")

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(color_mask_path, format="PNG")
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(wear_mask_path, format="PNG")

    # Variants Manifest referencing existing canonical base sprite
    manifest_dict = {
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
                "wall": [220, 230, 235],
                "roof": [65, 110, 145],
                "details": [245, 245, 240],
                "wear": 0.10
            },
            {
                "id": "suburban_beige",
                "wall": [215, 195, 160],
                "roof": [125, 75, 55],
                "details": [235, 225, 205],
                "wear": 0.05
            },
            {
                "id": "aged",
                "wall": [175, 170, 160],
                "roof": [90, 85, 80],
                "details": [160, 155, 145],
                "wear": 0.45
            }
        ]
    }

    manifest_path = os.path.join(output_dir, "house_small_01_variants.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_dict, f, indent=2)

    print(f"Generated pilot source masks and manifest in {output_dir}")

if __name__ == "__main__":
    base_path = os.path.abspath("assets/buildings/house_suburban_01_lvl1.png")
    out_dir = os.path.abspath("assets/source_masks/house_small_01")
    generate_house_small_01_masks(base_path, out_dir)
