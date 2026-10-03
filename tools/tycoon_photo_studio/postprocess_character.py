"""Post-process an 8-direction visitor walk bake using the frozen Tycoon studio recipe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import postprocess as base
from source_validation import validate_sources
from render_geometry import ortho_spans


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--studio-preset", required=True)
    return parser.parse_args()


def alpha_bounds(image: Image.Image):
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if bbox is None:
        return [0, 0, image.width, image.height]
    return list(map(int, bbox))


def rgba_digest(image: Image.Image) -> str:
    rgba = image.convert("RGBA")
    payload = rgba.width.to_bytes(4, "big") + rgba.height.to_bytes(4, "big") + rgba.tobytes()
    return hashlib.sha256(payload).hexdigest()


def scaled_pivot(frame_meta, metadata):
    source = frame_meta["groundOriginSourcePx"]
    render_width, render_height = metadata["renderResolution"]
    return {
        "x": int(round(source["x"] * base.FINAL_SIZE[0] / render_width)),
        "y": int(round(source["y"] * base.FINAL_SIZE[1] / render_height)),
    }


def checker_panel(size=(256, 256)):
    panel = Image.new("RGBA", size, (232, 229, 220, 255))
    draw = ImageDraw.Draw(panel)
    step = 16
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2:
                draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(217, 214, 205, 255))
    return panel


def make_fixed_sheet(frames_by_direction, direction_order, frame_count):
    fw, fh = base.FINAL_SIZE
    sheet = Image.new("RGBA", (fw * frame_count, fh * len(direction_order)), (0, 0, 0, 0))
    for row, direction in enumerate(direction_order):
        for frame_index in range(frame_count):
            sheet.alpha_composite(
                frames_by_direction[direction][frame_index],
                (frame_index * fw, row * fh),
            )
    return sheet


def make_trimmed_grid_atlas(frames_by_direction, pivots, direction_order, frame_count, padding=2):
    crops = {}
    max_w = 1
    max_h = 1
    for direction in direction_order:
        for frame_index in range(frame_count):
            sprite = frames_by_direction[direction][frame_index]
            bounds = alpha_bounds(sprite)
            crop = sprite.crop(tuple(bounds))
            crops[(direction, frame_index)] = (crop, bounds)
            max_w = max(max_w, crop.width)
            max_h = max(max_h, crop.height)

    cell_w = max_w + padding * 2
    cell_h = max_h + padding * 2
    atlas = Image.new(
        "RGBA",
        (cell_w * frame_count, cell_h * len(direction_order)),
        (0, 0, 0, 0),
    )
    records = []
    for row, direction in enumerate(direction_order):
        for frame_index in range(frame_count):
            crop, bounds = crops[(direction, frame_index)]
            x = frame_index * cell_w + padding
            y = row * cell_h + padding
            atlas.alpha_composite(crop, (x, y))
            pivot = pivots[(direction, frame_index)]
            records.append({
                "direction": direction,
                "frame": frame_index,
                "x": x,
                "y": y,
                "w": crop.width,
                "h": crop.height,
                "pivotX": pivot["x"] - bounds[0],
                "pivotY": pivot["y"] - bounds[1],
                "sourceBounds": bounds,
            })
    return atlas, records, {"cellWidth": cell_w, "cellHeight": cell_h}


def draw_grid_diamond(draw, cx, cy, width=128, height=64):
    pts = [
        (cx, cy - height // 2),
        (cx + width // 2, cy),
        (cx, cy + height // 2),
        (cx - width // 2, cy),
    ]
    draw.polygon(pts, fill=(109, 137, 79, 255), outline=(77, 101, 59, 255))


def make_direction_context(frames_by_direction, pivots, direction_order, metadata=None):
    metadata = metadata or {}
    size = next(iter(frames_by_direction.values()))[0].size
    scale = metadata.get("orthoScaleCalibrated", metadata.get("orthoScale"))
    tile_width = None
    if scale:
        span_x, _ = ortho_spans(scale, size)
        tile_width = metadata.get("blenderUnitsPerTile", 3.0) * math.sqrt(2) * size[0] / span_x
    panels = [base.make_context_panel(frames_by_direction[d][0], pivots[(d, 0)], d.upper(),
                                      metadata.get("footprint"), tile_width) for d in direction_order]
    panel_w, panel_h = max(p.width for p in panels), max(p.height for p in panels)
    rows = math.ceil(len(direction_order) / 4)
    board = Image.new("RGBA", (panel_w * 4, panel_h * rows + 44), (181, 196, 168, 255))
    draw = ImageDraw.Draw(board)
    draw.rectangle((0, 0, board.width, 44), fill=(244, 240, 228, 245))
    draw.text((14, 14), "Visitor NPC - synthetic grid review, not a runtime capture", fill=(35, 35, 35, 255))

    for index, direction in enumerate(direction_order):
        x0 = (index % 4) * panel_w
        y0 = 44 + (index // 4) * panel_h
        board.alpha_composite(panels[index], (x0, y0))
    return board


def make_sequence_review(frames_by_direction, direction_order, frame_count):
    thumb = 128
    label_w = 46
    header_h = 54
    board = Image.new(
        "RGBA",
        (label_w + frame_count * thumb, header_h + len(direction_order) * thumb),
        (245, 242, 233, 255),
    )
    draw = ImageDraw.Draw(board)
    draw.text((12, 12), f"Sequence candidate - {len(direction_order)} directions x {frame_count} walk frames", fill=(35, 35, 35, 255))
    for frame_index in range(frame_count):
        draw.text((label_w + frame_index * thumb + 54, 35), f"{frame_index}", fill=(75, 75, 75, 255))
    for row, direction in enumerate(direction_order):
        y = header_h + row * thumb
        draw.text((12, y + 56), direction.upper(), fill=(45, 45, 45, 255))
        for frame_index in range(frame_count):
            sprite = frames_by_direction[direction][frame_index]
            panel = checker_panel((thumb, thumb))
            reduced = sprite.copy()
            reduced.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
            panel.alpha_composite(reduced, ((thumb - reduced.width) // 2, (thumb - reduced.height) // 2))
            board.alpha_composite(panel, (label_w + frame_index * thumb, y))
    return board


def main():
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    preset = json.loads(Path(args.studio_preset).read_text(encoding="utf-8"))
    base.apply_studio_preset(preset)
    metadata = json.loads((input_dir / "character_studio_metadata.json").read_text(encoding="utf-8"))
    if metadata.get("studioPreset") != preset.get("id"):
        raise RuntimeError("Character source metadata and post-process studio preset do not match")
    if metadata.get("contract") != "TYCOON_CHARACTER_BAKE_V1":
        raise RuntimeError("Expected TYCOON_CHARACTER_BAKE_V1 source metadata")
    base.FINAL_SIZE = validate_sources(input_dir, metadata, preset, character=True)

    asset_id = metadata["sourceObject"]
    direction_order = tuple(metadata["directionOrder"])
    frame_count = int(metadata["animation"]["frameCount"])
    direction_meta = {item["id"]: item for item in metadata["directions"]}

    frames_by_direction = {}
    pivots = {}
    direction_records = []
    all_pivots = set()

    for direction in direction_order:
        baked_frames = []
        frame_records = []
        for frame_meta in direction_meta[direction]["frames"]:
            frame_index = int(frame_meta["frame"])
            color_source = Image.open(input_dir / frame_meta["colorSource"]).convert("RGBA")
            shadow_reference = Image.open(input_dir / frame_meta["shadowSource"]).convert("RGBA")
            shadow_source = base.derive_shadow(color_source, shadow_reference)
            color_small = base.downsample(color_source)
            shadow_small = base.downsample(shadow_source)
            variants = base.variants_for(color_small, shadow_small)
            candidate = variants[base.CANDIDATE_VARIANT_ID - 1]
            pivot = scaled_pivot(frame_meta, metadata)
            all_pivots.add((pivot["x"], pivot["y"]))

            token = f"{direction}_f{frame_index:02d}"
            color_small.save(output_dir / f"{asset_id}_{token}_color_pass.png")
            shadow_small.save(output_dir / f"{asset_id}_{token}_shadow_pass.png")
            candidate.save(output_dir / f"{asset_id}_{token}.png")

            object_bounds = alpha_bounds(color_small)
            sprite_bounds = alpha_bounds(candidate)
            frame_records.append({
                "frame": frame_index,
                "phase": frame_meta["phase"],
                "file": f"{asset_id}_{token}.png",
                "colorPass": f"{asset_id}_{token}_color_pass.png",
                "shadowPass": f"{asset_id}_{token}_shadow_pass.png",
                "pivot": pivot,
                "objectAlphaBounds": object_bounds,
                "spriteAlphaBounds": sprite_bounds,
                "visualDigest": rgba_digest(candidate),
            })
            baked_frames.append(candidate)
            pivots[(direction, frame_index)] = pivot

        if len(baked_frames) != frame_count:
            raise RuntimeError(f"Direction {direction} generated {len(baked_frames)} frames, expected {frame_count}")
        frames_by_direction[direction] = baked_frames
        direction_records.append({
            "direction": direction,
            "rotationDegrees": direction_meta[direction]["rotationDegrees"],
            "frames": frame_records,
        })

    if len(all_pivots) != 1:
        raise RuntimeError(f"All character directions/frames must share one projected world-origin pivot, got {sorted(all_pivots)}")

    sheet_name = f"{asset_id}_walk_{len(direction_order)}dir_{frame_count}frame.png"
    atlas_name = f"{asset_id}_walk_atlas.png"
    review_name = f"{asset_id}_sequence_review.png"
    context_name = f"{asset_id}_8dir_context.png"

    make_fixed_sheet(frames_by_direction, direction_order, frame_count).save(output_dir / sheet_name)
    atlas, atlas_records, cell = make_trimmed_grid_atlas(
        frames_by_direction, pivots, direction_order, frame_count
    )
    atlas.save(output_dir / atlas_name)
    make_sequence_review(frames_by_direction, direction_order, frame_count).save(output_dir / review_name)
    make_direction_context(frames_by_direction, pivots, direction_order, metadata).save(output_dir / context_name)

    manifest = {
        "contract": "TYCOON_CHARACTER_SEQUENCE_V1",
        "status": metadata.get("assetStatus", "production_candidate"),
        "humanApprovalRequired": True,
        "assetId": asset_id,
        "assetType": metadata.get("assetType", "visitor_npc"),
        "sourceContract": metadata.get("sourceContract"),
        "runtime": metadata.get("runtime", {
            "contract": "CH_ACTOR_RUNTIME_V1",
            "anchorPolicy": "shared_projected_world_origin",
        }),
        "assetConfig": metadata.get("assetConfig"),
        "studioPreset": metadata.get("studioPreset"),
        "studioFingerprint": metadata.get("studioFingerprint"),
        "orthoScale": metadata.get("orthoScale"),
        "blenderUnitsPerTile": metadata.get("blenderUnitsPerTile", 3.0),
        "cameraContract": metadata.get("cameraContract", "CH_CAMERA_V1"),
        "gridContract": metadata.get("gridContract", "CH_GRID_V1"),
        "projection": metadata.get("projection"),
        "yawDegrees": metadata.get("yawDegrees"),
        "elevationDegrees": metadata.get("elevationDegrees"),
        "tile": {"width": metadata.get("tileWidth", 128), "height": metadata.get("tileHeight", 64)},
        "footprint": metadata["footprint"],
        "blenderVersion": metadata.get("blenderVersion", "unknown"),
        "renderEngine": metadata.get("renderEngine", "unknown"),
        "renderResolution": metadata.get("renderResolution"),
        "finalFrameResolution": list(base.FINAL_SIZE),
        "directionCount": len(direction_order),
        "directionOrder": list(direction_order),
        "animation": {
            **metadata["animation"],
            "frameNaming": "{assetId}_{direction}_fNN.png",
            "sequencePolicy": "single canonical model + deterministic parametric pose",
        },
        "pivotPolicy": "projected world origin (0,0,0), identical for every direction and walk frame",
        "sharedPivot": {"x": next(iter(all_pivots))[0], "y": next(iter(all_pivots))[1]},
        "productionColorMode": preset["postProcess"].get("productionColorMode", "PNG_RGBA_FULL_COLOR"),
        "productionPaletteLimit": preset["postProcess"].get("productionPaletteLimit"),
        "retroComparison": {"paletteColors": base.PALETTE_COLORS, "purpose": "review_only"},
        "candidatePostProcess": {
            **base.postprocess_variant_metadata(base.CANDIDATE_VARIANT_ID),
            "variantId": base.CANDIDATE_VARIANT_ID,
            "studioPreset": metadata.get("studioPreset"),
        },
        "directions": direction_records,
        "atlas": {
            "file": atlas_name,
            "packing": f"deterministic_{frame_count}x{len(direction_order)}_trimmed_grid_v1",
            "paddingPx": 2,
            **cell,
            "frames": atlas_records,
        },
        "files": {
            "spriteSheet": sheet_name,
            "atlas": atlas_name,
            "sequenceReview": review_name,
            "context8Dir": context_name,
        },
        "coherenceRule": metadata.get("coherenceRule"),
        "githubRunId": os.environ.get("GITHUB_RUN_ID", "local"),
        "githubSha": os.environ.get("GITHUB_SHA", "local"),
        "approvalRule": "Do not add a second NPC until this first character is visually approved for silhouette, eight-direction identity and walk-frame continuity.",
    }

    if metadata.get("diagnosticProbe"):
        manifest["diagnosticProbe"] = metadata["diagnosticProbe"]

    manifest_path = output_dir / f"{asset_id}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Generated Tycoon Character Sequence V1 package:")
    print(" -", sheet_name)
    print(" -", atlas_name)
    print(" -", review_name)
    print(" -", context_name)
    print("sharedPivot:", manifest["sharedPivot"])


if __name__ == "__main__":
    main()
