"""Classic 2000-era pre-rendered building stylizer for City Horizon.

This stage intentionally runs *after* the generic TYCOON_ASSET_BAKE_V1 package
has been built. It does not change camera, pivot, footprint or world lighting.
Instead it converts the clean Blender render into the restricted visual language
used by early-2000s isometric city/tycoon sprites:

- stepped tonal bands instead of continuous CG gradients;
- restrained structural roof rows;
- hard alpha plus a one-pixel technical silhouette;
- stylized diagonal cyan/white glass reflections, isolated to window components;
- a small indexed palette with real Floyd-Steinberg diffusion.

The source Blender bake remains the canonical 3D source of truth.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

import postprocess as package_tools

DIRECTIONS = ("south", "east", "west", "north")
PALETTE_COLORS = 48
HARD_ALPHA_THRESHOLD = 72
OUTLINE_ALPHA = 112

# Window-component gate. The colour test deliberately over-selects teal-ish
# pixels, then connected-component filtering removes large wall regions.
GLASS_MIN_PIXELS = 5
GLASS_MAX_PIXELS = 900
GLASS_MAX_WIDTH_RATIO = 0.22
GLASS_MAX_HEIGHT_RATIO = 0.30


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--asset-id", required=True)
    return parser.parse_args()


def _is_glass_candidate(r: int, g: int, b: int) -> bool:
    """Broad chroma test; spatial component filtering provides final isolation."""
    return b >= 58 and g >= 55 and b > r * 1.10 and g > r * 1.05 and abs(b - g) < 78


def _is_roof(r: int, g: int, b: int) -> bool:
    # Muted clay/terracotta family used by the canonical residential house.
    return r >= 62 and r > g * 1.22 and g > b * 1.08 and b < 105


def build_glass_mask(image: Image.Image) -> Image.Image:
    """Return a binary mask containing only window-sized teal components.

    Earlier revisions applied the reflection convention directly from colour.
    Shadowed plaster can enter the same blue/teal range after the Blender bake,
    producing diagonal reflection stripes across masonry. Here colour is only a
    candidate test. Connected components that are too large to be a window are
    rejected, so reflection bands cannot escape into wall surfaces.
    """
    rgba = image.convert("RGBA")
    width, height = rgba.size
    src = rgba.load()
    candidate = [[False] * width for _ in range(height)]

    for y in range(height):
        for x in range(width):
            r, g, b, a = src[x, y]
            if a >= HARD_ALPHA_THRESHOLD and _is_glass_candidate(r, g, b):
                candidate[y][x] = True

    visited = [[False] * width for _ in range(height)]
    accepted = Image.new("L", (width, height), 0)
    out = accepted.load()
    max_w = max(2, int(width * GLASS_MAX_WIDTH_RATIO))
    max_h = max(2, int(height * GLASS_MAX_HEIGHT_RATIO))

    for y0 in range(height):
        for x0 in range(width):
            if not candidate[y0][x0] or visited[y0][x0]:
                continue

            queue = deque([(x0, y0)])
            visited[y0][x0] = True
            pixels = []
            min_x = max_x = x0
            min_y = max_y = y0

            while queue:
                x, y = queue.popleft()
                pixels.append((x, y))
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < width and 0 <= ny < height:
                        if candidate[ny][nx] and not visited[ny][nx]:
                            visited[ny][nx] = True
                            queue.append((nx, ny))

            count = len(pixels)
            box_w = max_x - min_x + 1
            box_h = max_y - min_y + 1
            window_like = (
                GLASS_MIN_PIXELS <= count <= GLASS_MAX_PIXELS
                and box_w <= max_w
                and box_h <= max_h
            )
            if window_like:
                for x, y in pixels:
                    out[x, y] = 255

    return accepted


def add_classic_surface_conventions(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    glass_mask = build_glass_mask(rgba)
    glass = glass_mask.load()

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < HARD_ALPHA_THRESHOLD:
                continue

            # Roof rows: a restrained 1px dark band every few screen pixels.
            if _is_roof(r, g, b) and (y % 6 == 0):
                pixels[x, y] = (
                    max(0, int(r * 0.72)),
                    max(0, int(g * 0.72)),
                    max(0, int(b * 0.72)),
                    a,
                )
                continue

            # Classic illustrated glass is now confined to window-sized connected
            # components. Wall pixels can no longer inherit diagonal reflections.
            if glass[x, y]:
                phase = (x + y) % 23
                if phase in (2, 3):
                    pixels[x, y] = (184, 226, 226, a)
                elif phase in (4, 5, 6):
                    pixels[x, y] = (92, 171, 184, a)
                else:
                    pixels[x, y] = (
                        min(86, int(r * 0.74)),
                        min(126, int(g * 0.86)),
                        min(145, int(b * 0.90)),
                        a,
                    )

    return rgba


def band_and_quantize(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    hard_alpha = alpha.point(lambda v: 255 if v >= HARD_ALPHA_THRESHOLD else 0)

    rgb = rgba.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.13)
    rgb = ImageEnhance.Color(rgb).enhance(1.04)
    rgb = ImageOps.posterize(rgb, 4)
    rgb = rgb.quantize(
        colors=PALETTE_COLORS,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    ).convert("RGB")

    out = rgb.convert("RGBA")
    out.putalpha(hard_alpha)
    return out


def add_technical_edges(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    dilated = alpha.filter(ImageFilter.MaxFilter(3))
    outside = ImageChops.subtract(dilated, alpha)
    outside = outside.point(lambda v: OUTLINE_ALPHA if v else 0)
    outline = Image.new("RGBA", rgba.size, (43, 37, 31, 0))
    outline.putalpha(outside)

    base = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    base = Image.alpha_composite(base, rgba)

    gray = ImageOps.grayscale(rgba.convert("RGB"))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    internal = edges.point(lambda v: 52 if v >= 74 else 0)
    internal = ImageChops.multiply(internal, alpha)
    ink = Image.new("RGBA", rgba.size, (37, 34, 31, 0))
    ink.putalpha(internal)
    return Image.alpha_composite(base, ink)


def stylize_color(image: Image.Image) -> Image.Image:
    image = add_classic_surface_conventions(image)
    image = band_and_quantize(image)
    return add_technical_edges(image)


def main():
    args = parse_args()
    package = Path(args.package)
    asset_id = args.asset_id
    manifest_path = package / f"{asset_id}_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pivots = {view["direction"]: view["pivot"] for view in manifest["views"]}

    candidates = {}
    for direction in DIRECTIONS:
        color_path = package / f"{asset_id}_{direction}_color_pass.png"
        shadow_path = package / f"{asset_id}_{direction}_shadow_pass.png"

        color = stylize_color(Image.open(color_path))
        shadow = Image.open(shadow_path).convert("RGBA")
        sprite = package_tools.composite_shadow(color, shadow)

        color.save(color_path)
        sprite.save(package / f"{asset_id}_{direction}.png")
        candidates[direction] = sprite

    package_tools.make_fixed_sheet(candidates).save(package / f"{asset_id}_4view.png")
    atlas, atlas_records = package_tools.make_trimmed_atlas(candidates, pivots)
    atlas.save(package / f"{asset_id}_atlas.png")
    package_tools.make_direction_review(candidates, pivots).save(package / f"{asset_id}_review.png")
    context = package_tools.make_context_board(candidates, pivots)
    context.save(package / f"{asset_id}_4dir_context.png")
    context.save(package / "tycoon_photo_studio_in_game_context.png")

    manifest["paletteColorCount"] = PALETTE_COLORS
    manifest["candidatePostProcess"] = {
        "mode": "classic_prerendered_building_v1",
        "paletteColors": PALETTE_COLORS,
        "dither": "floyd_steinberg",
        "posterizeBitsPerChannel": 4,
        "tonalIntent": "stepped_face_banding",
        "hardAlphaThreshold": HARD_ALPHA_THRESHOLD,
        "outlineAlpha": OUTLINE_ALPHA,
        "roofStructuralRows": True,
        "stylizedDiagonalGlassReflection": True,
        "glassIsolation": "connected_window_components",
        "glassMaxWidthRatio": GLASS_MAX_WIDTH_RATIO,
        "glassMaxHeightRatio": GLASS_MAX_HEIGHT_RATIO,
        "internalTechnicalEdges": True,
        "preservesCameraPivotAndFootprint": True,
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Approve at gameplay scale only if glass reflections remain inside window panes "
        "and the building reads as a classic pre-rendered 2D sprite."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("classicPrerenderedBuildingV1: PASS")
    print("paletteColors:", PALETTE_COLORS)
    print("dither: floyd_steinberg")
    print("glassIsolation: connected_window_components")


if __name__ == "__main__":
    main()
