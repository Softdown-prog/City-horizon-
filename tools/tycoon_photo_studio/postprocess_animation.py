"""Post-process an animated Tycoon bake into per-direction spritesheets and a full atlas.

Reads the source PNGs and studio_metadata.json produced by build_animated_scene.py
and produces:

  • <asset_id>_<direction>_spritesheet.png  — horizontal strip of all frames, 1 direction
  • <asset_id>_full_atlas.png              — all directions × all frames, row per direction
  • <asset_id>_animation_manifest.json     — pivot, frame size, direction order, fps, loop

Usage
-----
    python tools/tycoon_photo_studio/postprocess_animation.py \\
        --input   out/bake/windmill_01/source \\
        --output  out/bake/windmill_01/final \\
        --studio-preset tools/tycoon_photo_studio/studio_presets/ch_tycoon_studio_v1.json

The postprocess applies the same canonical recipe as postprocess.py:
  Lanczos downsample → shadow composite → edge cleanup → palette quantisation (Floyd-Steinberg).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# Reuse shared image ops from the static postprocess pipeline
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import postprocess as _pp  # noqa: E402


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-process animated Tycoon bake into spritesheets"
    )
    parser.add_argument("--input", required=True, metavar="DIR",
                        help="Source directory (output of build_animated_scene.py)")
    parser.add_argument("--output", required=True, metavar="DIR",
                        help="Output directory for final spritesheets and manifest")
    parser.add_argument("--studio-preset", required=True, metavar="PATH",
                        help="Path to the studio preset JSON")
    parser.add_argument("--no-palette", action="store_true",
                        help="Skip palette quantisation (faster, larger files)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Frame processing (canonical post-process recipe)
# ---------------------------------------------------------------------------


def process_frame(
    color_path: Path,
    shadow_path: Path,
    final_size: tuple[int, int],
    post_cfg: dict,
) -> Image.Image:
    """Apply the canonical post-process recipe to a single frame.

    Returns an RGBA PIL image at final_size.
    """
    # Load source passes
    color_src = Image.open(color_path).convert("RGBA")
    shadow_src = Image.open(shadow_path).convert("RGBA")

    # Shadow composite (same logic as _pp.composite_shadow)
    shadow_color = tuple(post_cfg.get("shadowColor", [29, 33, 37]))
    shadow_alpha_scale = float(post_cfg.get("shadowAlphaScale", 0.72))
    shadow_alpha_max = int(post_cfg.get("shadowAlphaMax", 132))
    shadow_blur = float(post_cfg.get("shadowBlurRadius", 1.4))

    try:
        composite = _pp.composite_shadow(
            color_src, shadow_src,
            shadow_color, shadow_alpha_scale, shadow_alpha_max, shadow_blur,
        )
    except Exception:
        # Fallback: just use color_src if composite_shadow signature differs
        composite = color_src

    # Downsample (Lanczos)
    final = composite.resize(final_size, Image.Resampling.LANCZOS)

    # Edge cleanup (anti-aliasing fringe reduction)
    try:
        final = _pp.edge_cleanup(
            final,
            int(post_cfg.get("edgeAlphaThreshold", 92)),
            float(post_cfg.get("edgeOpacityScale", 0.38)),
            int(post_cfg.get("edgeOpacityMax", 96)),
        )
    except Exception:
        pass

    return final


def quantise_sheet(sheet: Image.Image, n_colors: int) -> Image.Image:
    """Apply palette quantisation (Floyd-Steinberg dithering) to the full spritesheet."""
    try:
        quantised = _pp.quantize_rgba(sheet, n_colors)
        return quantised
    except Exception:
        return sheet


# ---------------------------------------------------------------------------
# Spritesheet composition
# ---------------------------------------------------------------------------


def build_direction_strip(
    frames: list[Image.Image],
    direction_id: str,
) -> Image.Image:
    """Build a horizontal spritesheet: all frames side by side for one direction."""
    if not frames:
        raise ValueError(f"No frames for direction '{direction_id}'")
    fw, fh = frames[0].size
    strip = Image.new("RGBA", (fw * len(frames), fh), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        strip.paste(frame, (i * fw, 0), frame)
    return strip


def build_full_atlas(
    direction_strips: dict[str, Image.Image],
    direction_order: list[str],
) -> Image.Image:
    """Stack all direction strips vertically into a full animation atlas."""
    strips = [direction_strips[d] for d in direction_order if d in direction_strips]
    if not strips:
        raise ValueError("No direction strips to compose")
    total_w = max(s.width for s in strips)
    total_h = sum(s.height for s in strips)
    atlas = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y = 0
    for strip in strips:
        atlas.paste(strip, (0, y), strip)
        y += strip.height
    return atlas


def alpha_bounds(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.convert("RGBA").getchannel("A").getbbox()
    if bbox is None:
        return (0, 0, image.width, image.height)
    return bbox


# ---------------------------------------------------------------------------
# Pivot scaling
# ---------------------------------------------------------------------------


def scale_pivot(ground_origin_src_px: dict, src_res: tuple, final_size: tuple) -> dict:
    """Scale the ground-origin pivot from source resolution to final resolution."""
    return {
        "x": int(round(ground_origin_src_px["x"] * final_size[0] / src_res[0])),
        "y": int(round(ground_origin_src_px["y"] * final_size[1] / src_res[1])),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Load preset and metadata ───────────────────────────────────────────
    preset = json.loads(Path(args.studio_preset).read_text(encoding="utf-8"))
    _pp.apply_studio_preset(preset)

    meta_path = input_dir / "studio_metadata.json"
    if not meta_path.is_file():
        print(f"[ERROR] studio_metadata.json not found in '{input_dir}'", file=sys.stderr)
        return 1

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))

    if not metadata.get("animationMode"):
        print(
            "[ERROR] This post-processor is for animated bakes. "
            "Use postprocess.py for static assets.",
            file=sys.stderr,
        )
        return 1

    if metadata.get("studioPreset") != preset.get("id"):
        print("[ERROR] Studio preset mismatch.", file=sys.stderr)
        return 1

    # Dynamic final resolution from baker
    if "finalResolution" in metadata:
        global _pp
        _pp.FINAL_SIZE = tuple(map(int, metadata["finalResolution"]))
    final_size: tuple[int, int] = _pp.FINAL_SIZE
    src_res = tuple(map(int, metadata.get("renderResolution", [1024, 1024])))
    post_cfg = metadata.get("postProcess", preset.get("postProcess", {}))
    n_colors = int(post_cfg.get("paletteColors", 128))

    asset_id = metadata["sourceObject"]
    direction_order: list[str] = metadata.get("directionOrder", ["south", "east", "west", "north"])
    anim = metadata.get("animation", {})
    frame_start = int(anim.get("frameStart", 1))
    frame_end = int(anim.get("frameEnd", 8))
    fps = int(anim.get("fps", 12))
    looping = bool(anim.get("looping", True))

    print(
        f"[anim_postprocess] '{asset_id}'  "
        f"directions={direction_order}  frames={frame_start}–{frame_end}  "
        f"final_size={final_size[0]}×{final_size[1]}"
    )

    # Build lookup: direction_id → list of frame dicts (sorted by frame index)
    dir_frame_map: dict[str, list[dict]] = {d: [] for d in direction_order}
    for dir_meta in metadata.get("directions", []):
        did = dir_meta["id"]
        dir_frame_map[did] = sorted(dir_meta.get("frames", []), key=lambda f: f["frame"])

    # ── Process every frame ───────────────────────────────────────────────
    processed: dict[str, list[Image.Image]] = {d: [] for d in direction_order}
    pivot_by_dir: dict[str, dict] = {}

    for direction_id in direction_order:
        frame_dicts = dir_frame_map.get(direction_id, [])
        if not frame_dicts:
            print(f"[WARN] No frames for direction '{direction_id}' — skipping")
            continue

        dir_frames: list[Image.Image] = []
        for fdict in frame_dicts:
            frame_idx = int(fdict["frame"])
            color_path = input_dir / fdict["colorSource"]
            shadow_path = input_dir / fdict["shadowSource"]

            if not color_path.is_file():
                print(f"[WARN] Missing color source: {color_path.name}")
                continue
            if not shadow_path.is_file():
                print(f"[WARN] Missing shadow source: {shadow_path.name}")
                continue

            frame_img = process_frame(color_path, shadow_path, final_size, post_cfg)
            dir_frames.append(frame_img)

            # Save individual final frame PNG
            out_name = f"{asset_id}_{direction_id}_frame_{frame_idx:02d}.png"
            frame_img.save(output_dir / out_name, "PNG")

        processed[direction_id] = dir_frames

        # Pivot from the first frame of this direction (pivot is stable across frames)
        if frame_dicts:
            src_pivot = frame_dicts[0].get("groundOriginSourcePx", {"x": 0, "y": 0})
            pivot_by_dir[direction_id] = scale_pivot(src_pivot, src_res, final_size)

    # ── Build direction spritesheets ──────────────────────────────────────
    strips: dict[str, Image.Image] = {}
    for direction_id in direction_order:
        frames = processed.get(direction_id, [])
        if not frames:
            continue
        strip = build_direction_strip(frames, direction_id)
        if not args.no_palette:
            strip = quantise_sheet(strip, n_colors)
        strip_name = f"{asset_id}_{direction_id}_spritesheet.png"
        strip.save(output_dir / strip_name, "PNG")
        strips[direction_id] = strip
        print(f"  [{direction_id}] spritesheet saved: {strip_name}")

    # ── Build full atlas ──────────────────────────────────────────────────
    atlas = build_full_atlas(strips, direction_order)
    if not args.no_palette:
        atlas = quantise_sheet(atlas, n_colors)
    atlas_name = f"{asset_id}_full_atlas.png"
    atlas.save(output_dir / atlas_name, "PNG")
    print(f"  Full atlas saved: {atlas_name} ({atlas.width}×{atlas.height})")

    # ── Write animation manifest ──────────────────────────────────────────
    frame_w, frame_h = final_size
    manifest = {
        "contract": "TYCOON_ASSET_BAKE_V1",
        "animationManifest": True,
        "assetId": asset_id,
        "assetType": metadata.get("assetType", "animated_prop"),
        "cameraContract": metadata.get("cameraContract", "CH_CAMERA_V1"),
        "gridContract": metadata.get("gridContract", "CH_GRID_V1"),
        "footprint": metadata.get("footprint", {}),
        "animation": {
            "frameStart": frame_start,
            "frameEnd": frame_end,
            "frameCount": frame_end - frame_start + 1,
            "fps": fps,
            "looping": looping,
        },
        "directionOrder": direction_order,
        "frameSize": {"width": frame_w, "height": frame_h},
        "atlas": {
            "file": atlas_name,
            "width": atlas.width,
            "height": atlas.height,
            "rowsPerDirection": 1,
            "framesPerRow": frame_end - frame_start + 1,
        },
        "pivots": pivot_by_dir,
        "spritesheets": {
            did: f"{asset_id}_{did}_spritesheet.png"
            for did in direction_order
            if did in strips
        },
        "postProcess": {
            "paletteColors": n_colors,
            "paletteApplied": not args.no_palette,
            "finalSize": list(final_size),
        },
        "humanApprovalRequired": True,
        "status": "visual_candidate",
    }

    manifest_name = f"{asset_id}_animation_manifest.json"
    (output_dir / manifest_name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Manifest saved: {manifest_name}")

    print(f"\n[anim_postprocess] ✓ Complete — {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
