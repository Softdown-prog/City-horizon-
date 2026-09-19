"""Classic 2000-era pre-rendered building stylizer for City Horizon.

This stage intentionally runs *after* the generic TYCOON_ASSET_BAKE_V1 package
has been built.  It does not change camera, pivot, footprint or world lighting.
Instead it converts the clean Blender render into the restricted visual language
used by early-2000s isometric city/tycoon sprites:

- stepped tonal bands instead of continuous CG gradients;
- restrained structural roof rows;
- hard alpha plus a one-pixel technical silhouette;
- stylized diagonal cyan/white glass reflections;
- a small indexed palette with real Floyd-Steinberg diffusion.

The source Blender bake remains the canonical 3D source of truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

import postprocess as package_tools

DIRECTIONS = ("south", "east", "west", "north")
PALETTE_COLORS = 48
HARD_ALPHA_THRESHOLD = 72
OUTLINE_ALPHA = 112


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--asset-id", required=True)
    return parser.parse_args()


def _is_glass(r: int, g: int, b: int) -> bool:
    # Canonical house glass is teal/cyan. Keep the test deliberately conservative
    # so plaster, roof, timber and stone never receive the reflection convention.
    return b >= 58 and g >= 55 and b > r * 1.10 and g > r * 1.05 and abs(b - g) < 78


def _is_roof(r: int, g: int, b: int) -> bool:
    # Muted clay/terracotta family used by the canonical residential house.
    return r >= 62 and r > g * 1.22 and g > b * 1.08 and b < 105


def add_classic_surface_conventions(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a < HARD_ALPHA_THRESHOLD:
                continue

            # Roof rows: a restrained 1px dark band every few screen pixels.
            # It is deliberately subtle; it breaks the large smooth roof mass
            # without pretending to be high-resolution geometry.
            if _is_roof(r, g, b) and (y % 6 == 0):
                pixels[x, y] = (
                    max(0, int(r * 0.72)),
                    max(0, int(g * 0.72)),
                    max(0, int(b * 0.72)),
                    a,
                )
                continue

            # Classic illustrated glass: petrol-blue body plus two narrow 45°
            # screen-space reflection bands.  The mask is derived from the baked
            # glass colour, so geometry/camera remain authoritative.
            if _is_glass(r, g, b):
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

    # Remove LANCZOS/transparency haze before palette work.
    hard_alpha = alpha.point(lambda v: 255 if v >= HARD_ALPHA_THRESHOLD else 0)

    rgb = rgba.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(1.13)
    rgb = ImageEnhance.Color(rgb).enhance(1.04)

    # Four bits/channel creates deliberate tonal steps first; Floyd-Steinberg
    # then expresses the transition between the small indexed palette colours.
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

    # One-pixel exterior silhouette.  This also closes anti-aliased fringes.
    dilated = alpha.filter(ImageFilter.MaxFilter(3))
    outside = ImageChops.subtract(dilated, alpha)
    outside = outside.point(lambda v: OUTLINE_ALPHA if v else 0)
    outline = Image.new("RGBA", rgba.size, (43, 37, 31, 0))
    outline.putalpha(outside)

    base = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    base = Image.alpha_composite(base, rgba)

    # Internal one-pixel contrast boundaries from already-banded luminance.
    # Threshold is intentionally high so material grain does not become noisy ink.
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
        "internalTechnicalEdges": True,
        "preservesCameraPivotAndFootprint": True,
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Approve at gameplay scale only if the building reads as a classic pre-rendered "
        "2D sprite rather than a modern miniature 3D render."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("classicPrerenderedBuildingV1: PASS")
    print("paletteColors:", PALETTE_COLORS)
    print("dither: floyd_steinberg")


if __name__ == "__main__":
    main()
