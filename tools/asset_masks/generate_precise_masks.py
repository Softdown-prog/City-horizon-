"""
CH_MASK_V1 — Precise Semantic Mask Generator for Phase 2 Assets.
Builds pixel-perfect masks for house_small_02, shop_cafe_01, clinic_small_01, and decor_lighthouse.
Strictly excludes ground, grass, plants, trees, rocks, outdoor seating, sidewalks, and protected branding/medical emblems.
"""

import os
import sys
import colorsys
from PIL import Image

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def build_house_small_02_mask(base_path: str, source_dir: str):
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # EXCLUDE GROUND, DRIVEWAY, GARDEN, FLOWERS (y >= 210)
            is_ground_or_garden = (y >= 210) or (g > r + 10 and y > 190)
            if is_ground_or_garden:
                continue

            # Details: window frames, door, trim
            is_detail = (v_val < 0.35) or (s_val > 0.40 and r < 130)
            is_roof = (y < 165) and not is_detail
            is_wall = not is_roof and not is_detail

            if is_roof:
                color_bytes[idx + 1] = 255  # G = Roof
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B = Details
                color_bytes[idx + 3] = 255
            elif is_wall:
                color_bytes[idx] = 255      # R = Wall
                color_bytes[idx + 3] = 255

            if is_roof and (y < 100 or y > 150 or x < 35 or x > 140):
                wear_bytes[idx] = 220; wear_bytes[idx+1] = 220; wear_bytes[idx+2] = 220; wear_bytes[idx+3] = 255
            elif is_wall and (y > 195 or x < 30 or x > 145):
                wear_bytes[idx] = 180; wear_bytes[idx+1] = 180; wear_bytes[idx+2] = 180; wear_bytes[idx+3] = 255

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(os.path.join(source_dir, "house_small_02_mask_color.png"))
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(os.path.join(source_dir, "house_small_02_mask_wear.png"))


def build_shop_cafe_01_mask(base_path: str, source_dir: str):
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # EXCLUDE OUTDOOR PATIO FLOOR, SIDEWALK, SEATING, TABLES, CHAIRS, UMBRELLAS, PLANTERS (y >= 98 or sides)
            is_ground_or_patio = (y >= 98) or (x < 32 or x > 156) or (g > r and y > 80)

            # PROTECT BRANDING LOGO, SIGNBOARD TEXT & COFFEE CUP EMBLEM
            is_logo_signboard = (38 <= x <= 150 and 12 <= y <= 58 and (v_val > 0.65 or (r > 160 and g > 130)))

            if is_ground_or_patio or is_logo_signboard:
                continue

            is_detail = (v_val < 0.30) or (s_val > 0.45 and r < 120)
            is_awning = (y < 82) and not is_detail
            is_wall = not is_awning and not is_detail

            if is_awning:
                color_bytes[idx + 1] = 255  # G = Awning
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B = Details
                color_bytes[idx + 3] = 255
            elif is_wall:
                color_bytes[idx] = 255      # R = Wall
                color_bytes[idx + 3] = 255

            if is_awning and (y < 35 or y > 75):
                wear_bytes[idx] = 200; wear_bytes[idx+1] = 200; wear_bytes[idx+2] = 200; wear_bytes[idx+3] = 255

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(os.path.join(source_dir, "shop_cafe_01_mask_color.png"))
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(os.path.join(source_dir, "shop_cafe_01_mask_wear.png"))


def build_clinic_small_01_mask(base_path: str, source_dir: str):
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # EXCLUDE STAIRS, RAMP, GROUND BASE, SIDEWALK, BUSHES/PLANTS (y >= 94 or bushes)
            is_ground_or_bushes = (y >= 94) or (g > r and y > 70)

            # PROTECT RED CROSS EMBLEM & EMERGENCY SIGNAGE
            is_red_cross_emblem = (r > 155 and g < 80 and b < 80) or (48 <= x <= 118 and 14 <= y <= 48 and r > 175)

            if is_ground_or_bushes or is_red_cross_emblem:
                continue

            is_detail = (v_val < 0.32) or (s_val > 0.45 and r < 130)
            is_roof = (y < 62) and not is_detail
            is_wall = not is_roof and not is_detail

            if is_roof:
                color_bytes[idx + 1] = 255  # G = Roof
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B = Details
                color_bytes[idx + 3] = 255
            elif is_wall:
                color_bytes[idx] = 255      # R = Wall
                color_bytes[idx + 3] = 255

            if is_roof and (y < 35 or y > 58):
                wear_bytes[idx] = 180; wear_bytes[idx+1] = 180; wear_bytes[idx+2] = 180; wear_bytes[idx+3] = 255

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(os.path.join(source_dir, "clinic_small_01_mask_color.png"))
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(os.path.join(source_dir, "clinic_small_01_mask_wear.png"))


def build_decor_lighthouse_mask(base_path: str, source_dir: str):
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()

    color_bytes = bytearray(w * h * 4)
    wear_bytes = bytearray(w * h * 4)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # EXCLUDE ROCK FOUNDATION BASE 100% (y >= 105)
            is_rock_base = (y >= 105)

            # PROTECT LANTERN LENS GLASS & LIGHT HOUSING (y < 42 with glass/bright beacon lens)
            is_lantern_lens = (y < 42 and v_val > 0.70 and (s_val < 0.22 or (r > 220 and g > 220)))

            if is_rock_base or is_lantern_lens:
                continue # Remain 100% UNMASKED / ORIGINAL

            is_detail = (v_val < 0.30) or (s_val > 0.40 and r < 120)
            is_dome = (y < 35) and not is_detail
            is_shaft = not is_dome and not is_detail

            if is_dome:
                color_bytes[idx + 1] = 255  # G = Dome cap
                color_bytes[idx + 3] = 255
            elif is_detail:
                color_bytes[idx + 2] = 255  # B = Railings/Trim
                color_bytes[idx + 3] = 255
            elif is_shaft:
                color_bytes[idx] = 255      # R = Shaft bands
                color_bytes[idx + 3] = 255

            if is_shaft and (y < 65 or y > 95):
                wear_bytes[idx] = 200; wear_bytes[idx+1] = 200; wear_bytes[idx+2] = 200; wear_bytes[idx+3] = 255

    Image.frombytes("RGBA", (w, h), bytes(color_bytes)).save(os.path.join(source_dir, "decor_lighthouse_mask_color.png"))
    Image.frombytes("RGBA", (w, h), bytes(wear_bytes)).save(os.path.join(source_dir, "decor_lighthouse_mask_wear.png"))


def build_all_precise_masks():
    assets = [
        ("house_small_02", "assets/buildings/house_suburban_02_lvl1.png", build_house_small_02_mask),
        ("shop_cafe_01", "assets/buildings/cafe_01_lvl1.png", build_shop_cafe_01_mask),
        ("clinic_small_01", "assets/buildings/clinic_small_01_lvl1.png", build_clinic_small_01_mask),
        ("decor_lighthouse", "assets/decor/beach/beach_lighthouse.png", build_decor_lighthouse_mask),
    ]

    for asset_id, base_rel, func in assets:
        base_p = os.path.join(repo_root, base_rel)
        source_d = os.path.join(repo_root, "assets", "source_masks", asset_id)
        os.makedirs(source_d, exist_ok=True)
        func(base_p, source_d)
        print(f"Precise semantic mask built for {asset_id}")

if __name__ == "__main__":
    build_all_precise_masks()
