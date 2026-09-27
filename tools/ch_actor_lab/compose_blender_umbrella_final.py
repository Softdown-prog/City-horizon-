"""Build a reviewable 36-frame white/striped umbrella pack from one CH Blender final job.

Input: canopy, fabric mask and accent mask for S/E/W/N from the same final job.
Output: 48x64 overlays/masks in a staging directory, never runtime assets.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from build_umbrella_overlays import FRAME_DIR, recolor
from compose_blender_umbrella_study import fit_canopy, overlay_for_pose


DIRECTIONS = {"s": "south", "e": "east", "w": "west", "n": "north"}
REVIEW_COLORS = {"s": (208, 79, 77), "e": (225, 181, 66),
                 "w": (119, 102, 172), "n": (89, 164, 114)}


def build(final_dir: Path, output: Path) -> None:
    passes = {}
    for code, name in DIRECTIONS.items():
        images = [Image.open(final_dir / f"{stem}_{name}.png").convert("RGBA")
                  for stem in ("canopy", "fabric_mask", "accent_mask")]
        passes[code] = fit_canopy(*images)
    frames = sorted(FRAME_DIR.glob("*.png"))
    if len(frames) != 36 or any(frame.stem[0] not in DIRECTIONS for frame in frames):
        raise ValueError("Expected 36 approved actor poses across S/E/W/N")
    (output / "frames").mkdir(parents=True, exist_ok=True)
    (output / "masks").mkdir(parents=True, exist_ok=True)
    board = Image.new("RGBA", (4 * 150, 3 * 200), (67, 91, 52, 255))
    painter = ImageDraw.Draw(board)
    for path in frames:
        actor = Image.open(path).convert("RGBA")
        if actor.size != (48, 64):
            raise ValueError(f"Unexpected actor size: {path}")
        code = path.stem[0]
        overlay, mask = overlay_for_pose(actor, *passes[code], code)
        selected = [(x, y) for y in range(64) for x in range(48)
                    if mask.getpixel((x, y))[0] == 255]
        if len(selected) < 50 or any(mask.getpixel((x, y))[3] !=
                                     overlay.getpixel((x, y))[3] for x, y in selected):
            raise ValueError(f"Misaligned color mask for {path.name}")
        overlay.save(output / "frames" / path.name)
        mask.save(output / "masks" / path.name)
        if path.stem[2:] not in ("idle", "walk_02", "walk_06"):
            continue
        col = list(DIRECTIONS).index(code)
        row = ("idle", "walk_02", "walk_06").index(path.stem[2:])
        preview = Image.alpha_composite(actor, recolor(overlay, mask, REVIEW_COLORS[code]))
        board.alpha_composite(preview.resize((144, 192), Image.Resampling.NEAREST),
                              (col * 150, row * 200 + 8))
        painter.text((col * 150 + 2, row * 200 + 1), path.stem, fill="white")
    board.convert("RGB").save(output / "four_directions.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.final_dir, args.output)
    print(f"Staged 36 CH Blender umbrella overlays/masks: {args.output}")


if __name__ == "__main__":
    main()
