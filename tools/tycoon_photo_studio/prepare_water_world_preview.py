"""Build world-sampled water captures from four Blender-baked views."""

import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PERIOD = 256
BASE = {"water_shallow": np.array([115, 200, 210]), "water_deep": np.array([80, 163, 194])}


def source_square(path):
    src = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)
    yy, xx = np.mgrid[0:128, 0:128].astype(np.float32)
    u = .035 + (xx + .5) / 128 * .93
    v = .035 + (yy + .5) / 128 * .93
    x = np.clip(63.5 + (u - v) * 63.5, 0, 127)
    y = np.clip((u + v) * 31.5, 0, 63)
    x0, y0 = x.astype(int), y.astype(int)
    x1, y1 = np.minimum(x0 + 1, 127), np.minimum(y0 + 1, 63)
    tx, ty = (x - x0)[..., None], (y - y0)[..., None]
    a = src[y0, x0] * (1 - tx) + src[y0, x1] * tx
    b = src[y1, x0] * (1 - tx) + src[y1, x1] * tx
    return (a * (1 - ty) + b * ty)[..., :3]


def build_world(variant, tile_dir, output_dir):
    names = ("00", "10", "01", "11")
    sources = [source_square(tile_dir / f"{variant}_{name}.png") for name in names]
    yy, xx = np.mgrid[0:PERIOD, 0:PERIOD]
    weights = [.4, .25, .2, .15]
    detail = np.zeros((PERIOD, PERIOD, 3), np.float32)
    for source, shift, weight in zip(sources, [(0, 0), (53, 97), (113, 31), (181, 157)], weights):
        sx = (xx + shift[0]) % PERIOD
        sy = (yy + shift[1]) % PERIOD
        sx = np.where(sx < 128, sx, 255 - sx)
        sy = np.where(sy < 128, sy, 255 - sy)
        detail += weight * (source[sy, sx] - source.mean(axis=(0, 1)))
    world = np.clip(BASE[variant] + detail * 1.6, 0, 255).astype(np.uint8)
    Image.fromarray(world, "RGB").save(output_dir / f"{variant}_world.png")
    return world


def capture(world, variant, turn, output_dir, glint=None, phase=0.0):
    h, w = 320, 640
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = (xx - 320) / 64
    b = yy / 32
    gx, gy = (a + b) / 2, (b - a) / 2
    transforms = ((gx, gy), (gy, 5 - gx), (5 - gx, 5 - gy), (5 - gy, gx))
    wx, wy = transforms[turn]
    sx = np.floor(wx * 64).astype(int) % PERIOD
    sy = np.floor(wy * 64).astype(int) % PERIOD
    pixels = world[sy, sx].copy()
    if glint is not None:
        shifted_x = (sx + round(5 * np.sin(phase))) % PERIOD
        shifted_y = (sy + round(5 * np.cos(phase))) % PERIOD
        alpha = glint[shifted_y, shifted_x][..., None] / 255.0
        pixels = np.clip(pixels * (1 - alpha) + np.array([220, 245, 249]) * alpha, 0, 255).astype(np.uint8)
    # Supersample just the outer water boundary; do not blur the interior art.
    silhouette = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(silhouette).polygon([(w * 2, 0), (w * 4 - 1, h * 2),
                                        (w * 2, h * 4 - 1), (0, h * 2)], fill=255)
    silhouette = silhouette.resize((w, h), Image.Resampling.LANCZOS)
    result = Image.composite(Image.fromarray(pixels, "RGB"),
                             Image.new("RGB", (w, h), (32, 45, 50)), silhouette)
    if glint is None:
        result.save(output_dir / f"{variant}_rotation_{turn * 90:03d}.png")
    return result


def build_glint(world, output_dir, variant):
    # A light-only overlay. The water colour remains entirely in the base.
    luma = (world.astype(np.float32) * np.array([.22, .68, .10])).sum(axis=2)
    # Blur a tiled copy so the highlight remains periodic at texture boundaries.
    repeated = np.tile(luma.astype(np.uint8), (3, 3))
    soft_full = np.asarray(Image.fromarray(repeated).filter(ImageFilter.GaussianBlur(8)), dtype=np.float32)
    soft = soft_full[PERIOD:2 * PERIOD, PERIOD:2 * PERIOD]
    light = np.clip((luma - soft - 1.2) * 2.5, 0, 44).astype(np.uint8)
    rgba = np.empty((PERIOD, PERIOD, 4), dtype=np.uint8)
    rgba[:, :, :3] = (220, 245, 249)
    rgba[:, :, 3] = light
    Image.fromarray(rgba, "RGBA").save(output_dir / f"{variant}_glint_overlay.png")
    return light


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    for kind in BASE:
        texture = build_world(kind, args.tile_dir, args.output)
        glint = build_glint(texture, args.output, kind)
        board = Image.new("RGB", (1304, 712), (32, 45, 50))
        pen = ImageDraw.Draw(board)
        for quarter_turn in range(4):
            water = capture(texture, kind, quarter_turn, args.output)
            col, row = quarter_turn % 2, quarter_turn // 2
            board.paste(water, (8 + col * 648, 24 + row * 344))
            pen.text((12 + col * 648, 8 + row * 344),
                     f"{kind} | view {quarter_turn * 90} deg", fill=(235, 245, 247))
        board.save(args.output / f"{kind}_4_rotations.png")
        frames = [capture(texture, kind, 0, args.output, glint, 2 * np.pi * step / 16)
                  for step in range(16)]
        frames[0].save(args.output / f"{kind}_motion_preview.gif", save_all=True,
                       append_images=frames[1:], duration=125, loop=0, optimize=True)
    print("waterContinuousPreview: PASS")


if __name__ == "__main__":
    main()
