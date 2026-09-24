"""Validate a generic TYCOON_ASSET_BAKE_V1 package and optional golden visual regression."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from PIL import Image

EXPECTED_ORDER = ["south", "east", "west", "north"]
EXPECTED_TURNS = {"south": 0, "east": 1, "west": 3, "north": 2}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    parser.add_argument("--golden-fingerprint")
    parser.add_argument("--golden-mean-abs-tolerance", type=float, default=6.0)
    return parser.parse_args()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_png(path: Path):
    require(path.is_file(), f"Missing PNG: {path}")
    with Image.open(path) as image:
        require(image.format == "PNG", f"Not a PNG: {path}")
        require(image.width > 0 and image.height > 0, f"Invalid PNG dimensions: {path}")
        image.verify()


def checked_rgba(path: Path, expected_size, *, allow_empty=False):
    """Read the actual exported pixels instead of trusting manifest geometry."""
    validate_png(path)
    with Image.open(path) as image:
        require(image.mode == "RGBA", f"Production PNG must be RGBA: {path} ({image.mode})")
        require(list(image.size) == expected_size, f"PNG size differs from manifest: {path} ({image.size} != {expected_size})")
        bounds = image.getchannel("A").getbbox()
        if not allow_empty:
            require(bounds is not None, f"Empty alpha in production PNG: {path}")
        return list(bounds) if bounds is not None else None


def rgba_digest(path: Path) -> str:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        payload = rgba.size[0].to_bytes(4, "big") + rgba.size[1].to_bytes(4, "big") + rgba.tobytes()
    return hashlib.sha256(payload).hexdigest()


def fingerprint_difference(actual_path: Path, golden_record, sample_size) -> float:
    with Image.open(actual_path) as actual_image:
        actual = actual_image.convert("RGBA").resize(tuple(sample_size), Image.Resampling.LANCZOS)
        actual_samples = list(actual.tobytes())
    encoded = golden_record.get("samplesBase64", "")
    expected_samples = list(base64.b64decode(encoded)) if encoded else []
    require(len(actual_samples) == len(expected_samples), f"Golden fingerprint length mismatch: {actual_path}")
    return sum(abs(a - b) for a, b in zip(actual_samples, expected_samples)) / len(actual_samples)


def main():
    args = parse_args()
    manifest_path = Path(args.manifest)
    require(manifest_path.is_file(), f"Manifest does not exist: {manifest_path}")
    manifest = load_json(manifest_path)
    asset = load_json(args.asset_config)
    studio = load_json(args.studio_preset)
    base = manifest_path.parent

    require(manifest.get("contract") == "TYCOON_ASSET_BAKE_V1", "Wrong bake contract")
    require(manifest.get("sourceContract") == "TYCOON_ASSET_SOURCE_V1", "Wrong source contract")
    require(manifest.get("assetId") == asset.get("assetId"), "Manifest assetId does not match asset config")
    require(manifest.get("assetType") == asset.get("assetType"), "Manifest assetType does not match asset config")
    require(manifest.get("studioPreset") == studio.get("id"), "Wrong studio preset")
    require(asset.get("studioPreset") == studio.get("id"), "Asset requests a different studio preset")
    require(manifest.get("cameraContract") == studio["camera"]["contract"] == "CH_CAMERA_V1", "Wrong camera contract")
    require(manifest.get("gridContract") == "CH_GRID_V1", "Wrong grid contract")
    require(manifest.get("directionCount") == 4, "Direction count must be four")
    require(manifest.get("directionOrder") == EXPECTED_ORDER, "Canonical direction order changed")
    require(manifest.get("footprint") == asset.get("footprint"), "Footprint differs from asset source")
    frame_size = manifest.get("finalFrameResolution")
    minimum_size = studio["render"]["finalResolution"]
    require(isinstance(frame_size, list) and len(frame_size) == 2 and
            all(type(value) is int and value > 0 for value in frame_size), "Invalid final frame resolution")
    require(all(actual >= minimum for actual, minimum in zip(frame_size, minimum_size)),
            "Final resolution is smaller than the studio preset minimum")
    require(manifest.get("paletteColorCount") == studio["postProcess"]["paletteColors"], "Palette size differs from studio preset")
    require(
        manifest.get("candidatePostProcess", {}).get("variantId") == studio["postProcess"]["candidateVariant"],
        "Candidate post-process variant differs from studio preset",
    )

    views = manifest.get("views", [])
    require(len(views) == 4, "Manifest must contain exactly four view records")
    require([view.get("direction") for view in views] == EXPECTED_ORDER, "View records are not in canonical order")
    turns = {view.get("direction"): view.get("quarterTurns") for view in views}
    require(turns == EXPECTED_TURNS, f"Quarter-turn mapping changed: {turns}")

    pivots = {(view["pivot"]["x"], view["pivot"]["y"]) for view in views}
    require(len(pivots) == 1, f"Four views do not share one projected world-origin pivot: {sorted(pivots)}")

    alpha_bounds = []
    visual_digests = []
    for view in views:
        direction = view["direction"]
        file_path = base / view["file"]
        bounds = view.get("spriteAlphaBounds")
        require(isinstance(bounds, list) and len(bounds) == 4, f"Missing alpha bounds for {direction}")
        actual_bounds = checked_rgba(file_path, frame_size)
        require(bounds == actual_bounds, f"Sprite alpha bounds differ from PNG for {direction}: {bounds} != {actual_bounds}")
        color_bounds = checked_rgba(base / view["colorPass"], frame_size)
        require(view.get("objectAlphaBounds") == color_bounds,
                f"Object alpha bounds differ from color pass for {direction}")
        checked_rgba(base / view["shadowPass"], frame_size, allow_empty=True)
        if "maskPass" in view:
            mask_bounds = checked_rgba(base / view["maskPass"], frame_size)
            require(view.get("maskAlphaBounds") == mask_bounds,
                    f"Mask alpha bounds differ from PNG for {direction}")
        alpha_bounds.append(tuple(bounds))
        visual_digests.append(rgba_digest(file_path))

    validation = asset.get("validation", {})
    minimum_distinct_visuals = int(validation.get("minimumDistinctDirectionVisuals", 1))
    require(1 <= minimum_distinct_visuals <= 4, "minimumDistinctDirectionVisuals must be between 1 and 4")
    distinct_visual_count = len(set(visual_digests))
    require(
        distinct_visual_count >= minimum_distinct_visuals,
        f"Four-direction bake produced only {distinct_visual_count} distinct visual outputs; asset requires {minimum_distinct_visuals}",
    )

    atlas_frames = manifest.get("atlas", {}).get("frames", [])
    require([frame.get("direction") for frame in atlas_frames] == EXPECTED_ORDER, "Atlas direction order changed")
    for frame, view in zip(atlas_frames, views):
        require(frame.get("w", 0) > 0 and frame.get("h", 0) > 0, f"Invalid atlas frame: {frame}")
        require("pivotX" in frame and "pivotY" in frame, f"Atlas frame missing trimmed pivot: {frame}")
        left, top, right, bottom = view["spriteAlphaBounds"]
        require(frame.get("sourceBounds") == [left, top, right, bottom] and
                [frame["w"], frame["h"]] == [right - left, bottom - top],
                f"Atlas crop differs from sprite bounds for {view['direction']}")
        require(frame["pivotX"] == view["pivot"]["x"] - left and
                frame["pivotY"] == view["pivot"]["y"] - top,
                f"Trimmed atlas pivot differs from shared pivot for {view['direction']}")

    files = manifest.get("files", {})
    for key in ("south", "east", "west", "north", "spriteSheet", "atlas", "reviewSheet", "styleMatrix", "context4Dir"):
        require(key in files, f"Manifest files node is missing {key}")
        validate_png(base / files[key])
    for view in views:
        require(files[view["direction"]] == view["file"],
                f"Direction file mapping differs from view record for {view['direction']}")
    with Image.open(base / files["spriteSheet"]) as sheet:
        require(sheet.size == (frame_size[0] * 4, frame_size[1]),
                "Fixed four-view sheet dimensions differ from final frame resolution")

    if args.golden_fingerprint:
        golden = load_json(args.golden_fingerprint)
        require(golden.get("contract") == "TYCOON_GOLDEN_FINGERPRINT_V1", "Wrong golden fingerprint contract")
        require(golden.get("assetId") == asset.get("assetId"), "Golden fingerprint belongs to another asset")
        sample_size = golden.get("sampleSize", [32, 32])
        scores = {}
        for direction in EXPECTED_ORDER:
            actual = base / files[direction]
            record = golden.get("directions", {}).get(direction)
            require(record is not None, f"Golden fingerprint missing direction: {direction}")
            score = fingerprint_difference(actual, record, sample_size)
            scores[direction] = score
            require(
                score <= args.golden_mean_abs_tolerance,
                f"Golden visual regression failed for {direction}: fingerprint mean abs diff {score:.3f} > {args.golden_mean_abs_tolerance:.3f}",
            )
        print("goldenFingerprintMeanAbsDiff:", {key: round(value, 4) for key, value in scores.items()})

    print("TYCOON_ASSET_BAKE_V1 validation passed")
    print("assetId:", asset["assetId"])
    print("studioPreset:", studio["id"])
    print("sharedPivot:", next(iter(pivots)))
    print("distinctDirectionalBounds:", len(set(alpha_bounds)))
    print("distinctDirectionalVisuals:", distinct_visual_count)


if __name__ == "__main__":
    main()
