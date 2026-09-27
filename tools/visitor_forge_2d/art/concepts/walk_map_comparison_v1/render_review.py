"""Compare two existing EAST gait candidates on the same MapForge capture.

This is a visual review artifact, not an engine capture or a sprite exporter.
It never changes the source frames or the runtime catalogue.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
FRAME_ROOT = REPO / "tools/visitor_forge_2d/art/concepts"
CROP = (260, 310, 640, 690)
START_FOOT = (142, 306)  # Within the crop; clear ground in front of the shop.
TILE_VECTOR_EAST = (64.0, 32.0)  # CH_CAMERA_V1, 128x64 reference tile.
SPEED_TILES_PER_SECOND = 0.30
BODY_SCALE = 56.0 / 97.0
FRAME_SIZE = round(128 * BODY_SCALE)
PIVOT = (round(64 * BODY_SCALE), round(116 * BODY_SCALE))

CANDIDATES = (
    ("Structural Gait V2", "directional_gait_candidate_v2", 220),
    ("Full Pose EAST", "full_pose_east_candidate_v1", 270),
)


def _frames(folder: str) -> tuple[Image.Image, Image.Image]:
    result = []
    for pose in ("a", "b"):
        with Image.open(FRAME_ROOT / folder / f"east_walk_{pose}.png") as source:
            if source.mode != "RGBA" or source.size != (128, 128):
                raise ValueError(f"{folder}/east_walk_{pose} must be RGBA 128x128")
            result.append(source.resize((FRAME_SIZE, FRAME_SIZE), Image.Resampling.LANCZOS))
    return result[0], result[1]


def _scene(background: Image.Image, sprite: Image.Image, elapsed_ms: int, title: str) -> Image.Image:
    scene = background.copy()
    x = START_FOOT[0] + round(TILE_VECTOR_EAST[0] * SPEED_TILES_PER_SECOND * elapsed_ms / 1000)
    y = START_FOOT[1] + round(TILE_VECTOR_EAST[1] * SPEED_TILES_PER_SECOND * elapsed_ms / 1000)
    scene.alpha_composite(sprite, (x - PIVOT[0], y - PIVOT[1]))
    draw = ImageDraw.Draw(scene)
    draw.rectangle((5, 5, 224, 28), fill=(20, 32, 29, 230))
    draw.text((12, 10), title, fill=(255, 255, 245, 255))
    return scene


def render(capture: Path, output: Path) -> dict:
    with Image.open(capture) as source:
        if source.width < CROP[2] or source.height < CROP[3]:
            raise ValueError("Map capture is too small for the established review crop")
        background = source.convert("RGBA").crop(CROP)
    if background.size != (380, 380):
        raise AssertionError("Map crop changed")
    output.mkdir(parents=True, exist_ok=True)
    sources = {name: _frames(folder) for name, folder, _ in CANDIDATES}

    # Six stills per candidate expose the pose and ground pivot at gameplay
    # scale; the GIF adds the timed A/B exchange and continuous world motion.
    times = (0, 220, 440, 660, 880, 1100)
    contact = Image.new("RGBA", (6 * 190, 2 * 240), (31, 44, 38, 255))
    for row, (name, _, cadence) in enumerate(CANDIDATES):
        for col, elapsed in enumerate(times):
            pose = (elapsed // cadence) % 2
            scene = _scene(background, sources[name][pose], elapsed,
                           f"{name} | {elapsed}ms | {'AB'[pose]}")
            # Crop around the same path, keeping characters at their true 56px size.
            cell = scene.crop((90, 110, 280, 350))
            label = ImageDraw.Draw(cell)
            label.rectangle((0, 0, 189, 24), fill=(20, 32, 29, 230))
            label.text((5, 6), f"{name} {elapsed}ms {'AB'[pose]}", fill="white")
            contact.alpha_composite(cell, (col * 190, row * 240))
    contact_path = output / "east_steps_on_map_56px.png"
    contact.save(contact_path, format="PNG")

    motion = []
    for elapsed in range(0, 1620, 90):
        pair = Image.new("RGBA", (760, 380), (31, 44, 38, 255))
        for col, (name, _, cadence) in enumerate(CANDIDATES):
            pose = (elapsed // cadence) % 2
            pair.alpha_composite(_scene(background, sources[name][pose], elapsed,
                                        f"{name} | {'AB'[pose]} | {elapsed}ms"), (col * 380, 0))
        motion.append(pair.convert("RGB"))
    gif_path = output / "east_steps_on_map_56px.gif"
    motion[0].save(gif_path, save_all=True, append_images=motion[1:], duration=90,
                   loop=0, optimize=True)

    report = {
        "contract": "CH_VISITOR_WALK_MAP_COMPARISON_V1",
        "sourceCaptureSha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
        "crop": list(CROP), "camera": "CH_CAMERA_V1", "tile": [128, 64],
        "direction": "east", "displayBodyHeightPx": 56,
        "anchor": [64, 116], "speedTilesPerSecond": SPEED_TILES_PER_SECOND,
        "candidateFrameDurationsMs": {name: cadence for name, _, cadence in CANDIDATES},
        "files": [contact_path.name, gif_path.name],
        "engineCapture": False, "artApproved": False, "runtimePromotion": False,
    }
    (output / "review.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    print(json.dumps(render(args.capture, args.output), indent=2))
