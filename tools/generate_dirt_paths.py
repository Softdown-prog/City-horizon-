"""Author connected dirt-path tiles with a richer tycoon-like material.

Topology remains identical to RoadManager/SidewalkManager:
N=1, E=2, S=4 and W=8.  The visual authoring step is deliberately
separate from topology: the mask defines connectivity while this generator
defines a reusable soil material with macro, meso and micro variation.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, SS = 128, 64, 4
NW, NH = W * SS, H * SS
N, E, S, WEST = 1, 2, 4, 8
PORTS = {N: (96 * SS, 16 * SS), E: (96 * SS, 48 * SS), S: (32 * SS, 48 * SS), WEST: (32 * SS, 16 * SS)}
CENTER = (64 * SS, 32 * SS)
NAMES = (
    "dirt_path_00_isolated.png", "dirt_path_01_end_n.png", "dirt_path_02_end_e.png", "dirt_path_03_curve_ne.png",
    "dirt_path_04_end_s.png", "dirt_path_05_straight_ns.png", "dirt_path_06_curve_es.png", "dirt_path_07_tee_no_w.png",
    "dirt_path_08_end_w.png", "dirt_path_09_curve_nw.png", "dirt_path_10_straight_ew.png", "dirt_path_11_tee_no_s.png",
    "dirt_path_12_curve_sw.png", "dirt_path_13_tee_no_e.png", "dirt_path_14_tee_no_n.png", "dirt_path_15_cross.png",
)


def diamond() -> Image.Image:
    alpha = Image.new("L", (NW, NH), 0)
    ImageDraw.Draw(alpha).polygon(((NW // 2, 0), (NW, NH // 2), (NW // 2, NH), (0, NH // 2)), fill=255)
    return alpha


def display_diamond() -> Image.Image:
    """Keep the final shared edge hard so connected tiles do not reveal grass hairlines."""
    alpha = Image.new("L", (W, H), 0)
    ImageDraw.Draw(alpha).polygon(((W // 2, 0), (W - 1, H // 2), (W // 2, H - 1), (0, H // 2)), fill=255)
    return alpha


def _seed(tag: str) -> int:
    return int.from_bytes(hashlib.sha256(tag.encode("utf-8")).digest()[:8], "big")


def _multiscale_noise() -> Image.Image:
    """Build tileable-looking soil value variation at three spatial scales."""
    rng = random.Random(_seed("CH_DIRT_PATH_V2:noise"))
    out = Image.new("L", (NW, NH), 128)
    for scale, amount in ((16, 46), (32, 30), (64, 18)):
        sw = max(2, NW // scale)
        sh = max(2, NH // scale)
        src = Image.new("L", (sw, sh))
        px = src.load()
        for y in range(sh):
            for x in range(sw):
                px[x, y] = rng.randrange(0, 256)
        layer = src.resize((NW, NH), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(scale * 0.12))
        out = ImageChops.add(out, layer.point(lambda v, a=amount: int((v - 128) * a / 128 + 128)), scale=2.0, offset=-64)
    return out.filter(ImageFilter.GaussianBlur(SS * 0.7))


def dirt_surface() -> Image.Image:
    """Create one shared material domain with macro/meso/micro soil structure."""
    rng = random.Random(_seed("CH_DIRT_PATH_V2:surface"))
    noise = _multiscale_noise()
    base = Image.new("RGBA", (NW, NH), (128, 90, 50, 255))
    bp = base.load()
    np = noise.load()
    for y in range(NH):
        for x in range(NW):
            n = np[x, y] - 128
            # Warm compact earth palette.  Variation is low enough to remain
            # readable after 4x downsample, but no longer looks flat-painted.
            bp[x, y] = (
                max(72, min(177, 128 + n // 3)),
                max(49, min(135, 90 + n // 4)),
                max(31, min(92, 50 + n // 6)),
                255,
            )

    detail = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(detail)

    # Meso-scale compressed patches / shallow pits.
    for _ in range(95):
        x = rng.randrange(0, NW)
        y = rng.randrange(0, NH)
        rx = rng.randrange(6, 28) * SS // 2
        ry = max(2, rx // rng.randrange(2, 5))
        dark = rng.choice(((69, 47, 30, 28), (91, 58, 33, 34), (77, 50, 31, 24)))
        light = rng.choice(((178, 130, 76, 20), (160, 113, 66, 24)))
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=dark)
        draw.arc((x - rx, y - ry, x + rx, y + ry), 205, 338, fill=light, width=max(1, SS))

    # Small stones and hard grains.  A paired highlight/shadow produces
    # pre-rendered relief without requiring runtime normal mapping.
    for _ in range(155):
        x = rng.randrange(6 * SS, NW - 6 * SS)
        y = rng.randrange(4 * SS, NH - 4 * SS)
        rx = rng.randrange(1, 4) * SS
        ry = max(SS, rx // 2)
        stone = rng.choice(((111, 87, 60, 150), (143, 113, 77, 145), (88, 72, 52, 150), (160, 132, 91, 125)))
        draw.ellipse((x - rx + SS, y - ry + SS, x + rx + SS, y + ry + SS), fill=(50, 35, 24, 72))
        draw.ellipse((x - rx, y - ry, x + rx, y + ry), fill=stone)
        draw.arc((x - rx, y - ry, x + rx, y + ry), 185, 300, fill=(205, 170, 118, 130), width=max(1, SS))

    # Short cracks/scratches break up broad muddy patches.
    for _ in range(58):
        x = rng.randrange(8 * SS, NW - 8 * SS)
        y = rng.randrange(5 * SS, NH - 5 * SS)
        length = rng.randrange(3, 10) * SS
        angle = rng.uniform(-0.45, 0.45)
        x2 = x + int(math.cos(angle) * length)
        y2 = y + int(math.sin(angle) * length * 0.42)
        draw.line((x, y, x2, y2), fill=(58, 40, 27, rng.randrange(35, 70)), width=max(1, SS // 2))

    detail = detail.filter(ImageFilter.GaussianBlur(SS * 0.22))
    return Image.alpha_composite(base, detail)


def wear_overlay(mask: int) -> Image.Image:
    """Topology only: compacted traffic/wear follows active ports."""
    wear = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    active = [bit for bit in (N, E, S, WEST) if mask & bit]

    if not active:
        # Isolated path tile still gets a small compacted center patch.
        r = 16 * SS
        draw.ellipse((CENTER[0] - r, CENTER[1] - r // 2, CENTER[0] + r, CENTER[1] + r // 2), fill=(92, 59, 35, 34))
    else:
        for bit in active:
            px, py = PORTS[bit]
            draw.line((CENTER, (px, py)), fill=(77, 49, 31, 54), width=15 * SS)
            draw.line((CENTER, (px, py)), fill=(182, 133, 76, 28), width=6 * SS)

    return wear.filter(ImageFilter.GaussianBlur(SS * 2.0))


def render(mask: int) -> Image.Image:
    image = dirt_surface()
    image = Image.alpha_composite(image, wear_overlay(mask))
    image.putalpha(diamond())
    result = image.resize((W, H), Image.Resampling.LANCZOS)
    result.putalpha(display_diamond())
    return result


def preview(tiles: dict[int, Image.Image], path: Path) -> None:
    canvas = Image.new("RGBA", (896, 448), (87, 126, 62, 255))
    origin = (224, 54)

    def at(x: int, y: int) -> tuple[int, int]:
        return origin[0] + (x - y) * 64 - 64, origin[1] + (x + y) * 32

    layout = [
        (0, 0, 5), (0, -1, 5), (0, -2, 5),
        (3, 0, 10), (4, 0, 10), (5, 0, 10),
        (2, 3, 3), (4, 3, 7), (6, 3, 15),
        (2, 5, 1), (4, 5, 6), (6, 5, 14),
    ]
    for x, y, m in layout:
        canvas.alpha_composite(tiles[m], at(x, y))
    canvas.save(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terrain/paths/dirt_01"))
    parser.add_argument("--preview", type=Path, default=Path("work/dirt_path_autotile_preview.png"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.preview.parent.mkdir(parents=True, exist_ok=True)

    tiles = {mask: render(mask) for mask in range(16)}
    for mask, tile in tiles.items():
        tile.save(args.output_dir / NAMES[mask])
    preview(tiles, args.preview)


if __name__ == "__main__":
    main()
