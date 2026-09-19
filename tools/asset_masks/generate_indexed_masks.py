"""
CH_MASK_V1 — Generator for 8-Bit Grayscale Single-Channel Region Masks (mode: "L") and Manifests.
Generates masks & manifest definitions for 6 target assets:
1. house_small_02
2. shop_cafe_01
3. clinic_small_01
4. decor_lighthouse
5. commercial_building_01
6. terrain_grass_base
"""

import os
import json
import colorsys
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def build_house_small_02_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # Ground / driveway / garden exclusion
            is_ground_or_garden = (y >= 210) or (g > r + 10 and y > 190)
            if is_ground_or_garden:
                continue # ID 0

            is_detail = (v_val < 0.35) or (s_val > 0.40 and r < 130)
            is_roof = (y < 165) and not is_detail
            is_wall = not is_roof and not is_detail

            if is_wall:
                mask_bytes[y * w + x] = 1 # wall
            elif is_roof:
                mask_bytes[y * w + x] = 2 # roof
            elif is_detail:
                mask_bytes[y * w + x] = 3 # trim

    mask_path = os.path.join(mask_dir, "house_small_02_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "house_small_02",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "house_small_02_semantic_mask.png",
        "regions": {
            "wall": 1,
            "roof": 2,
            "trim": 3
        },
        "variants": [
            {
                "id": "terracotta_cream",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [220, 190, 150]},
                    "roof": {"mode": "recolor", "targetRGB": [180, 70, 50]},
                    "trim": {"mode": "recolor", "targetRGB": [60, 45, 35]}
                },
                "wear": 0.15
            },
            {
                "id": "slate_blue",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [150, 175, 195]},
                    "roof": {"mode": "recolor", "targetRGB": [60, 75, 95]},
                    "trim": {"mode": "recolor", "targetRGB": [220, 220, 220]}
                },
                "wear": 0.10
            },
            {
                "id": "sage_green",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [160, 180, 155]},
                    "roof": {"mode": "recolor", "targetRGB": [110, 80, 60]},
                    "trim": {"mode": "recolor", "targetRGB": [240, 235, 220]}
                },
                "wear": 0.05
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "house_small_02_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_shop_cafe_01_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            is_ground_or_patio = (y >= 98) or (x < 32 or x > 156) or (g > r and y > 80)
            is_logo_signboard = (38 <= x <= 150 and 12 <= y <= 58 and (v_val > 0.65 or (r > 160 and g > 130)))

            if is_ground_or_patio or is_logo_signboard:
                continue

            is_detail = (v_val < 0.30) or (s_val > 0.45 and r < 120)
            is_awning = (y < 82) and not is_detail
            is_wall = not is_awning and not is_detail

            if is_wall:
                mask_bytes[y * w + x] = 1 # wall
            elif is_awning:
                mask_bytes[y * w + x] = 2 # fabric
            elif is_detail:
                mask_bytes[y * w + x] = 3 # trim

    mask_path = os.path.join(mask_dir, "shop_cafe_01_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "shop_cafe_01",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "shop_cafe_01_semantic_mask.png",
        "regions": {
            "wall": 1,
            "fabric": 2,
            "trim": 3
        },
        "variants": [
            {
                "id": "espresso_bistro",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [215, 195, 175]},
                    "fabric": {"mode": "recolor", "targetRGB": [130, 40, 40]},
                    "trim": {"mode": "recolor", "targetRGB": [50, 35, 30]}
                },
                "wear": 0.10
            },
            {
                "id": "coastal_blue",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [235, 235, 230]},
                    "fabric": {"mode": "recolor", "targetRGB": [45, 115, 165]},
                    "trim": {"mode": "recolor", "targetRGB": [210, 175, 120]}
                },
                "wear": 0.05
            },
            {
                "id": "vintage_mint",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [240, 230, 215]},
                    "fabric": {"mode": "recolor", "targetRGB": [75, 145, 125]},
                    "trim": {"mode": "recolor", "targetRGB": [160, 100, 60]}
                },
                "wear": 0.12
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "shop_cafe_01_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_clinic_small_01_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            is_ground_or_bushes = (y >= 94) or (g > r and y > 70)
            is_red_cross_emblem = (r > 155 and g < 80 and b < 80) or (48 <= x <= 118 and 14 <= y <= 48 and r > 175)

            if is_ground_or_bushes or is_red_cross_emblem:
                continue

            is_detail = (v_val < 0.32) or (s_val > 0.45 and r < 130)
            is_roof = (y < 62) and not is_detail
            is_wall = not is_roof and not is_detail

            if is_wall:
                mask_bytes[y * w + x] = 1 # wall
            elif is_roof:
                mask_bytes[y * w + x] = 2 # roof
            elif is_detail:
                mask_bytes[y * w + x] = 3 # trim

    mask_path = os.path.join(mask_dir, "clinic_small_01_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "clinic_small_01",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "clinic_small_01_semantic_mask.png",
        "regions": {
            "wall": 1,
            "roof": 2,
            "trim": 3
        },
        "variants": [
            {
                "id": "sanitary_white",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [235, 240, 245]},
                    "roof": {"mode": "recolor", "targetRGB": [70, 130, 180]},
                    "trim": {"mode": "recolor", "targetRGB": [180, 190, 200]}
                },
                "wear": 0.05
            },
            {
                "id": "warm_brick",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [190, 110, 90]},
                    "roof": {"mode": "recolor", "targetRGB": [80, 90, 100]},
                    "trim": {"mode": "recolor", "targetRGB": [235, 230, 220]}
                },
                "wear": 0.15
            },
            {
                "id": "modern_teal",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [225, 230, 230]},
                    "roof": {"mode": "recolor", "targetRGB": [35, 125, 125]},
                    "trim": {"mode": "recolor", "targetRGB": [70, 80, 90]}
                },
                "wear": 0.08
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "clinic_small_01_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_decor_lighthouse_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            is_rock_base = (y >= 105)
            is_lantern_lens = (y < 42 and v_val > 0.70 and (s_val < 0.22 or (r > 220 and g > 220)))

            if is_rock_base or is_lantern_lens:
                continue

            is_detail = (v_val < 0.30) or (s_val > 0.40 and r < 120)
            is_dome = (y < 35) and not is_detail
            is_shaft = not is_dome and not is_detail

            if is_dome:
                mask_bytes[y * w + x] = 1 # metal
            elif is_shaft:
                mask_bytes[y * w + x] = 2 # wall
            elif is_detail:
                mask_bytes[y * w + x] = 3 # trim

    mask_path = os.path.join(mask_dir, "decor_lighthouse_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "decor_lighthouse",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "decor_lighthouse_semantic_mask.png",
        "regions": {
            "metal": 1,
            "wall": 2,
            "trim": 3
        },
        "variants": [
            {
                "id": "nautical_red",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [220, 50, 50]},
                    "metal": {"mode": "recolor", "targetRGB": [40, 45, 50]},
                    "trim": {"mode": "recolor", "targetRGB": [240, 240, 240]}
                },
                "wear": 0.20
            },
            {
                "id": "navy_beacon",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [35, 65, 115]},
                    "metal": {"mode": "recolor", "targetRGB": [180, 140, 60]},
                    "trim": {"mode": "recolor", "targetRGB": [245, 245, 240]}
                },
                "wear": 0.10
            },
            {
                "id": "heritage_black",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [50, 55, 60]},
                    "metal": {"mode": "recolor", "targetRGB": [160, 50, 40]},
                    "trim": {"mode": "recolor", "targetRGB": [230, 225, 210]}
                },
                "wear": 0.25
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "decor_lighthouse_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_commercial_building_01_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            r, g, b, a = base_bytes[idx], base_bytes[idx+1], base_bytes[idx+2], base_bytes[idx+3]
            if a == 0: continue

            h_val, s_val, v_val = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

            # Exclude ground base (y >= 260)
            if y >= 260:
                continue

            is_detail = (v_val < 0.25) or (s_val > 0.40 and r < 110)
            is_roof = (y < 40) and not is_detail
            is_wall = not is_roof and not is_detail

            if is_wall:
                mask_bytes[y * w + x] = 1 # wall
            elif is_roof:
                mask_bytes[y * w + x] = 2 # roof
            elif is_detail:
                mask_bytes[y * w + x] = 3 # trim

    mask_path = os.path.join(mask_dir, "commercial_building_01_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "commercial_building_01",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "commercial_building_01_semantic_mask.png",
        "regions": {
            "wall": 1,
            "roof": 2,
            "trim": 3
        },
        "variants": [
            {
                "id": "corporate_navy",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [160, 175, 195]},
                    "roof": {"mode": "recolor", "targetRGB": [45, 65, 95]},
                    "trim": {"mode": "recolor", "targetRGB": [220, 225, 230]}
                },
                "wear": 0.05
            },
            {
                "id": "bronze_glass",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [180, 160, 135]},
                    "roof": {"mode": "recolor", "targetRGB": [90, 75, 60]},
                    "trim": {"mode": "recolor", "targetRGB": [60, 50, 45]}
                },
                "wear": 0.08
            },
            {
                "id": "emerald_plaza",
                "region_recipes": {
                    "wall": {"mode": "recolor", "targetRGB": [170, 195, 180]},
                    "roof": {"mode": "recolor", "targetRGB": [40, 85, 65]},
                    "trim": {"mode": "recolor", "targetRGB": [240, 240, 235]}
                },
                "wear": 0.10
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "commercial_building_01_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_terrain_grass_base_indexed(base_path: str, mask_dir: str):
    os.makedirs(mask_dir, exist_ok=True)
    img = Image.open(base_path).convert("RGBA")
    w, h = img.size
    base_bytes = img.tobytes()
    mask_bytes = bytearray(w * h)

    # For terrain tile, all non-transparent pixels belong to surface (region 1)
    for y in range(h):
        for x in range(w):
            idx = (y * w + x) * 4
            a = base_bytes[idx + 3]
            if a > 0:
                mask_bytes[y * w + x] = 1 # surface

    mask_path = os.path.join(mask_dir, "terrain_grass_base_semantic_mask.png")
    Image.frombytes("L", (w, h), bytes(mask_bytes)).save(mask_path)

    mat_dir = os.path.relpath(os.path.join(REPO_ROOT, "assets", "materials", "terrain"), mask_dir).replace("\\", "/")

    manifest = {
        "contract": "CH_MASK_V1",
        "assetId": "terrain_grass_base",
        "base": os.path.relpath(base_path, mask_dir).replace("\\", "/"),
        "semanticMask": "terrain_grass_base_semantic_mask.png",
        "regions": {
            "surface": 1
        },
        "variants": [
            {
                "id": "dirt_surface",
                "region_recipes": {
                    "surface": {
                        "mode": "texture",
                        "texture": f"{mat_dir}/dirt_01.png",
                        "preserveShading": False,
                        "scale": 1.0
                    }
                }
            },
            {
                "id": "stone_surface",
                "region_recipes": {
                    "surface": {
                        "mode": "texture",
                        "texture": f"{mat_dir}/stone_01.png",
                        "preserveShading": False,
                        "scale": 1.0
                    }
                }
            },
            {
                "id": "sand_surface",
                "region_recipes": {
                    "surface": {
                        "mode": "texture",
                        "texture": f"{mat_dir}/sand_01.png",
                        "preserveShading": False,
                        "scale": 1.0
                    }
                }
            },
            {
                "id": "gravel_surface",
                "region_recipes": {
                    "surface": {
                        "mode": "texture",
                        "texture": f"{mat_dir}/gravel_01.png",
                        "preserveShading": False,
                        "scale": 1.0
                    }
                }
            }
        ]
    }

    manifest_path = os.path.join(mask_dir, "terrain_grass_base_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def build_all():
    out_mask_dir = os.path.join(REPO_ROOT, "assets", "source_masks")
    os.makedirs(out_mask_dir, exist_ok=True)

    manifests = []

    # 1. house_small_02
    p1 = build_house_small_02_indexed(
        os.path.join(REPO_ROOT, "assets", "buildings", "house_suburban_02_lvl1.png"),
        os.path.join(out_mask_dir, "house_small_02")
    )
    manifests.append(p1)

    # 2. shop_cafe_01
    p2 = build_shop_cafe_01_indexed(
        os.path.join(REPO_ROOT, "assets", "buildings", "cafe_01_lvl1.png"),
        os.path.join(out_mask_dir, "shop_cafe_01")
    )
    manifests.append(p2)

    # 3. clinic_small_01
    p3 = build_clinic_small_01_indexed(
        os.path.join(REPO_ROOT, "assets", "buildings", "clinic_small_01_lvl1.png"),
        os.path.join(out_mask_dir, "clinic_small_01")
    )
    manifests.append(p3)

    # 4. decor_lighthouse
    p4 = build_decor_lighthouse_indexed(
        os.path.join(REPO_ROOT, "assets", "decor", "beach", "beach_lighthouse.png"),
        os.path.join(out_mask_dir, "decor_lighthouse")
    )
    manifests.append(p4)

    # 5. commercial_building_01
    p5 = build_commercial_building_01_indexed(
        os.path.join(REPO_ROOT, "assets", "buildings", "commercial_building_01_lvl1.png"),
        os.path.join(out_mask_dir, "commercial_building_01")
    )
    manifests.append(p5)

    # 6. terrain_grass_base
    p6 = build_terrain_grass_base_indexed(
        os.path.join(REPO_ROOT, "assets", "terrain", "grass_isometric_01.png"),
        os.path.join(out_mask_dir, "terrain_grass_base")
    )
    manifests.append(p6)

    print(f"Successfully generated {len(manifests)} indexed 8-bit masks and manifests:")
    for m in manifests:
        print(f" - {m}")

if __name__ == "__main__":
    build_all()
