"""Validate the first City Horizon NPC sequence consistency package."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

EXPECTED_DIRECTIONS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--asset-config", required=True)
    parser.add_argument("--studio-preset", required=True)
    return parser.parse_args()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_png(path: Path):
    require(path.is_file(), f"Missing PNG: {path}")
    with Image.open(path) as image:
        require(image.format == "PNG", f"Not a PNG: {path}")
        image.verify()


def rgba_digest(path: Path) -> str:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        payload = rgba.width.to_bytes(4, "big") + rgba.height.to_bytes(4, "big") + rgba.tobytes()
    return hashlib.sha256(payload).hexdigest()


def main():
    args = parse_args()
    manifest_path = Path(args.manifest)
    base = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = json.loads(Path(args.asset_config).read_text(encoding="utf-8"))
    studio = json.loads(Path(args.studio_preset).read_text(encoding="utf-8"))

    require(manifest.get("contract") == "TYCOON_CHARACTER_SEQUENCE_V1", "Character manifest contract changed")
    require(asset.get("contract") == "TYCOON_CHARACTER_SOURCE_V1", "Character source contract changed")
    require(manifest.get("assetId") == asset.get("assetId"), "Asset ID mismatch")
    require(manifest.get("studioPreset") == studio.get("id") == "CH_TYCOON_STUDIO_V1", "Frozen studio mismatch")
    require(manifest.get("cameraContract") == "CH_CAMERA_V1", "Camera contract changed")
    require(tuple(manifest.get("directionOrder", [])) == EXPECTED_DIRECTIONS, "8-direction order changed")
    require(manifest.get("directionCount") == 8, "Character must bake exactly 8 directions")

    runtime = manifest.get("runtime", {})
    require(runtime.get("contract") == "CH_ACTOR_RUNTIME_V1", "Character runtime contract changed")
    require(runtime.get("anchorPolicy") == "shared_projected_world_origin", "Character anchor policy changed")
    require(runtime.get("frameCount") == 8, "Runtime frame count must be eight")
    require(tuple(runtime.get("directionOrder", [])) == EXPECTED_DIRECTIONS, "Runtime direction order changed")

    animation = manifest.get("animation", {})
    require(animation.get("id") == "walk", "Expected walk animation")
    require(animation.get("frameCount") == 8, "Walk cycle must contain exactly 8 frames")
    require(animation.get("loop") is True, "Walk cycle must loop")
    require(int(animation.get("frameDurationMs", 0)) > 0, "Frame duration must be positive")

    directions = manifest.get("directions", [])
    require(len(directions) == 8, "Manifest must contain 8 directional sequences")

    validation = asset.get("validation", {})
    minimum_distinct = int(validation.get("minimumDistinctFramesPerDirection", 6))
    max_height_jitter = int(validation.get("maximumObjectHeightJitterPx", 18))
    max_width_jitter = int(validation.get("maximumObjectWidthJitterPx", 24))

    pivots = set()
    total_frames = 0
    first_frame_digests = []
    for direction_record in directions:
        direction = direction_record.get("direction")
        require(direction in EXPECTED_DIRECTIONS, f"Unexpected direction {direction!r}")
        frames = direction_record.get("frames", [])
        require(len(frames) == 8, f"{direction} does not have 8 frames")
        require([frame.get("frame") for frame in frames] == list(range(8)), f"{direction} frame order changed")

        visual_digests = []
        object_widths = []
        object_heights = []
        for frame in frames:
            file_path = base / frame["file"]
            validate_png(file_path)
            validate_png(base / frame["colorPass"])
            validate_png(base / frame["shadowPass"])
            pivot = frame.get("pivot", {})
            pivots.add((pivot.get("x"), pivot.get("y")))

            bounds = frame.get("objectAlphaBounds")
            require(isinstance(bounds, list) and len(bounds) == 4, f"Missing object bounds: {direction} f{frame['frame']:02d}")
            require(bounds[2] > bounds[0] and bounds[3] > bounds[1], f"Empty object bounds: {direction} f{frame['frame']:02d}")
            object_widths.append(bounds[2] - bounds[0])
            object_heights.append(bounds[3] - bounds[1])

            digest = rgba_digest(file_path)
            require(digest == frame.get("visualDigest"), f"Digest mismatch: {direction} f{frame['frame']:02d}")
            visual_digests.append(digest)
            total_frames += 1

        require(
            len(set(visual_digests)) >= minimum_distinct,
            f"{direction} produced only {len(set(visual_digests))} distinct frames; expected at least {minimum_distinct}",
        )
        require(
            max(object_heights) - min(object_heights) <= max_height_jitter,
            f"{direction} object height jitters by {max(object_heights)-min(object_heights)} px; limit {max_height_jitter}",
        )
        require(
            max(object_widths) - min(object_widths) <= max_width_jitter,
            f"{direction} object width jitters by {max(object_widths)-min(object_widths)} px; limit {max_width_jitter}",
        )
        first_frame_digests.append(visual_digests[0])

    require(total_frames == 64, f"Expected 64 final character frames, got {total_frames}")
    require(len(pivots) == 1, f"All directions and frames must share one pivot, got {sorted(pivots)}")
    require(len(set(first_frame_digests)) == 8, "The 8 directional views are not all visually distinct")

    files = manifest.get("files", {})
    for key in ("spriteSheet", "atlas", "sequenceReview", "context8Dir"):
        validate_png(base / files[key])

    atlas = manifest.get("atlas", {})
    atlas_frames = atlas.get("frames", [])
    require(len(atlas_frames) == 64, "Atlas must contain 64 frame records")
    expected_order = [(d, f) for d in EXPECTED_DIRECTIONS for f in range(8)]
    actual_order = [(record.get("direction"), record.get("frame")) for record in atlas_frames]
    require(actual_order == expected_order, "Atlas direction/frame ordering changed")

    print("TYCOON_CHARACTER_SEQUENCE_V1 validation passed")
    print("assetId:", manifest["assetId"])
    print("studioPreset:", manifest["studioPreset"])
    print("sharedPivot:", next(iter(pivots)))
    print("directions:", 8)
    print("framesPerDirection:", 8)
    print("totalFrames:", total_frames)
    print("characterSequenceGate: PASS")


if __name__ == "__main__":
    main()
