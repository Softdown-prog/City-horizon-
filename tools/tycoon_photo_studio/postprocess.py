"""Post-process Tycoon Photo Studio POC renders into four comparable variants."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

FINAL_SIZE = (256, 256)
PALETTE_COLORS = 128


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def percentile_from_histogram(hist, percentile):
    total = sum(hist)
    if total <= 0:
        return 255
    target = total * percentile
    cumulative = 0
    for value, count in enumerate(hist):
        cumulative += count
        if cumulative >= target:
            return value
    return 255


def derive_shadow(color_source: Image.Image, shadow_reference: Image.Image) -> Image.Image:
    """Extract only ground darkening from the shadow reference.

    The object itself is masked using the independent transparent color pass, so
    the resulting image is a black RGBA shadow layer rather than a second object
    silhouette. This is deliberately simple and deterministic for the POC.
    """

    reference = shadow_reference.convert("RGBA")
    object_alpha = color_source.convert("RGBA").getchannel("A")
    receiver_alpha = reference.getchannel("A")
    luminance = ImageOps.grayscale(reference.convert("RGB"))

    # Estimate the lit receiver level from the upper tail of the visible ground.
    # Transparent background does not influence the estimate.
    masked_values = []
    lum_data = luminance.load()
    recv_data = receiver_alpha.load()
    obj_data = object_alpha.load()
    width, height = reference.size
    for y in range(height):
        for x in range(width):
            if recv_data[x, y] > 220 and obj_data[x, y] < 16:
                masked_values.append(lum_data[x, y])

    if masked_values:
        hist = [0] * 256
        for value in masked_values:
            hist[value] += 1
        baseline = max(1, percentile_from_histogram(hist, 0.88))
    else:
        baseline = 220

    shadow_alpha = Image.new("L", reference.size, 0)
    out = shadow_alpha.load()
    for y in range(height):
        for x in range(width):
            if recv_data[x, y] < 16 or obj_data[x, y] > 24:
                continue
            delta = max(0, baseline - lum_data[x, y])
            alpha = min(118, int(delta * 2.15))
            out[x, y] = alpha

    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=2.4))
    shadow = Image.new("RGBA", reference.size, (28, 31, 34, 0))
    shadow.putalpha(shadow_alpha)
    return shadow


def downsample(image: Image.Image) -> Image.Image:
    return image.resize(FINAL_SIZE, Image.Resampling.LANCZOS)


def composite_shadow(color: Image.Image, shadow: Image.Image) -> Image.Image:
    out = Image.new("RGBA", color.size, (0, 0, 0, 0))
    out = Image.alpha_composite(out, shadow)
    out = Image.alpha_composite(out, color)
    return out


def quantize_rgba(image: Image.Image, *, dither: bool) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")

    matte = Image.new("RGB", rgba.size, (214, 211, 202))
    matte.paste(rgba.convert("RGB"), mask=alpha)
    mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    quantized = matte.quantize(colors=PALETTE_COLORS, method=Image.Quantize.MEDIANCUT, dither=mode).convert("RGB")
    result = quantized.convert("RGBA")
    result.putalpha(alpha)
    return result


def edge_cleanup(color_only: Image.Image) -> Image.Image:
    rgba = color_only.convert("RGBA")
    alpha = rgba.getchannel("A")
    hard_alpha = alpha.point(lambda value: 255 if value >= 92 else 0)
    rgba.putalpha(hard_alpha)

    dilated = hard_alpha.filter(ImageFilter.MaxFilter(3))
    edge = ImageChops.subtract(dilated, hard_alpha)
    edge = edge.point(lambda value: min(112, int(value * 0.44)))

    outline = Image.new("RGBA", rgba.size, (48, 42, 37, 0))
    outline.putalpha(edge)
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    result = Image.alpha_composite(result, outline)
    result = Image.alpha_composite(result, rgba)
    return result


def alpha_bounds_and_pivot(color: Image.Image):
    alpha = color.getchannel("A")
    bbox = alpha.getbbox() or (0, 0, color.width, color.height)
    pivot = {
        "x": int(round((bbox[0] + bbox[2]) * 0.5)),
        "y": int(bbox[3]),
    }
    return list(map(int, bbox)), pivot


def draw_diamond(draw, center_x, center_y, width=128, height=64, fill=(108, 137, 78, 255), outline=(80, 104, 60, 255)):
    points = [
        (center_x, center_y - height // 2),
        (center_x + width // 2, center_y),
        (center_x, center_y + height // 2),
        (center_x - width // 2, center_y),
    ]
    draw.polygon(points, fill=fill, outline=outline)


def make_context(sprite: Image.Image) -> Image.Image:
    canvas = Image.new("RGBA", (768, 512), (185, 198, 171, 255))
    draw = ImageDraw.Draw(canvas)
    origin_x, origin_y = 384, 250

    for gy in range(-3, 4):
        for gx in range(-4, 5):
            sx = origin_x + (gx - gy) * 64
            sy = origin_y + (gx + gy) * 32
            is_path = gx == 1 or gy == 1
            fill = (139, 132, 119, 255) if is_path else (110, 139, 79, 255)
            outline = (101, 94, 84, 255) if is_path else (81, 105, 61, 255)
            draw_diamond(draw, sx, sy, fill=fill, outline=outline)

    enlarged = sprite.resize((320, 320), Image.Resampling.NEAREST)
    canvas.alpha_composite(enlarged, (224, 76))
    draw.rectangle((16, 16, 752, 56), fill=(245, 242, 233, 236))
    draw.text((28, 28), "Synthetic CH_CAMERA_V1 scale context — not a runtime screenshot", fill=(42, 42, 42, 255))
    return canvas


def checker_panel(size=(256, 256)):
    panel = Image.new("RGBA", size, (231, 229, 223, 255))
    draw = ImageDraw.Draw(panel)
    step = 16
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(217, 215, 208, 255))
    return panel


def make_board(variants):
    labels = [
        "01 Full Color Smooth",
        "02 Palette Reduced",
        "03 Palette + Dither",
        "04 Dither + Edge Cleanup",
    ]
    board = Image.new("RGBA", (4 * 300, 360), (247, 245, 239, 255))
    draw = ImageDraw.Draw(board)
    draw.text((20, 14), "Tycoon Photo Studio POC — same render, four post-process variants", fill=(32, 32, 32, 255))

    for index, (label, sprite) in enumerate(zip(labels, variants)):
        x0 = index * 300 + 22
        y0 = 62
        panel = checker_panel()
        panel.alpha_composite(sprite)
        board.alpha_composite(panel, (x0, y0))
        draw.text((x0, 326), label, fill=(40, 40, 40, 255))
    return board


def main():
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    color_source = Image.open(input_dir / "tycoon_photo_studio_color_source.png").convert("RGBA")
    shadow_reference = Image.open(input_dir / "tycoon_photo_studio_shadow_reference.png").convert("RGBA")
    metadata = json.loads((input_dir / "studio_metadata.json").read_text(encoding="utf-8"))

    shadow_source = derive_shadow(color_source, shadow_reference)
    color_small = downsample(color_source)
    shadow_small = downsample(shadow_source)

    color_small.save(output_dir / "tycoon_photo_studio_color_pass.png")
    shadow_small.save(output_dir / "tycoon_photo_studio_shadow_pass.png")

    v1 = composite_shadow(color_small, shadow_small)

    q2_color = quantize_rgba(color_small, dither=False)
    v2 = composite_shadow(q2_color, shadow_small)

    q3_color = quantize_rgba(color_small, dither=True)
    v3 = composite_shadow(q3_color, shadow_small)

    cleaned_color = edge_cleanup(q3_color)
    v4 = composite_shadow(cleaned_color, shadow_small)

    variants = [v1, v2, v3, v4]
    for index, image in enumerate(variants, start=1):
        image.save(output_dir / f"tycoon_photo_studio_variant_{index:02d}.png")

    board = make_board(variants)
    board.save(output_dir / "tycoon_photo_studio_comparison_board.png")

    context = make_context(v4)
    context.save(output_dir / "tycoon_photo_studio_in_game_context.png")

    bbox, pivot = alpha_bounds_and_pivot(color_small)
    manifest = {
        "contract": "TYCOON_PHOTO_STUDIO_POC_V1",
        "status": "visual_experiment_only",
        "humanApprovalRequired": True,
        "cameraContract": metadata.get("cameraContract", "CH_CAMERA_V1"),
        "projection": metadata.get("projection", "orthographic"),
        "yawDegrees": metadata.get("yawDegrees", 45.0),
        "elevationDegrees": metadata.get("elevationDegrees", 30.0),
        "blenderVersion": metadata.get("blenderVersion", "unknown"),
        "renderEngine": metadata.get("renderEngine", "unknown"),
        "sourceObject": metadata.get("sourceObject", "park_kiosk_1x1"),
        "renderResolution": metadata.get("renderResolution", [1024, 1024]),
        "finalResolution": list(FINAL_SIZE),
        "paletteColorCount": PALETTE_COLORS,
        "autoCropBoundsAtFinalResolution": bbox,
        "pivotAtFinalResolution": pivot,
        "variants": [
            {"id": 1, "mode": "full_color_smooth", "dither": "none", "edgeCleanup": "none"},
            {"id": 2, "mode": "palette_reduced", "dither": "none", "edgeCleanup": "none"},
            {"id": 3, "mode": "palette_reduced", "dither": "floyd_steinberg", "edgeCleanup": "none"},
            {"id": 4, "mode": "palette_reduced", "dither": "floyd_steinberg", "edgeCleanup": "binary_alpha_plus_subtle_1px_selout"},
        ],
        "shadowPass": "derived from dedicated white-receiver render and object-alpha mask",
        "contextPreview": "synthetic 2:1 tile context; not a City Horizon runtime screenshot",
        "githubRunId": os.environ.get("GITHUB_RUN_ID", "local"),
        "githubSha": os.environ.get("GITHUB_SHA", "local"),
        "approvalRule": "Do not promote this pipeline until the downsampled sprite is visually accepted in the classic Tycoon/Zoo Tycoon 1 family.",
    }
    (output_dir / "tycoon_photo_studio_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Generated Tycoon Photo Studio POC outputs:")
    for path in sorted(output_dir.glob("tycoon_photo_studio_*")):
        print(" -", path.name)


if __name__ == "__main__":
    main()
