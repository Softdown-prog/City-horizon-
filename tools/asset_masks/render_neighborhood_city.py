"""
CH_MASK_V1 — Real City Neighborhood Viewport Renderer.
Renders initial_city.json scenario with CH_MASK_V1 variants integrated alongside original buildings,
roads, sidewalks, and coastal terrain to test visual variety, depth sorting, and neighborhood context.
"""

import os
import sys
import json
from PIL import Image, ImageDraw, ImageFont

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.map_forge.core.projection import tile_visual_top_world, world_to_screen, Camera


def render_city_neighborhood():
    artifact_dir = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"
    scenario_path = os.path.join(repo_root, "assets", "scenarios", "initial_city.json")

    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    canvas_w, canvas_h = 1920, 1080
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (22, 28, 36, 255))
    draw = ImageDraw.Draw(canvas)

    # Camera looking at the main residential/commercial neighborhood
    cam = Camera(world_x=0.0, world_y=2.0, zoom=1.1, rotation=0)

    # 1. Load & Render Terrain Tiles
    terrain_tiles = scenario.get("terrain", [])
    grass_default_path = os.path.join(repo_root, "assets", "terrain", "grass_isometric_01.png")
    default_grass_img = Image.open(grass_default_path).convert("RGBA") if os.path.exists(grass_default_path) else None

    # Load terrain texture cache
    terrain_cache = {}

    for t_info in terrain_tiles:
        tx, ty = t_info["tileX"], t_info["tileY"]
        tex_path = os.path.join(repo_root, t_info.get("texture", ""))
        
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

        # Draw tile base polygon or image
        if os.path.exists(tex_path):
            if tex_path not in terrain_cache:
                terrain_cache[tex_path] = Image.open(tex_path).convert("RGBA")
            t_img = terrain_cache[tex_path]
            # Center tile sprite
            canvas.paste(t_img, (int(sx - 64 * cam.zoom), int(sy)), t_img)
        else:
            half_w = 64 * cam.zoom
            half_h = 32 * cam.zoom
            pts = [(sx, sy), (sx + half_w, sy + half_h), (sx, sy + 2 * half_h), (sx - half_w, sy + half_h)]
            draw.polygon(pts, fill=(35, 55, 40, 255), outline=(50, 75, 55, 255))

    # 2. Load & Render Roads
    roads = scenario.get("roads", [])
    road_img_path = os.path.join(repo_root, "assets", "roads", "road_straight_ns.png")
    road_img = Image.open(road_img_path).convert("RGBA") if os.path.exists(road_img_path) else None

    for r_info in roads:
        tx, ty = r_info["tileX"], r_info["tileY"]
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

        if road_img:
            canvas.paste(road_img, (int(sx - 64 * cam.zoom), int(sy)), road_img)
        else:
            half_w = 64 * cam.zoom; half_h = 32 * cam.zoom
            pts = [(sx, sy), (sx + half_w, sy + half_h), (sx, sy + 2 * half_h), (sx - half_w, sy + half_h)]
            draw.polygon(pts, fill=(60, 65, 70, 255), outline=(80, 85, 90, 255))

    # 3. Load & Render Buildings (Mixing Original and CH_MASK_V1 Variants)
    buildings = scenario.get("buildings", [])

    # Map of building definitions to CH_MASK_V1 generated variant PNG paths
    variant_pool = {
        "house_suburban_01": [
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_01", "house_small_01_coastal_blue.png"),
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_01", "house_small_01_suburban_beige.png"),
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_01", "house_small_01_aged.png"),
        ],
        "house_suburban_02": [
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_02", "house_small_02_coastal_blue.png"),
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_02", "house_small_02_suburban_beige.png"),
            os.path.join(repo_root, "assets", "generated", "variants", "house_small_02", "house_small_02_aged.png"),
        ],
        "cafe_01": [
            os.path.join(repo_root, "assets", "generated", "variants", "shop_cafe_01", "shop_cafe_01_vibrant_blue.png"),
            os.path.join(repo_root, "assets", "generated", "variants", "shop_cafe_01", "shop_cafe_01_terracotta_retail.png"),
        ],
        "clinic_small_01": [
            os.path.join(repo_root, "assets", "generated", "variants", "clinic_small_01", "clinic_small_01_medical_white.png"),
        ],
        "beach_lighthouse": [
            os.path.join(repo_root, "assets", "generated", "variants", "decor_lighthouse", "decor_lighthouse_nautical_red_white.png"),
        ]
    }

    # Sort buildings by depth key (tile_x + tile_y) for correct isometric depth sorting
    sorted_buildings = sorted(buildings, key=lambda b: (b["tileX"] + b["tileY"], b["tileX"]))

    sprite_cache = {}
    variant_counters = {}

    for b_info in sorted_buildings:
        tx, ty = b_info["tileX"], b_info["tileY"]
        def_id = b_info["definitionId"]

        # Check if we should use a CH_MASK_V1 variant
        use_variant_path = None
        if def_id in variant_pool and variant_pool[def_id]:
            v_idx = variant_counters.get(def_id, 0)
            variant_counters[def_id] = v_idx + 1
            # Alternate between original base and variants
            if v_idx % 2 == 1:
                pool = variant_pool[def_id]
                use_variant_path = pool[(v_idx // 2) % len(pool)]

        if use_variant_path and os.path.exists(use_variant_path):
            sprite_path = use_variant_path
            is_mask_variant = True
        else:
            # Original building sprite from definition
            def_path = os.path.join(repo_root, "assets", "definitions", f"{def_id}.json")
            sprite_path = None
            if os.path.exists(def_path):
                with open(def_path, "r", encoding="utf-8") as fdef:
                    ddata = json.load(fdef)
                    sprite_path = os.path.join(repo_root, ddata.get("texture", ""))
            is_mask_variant = False

        if not sprite_path or not os.path.exists(sprite_path):
            continue

        if sprite_path not in sprite_cache:
            sprite_cache[sprite_path] = Image.open(sprite_path).convert("RGBA")
        b_sprite = sprite_cache[sprite_path]

        sw, sh = b_sprite.size
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

        # Standard anchor calculation (bottom center of footprint)
        anc_x = sw // 2
        anc_y = int(sh * 0.88)
        rx = int(sx - anc_x)
        ry = int(sy - anc_y + 32)

        # Render building
        canvas.paste(b_sprite, (rx, ry), b_sprite)

        # Indicator tag for CH_MASK_V1 variant vs Original Base
        if is_mask_variant:
            var_name = os.path.basename(sprite_path).replace(".png", "").replace(f"{def_id}_", "")
            draw.rectangle([rx + 5, ry + 5, rx + 120, ry + 22], fill=(20, 80, 140, 220), outline=(80, 180, 255))
            draw.text((rx + 8, ry + 7), f"CH_MASK: {var_name}", fill=(240, 250, 255))

    # Header title banner
    draw.rectangle([20, 15, 750, 70], fill=(16, 22, 30, 230), outline=(40, 160, 220), width=2)
    draw.text((35, 25), "CITY HORIZON — REAL NEIGHBORHOOD INTEGRATION TEST", fill=(80, 220, 255))
    draw.text((35, 48), "CH_MASK_V1 Variants Mixed in Real City Scenario (initial_city.json)", fill=(160, 190, 210))

    neighborhood_artifact = os.path.join(artifact_dir, "mask_neighborhood_city_render.png")
    canvas.save(neighborhood_artifact, format="PNG")
    print(f"Real City Neighborhood Viewport Render saved to: {neighborhood_artifact}")

    return neighborhood_artifact

if __name__ == "__main__":
    render_city_neighborhood()
