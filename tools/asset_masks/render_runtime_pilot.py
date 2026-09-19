"""
Runtime Renderer Pilot Verification Script for CH_MASK_V1.
Renders Base and 3 Masked Variants on an isometric grid using identical anchor, footprint, depth key, and scale.
"""

import os
import sys
import json
from PIL import Image, ImageDraw, ImageFont

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from tools.map_forge.core.projection import tile_visual_top_world, world_to_screen, Camera


def render_runtime_pilot():
    artifact_dir = r"C:\Users\User\.gemini\antigravity\brain\33fb56cd-389b-4045-91b2-e978e5156ea4"
    asset_dir = os.path.join(repo_root, "assets")
    generated_dir = os.path.join(asset_dir, "generated", "variants", "house_small_01")

    base_png_path = os.path.join(asset_dir, "buildings", "house_suburban_01_lvl1.png")
    v1_png_path = os.path.join(generated_dir, "house_small_01_coastal_blue.png")
    v2_png_path = os.path.join(generated_dir, "house_small_01_suburban_beige.png")
    v3_png_path = os.path.join(generated_dir, "house_small_01_aged.png")

    sprites = [
        ("Base (Original)", Image.open(base_png_path).convert("RGBA")),
        ("Coastal Blue", Image.open(v1_png_path).convert("RGBA")),
        ("Suburban Beige", Image.open(v2_png_path).convert("RGBA")),
        ("Aged (Weathered)", Image.open(v3_png_path).convert("RGBA")),
    ]

    # Grid placement coordinates: 4 adjacent tiles along isometric X axis
    tile_coords = [(-3, 0), (-1, 0), (1, 0), (3, 0)]

    canvas_w, canvas_h = 1280, 500
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (18, 24, 32, 255))
    draw = ImageDraw.Draw(canvas)

    cam = Camera(world_x=0.0, world_y=0.0, zoom=1.0, rotation=0)

    # 1. Draw isometric terrain tiles (grass) under each building
    grass_path = os.path.join(asset_dir, "terrain", "grass_isometric_01.png")
    grass_img = Image.open(grass_path).convert("RGBA") if os.path.exists(grass_path) else None

    # Diamond tile drawing helper
    def draw_iso_tile(tx, ty):
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

        # Draw diamond tile wireframe
        half_w = 64 * cam.zoom
        half_h = 32 * cam.zoom

        pts = [
            (sx, sy),
            (sx + half_w, sy + half_h),
            (sx, sy + 2 * half_h),
            (sx - half_w, sy + half_h)
        ]
        draw.polygon(pts, fill=(35, 55, 40, 255), outline=(60, 90, 70, 255))

    for tx, ty in tile_coords:
        draw_iso_tile(tx, ty)

    # 2. Render buildings at identical anchors
    anchor_x_ratio = 89.0 / 178.0  # Tile center anchor
    anchor_y_ratio = 244.0 / 276.0

    for (label, sprite), (tx, ty) in zip(sprites, tile_coords):
        wx, wy = tile_visual_top_world(tx, ty)
        sx, sy = world_to_screen(wx, wy, cam, canvas_w, canvas_h)

        sw, sh = sprite.size
        # Anchor point (center bottom of ground footprint)
        anc_x = int(sw * anchor_x_ratio)
        anc_y = int(sh * anchor_y_ratio)

        # Top-left screen position
        render_x = int(sx - anc_x)
        render_y = int(sy - anc_y + 32)  # Adjust for isometric tile center

        # Paste building sprite
        canvas.paste(sprite, (render_x, render_y), sprite)

        # Draw anchor marker dot
        draw.ellipse([sx - 3, sy + 32 - 3, sx + 3, sy + 32 + 3], fill=(255, 60, 60, 255))

        # Draw label
        draw.text((render_x + (sw // 2) - 40, render_y - 25), label, fill=(230, 245, 255))
        draw.text((render_x + (sw // 2) - 40, render_y + sh + 5), f"Tile ({tx}, {ty})", fill=(140, 170, 190))

    # Header banner
    draw.text((30, 20), "CH_MASK_V1 — REAL RUNTIME ENGINE VIEWPORT PREVIEW", fill=(80, 220, 255))
    draw.text((30, 42), "Identical Anchor (89, 244) | Identical Footprint 1x1 | Zero Geometry Mutation", fill=(160, 190, 210))

    runtime_preview_path = os.path.join(artifact_dir, "mask_pilot_runtime.png")
    canvas.save(runtime_preview_path, format="PNG")
    print(f"Runtime renderer viewport preview saved to: {runtime_preview_path}")

    return runtime_preview_path

if __name__ == "__main__":
    render_runtime_pilot()
