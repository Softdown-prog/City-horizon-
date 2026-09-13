"""Derive deterministic Water V2 base and continuous-caustic pilot assets.

This tool never changes the approved master.  The bases are opaque colour
swatches sampled from it; the overlays retain only high-frequency caustic
light, mapped into a large world-period texture rather than a diamond tile.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageFilter


MASTER_NAME = "water_surface_v2_master.png"
BASE_DEEP_NAME = "water_base_deep.png"
BASE_SHALLOW_NAME = "water_base_shallow.png"
OVERLAY_NAMES = tuple(f"water_caustics_overlay_{index:02d}.png" for index in range(1, 5))
OVERLAY_SIZE = (1024, 512)


def clamp(value: float) -> int:
    return max(0, min(255, round(value)))


def sample_rgba(image: Image.Image, x: float, y: float) -> tuple[int, int, int, int]:
    x = max(0.0, min(image.width - 1.0, x))
    y = max(0.0, min(image.height - 1.0, y))
    x0, y0 = int(x), int(y)
    x1, y1 = min(x0 + 1, image.width - 1), min(y0 + 1, image.height - 1)
    tx, ty = x - x0, y - y0
    a = image.getpixel((x0, y0))
    b = image.getpixel((x1, y0))
    c = image.getpixel((x0, y1))
    d = image.getpixel((x1, y1))
    return tuple(clamp(
        a[channel] * (1.0 - tx) * (1.0 - ty) +
        b[channel] * tx * (1.0 - ty) +
        c[channel] * (1.0 - tx) * ty +
        d[channel] * tx * ty
    ) for channel in range(4))


def master_colour_stats(master: Image.Image) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    pixels = [pixel for pixel in master.getdata() if pixel[3] >= 250]
    if not pixels:
        raise ValueError("approved master has no opaque pixels")
    deep = tuple(clamp(sum(pixel[channel] for pixel in pixels) / len(pixels)) for channel in range(3))
    # Shallow is not new art: it is sampled from the bright half of this same
    # approved image, preserving its palette while giving shore systems a
    # lighter material token for later use.
    ranked = sorted(pixels, key=lambda pixel: pixel[0] * 0.2126 + pixel[1] * 0.7152 + pixel[2] * 0.0722)
    bright = ranked[len(ranked) // 2 :]
    shallow = tuple(clamp(sum(pixel[channel] for pixel in bright) / len(bright)) for channel in range(3))
    return deep, shallow


def write_opaque_base(path: Path, colour: tuple[int, int, int]) -> None:
    # This is deliberately a fully opaque rectangular colour token.  Actual
    # world coverage is the renderer's proven diamond geometry, not PNG alpha.
    Image.new("RGBA", (128, 64), (*colour, 255)).save(path)


def make_overlay(master: Image.Image, phase_x: float, phase_y: float) -> Image.Image:
    rgba = master.convert("RGBA")
    blurred = rgba.filter(ImageFilter.GaussianBlur(radius=3.0))
    out = Image.new("RGBA", OVERLAY_SIZE, (0, 0, 0, 0))
    output = out.load()

    # Source uv describes the approved isometric diamond.  Mapping it once
    # across a 16x16 logical-world period gives adjacent cells shared UVs;
    # this no longer resets one master image per 128x64 cell.
    for oy in range(OVERLAY_SIZE[1]):
        v = ((oy + phase_y) % OVERLAY_SIZE[1]) / OVERLAY_SIZE[1]
        for ox in range(OVERLAY_SIZE[0]):
            u = ((ox + phase_x) % OVERLAY_SIZE[0]) / OVERLAY_SIZE[0]
            sx = (u - v) * (rgba.width - 1) * 0.5 + (rgba.width - 1) * 0.5
            sy = (u + v) * (rgba.height - 1) * 0.5
            red, green, blue, alpha = sample_rgba(rgba, sx, sy)
            br, bg, bb, _ = sample_rgba(blurred, sx, sy)
            if alpha < 240:
                continue
            # Only positive high-frequency luminance survives.  This drops the
            # master tile's dark alpha edge and leaves cyan/white caustic light.
            detail = max(0.0, (red + green + blue - br - bg - bb) / 3.0)
            if detail < 4.0:
                continue
            # Keep the derived overlay intentionally restrained: it conveys
            # moving light without turning the low-resolution reference into
            # large stamped shapes at the 16-cell world period.
            opacity = clamp(min(48.0, detail * 1.6))
            output[ox, oy] = (clamp(150 + detail * 2.4), clamp(215 + detail * 1.1), 235, opacity)

    # Match opposite one-pixel edges so SDL linear sampling at the periodic
    # boundary cannot inject a new seam.
    for y in range(OVERLAY_SIZE[1]):
        blended = tuple((output[0, y][channel] + output[OVERLAY_SIZE[0] - 1, y][channel]) // 2 for channel in range(4))
        output[0, y] = blended
        output[OVERLAY_SIZE[0] - 1, y] = blended
    for x in range(OVERLAY_SIZE[0]):
        blended = tuple((output[x, 0][channel] + output[x, OVERLAY_SIZE[1] - 1][channel]) // 2 for channel in range(4))
        output[x, 0] = blended
        output[x, OVERLAY_SIZE[1] - 1] = blended
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("asset_root", type=Path, help="runtime root containing assets/")
    args = parser.parse_args()
    coast = args.asset_root / "assets" / "terrain" / "coast_adjusted"
    master_path = coast / MASTER_NAME
    if not master_path.is_file():
        raise FileNotFoundError(master_path)
    master = Image.open(master_path).convert("RGBA")
    if master.size != (170, 85):
        raise ValueError(f"master contract is 170x85, got {master.size}")

    deep, shallow = master_colour_stats(master)
    write_opaque_base(coast / BASE_DEEP_NAME, deep)
    write_opaque_base(coast / BASE_SHALLOW_NAME, shallow)
    phases = ((0, 0), (173, 71), (347, 143), (521, 215))
    for name, (phase_x, phase_y) in zip(OVERLAY_NAMES, phases, strict=True):
        make_overlay(master, phase_x, phase_y).save(coast / name)

    manifest = {
        "contract": "WATER_V2_LAYER_PILOT",
        "status": "CH_WATER_V2_PILOT_APPROVED",
        "master": MASTER_NAME,
        "base": {"deep": {"file": BASE_DEEP_NAME, "rgb": deep}, "shallow": {"file": BASE_SHALLOW_NAME, "rgb": shallow}},
        "overlays": [{"file": name, "size": OVERLAY_SIZE, "world_period": 16} for name in OVERLAY_NAMES],
        "note": "Derived deterministically from the approved master; master not modified.",
    }
    (coast / "water_layers_v2_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
