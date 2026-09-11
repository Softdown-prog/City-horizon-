#!/usr/bin/env python3
"""Prepare directional driving loops for cars, tractors, and other four-wheel vehicles.

Each source is a horizontal sprite strip. The tool extracts equal-width frames,
removes an exterior black/white backdrop and its matte, preserves the original
cell canvas (so vehicles never jitter), and writes a data-driven manifest.

Example:
  python tools/prepare_four_wheel_vehicle_animation.py raw tractor_red \
    --sheet front=tractor_front.png --sheet right=tractor_right.png \
    --sheet left=tractor_left.png --sheet back=tractor_back.png --frames-per-sheet 4
"""

from __future__ import annotations

import argparse
import json
import math
from collections import deque
from pathlib import Path

from PIL import Image


DIRECTIONS = ("front", "right", "back", "left")


def exterior_backdrop(image: Image.Image) -> bytearray:
    """Flood-fill only a studio-like outer backdrop; enclosed dark pixels survive."""
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    mask = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    corners = [pixels[x, y] for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1))]

    def is_neutral_light(red: int, green: int, blue: int) -> bool:
        # Some supplied strips use a grey editor checkerboard rather than a
        # flat white background. It is neutral, including at the corners, but
        # not bright enough for the previous white-matte threshold.
        return min(red, green, blue) >= 100 and max(red, green, blue) - min(red, green, blue) <= 18

    # A strip whose width is not divisible by its frame count gets padded by
    # one transparent column. Two opaque light corners are enough to identify
    # the checkerboard in that final frame.
    light = sum(is_neutral_light(red, green, blue) for red, green, blue, _ in corners) >= 2

    def enqueue(x: int, y: int) -> None:
        index = y * width + x
        if mask[index]:
            return
        red, green, blue, alpha = pixels[x, y]
        backdrop = alpha == 0 or max(red, green, blue) <= 48 or (light and is_neutral_light(red, green, blue))
        if backdrop:
            mask[index] = 1
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0); enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y); enqueue(width - 1, y)
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)
    return mask


def clean_frame(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    exterior = exterior_backdrop(rgba)
    for y in range(height):
        for x in range(width):
            if exterior[y * width + x]:
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def parse_sheet(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--sheet must use DIRECTION=PATH")
    direction, filename = value.split("=", 1)
    if direction not in DIRECTIONS:
        raise argparse.ArgumentTypeError(f"unknown direction: {direction}")
    return direction, Path(filename)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="base folder used for relative --sheet paths")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--vehicle", default="vehicle_four_wheel")
    parser.add_argument("--frame-duration-ms", type=int, default=130)
    parser.add_argument("--render-scale", type=int, default=1)
    parser.add_argument("--frames-per-sheet", type=int, default=4)
    parser.add_argument("--sheet", action="append", default=[], type=parse_sheet, metavar="DIRECTION=PATH")
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    if args.frame_duration_ms <= 0 or args.render_scale <= 0 or args.frames_per_sheet <= 0:
        raise SystemExit("frame duration, scale and frame count must be positive")
    sheets = dict(args.sheet)
    missing = [direction for direction in DIRECTIONS if direction not in sheets]
    if missing:
        raise SystemExit("missing sheets for: " + ", ".join(missing))

    frames_dir = args.output_dir / "frames"
    animations: dict[str, object] = {}
    preview_frames: list[Image.Image] = []
    for direction in DIRECTIONS:
        source = sheets[direction]
        if not source.is_absolute():
            source = args.input_dir / source
        if not source.is_file():
            raise SystemExit(f"missing sheet: {source}")
        sheet = Image.open(source).convert("RGBA")
        # AI-generated strips commonly gain one or two pixels during export.
        # Normalize them onto equal cells instead of rejecting an otherwise
        # valid animation, preserving a shared frame canvas and baseline.
        cell_width = math.ceil(sheet.width / args.frames_per_sheet)
        saved: list[str] = []
        for index in range(args.frames_per_sheet):
            left = index * cell_width
            right = min(sheet.width, left + cell_width)
            source_frame = sheet.crop((left, 0, right, sheet.height))
            frame_canvas = Image.new("RGBA", (cell_width, sheet.height), (0, 0, 0, 0))
            frame_canvas.alpha_composite(source_frame, (0, 0))
            frame = clean_frame(frame_canvas)
            filename = f"drive_{direction}_{index + 1:02d}.png"
            destination = frames_dir / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            frame.save(destination, "PNG", optimize=True)
            saved.append((Path("frames") / filename).as_posix())
            if direction == "front":
                preview_frames.append(frame)
        animations[f"drive_{direction}"] = {"frameDurationMs": args.frame_duration_ms, "frames": saved}

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": args.vehicle, "vehicleType": "four_wheel", "renderScale": args.render_scale,
                "directions": list(DIRECTIONS), "animations": animations}
    (args.output_dir / "animation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if args.preview:
        preview = Image.new("RGBA", (sum(frame.width for frame in preview_frames), max(frame.height for frame in preview_frames)), (69, 107, 76, 255))
        offset = 0
        for frame in preview_frames:
            preview.alpha_composite(frame, (offset, 0)); offset += frame.width
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview.save(args.preview, "PNG", optimize=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
