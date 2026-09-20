"""City Horizon stylized pre-rendered building treatment.

This stage runs after the generic TYCOON_ASSET_BAKE_V1 package. It never changes
camera, pivot, footprint or authored geometry. Its job is to keep the useful
material/lighting information from Blender while making the final sprite read
cleanly at city-builder gameplay scale.

The current production direction is CH_STYLIZED_PRERENDER_V1. Classic Tycoon
art remains a readability influence, not a hardware-era emulation target.
Per-asset ``buildingPostProcess`` values are optional; assets without a profile
retain the older, stronger stylization defaults for backwards compatibility.

Surface handling is deliberately conservative:
- broad wall/material lighting is preserved rather than crushed into large bands;
- clay-like roof pixels can receive restrained structural rows;
- stylized glass reflections are limited to window-sized connected components;
- silhouette/internal edges are configurable and kept secondary to material read.

True material-ID masks are a future pipeline extension. The current roof/glass
separation is a deterministic image-space surface classification, so the manifest
states that limitation explicitly instead of pretending it is a Blender material pass.
"""

from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

import postprocess as package_tools

DIRECTIONS = ("south", "east", "west", "north")
HARD_ALPHA_THRESHOLD = 72
GLASS_MIN_PIXELS = 5
GLASS_MAX_PIXELS = 900
GLASS_MAX_WIDTH_RATIO = 0.22
GLASS_MAX_HEIGHT_RATIO = 0.30

LEGACY_DEFAULTS = {
    "profile": "classic_prerendered_building_v1",
    "paletteColors": 48,
    "paletteDither": True,
    "posterizeBitsPerChannel": 4,
    "contrastMultiplier": 1.13,
    "saturationMultiplier": 1.04,
    "outlineAlpha": 112,
    "internalEdgeAlpha": 52,
    "internalEdgeThreshold": 74,
    "roofStructuralRows": True,
    "roofRowSpacingPx": 6,
    "roofRowDarken": 0.72,
    "glassReflectionStrength": 1.0,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-config")
    return parser.parse_args()


def load_profile(asset_config: str | None) -> dict:
    profile = dict(LEGACY_DEFAULTS)
    if asset_config:
        asset = json.loads(Path(asset_config).read_text(encoding="utf-8"))
        overrides = asset.get("buildingPostProcess", {})
        for key in profile:
            if key in overrides:
                profile[key] = overrides[key]
        profile["intent"] = overrides.get(
            "intent", "stylized_prerender_not_historical_emulation"
        )
        profile["surfacePolicy"] = overrides.get("surfacePolicy", {})
    else:
        profile["intent"] = "legacy_stronger_stylization"
        profile["surfacePolicy"] = {}

    profile["paletteColors"] = max(16, min(192, int(profile["paletteColors"])))
    profile["posterizeBitsPerChannel"] = max(4, min(8, int(profile["posterizeBitsPerChannel"])))
    profile["contrastMultiplier"] = max(0.5, min(1.5, float(profile["contrastMultiplier"])))
    profile["saturationMultiplier"] = max(0.5, min(1.5, float(profile["saturationMultiplier"])))
    profile["outlineAlpha"] = max(0, min(180, int(profile["outlineAlpha"])))
    profile["internalEdgeAlpha"] = max(0, min(120, int(profile["internalEdgeAlpha"])))
    profile["internalEdgeThreshold"] = max(1, min(254, int(profile["internalEdgeThreshold"])))
    profile["roofRowSpacingPx"] = max(3, int(profile["roofRowSpacingPx"]))
    profile["roofRowDarken"] = max(0.55, min(1.0, float(profile["roofRowDarken"])))
    profile["glassReflectionStrength"] = max(0.0, min(1.0, float(profile["glassReflectionStrength"])))
    profile["paletteDither"] = bool(profile["paletteDither"])
    profile["roofStructuralRows"] = bool(profile["roofStructuralRows"])
    return profile


def _is_glass_candidate(r: int, g: int, b: int) -> bool:
    return b >= 58 and g >= 55 and b > r * 1.10 and g > r * 1.05 and abs(b - g) < 78


def _is_roof(r: int, g: int, b: int) -> bool:
    # Broad muted clay/terracotta classifier. Kept intentionally conservative:
    # wall treatment must not depend on this test.
    return r >= 62 and r > g * 1.22 and g > b * 1.08 and b < 125


def build_glass_mask(image: Image.Image) -> Image.Image:
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
            if (
                GLASS_MIN_PIXELS <= count <= GLASS_MAX_PIXELS
                and box_w <= max_w
                and box_h <= max_h
            ):
                for x, y in pixels:
                    out[x, y] = 255
    return accepted


def _blend_rgb(source, target, strength):
    return tuple(
        max(0, min(255, int(round(source[i] * (1.0 - strength) + target[i] * strength))))
        for i in range(3)
    )


def add_surface_conventions(image: Image.Image, profile: dict) -> Image.Image:
    """Apply only local conventions; broad walls remain close to the Blender bake."""
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    glass_mask = build_glass_mask(rgba)
    glass = glass_mask.load()
    roof_rows = bool(profile["roofStructuralRows"])
    row_spacing = int(profile["roofRowSpacingPx"])
    row_darken = float(profile["roofRowDarken"])
    glass_strength = float(profile["glassReflectionStrength"])

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < HARD_ALPHA_THRESHOLD:
                continue

            if roof_rows and _is_roof(r, g, b) and (y % row_spacing == 0):
                pixels[x, y] = (
                    max(0, int(r * row_darken)),
                    max(0, int(g * row_darken)),
                    max(0, int(b * row_darken)),
                    a,
                )
                continue

            if glass[x, y] and glass_strength > 0.0:
                phase = (x + y) % 23
                if phase in (2, 3):
                    target = (184, 226, 226)
                elif phase in (4, 5, 6):
                    target = (92, 171, 184)
                else:
                    target = (
                        min(86, int(r * 0.82)),
                        min(126, int(g * 0.92)),
                        min(145, int(b * 0.94)),
                    )
                nr, ng, nb = _blend_rgb((r, g, b), target, glass_strength)
                pixels[x, y] = (nr, ng, nb, a)

    return rgba


def restrain_palette(image: Image.Image, profile: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    hard_alpha = alpha.point(lambda v: 255 if v >= HARD_ALPHA_THRESHOLD else 0)

    rgb = rgba.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(float(profile["contrastMultiplier"]))
    rgb = ImageEnhance.Color(rgb).enhance(float(profile["saturationMultiplier"]))

    bits = int(profile["posterizeBitsPerChannel"])
    if bits < 8:
        rgb = ImageOps.posterize(rgb, bits)

    dither = Image.Dither.FLOYDSTEINBERG if profile["paletteDither"] else Image.Dither.NONE
    rgb = rgb.quantize(
        colors=int(profile["paletteColors"]),
        method=Image.Quantize.MEDIANCUT,
        dither=dither,
    ).convert("RGB")

    out = rgb.convert("RGBA")
    out.putalpha(hard_alpha)
    return out


def add_technical_edges(image: Image.Image, profile: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    dilated = alpha.filter(ImageFilter.MaxFilter(3))
    outside = ImageChops.subtract(dilated, alpha)
    outline_alpha = int(profile["outlineAlpha"])
    outside = outside.point(lambda v: outline_alpha if v else 0)
    outline = Image.new("RGBA", rgba.size, (43, 37, 31, 0))
    outline.putalpha(outside)

    base = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    base = Image.alpha_composite(base, rgba)

    internal_alpha = int(profile["internalEdgeAlpha"])
    if internal_alpha <= 0:
        return base

    gray = ImageOps.grayscale(rgba.convert("RGB"))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    threshold = int(profile["internalEdgeThreshold"])
    internal = edges.point(lambda v: internal_alpha if v >= threshold else 0)
    internal = ImageChops.multiply(internal, alpha)
    ink = Image.new("RGBA", rgba.size, (37, 34, 31, 0))
    ink.putalpha(internal)
    return Image.alpha_composite(base, ink)


def stylize_color(image: Image.Image, profile: dict) -> Image.Image:
    image = add_surface_conventions(image, profile)
    image = restrain_palette(image, profile)
    return add_technical_edges(image, profile)


def main():
    args = parse_args()
    package = Path(args.package)
    asset_id = args.asset_id
    profile = load_profile(args.asset_config)
    manifest_path = package / f"{asset_id}_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pivots = {view["direction"]: view["pivot"] for view in manifest["views"]}

    candidates = {}
    for direction in DIRECTIONS:
        color_path = package / f"{asset_id}_{direction}_color_pass.png"
        shadow_path = package / f"{asset_id}_{direction}_shadow_pass.png"

        color = stylize_color(Image.open(color_path), profile)
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

    manifest["paletteColorCount"] = int(profile["paletteColors"])
    manifest["candidatePostProcess"] = {
        "mode": "ch_stylized_prerender_building_v2",
        "styleContract": "CH_STYLIZED_PRERENDER_V1",
        "profile": str(profile["profile"]),
        "intent": str(profile["intent"]),
        "paletteColors": int(profile["paletteColors"]),
        "dither": "floyd_steinberg" if profile["paletteDither"] else "none",
        "posterizeBitsPerChannel": int(profile["posterizeBitsPerChannel"]),
        "contrastMultiplier": float(profile["contrastMultiplier"]),
        "saturationMultiplier": float(profile["saturationMultiplier"]),
        "tonalIntent": "preserve_blender_material_lighting_with_palette_restraint",
        "hardAlphaThreshold": HARD_ALPHA_THRESHOLD,
        "outlineAlpha": int(profile["outlineAlpha"]),
        "internalEdgeAlpha": int(profile["internalEdgeAlpha"]),
        "internalEdgeThreshold": int(profile["internalEdgeThreshold"]),
        "roofStructuralRows": bool(profile["roofStructuralRows"]),
        "roofRowSpacingPx": int(profile["roofRowSpacingPx"]),
        "roofRowDarken": float(profile["roofRowDarken"]),
        "glassReflectionStrength": float(profile["glassReflectionStrength"]),
        "glassIsolation": "connected_window_components",
        "surfaceIdentityMode": "deterministic_image_space_roof_and_glass_classification_v1",
        "trueMaterialIdMasks": False,
        "surfacePolicy": profile.get("surfacePolicy", {}),
        "preservesCameraPivotAndFootprint": True,
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Approve at gameplay scale only if walls keep broad material continuity, roof hue remains coherent "
        "across light/shadow, glass treatment stays inside windows, and no large artificial tonal patches appear."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("chStylizedPrerenderBuildingV2: PASS")
    print("profile:", profile["profile"])
    print("paletteColors:", profile["paletteColors"])
    print("dither:", "floyd_steinberg" if profile["paletteDither"] else "none")
    print("posterizeBitsPerChannel:", profile["posterizeBitsPerChannel"])


if __name__ == "__main__":
    main()
