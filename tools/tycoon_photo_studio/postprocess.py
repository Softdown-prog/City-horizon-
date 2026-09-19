"""Post-process a Tycoon Asset Baker V1 source bake into a four-direction package."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

FINAL_SIZE = (256, 256)
PALETTE_COLORS = 128
CANDIDATE_VARIANT_ID = 3
SHADOW_COLOR = (29, 33, 37)
SHADOW_ALPHA_SCALE = 0.72
SHADOW_ALPHA_MAX = 132
SHADOW_BLUR_RADIUS = 1.4
FALLBACK_SHADOW_THRESHOLD = 12
FALLBACK_SHADOW_SCALE = 2.05
FALLBACK_SHADOW_ALPHA_MAX = 118
FALLBACK_SHADOW_BLUR_RADIUS = 2.2
EDGE_ALPHA_THRESHOLD = 92
EDGE_OPACITY_SCALE = 0.38
EDGE_OPACITY_MAX = 96
DIRECTION_ORDER = ("south", "east", "west", "north")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--studio-preset", required=True)
    return parser.parse_args()


def apply_studio_preset(preset):
    global FINAL_SIZE, PALETTE_COLORS, CANDIDATE_VARIANT_ID
    global SHADOW_COLOR, SHADOW_ALPHA_SCALE, SHADOW_ALPHA_MAX, SHADOW_BLUR_RADIUS
    global FALLBACK_SHADOW_THRESHOLD, FALLBACK_SHADOW_SCALE, FALLBACK_SHADOW_ALPHA_MAX, FALLBACK_SHADOW_BLUR_RADIUS
    global EDGE_ALPHA_THRESHOLD, EDGE_OPACITY_SCALE, EDGE_OPACITY_MAX

    render = preset["render"]
    post = preset["postProcess"]
    FINAL_SIZE = tuple(map(int, render["finalResolution"]))
    PALETTE_COLORS = int(post["paletteColors"])
    CANDIDATE_VARIANT_ID = int(post["candidateVariant"])
    SHADOW_COLOR = tuple(map(int, post["shadowColor"]))
    SHADOW_ALPHA_SCALE = float(post["shadowAlphaScale"])
    SHADOW_ALPHA_MAX = int(post["shadowAlphaMax"])
    SHADOW_BLUR_RADIUS = float(post["shadowBlurRadius"])
    FALLBACK_SHADOW_THRESHOLD = int(post["fallbackShadowThreshold"])
    FALLBACK_SHADOW_SCALE = float(post["fallbackShadowScale"])
    FALLBACK_SHADOW_ALPHA_MAX = int(post["fallbackShadowAlphaMax"])
    FALLBACK_SHADOW_BLUR_RADIUS = float(post["fallbackShadowBlurRadius"])
    EDGE_ALPHA_THRESHOLD = int(post["edgeAlphaThreshold"])
    EDGE_OPACITY_SCALE = float(post["edgeOpacityScale"])
    EDGE_OPACITY_MAX = int(post["edgeOpacityMax"])


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
    reference = shadow_reference.convert("RGBA")
    receiver_alpha = reference.getchannel("A")
    alpha_hist = receiver_alpha.histogram()
    nonzero = sum(alpha_hist[1:])
    coverage = nonzero / float(reference.width * reference.height)
    alpha_bbox = receiver_alpha.getbbox()

    if alpha_bbox is not None and 0.0005 < coverage < 0.45:
        clean_alpha = receiver_alpha.point(
            lambda value: min(SHADOW_ALPHA_MAX, int(value * SHADOW_ALPHA_SCALE))
        )
        clean_alpha = clean_alpha.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR_RADIUS))
        shadow = Image.new("RGBA", reference.size, (*SHADOW_COLOR, 0))
        shadow.putalpha(clean_alpha)
        return shadow

    object_alpha = color_source.convert("RGBA").getchannel("A")
    luminance = ImageOps.grayscale(reference.convert("RGB"))
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
            if delta < FALLBACK_SHADOW_THRESHOLD:
                continue
            out[x, y] = min(
                FALLBACK_SHADOW_ALPHA_MAX,
                int((delta - FALLBACK_SHADOW_THRESHOLD) * FALLBACK_SHADOW_SCALE),
            )

    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(radius=FALLBACK_SHADOW_BLUR_RADIUS))
    shadow = Image.new("RGBA", reference.size, (*SHADOW_COLOR, 0))
    shadow.putalpha(shadow_alpha)
    return shadow


def downsample(image: Image.Image) -> Image.Image:
    return image.resize(FINAL_SIZE, Image.Resampling.LANCZOS)


def composite_shadow(color: Image.Image, shadow: Image.Image) -> Image.Image:
    out = Image.new("RGBA", color.size, (0, 0, 0, 0))
    out = Image.alpha_composite(out, shadow)
    return Image.alpha_composite(out, color)


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
    hard_alpha = alpha.point(lambda value: 255 if value >= EDGE_ALPHA_THRESHOLD else 0)
    rgba.putalpha(hard_alpha)
    dilated = hard_alpha.filter(ImageFilter.MaxFilter(3))
    edge = ImageChops.subtract(dilated, hard_alpha)
    edge = edge.point(lambda value: min(EDGE_OPACITY_MAX, int(value * EDGE_OPACITY_SCALE)))
    outline = Image.new("RGBA", rgba.size, (48, 42, 37, 0))
    outline.putalpha(edge)
    result = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    result = Image.alpha_composite(result, outline)
    return Image.alpha_composite(result, rgba)


def alpha_bounds(image: Image.Image):
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if bbox is None:
        return [0, 0, image.width, image.height]
    return list(map(int, bbox))


def variants_for(color_small: Image.Image, shadow_small: Image.Image):
    v1 = composite_shadow(color_small, shadow_small)
    q2_color = quantize_rgba(color_small, dither=False)
    v2 = composite_shadow(q2_color, shadow_small)
    q3_color = quantize_rgba(color_small, dither=True)
    v3 = composite_shadow(q3_color, shadow_small)
    cleaned_color = edge_cleanup(q3_color)
    v4 = composite_shadow(cleaned_color, shadow_small)
    return [v1, v2, v3, v4]


def scaled_pivot(direction_meta, metadata):
    source = direction_meta["groundOriginSourcePx"]
    render_width, render_height = metadata["renderResolution"]
    return {
        "x": int(round(source["x"] * FINAL_SIZE[0] / render_width)),
        "y": int(round(source["y"] * FINAL_SIZE[1] / render_height)),
    }


def checker_panel(size=None):
    size = size or FINAL_SIZE
    panel = Image.new("RGBA", size, (231, 229, 223, 255))
    draw = ImageDraw.Draw(panel)
    step = 16
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(217, 215, 208, 255))
    return panel


def draw_diamond(draw, center_x, center_y, width=128, height=64, fill=(108, 137, 78, 115), outline=(79, 104, 60, 210)):
    points = [
        (center_x, center_y - height // 2),
        (center_x + width // 2, center_y),
        (center_x, center_y + height // 2),
        (center_x - width // 2, center_y),
    ]
    draw.polygon(points, fill=fill, outline=outline)


def draw_pivot(draw, pivot):
    x, y = pivot["x"], pivot["y"]
    draw.line((x - 5, y, x + 5, y), fill=(230, 72, 58, 255), width=1)
    draw.line((x, y - 5, x, y + 5), fill=(230, 72, 58, 255), width=1)


def make_direction_review(candidates, pivots):
    board = Image.new("RGBA", (4 * 300, 380), (247, 245, 239, 255))
    draw = ImageDraw.Draw(board)
    draw.text((20, 14), "Tycoon Asset Baker V1 - four rotations, one source, frozen studio", fill=(32, 32, 32, 255))
    for index, direction in enumerate(DIRECTION_ORDER):
        x0 = index * 300 + 22
        y0 = 62
        panel = checker_panel()
        pdraw = ImageDraw.Draw(panel)
        pivot = pivots[direction]
        draw_diamond(pdraw, pivot["x"], pivot["y"])
        panel.alpha_composite(candidates[direction])
        draw_pivot(pdraw, pivot)
        board.alpha_composite(panel, (x0, y0))
        draw.text((x0, 326), direction.upper(), fill=(40, 40, 40, 255))
        draw.text((x0, 344), f"pivot {pivot['x']},{pivot['y']}", fill=(72, 72, 72, 255))
    return board


def make_style_matrix(all_variants):
    labels = ("01 Full Color", "02 Palette", "03 Palette+Dither", "04 +Edge Cleanup")
    cell = 276
    left = 110
    top = 62
    board = Image.new("RGBA", (left + 4 * cell, top + 4 * cell + 36), (247, 245, 239, 255))
    draw = ImageDraw.Draw(board)
    draw.text((18, 14), "Four-direction style matrix - same Blender source bake", fill=(32, 32, 32, 255))
    for column, label in enumerate(labels):
        draw.text((left + column * cell + 8, 40), label, fill=(55, 55, 55, 255))
    for row, direction in enumerate(DIRECTION_ORDER):
        draw.text((18, top + row * cell + 118), direction.upper(), fill=(45, 45, 45, 255))
        for column, sprite in enumerate(all_variants[direction]):
            panel = checker_panel()
            panel.alpha_composite(sprite)
            board.alpha_composite(panel, (left + column * cell, top + row * cell))
    return board


def make_context_panel(sprite, pivot, label):
    panel = Image.new("RGBA", (420, 320), (185, 198, 171, 255))
    draw = ImageDraw.Draw(panel)
    origin_x, origin_y = 210, 196
    for gy in range(-2, 3):
        for gx in range(-2, 3):
            sx = origin_x + (gx - gy) * 64
            sy = origin_y + (gx + gy) * 32
            draw_diamond(draw, sx, sy, fill=(110, 139, 79, 255), outline=(81, 105, 61, 255))
    panel.alpha_composite(sprite, (origin_x - pivot["x"], origin_y - pivot["y"]))
    draw.rectangle((8, 8, 146, 32), fill=(245, 242, 233, 230))
    draw.text((16, 15), label, fill=(42, 42, 42, 255))
    return panel


def make_context_board(candidates, pivots):
    board = Image.new("RGBA", (840, 680), (185, 198, 171, 255))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, 840, 40), fill=(245, 242, 233, 245))
    draw.text((16, 14), "Synthetic CH_CAMERA_V1 gameplay-scale context - not a runtime screenshot", fill=(42, 42, 42, 255))
    positions = ((0, 40), (420, 40), (0, 360), (420, 360))
    for direction, pos in zip(DIRECTION_ORDER, positions):
        board.alpha_composite(make_context_panel(candidates[direction], pivots[direction], direction.upper()), pos)
    return board


def make_fixed_sheet(candidates):
    sheet = Image.new("RGBA", (FINAL_SIZE[0] * 4, FINAL_SIZE[1]), (0, 0, 0, 0))
    for index, direction in enumerate(DIRECTION_ORDER):
        sheet.alpha_composite(candidates[direction], (index * FINAL_SIZE[0], 0))
    return sheet


def make_trimmed_atlas(candidates, pivots, padding=2):
    records = []
    crops = []
    total_width = 0
    max_height = 0
    for direction in DIRECTION_ORDER:
        sprite = candidates[direction]
        left, top, right, bottom = alpha_bounds(sprite)
        crop = sprite.crop((left, top, right, bottom))
        crops.append((direction, crop, [left, top, right, bottom]))
        total_width += crop.width + padding * 2
        max_height = max(max_height, crop.height + padding * 2)

    atlas = Image.new("RGBA", (total_width, max_height), (0, 0, 0, 0))
    cursor_x = 0
    for direction, crop, bounds in crops:
        x = cursor_x + padding
        y = padding
        atlas.alpha_composite(crop, (x, y))
        pivot = pivots[direction]
        records.append({
            "direction": direction, "x": x, "y": y, "w": crop.width, "h": crop.height,
            "pivotX": pivot["x"] - bounds[0], "pivotY": pivot["y"] - bounds[1],
            "sourceBounds": bounds,
        })
        cursor_x += crop.width + padding * 2
    return atlas, records


def main():
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    preset = json.loads(Path(args.studio_preset).read_text(encoding="utf-8"))
    apply_studio_preset(preset)
    metadata = json.loads((input_dir / "studio_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("studioPreset") != preset.get("id"):
        raise RuntimeError("Source metadata and post-process studio preset do not match")
    asset_id = metadata["sourceObject"]
    direction_meta = {item["id"]: item for item in metadata["directions"]}
    if tuple(metadata.get("directionOrder", [])) != DIRECTION_ORDER:
        raise RuntimeError(f"Direction order must be {DIRECTION_ORDER}, got {metadata.get('directionOrder')}")

    candidates = {}
    pivots = {}
    all_variants = {}
    view_records = []
    for direction in DIRECTION_ORDER:
        meta = direction_meta[direction]
        color_source = Image.open(input_dir / meta["colorSource"]).convert("RGBA")
        shadow_reference = Image.open(input_dir / meta["shadowSource"]).convert("RGBA")
        shadow_source = derive_shadow(color_source, shadow_reference)
        color_small = downsample(color_source)
        shadow_small = downsample(shadow_source)
        variants = variants_for(color_small, shadow_small)
        candidate = variants[CANDIDATE_VARIANT_ID - 1]
        pivot = scaled_pivot(meta, metadata)

        color_small.save(output_dir / f"{asset_id}_{direction}_color_pass.png")
        shadow_small.save(output_dir / f"{asset_id}_{direction}_shadow_pass.png")
        for index, image in enumerate(variants, start=1):
            image.save(output_dir / f"{asset_id}_{direction}_variant_{index:02d}.png")
        candidate.save(output_dir / f"{asset_id}_{direction}.png")

        candidates[direction] = candidate
        pivots[direction] = pivot
        all_variants[direction] = variants
        view_records.append({
            "direction": direction,
            "quarterTurns": meta["quarterTurns"],
            "rotationDegrees": meta["rotationDegrees"],
            "file": f"{asset_id}_{direction}.png",
            "colorPass": f"{asset_id}_{direction}_color_pass.png",
            "shadowPass": f"{asset_id}_{direction}_shadow_pass.png",
            "pivot": pivot,
            "objectAlphaBounds": alpha_bounds(color_small),
            "spriteAlphaBounds": alpha_bounds(candidate),
        })

    unique_pivots = {(p["x"], p["y"]) for p in pivots.values()}
    if len(unique_pivots) != 1:
        raise RuntimeError(f"All four rotations must share one projected ground-origin pivot, got {sorted(unique_pivots)}")

    make_fixed_sheet(candidates).save(output_dir / f"{asset_id}_4view.png")
    atlas, atlas_records = make_trimmed_atlas(candidates, pivots)
    atlas.save(output_dir / f"{asset_id}_atlas.png")
    make_direction_review(candidates, pivots).save(output_dir / f"{asset_id}_review.png")
    style_matrix = make_style_matrix(all_variants)
    style_matrix.save(output_dir / f"{asset_id}_style_matrix.png")
    style_matrix.save(output_dir / "tycoon_photo_studio_comparison_board.png")
    context = make_context_board(candidates, pivots)
    context.save(output_dir / f"{asset_id}_4dir_context.png")
    context.save(output_dir / "tycoon_photo_studio_in_game_context.png")

    manifest = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "status": "golden_pipeline_candidate",
        "humanApprovalRequired": True,
        "assetId": asset_id,
        "assetType": metadata.get("assetType", "static_prop"),
        "sourceContract": metadata.get("sourceContract"),
        "assetConfig": metadata.get("assetConfig"),
        "studioPreset": metadata.get("studioPreset"),
        "cameraContract": metadata.get("cameraContract", "CH_CAMERA_V1"),
        "gridContract": metadata.get("gridContract", "CH_GRID_V1"),
        "projection": metadata.get("projection", "orthographic_dimetric_2_to_1"),
        "yawDegrees": metadata.get("yawDegrees", 45.0),
        "elevationDegrees": metadata.get("elevationDegrees", 30.0),
        "tile": {"width": metadata.get("tileWidth", 128), "height": metadata.get("tileHeight", 64)},
        "footprint": metadata["footprint"],
        "blenderVersion": metadata.get("blenderVersion", "unknown"),
        "renderEngine": metadata.get("renderEngine", "unknown"),
        "renderResolution": metadata.get("renderResolution", [1024, 1024]),
        "finalFrameResolution": list(FINAL_SIZE),
        "directionCount": 4,
        "directionOrder": list(DIRECTION_ORDER),
        "rotationPolicy": metadata.get("rotationPolicy", {}),
        "pivotPolicy": "projected world origin (0,0,0), fixed across all directions",
        "paletteColorCount": PALETTE_COLORS,
        "candidatePostProcess": {
            "variantId": CANDIDATE_VARIANT_ID,
            "mode": "palette_reduced",
            "dither": "floyd_steinberg",
            "edgeCleanup": "none",
            "studioPreset": metadata.get("studioPreset"),
        },
        "sourceSummary": metadata.get("sourceSummary", {}),
        "views": view_records,
        "atlas": {
            "file": f"{asset_id}_atlas.png",
            "packing": "deterministic_single_row_trimmed_v1",
            "paddingPx": 2,
            "frames": atlas_records,
        },
        "files": {
            "south": f"{asset_id}_south.png",
            "east": f"{asset_id}_east.png",
            "west": f"{asset_id}_west.png",
            "north": f"{asset_id}_north.png",
            "spriteSheet": f"{asset_id}_4view.png",
            "atlas": f"{asset_id}_atlas.png",
            "reviewSheet": f"{asset_id}_review.png",
            "styleMatrix": f"{asset_id}_style_matrix.png",
            "context4Dir": f"{asset_id}_4dir_context.png",
        },
        "reuse": {
            "directionOrderSource": "C++/MapForge2/src/building_export_pipeline.cpp::kViews",
            "directionQuarterTurnsSource": "C++/MapForge2/src/building_composer.cpp::quarterTurns",
            "fileNamingCompatibleWithBuildingExportPipeline": True,
            "cameraContractReused": True,
            "futureAnimationExpansion": "same source root; bake directions x animation frames",
        },
        "githubRunId": os.environ.get("GITHUB_RUN_ID", "local"),
        "githubSha": os.environ.get("GITHUB_SHA", "local"),
        "approvalRule": "Golden kiosk guards the approved visual recipe; new assets must use the same frozen studio unless a new studio version is explicitly approved.",
    }
    manifest_text = json.dumps(manifest, indent=2)
    (output_dir / f"{asset_id}_manifest.json").write_text(manifest_text, encoding="utf-8")
    (output_dir / "tycoon_photo_studio_manifest.json").write_text(manifest_text, encoding="utf-8")

    print("Generated Tycoon Asset Baker V1 package:")
    for direction in DIRECTION_ORDER:
        print(" -", f"{asset_id}_{direction}.png", "pivot", pivots[direction])


if __name__ == "__main__":
    main()
