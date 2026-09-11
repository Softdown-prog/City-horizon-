#!/usr/bin/env python3
"""Prepare transparent directional pedestrian frames and an animation manifest.

Expected input names are ``idle_<direction>.png`` and
``walk_<direction>_<frame>.png`` (for example ``walk_front_01.png``).  The
tool deliberately keeps frames separate: the game can choose its own texture
packing later, while the manifest provides a stable, data-driven contract.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path

from PIL import Image


DIRECTIONS = ("front", "back", "left", "right")
WALK_PATTERN = re.compile(r"^walk_(front|back|left|right)_(\d+)\.png$", re.IGNORECASE)
BACKGROUND_MAX_CHANNEL = 48


def exterior_background(image: Image.Image) -> bytearray:
    """Return exterior black or white studio backgrounds, preserving outlines."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    mask = bytearray(width * height)
    pending: deque[tuple[int, int]] = deque()
    corners = (pixels[0, 0], pixels[width - 1, 0], pixels[0, height - 1], pixels[width - 1, height - 1])
    light_background = sum(red + green + blue for red, green, blue, _ in corners) / 12.0 >= 220.0

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if mask[index]:
            return
        red, green, blue, alpha = pixels[x, y]
        is_black = max(red, green, blue) <= BACKGROUND_MAX_CHANNEL
        # JPEG compression leaves pale-grey pixels around a white canvas. The
        # character has no near-white material, so this also removes that halo
        # without touching skin highlights or the dark pixel outline.
        is_white = light_background and min(red, green, blue) >= 180
        if alpha == 0 or is_black or is_white:
            mask[index] = 1
            pending.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)
    while pending:
        x, y = pending.popleft()
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                enqueue(next_x, next_y)
    return mask


def remove_background_and_halo_image(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    pixels = image.load()
    exterior = exterior_background(image)
    for y in range(height):
        for x in range(width):
            if exterior[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
            elif pixels[x, y][3] < 255:
                # Transparent edge pixels must not retain black RGB data, which
                # otherwise becomes a dark halo when a renderer filters them.
                red, green, blue, alpha = pixels[x, y]
                pixels[x, y] = (red, green, blue, alpha)
    return image


def remove_background_and_halo(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    remove_background_and_halo_image(Image.open(source)).save(destination, "PNG", optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--character", default="citizen_common")
    parser.add_argument("--frame-duration-ms", type=int, default=160)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--sheet", action="append", default=[], metavar="DIRECTION=PATH",
                        help="extract an equal-width horizontal strip directly from a source sheet")
    parser.add_argument("--frames-per-sheet", type=int, default=5)
    parser.add_argument("--preview", type=Path, help="optional contact-sheet preview of the front walk loop")
    args = parser.parse_args()

    if args.frame_duration_ms <= 0 or args.scale <= 0:
        raise SystemExit("frame duration and scale must be positive")

    files = sorted(args.input_dir.glob("*.png"))
    walks: dict[str, list[tuple[int, Path]]] = {direction: [] for direction in DIRECTIONS}
    idle: dict[str, Path] = {}
    for source in files:
        if match := WALK_PATTERN.match(source.name):
            walks[match.group(1).lower()].append((int(match.group(2)), source))
        elif source.stem.lower().startswith("idle_"):
            direction = source.stem[5:].lower()
            if direction in DIRECTIONS:
                idle[direction] = source

    for entry in args.sheet:
        if "=" not in entry:
            raise SystemExit("--sheet must use DIRECTION=PATH")
        direction, source_text = entry.split("=", 1)
        direction = direction.lower()
        source = Path(source_text)
        if direction not in DIRECTIONS or not source.is_file():
            raise SystemExit(f"invalid sheet: {entry}")
        sheet = Image.open(source).convert("RGBA")
        if sheet.width % args.frames_per_sheet != 0:
            raise SystemExit(f"sheet width is not divisible by frame count: {source}")
        cell_width = sheet.width // args.frames_per_sheet
        # A common crop preserves the original baseline and prevents visible
        # vertical jitter across the walk loop.
        for index in range(args.frames_per_sheet):
            frame = sheet.crop((index * cell_width, 0, (index + 1) * cell_width, sheet.height))
            staged = args.output_dir / ".staging" / f"walk_{direction}_{index + 1:02d}.png"
            staged.parent.mkdir(parents=True, exist_ok=True)
            frame.save(staged, "PNG")
            walks[direction].append((index + 1, staged))

    missing = [direction for direction in DIRECTIONS if not walks[direction]]
    if missing:
        raise SystemExit("missing walk frames for: " + ", ".join(missing))

    output_frames = args.output_dir / "frames"
    manifest: dict[str, object] = {
        "id": args.character,
        "renderScale": args.scale,
        "animations": {},
    }
    animations: dict[str, object] = manifest["animations"]  # type: ignore[assignment]
    for direction in DIRECTIONS:
        processed_walks: list[str] = []
        for _, source in sorted(walks[direction]):
            destination = output_frames / source.name.lower()
            remove_background_and_halo(source, destination)
            processed_walks.append((Path("frames") / destination.name).as_posix())
        animations[f"walk_{direction}"] = {"frameDurationMs": args.frame_duration_ms, "frames": processed_walks}
        if direction in idle:
            destination = output_frames / f"idle_{direction}.png"
            remove_background_and_halo(idle[direction], destination)
            animations[f"idle_{direction}"] = {"frameDurationMs": args.frame_duration_ms, "frames": [(Path("frames") / destination.name).as_posix()]}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "animation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.preview:
        front_frames = [Image.open(args.output_dir / relative).convert("RGBA")
                        for relative in animations["walk_front"]["frames"]]  # type: ignore[index]
        preview = Image.new("RGBA", (sum(frame.width for frame in front_frames), max(frame.height for frame in front_frames)),
                            (91, 132, 93, 255))
        x = 0
        for frame in front_frames:
            preview.alpha_composite(frame, (x, 0))
            x += frame.width
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(args.preview, "PNG", optimize=True)
    staging = args.output_dir / ".staging"
    if staging.exists():
        for temporary in staging.glob("*.png"):
            temporary.unlink()
        staging.rmdir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
