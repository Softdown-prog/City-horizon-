"""Promote approved continuous water and its subtle palette-cycled glint atlas.

Usage: python tools/tycoon_photo_studio/promote_water_surface.py \
  --continuous out/water/continuous --output assets/terrain/water
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image

KINDS = ("water_shallow", "water_deep")
SIZE = 256
FRAMES = 16
DURATION_MS = 125
GUTTER = 1
STRIDE = SIZE + 2 * GUTTER
GLINT_RGB = (220, 245, 249)
# The four palette positions vary only the highlight alpha, by at most 3/255.
PALETTE_DELTA = (-3, 0, 3, 0)


def palette_tables():
    tables = []
    for cycle in range(4):
        entries = []
        for base_alpha in range(64):
            for phase in range(4):
                alpha = 0 if base_alpha == 0 else min(255, max(1, base_alpha + PALETTE_DELTA[(phase + cycle) % 4]))
                entries.append([*GLINT_RGB, alpha])
        tables.append(entries)
    return tables


def put_wrapped_frame(atlas, frame, column, row):
    x = column * STRIDE
    y = row * STRIDE
    padded = np.pad(frame, ((GUTTER, GUTTER), (GUTTER, GUTTER), (0, 0)), mode="wrap")
    atlas[y:y + STRIDE, x:x + STRIDE] = padded


def promote(kind, continuous, output, tables):
    base_source = continuous / f"{kind}_world.png"
    glint_source = continuous / f"{kind}_glint_overlay.png"
    base = Image.open(base_source).convert("RGB")
    glint = np.asarray(Image.open(glint_source).convert("RGBA"))
    if base.size != (SIZE, SIZE) or glint.shape != (SIZE, SIZE, 4):
        raise ValueError(f"{kind}: expected 256x256 base and overlay")
    alpha = glint[:, :, 3].astype(np.uint16)
    if int(alpha.max()) > 63:
        raise ValueError(f"{kind}: overlay alpha exceeds the 6-bit palette range")

    # Each 8-bit index holds the original opacity (six bits) and local phase
    # (two bits). Palette cycling leaves the approved base and glint positions intact.
    phase = ((alpha // 6) % 4).astype(np.uint8)
    indices = (alpha * 4 + phase).astype(np.uint8)
    Image.fromarray(indices, "L").save(output / f"{kind}_glint_indices.png")
    shutil.copyfile(base_source, output / base_source.name)
    shutil.copyfile(glint_source, output / glint_source.name)

    atlas = np.zeros((STRIDE * 4, STRIDE * 4, 4), dtype=np.uint8)
    for frame in range(FRAMES):
        angle = 2 * np.pi * frame / FRAMES
        dx = round(5 * np.sin(angle))
        dy = round(5 * np.cos(angle))
        moved = np.roll(indices, shift=(-dy, -dx), axis=(0, 1))
        rgba = np.asarray(tables[frame // 4], dtype=np.uint8)[moved]
        put_wrapped_frame(atlas, rgba, frame % 4, frame // 4)
    Image.fromarray(atlas, "RGBA").save(output / f"{kind}_glint_cycle_atlas.png")

    return {
        "base": f"assets/terrain/water/{kind}_world.png",
        "originalOverlay": f"assets/terrain/water/{kind}_glint_overlay.png",
        "indexedOverlay": f"assets/terrain/water/{kind}_glint_indices.png",
        "rgbaFrameAtlas": f"assets/terrain/water/{kind}_glint_cycle_atlas.png",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--continuous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tables = palette_tables()
    surfaces = {kind: promote(kind, args.continuous, args.output, tables) for kind in KINDS}
    manifest = {
        "contract": "CH_WATER_SURFACE_V1",
        "projection": "CH_CAMERA_V1",
        "textureSize": [SIZE, SIZE],
        "worldPeriodTiles": 4,
        "layers": ["base", "rgbaFrameAtlas"],
        "animation": {
            "technique": "subtle-palette-cycle-plus-original-glint-drift",
            "frameCount": FRAMES,
            "frameDurationMs": DURATION_MS,
            "atlasColumns": 4,
            "atlasRows": 4,
            "frameSize": [SIZE, SIZE],
            "gutterPx": GUTTER,
            "stridePx": STRIDE,
            "frameOrder": "row-major",
            "paletteIndexEncoding": "original alpha (6 high bits), phase (2 low bits)",
            "paletteRGBA": tables,
        },
        "surfaces": surfaces,
    }
    (args.output / "water_surfaces.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
