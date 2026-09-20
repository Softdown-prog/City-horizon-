"""Author the first connected ground-path family.

The grid topology is deliberately identical to RoadManager/SidewalkManager:
N=1, E=2, S=4 and W=8.  Those directions are the four shared *sides* of a
2:1 isometric diamond, so a line painted in either screen diagonal continues
through its neighbour without inventing a separate diagonal grid rule.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

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
    ImageDraw.Draw(alpha).polygon(((NW//2, 0), (NW, NH//2), (NW//2, NH), (0, NH//2)), fill=255)
    return alpha

def dirt_surface(mask: int) -> Image.Image:
    # Coarse, low-contrast grains survive the 4x downsample as old tycoon
    # terrain, rather than as salt-and-pepper noise.
    seed = int.from_bytes(hashlib.sha256(f"CH_DIRT_PATH_V1:{mask}".encode()).digest()[:8], "big")
    import random
    rng = random.Random(seed)
    base = Image.new("RGB", (NW, NH), (129, 91, 51))
    d = ImageDraw.Draw(base)
    for _ in range(340):
        x, y = rng.randrange(NW), rng.randrange(NH)
        r = rng.randrange(3, 16)
        c = rng.choice(((111, 75, 42), (146, 105, 62), (157, 117, 69), (122, 84, 47)))
        d.ellipse((x-r, y-r//2, x+r, y+r//2), fill=c)
    return base.filter(ImageFilter.GaussianBlur(SS * 1.4)).convert("RGBA")

def render(mask: int) -> Image.Image:
    alpha = diamond()
    image = dirt_surface(mask)
    # Subtle compacted wear tells the topology apart, but does not make a
    # corridor: every tile remains a walkable dirt surface.
    wear = Image.new("RGBA", (NW, NH), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wear)
    active = [bit for bit in (N, E, S, WEST) if mask & bit]
    for bit in active:
        px, py = PORTS[bit]
        draw.line((CENTER, (px, py)), fill=(85, 57, 34, 45), width=13 * SS)
        draw.line((CENTER, (px, py)), fill=(181, 137, 79, 42), width=5 * SS)
    wear = wear.filter(ImageFilter.GaussianBlur(SS * 2.4))
    image = Image.alpha_composite(image, wear)
    image.putalpha(alpha)
    return image.resize((W, H), Image.Resampling.LANCZOS)

def preview(tiles: dict[int, Image.Image], path: Path) -> None:
    canvas = Image.new("RGBA", (768, 384), (87, 126, 62, 255))
    origin = (192, 48)
    def at(x: int, y: int) -> tuple[int, int]:
        return origin[0] + (x-y)*64 - 64, origin[1] + (x+y)*32
    # two diagonals, a corner, a T and a cross exercise all connection styles
    layout = [(0,0,5),(0,-1,5),(0,-2,5),(3,0,10),(4,0,10),(2,3,3),(4,3,7),(6,3,15)]
    for x, y, m in layout: canvas.alpha_composite(tiles[m], at(x,y))
    canvas.save(path)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("assets/terrain/paths/dirt_01"))
    parser.add_argument("--preview", type=Path, default=Path("work/dirt_path_autotile_preview.png"))
    args = parser.parse_args(); args.output_dir.mkdir(parents=True, exist_ok=True); args.preview.parent.mkdir(parents=True, exist_ok=True)
    tiles = {mask: render(mask) for mask in range(16)}
    for mask, tile in tiles.items(): tile.save(args.output_dir / NAMES[mask])
    preview(tiles, args.preview)

if __name__ == "__main__": main()
