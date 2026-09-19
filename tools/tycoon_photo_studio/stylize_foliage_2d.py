"""Apply a classic 2D Tycoon foliage treatment to an already baked static asset package.

This stage is intentionally asset-class specific. It keeps the canonical camera, pivot,
Blender source bake and generic package format intact, while reducing modern 3D cues:
soft gradients, excessive palette depth, long dark shadows and antialiased silhouette haze.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

import postprocess as package_tools

DIRECTIONS = ("south", "east", "west", "north")
PALETTE_COLORS = 24
SHADOW_ALPHA_MAX = 62
SHADOW_RADIUS_PX = 82.0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--asset-id", required=True)
    return parser.parse_args()


def flatten_color(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    # Remove translucent fringe before color reduction. The final outline is rebuilt below.
    hard_alpha = alpha.point(lambda value: 255 if value >= 72 else 0)
    rgb = rgba.convert("RGB")
    rgb = ImageEnhance.Color(rgb).enhance(1.18)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.12)
    rgb = ImageOps.posterize(rgb, 4)
    rgb = rgb.quantize(
        colors=PALETTE_COLORS,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")

    out = rgb.convert("RGBA")
    out.putalpha(hard_alpha)

    # One-pixel restrained outline gives the miniature a painted sprite silhouette.
    dilated = hard_alpha.filter(ImageFilter.MaxFilter(3))
    edge = ImageChops.subtract(dilated, hard_alpha)
    edge = edge.point(lambda value: 72 if value else 0)
    outline = Image.new("RGBA", out.size, (39, 45, 32, 0))
    outline.putalpha(edge)
    base = Image.new("RGBA", out.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    return Image.alpha_composite(base, out)


def simplify_shadow(image: Image.Image, pivot: dict[str, int]) -> Image.Image:
    rgba = image.convert("RGBA")
    src = rgba.getchannel("A")
    width, height = rgba.size
    px = float(pivot["x"])
    py = float(pivot["y"])
    inp = src.load()
    out_alpha = Image.new("L", rgba.size, 0)
    out = out_alpha.load()

    # Fade aggressively with distance from the contact pivot so the shadow reads as a
    # compact gameplay cue instead of a physically rendered studio shadow.
    for y in range(height):
        for x in range(width):
            value = inp[x, y]
            if value == 0:
                continue
            dx = x - px
            dy = (y - py) * 1.25
            distance = math.sqrt(dx * dx + dy * dy)
            falloff = max(0.0, 1.0 - distance / SHADOW_RADIUS_PX)
            value = min(SHADOW_ALPHA_MAX, int(value * 0.42 * falloff))
            if value >= 5:
                out[x, y] = value

    out_alpha = out_alpha.filter(ImageFilter.GaussianBlur(radius=0.75))
    shadow = Image.new("RGBA", rgba.size, (42, 45, 39, 0))
    shadow.putalpha(out_alpha)
    return shadow


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
        color = flatten_color(Image.open(color_path))
        shadow = simplify_shadow(Image.open(shadow_path), pivots[direction])
        sprite = package_tools.composite_shadow(color, shadow)

        color.save(color_path)
        shadow.save(shadow_path)
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
        "mode": "classic_2d_foliage_v1",
        "paletteColors": PALETTE_COLORS,
        "dither": "none",
        "posterizeBitsPerChannel": 4,
        "saturationMultiplier": 1.18,
        "contrastMultiplier": 1.12,
        "hardAlphaThreshold": 72,
        "outlineAlpha": 72,
        "shadowAlphaMax": SHADOW_ALPHA_MAX,
        "shadowRadiusPx": SHADOW_RADIUS_PX,
        "preservesCameraAndPivot": True,
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Classic 2D foliage profile reduces Blender render cues; approve only after "
        "gameplay-scale visual review."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("classic2DFoliageProfile: PASS")
    print("paletteColors:", PALETTE_COLORS)
    print("shadowAlphaMax:", SHADOW_ALPHA_MAX)


if __name__ == "__main__":
    main()
