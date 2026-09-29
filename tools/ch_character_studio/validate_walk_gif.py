#!/usr/bin/env python3
"""Validate Character Studio walk-preview GIFs before sharing/review.

This is intentionally a small fail-fast gate: an animation preview is only valid
when Pillow can reopen every frame and the expected frame count/size are intact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError


def validate(path: Path, *, frames: int, width: int, height: int) -> dict:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"GIF does not exist or is empty: {path}")

    try:
        image = Image.open(path)
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"GIF cannot be opened: {exc}") from exc

    if image.format != "GIF":
        raise ValueError(f"expected GIF, got {image.format!r}")
    if image.size != (width, height):
        raise ValueError(f"expected {width}x{height}, got {image.size[0]}x{image.size[1]}")
    if getattr(image, "n_frames", 1) != frames:
        raise ValueError(f"expected {frames} frames, got {getattr(image, 'n_frames', 1)}")

    durations: list[int] = []
    for index in range(frames):
        image.seek(index)
        # Force full decode so truncated/corrupt later frames fail here.
        image.convert("RGBA").load()
        durations.append(int(image.info.get("duration", 0)))

    return {
        "contract": "CH_CHARACTER_GIF_VALIDATION_V0",
        "status": "ok",
        "path": str(path),
        "format": image.format,
        "size": [width, height],
        "frames": frames,
        "durationsMs": durations,
        "loop": int(image.info.get("loop", 0)),
        "bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif", type=Path)
    parser.add_argument("--frames", type=int, default=8)
    parser.add_argument("--width", type=int, default=384)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args()

    try:
        report = validate(args.gif, frames=args.frames, width=args.width, height=args.height)
    except (OSError, ValueError) as exc:
        print(json.dumps({
            "contract": "CH_CHARACTER_GIF_VALIDATION_V0",
            "status": "error",
            "message": str(exc),
        }, indent=2))
        return 2

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
