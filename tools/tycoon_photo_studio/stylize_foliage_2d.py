"""Apply a classic pre-rendered Tycoon foliage treatment to an already baked tree package.

V2 assumes the Blender source contains dense leaf micro-geometry. Instead of crushing
that information into large flat bands, it preserves small leaf-to-leaf contrast,
uses a restrained indexed palette with Floyd-Steinberg diffusion, and keeps the ground
shadow compact so the final sprite reads as pre-rendered 2D rather than modern 3D.

Per-asset foliagePostProcess values are optional. Assets without them retain the legacy
V2 defaults, so approved trees are not changed when another tree is calibrated.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

import postprocess as package_tools

DIRECTIONS = ("south", "east", "west", "north")
PALETTE_COLORS = 64
DEFAULT_SHADOW_ALPHA_MAX = 54
DEFAULT_SHADOW_STRENGTH = 0.34
DEFAULT_SHADOW_RADIUS_PX = 72.0
DEFAULT_SATURATION_MULTIPLIER = 1.12
DEFAULT_CONTRAST_MULTIPLIER = 1.08
DEFAULT_LUMINANCE_COMPRESSION = 1.0
DEFAULT_MIDTONE_LIFT = 0.0
DEFAULT_POSTERIZE_BITS = 5
DEFAULT_OUTLINE_ALPHA = 46


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--asset-config")
    return parser.parse_args()


def load_profile(asset_config: str | None) -> dict:
    profile = {
        "shadowAlphaMax": DEFAULT_SHADOW_ALPHA_MAX,
        "shadowStrength": DEFAULT_SHADOW_STRENGTH,
        "shadowRadiusPx": DEFAULT_SHADOW_RADIUS_PX,
        "saturationMultiplier": DEFAULT_SATURATION_MULTIPLIER,
        "contrastMultiplier": DEFAULT_CONTRAST_MULTIPLIER,
        "luminanceCompression": DEFAULT_LUMINANCE_COMPRESSION,
        "midtoneLift": DEFAULT_MIDTONE_LIFT,
        "paletteColors": PALETTE_COLORS,
        "posterizeBitsPerChannel": DEFAULT_POSTERIZE_BITS,
        "outlineAlpha": DEFAULT_OUTLINE_ALPHA,
        "shadowBlendIntent": "alpha_darkening",
    }
    if asset_config:
        asset = json.loads(Path(asset_config).read_text(encoding="utf-8"))
        overrides = asset.get("foliagePostProcess", {})
        for key in profile:
            if key in overrides:
                profile[key] = overrides[key]

    profile["shadowAlphaMax"] = max(0, min(255, int(profile["shadowAlphaMax"])))
    profile["shadowStrength"] = max(0.0, min(1.0, float(profile["shadowStrength"])))
    profile["shadowRadiusPx"] = max(8.0, float(profile["shadowRadiusPx"]))
    profile["saturationMultiplier"] = max(0.1, float(profile["saturationMultiplier"]))
    profile["contrastMultiplier"] = max(0.1, float(profile["contrastMultiplier"]))
    profile["luminanceCompression"] = max(0.35, min(1.0, float(profile["luminanceCompression"])))
    profile["midtoneLift"] = max(-32.0, min(32.0, float(profile["midtoneLift"])))
    profile["paletteColors"] = max(16, min(128, int(profile["paletteColors"])))
    profile["posterizeBitsPerChannel"] = max(3, min(8, int(profile["posterizeBitsPerChannel"])))
    profile["outlineAlpha"] = max(0, min(96, int(profile["outlineAlpha"])))
    return profile


def flatten_luminance(rgb: Image.Image, profile: dict) -> Image.Image:
    """Compress directional 3D lighting while preserving chroma and leaf microstructure."""
    compression = float(profile["luminanceCompression"])
    lift = float(profile["midtoneLift"])
    if abs(compression - 1.0) < 1e-6 and abs(lift) < 1e-6:
        return rgb

    ycbcr = rgb.convert("YCbCr")
    y, cb, cr = ycbcr.split()
    lut = []
    for value in range(256):
        compressed = 128.0 + (value - 128.0) * compression + lift
        lut.append(max(0, min(255, int(round(compressed)))))
    y = y.point(lut)
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


def stylize_color(image: Image.Image, profile: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    # Preserve leaf-sized gaps and hard silhouette while removing translucent render haze.
    hard_alpha = alpha.point(lambda value: 255 if value >= 64 else 0)
    rgb = rgba.convert("RGB")
    rgb = flatten_luminance(rgb, profile)
    rgb = ImageEnhance.Color(rgb).enhance(float(profile["saturationMultiplier"]))
    rgb = ImageEnhance.Contrast(rgb).enhance(float(profile["contrastMultiplier"]))
    rgb = ImageOps.posterize(rgb, int(profile["posterizeBitsPerChannel"]))
    rgb = rgb.quantize(
        colors=int(profile["paletteColors"]),
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.FLOYDSTEINBERG,
    ).convert("RGB")

    out = rgb.convert("RGBA")
    out.putalpha(hard_alpha)

    # A restrained edge only closes LANCZOS fringe; it must not become a cartoon outline.
    dilated = hard_alpha.filter(ImageFilter.MaxFilter(3))
    edge = ImageChops.subtract(dilated, hard_alpha)
    outline_alpha = int(profile["outlineAlpha"])
    edge = edge.point(lambda value: outline_alpha if value else 0)
    outline = Image.new("RGBA", out.size, (34, 40, 29, 0))
    outline.putalpha(edge)
    base = Image.new("RGBA", out.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    return Image.alpha_composite(base, out)


def simplify_shadow(image: Image.Image, pivot: dict[str, int], profile: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    src = rgba.getchannel("A")
    width, height = rgba.size
    px = float(pivot["x"])
    py = float(pivot["y"])
    inp = src.load()
    out_alpha = Image.new("L", rgba.size, 0)
    out = out_alpha.load()

    shadow_alpha_max = int(profile["shadowAlphaMax"])
    shadow_strength = float(profile["shadowStrength"])
    shadow_radius = float(profile["shadowRadiusPx"])

    for y in range(height):
        for x in range(width):
            value = inp[x, y]
            if value == 0:
                continue
            dx = x - px
            dy = (y - py) * 1.30
            distance = math.sqrt(dx * dx + dy * dy)
            falloff = max(0.0, 1.0 - distance / shadow_radius)
            value = min(shadow_alpha_max, int(value * shadow_strength * falloff))
            if value >= 4:
                out[x, y] = value

    out_alpha = out_alpha.filter(ImageFilter.GaussianBlur(radius=0.65))
    # Semi-transparent dark pixels are intentionally kept separate from the foliage alpha.
    # When the PNG is composited by the engine they darken the destination similarly to a
    # classic multiply-style ground shadow while remaining background-independent.
    shadow = Image.new("RGBA", rgba.size, (43, 46, 39, 0))
    shadow.putalpha(out_alpha)
    return shadow


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
        shadow = simplify_shadow(Image.open(shadow_path), pivots[direction], profile)
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

    manifest["paletteColorCount"] = int(profile["paletteColors"])
    manifest["candidatePostProcess"] = {
        "mode": "classic_prerendered_foliage_v2",
        "paletteColors": int(profile["paletteColors"]),
        "dither": "floyd_steinberg",
        "posterizeBitsPerChannel": int(profile["posterizeBitsPerChannel"]),
        "saturationMultiplier": float(profile["saturationMultiplier"]),
        "contrastMultiplier": float(profile["contrastMultiplier"]),
        "luminanceCompression": float(profile["luminanceCompression"]),
        "midtoneLift": float(profile["midtoneLift"]),
        "hardAlphaThreshold": 64,
        "outlineAlpha": int(profile["outlineAlpha"]),
        "shadowAlphaMax": int(profile["shadowAlphaMax"]),
        "shadowStrength": float(profile["shadowStrength"]),
        "shadowRadiusPx": float(profile["shadowRadiusPx"]),
        "shadowBlendIntent": str(profile["shadowBlendIntent"]),
        "preservesCameraAndPivot": True,
        "expectsLeafMicrogeometry": True,
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Classic pre-rendered foliage V2 preserves leaf microdetail while allowing per-asset "
        "luminance compression to suppress modern 3D lighting; approve only after gameplay-scale visual review."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("classicPrerenderedFoliageV2: PASS")
    print("paletteColors:", profile["paletteColors"])
    print("luminanceCompression:", profile["luminanceCompression"])
    print("midtoneLift:", profile["midtoneLift"])
    print("shadowAlphaMax:", profile["shadowAlphaMax"])
    print("shadowStrength:", profile["shadowStrength"])
    print("shadowRadiusPx:", profile["shadowRadiusPx"])


if __name__ == "__main__":
    main()
