"""Apply the City Horizon stylized pre-render treatment to baked tree packages.

Foliage and woody structure intentionally use different finishing paths.
Dense leaf-card crowns retain the approved foliage treatment (luminance compression,
posterization and indexed Floyd-Steinberg diffusion). Trunk/branch pixels are isolated
before that stage and rebuilt from a restrained bark palette with deterministic,
low-frequency organic variation. This prevents Blender face lighting from becoming
large triangular/diagonal colour plates on the trunk while preserving the crown.
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
DEFAULT_WOOD_TONE_COUNT = 4
DEFAULT_WOOD_ORGANIC_STRENGTH = 0.26
DEFAULT_WOOD_VERTICAL_SCALE = 23.0
DEFAULT_WOOD_HORIZONTAL_SCALE = 37.0


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
        "woodToneCount": DEFAULT_WOOD_TONE_COUNT,
        "woodOrganicStrength": DEFAULT_WOOD_ORGANIC_STRENGTH,
        "woodVerticalScale": DEFAULT_WOOD_VERTICAL_SCALE,
        "woodHorizontalScale": DEFAULT_WOOD_HORIZONTAL_SCALE,
    }
    if asset_config:
        asset = json.loads(Path(asset_config).read_text(encoding="utf-8"))
        overrides = asset.get("foliagePostProcess", {})
        for key in profile:
            if key in overrides:
                profile[key] = overrides[key]
        wood = asset.get("woodPostProcess", {})
        for key in ("woodToneCount", "woodOrganicStrength", "woodVerticalScale", "woodHorizontalScale"):
            if key in wood:
                profile[key] = wood[key]

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
    profile["woodToneCount"] = max(3, min(5, int(profile["woodToneCount"])))
    profile["woodOrganicStrength"] = max(0.0, min(0.65, float(profile["woodOrganicStrength"])))
    profile["woodVerticalScale"] = max(8.0, float(profile["woodVerticalScale"]))
    profile["woodHorizontalScale"] = max(8.0, float(profile["woodHorizontalScale"]))
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


def make_wood_mask(rgba: Image.Image) -> Image.Image:
    """Identify visible bark/branch pixels from the clean bake before palette reduction.

    The source tree contract keeps wood in a warm brown family and leaves in green
    families, so this classification is deliberately narrow. It is only a routing
    mask: it never changes camera, geometry or alpha.
    """
    src = rgba.convert("RGBA")
    out = Image.new("L", src.size, 0)
    inp = src.load()
    dst = out.load()
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, a = inp[x, y]
            if a < 64:
                continue
            warm_brown = r >= 24 and r > g * 1.07 and g > b * 1.04 and (r - b) >= 10
            if warm_brown:
                dst[x, y] = 255
    # Close tiny lighting gaps without expanding into the green crown.
    return out.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))


def stylize_foliage_layer(rgba: Image.Image, profile: dict, foliage_mask: Image.Image) -> Image.Image:
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
    out.putalpha(foliage_mask)
    return out


def _wood_base_colour(rgba: Image.Image, mask: Image.Image) -> tuple[int, int, int]:
    src = rgba.convert("RGB")
    pixels = src.load()
    m = mask.load()
    samples = []
    for y in range(rgba.height):
        for x in range(rgba.width):
            if m[x, y] >= 128:
                samples.append(pixels[x, y])
    if not samples:
        return (92, 68, 52)
    samples.sort(key=lambda c: c[0] + c[1] + c[2])
    mid = samples[len(samples) // 2]
    return tuple(int(v) for v in mid)


def stylize_wood_layer(rgba: Image.Image, profile: dict, wood_mask: Image.Image) -> Image.Image:
    """Replace polygon-lighting plates with 3-5 organic bark tone masses.

    The field is screen-space but low-frequency and deterministic. Source luminance has
    only a small influence, so triangles caused by mesh faces cannot dominate the final
    sprite. Variation is biased vertically to read as bark rather than camouflage.
    """
    out = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    dst = out.load()
    src = rgba.convert("RGB").load()
    mask = wood_mask.load()
    base = _wood_base_colour(rgba, wood_mask)
    tone_count = int(profile["woodToneCount"])
    strength = float(profile["woodOrganicStrength"])
    vscale = float(profile["woodVerticalScale"])
    hscale = float(profile["woodHorizontalScale"])

    # Restrained warm bark ramp centred around the median source colour.
    factors = [0.72 + (0.52 * i / max(1, tone_count - 1)) for i in range(tone_count)]
    palette = [tuple(max(0, min(255, int(channel * factor))) for channel in base) for factor in factors]

    for y in range(rgba.height):
        for x in range(rgba.width):
            if mask[x, y] < 128:
                continue
            r, g, b = src[x, y]
            lum = (r * 0.299 + g * 0.587 + b * 0.114) / 255.0
            organic = (
                math.sin(y / vscale + math.sin(x / hscale) * 1.7) * 0.52
                + math.sin((y + x * 0.31) / (vscale * 0.57) + 1.3) * 0.31
                + math.sin((y - x * 0.18) / (vscale * 1.71) - 0.8) * 0.17
            )
            # Geometry luminance is deliberately subordinate to organic bark variation.
            value = 0.50 + organic * strength + (lum - 0.5) * 0.16
            index = max(0, min(tone_count - 1, int(value * tone_count)))
            colour = palette[index]
            dst[x, y] = (*colour, 255)
    return out


def add_outline(image: Image.Image, hard_alpha: Image.Image, profile: dict) -> Image.Image:
    dilated = hard_alpha.filter(ImageFilter.MaxFilter(3))
    edge = ImageChops.subtract(dilated, hard_alpha)
    outline_alpha = int(profile["outlineAlpha"])
    edge = edge.point(lambda value: outline_alpha if value else 0)
    outline = Image.new("RGBA", image.size, (34, 40, 29, 0))
    outline.putalpha(edge)
    base = Image.new("RGBA", image.size, (0, 0, 0, 0))
    base = Image.alpha_composite(base, outline)
    return Image.alpha_composite(base, image)


def stylize_color(image: Image.Image, profile: dict) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    hard_alpha = alpha.point(lambda value: 255 if value >= 64 else 0)

    wood_mask = ImageChops.multiply(make_wood_mask(rgba), hard_alpha)
    foliage_mask = ImageChops.subtract(hard_alpha, wood_mask)

    foliage = stylize_foliage_layer(rgba, profile, foliage_mask)
    wood = stylize_wood_layer(rgba, profile, wood_mask)
    combined = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    combined = Image.alpha_composite(combined, wood)
    combined = Image.alpha_composite(combined, foliage)
    return add_outline(combined, hard_alpha, profile)


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
        "mode": "stylized_prerender_foliage_wood_split_v1",
        "paletteColors": int(profile["paletteColors"]),
        "dither": "floyd_steinberg_foliage_only",
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
        "foliageTreatmentFrozen": True,
        "woodTreatment": {
            "mode": "organic_bark_tone_masses_v1",
            "toneCount": int(profile["woodToneCount"]),
            "organicStrength": float(profile["woodOrganicStrength"]),
            "verticalScale": float(profile["woodVerticalScale"]),
            "horizontalScale": float(profile["woodHorizontalScale"]),
            "sourceLuminanceInfluence": 0.16,
            "floydSteinberg": False,
        },
    }
    manifest["atlas"]["frames"] = atlas_records
    manifest["humanApprovalRequired"] = True
    manifest["approvalRule"] = (
        "Crown treatment is frozen. Approve the wood pass only if trunk and branches read as restrained, "
        "organic bark tone masses without large polygonal or diagonal colour plates at close review."
    )
    text = json.dumps(manifest, indent=2)
    manifest_path.write_text(text, encoding="utf-8")
    (package / "tycoon_photo_studio_manifest.json").write_text(text, encoding="utf-8")

    print("stylizedPrerenderFoliageWoodSplitV1: PASS")
    print("foliagePaletteColors:", profile["paletteColors"])
    print("woodToneCount:", profile["woodToneCount"])
    print("woodOrganicStrength:", profile["woodOrganicStrength"])
    print("shadowAlphaMax:", profile["shadowAlphaMax"])


if __name__ == "__main__":
    main()
