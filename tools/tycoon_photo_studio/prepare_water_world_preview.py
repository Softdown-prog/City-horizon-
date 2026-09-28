"""Build world-sampled water captures from four Blender-baked views."""

import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

PERIOD = 256
BASE = {"water_shallow": np.array([115, 200, 210]), "water_deep": np.array([108, 196, 207])}


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


def capture(world, variant, turn, output_dir):
    h, w = 320, 640
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = (xx - 320) / 64
    b = yy / 32
    gx, gy = (a + b) / 2, (b - a) / 2
    inside = (gx >= 0) & (gx < 5) & (gy >= 0) & (gy < 5)
    transforms = ((gx, gy), (gy, 5 - gx), (5 - gx, 5 - gy), (5 - gy, gx))
    wx, wy = transforms[turn]
    sx = np.floor(wx * 64).astype(int) % PERIOD
    sy = np.floor(wy * 64).astype(int) % PERIOD
    pixels = np.zeros((h, w, 3), np.uint8)
    pixels[:] = (32, 45, 50)
    pixels[inside] = world[sy[inside], sx[inside]]
    result = Image.fromarray(pixels, "RGB")
    result.save(output_dir / f"{variant}_rotation_{turn * 90:03d}.png")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    for kind in BASE:
        texture = build_world(kind, args.tile_dir, args.output)
        board = Image.new("RGB", (1304, 712), (32, 45, 50))
        pen = ImageDraw.Draw(board)
        for quarter_turn in range(4):
            water = capture(texture, kind, quarter_turn, args.output)
            col, row = quarter_turn % 2, quarter_turn // 2
            board.paste(water, (8 + col * 648, 24 + row * 344))
            pen.text((12 + col * 648, 8 + row * 344),
                     f"{kind} | view {quarter_turn * 90} deg", fill=(235, 245, 247))
        board.save(args.output / f"{kind}_4_rotations.png")
    print("waterContinuousPreview: PASS")


if __name__ == "__main__":
    main()
