#!/usr/bin/env python3
"""SOUTH-only 2D procedural prototype for the City Horizon park ticket booth.

The runtime target remains a transparent PNG. This prototype intentionally uses
no Blender/3D source and exists only for visual review before four-view authoring.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

TILE_W = 128.0
TILE_H = 64.0
FINAL_SIZE = 512
SS = 3


def iso(x: float, y: float, z: float) -> tuple[float, float]:
    cx = FINAL_SIZE * SS * 0.50
    gy = FINAL_SIZE * SS * 0.79
    return (
        cx + (x - y) * (TILE_W * 0.5 * SS),
        gy + (x + y) * (TILE_H * 0.5 * SS) - z * SS,
    )


def arch_points(cx: float, rx: float, spring: float, rz: float, y: float, steps: int = 24):
    points = []
    for i in range(steps + 1):
        a = math.pi - math.pi * i / steps
        points.append((cx + rx * math.cos(a), y, spring + rz * math.sin(a)))
    return points


def star_points(cx: float, cy: float, outer: float, inner: float):
    result = []
    for i in range(10):
        radius = outer if i % 2 == 0 else inner
        angle = -math.pi / 2 + i * math.pi / 5
        result.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return result


def render() -> Image.Image:
    image = Image.new("RGBA", (FINAL_SIZE * SS, FINAL_SIZE * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image, "RGBA")

    def poly(points, fill, outline=None, width=1):
        xy = [iso(*p) for p in points]
        draw.polygon(xy, fill=fill)
        if outline is not None:
            draw.line(xy + [xy[0]], fill=outline, width=width * SS, joint="curve")

    def line(a, b, fill, width=1):
        draw.line([iso(*a), iso(*b)], fill=fill, width=width * SS)

    def front_rect(x0, x1, z0, z1, fill, outline=None, y=1.02):
        poly([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], fill, outline)

    # Reference palette.
    wall_front = (232, 219, 190, 255)
    wall_side = (207, 190, 160, 255)
    outline = (82, 68, 58, 220)
    stone = (190, 158, 120, 255)
    stone_light = (220, 196, 158, 255)
    roof_front = (199, 63, 49, 255)
    roof_side = (166, 48, 40, 255)
    roof_line = (109, 37, 33, 210)
    green = (44, 123, 50, 255)
    cream = (247, 235, 209, 255)
    blue = (48, 91, 145, 255)
    gold = (227, 166, 48, 255)
    wood = (175, 112, 43, 255)
    recess = (45, 35, 33, 255)
    red = (211, 65, 48, 255)
    white = (246, 232, 208, 255)

    h = 84.0
    roof_h = 48.0

    # 2x2 building body: no ground, queue, fences, plants, posts or lanterns.
    poly([(1, -1, 0), (1, 1, 0), (1, 1, h), (1, -1, h)], wall_side, outline)
    poly([(-1, 1, 0), (1, 1, 0), (1, 1, h), (-1, 1, h)], wall_front, outline)

    front_rect(-1, 1, 0, 9, stone, outline)
    for row in range(4):
        z0 = 12 + row * 16
        z1 = z0 + 10
        front_rect(-1.01, -0.84, z0, z1, stone_light if row % 2 == 0 else stone, outline)
        front_rect(0.84, 1.01, z0, z1, stone if row % 2 == 0 else stone_light, outline)

    # Ticket window and wooden counter.
    front_rect(-0.74, -0.13, 22, 58, recess, outline)
    front_rect(-0.74, -0.67, 22, 58, blue, outline, 1.03)
    front_rect(-0.20, -0.13, 22, 58, blue, outline, 1.03)
    front_rect(-0.79, -0.08, 18, 24, wood, outline, 1.04)
    front_rect(-0.37, -0.24, 25, 33, cream, (132, 98, 55, 255), 1.05)

    # Red/cream awning projecting from the south facade.
    ax0, ax1 = -0.81, -0.05
    for i in range(5):
        x0 = ax0 + (ax1 - ax0) * i / 5
        x1 = ax0 + (ax1 - ax0) * (i + 1) / 5
        fill = red if i % 2 == 0 else white
        poly([(x0, 1.02, 63), (x1, 1.02, 63), (x1, 1.31, 55), (x0, 1.31, 55)], fill, outline)

    # Large arched ride entrance.
    center = 0.48
    outer = [(center - 0.42, 1.025, 8), (center - 0.42, 1.025, 48)]
    outer += arch_points(center, 0.42, 48, 24, 1.025)
    outer += [(center + 0.42, 1.025, 8)]
    poly(outer, cream, outline)

    inner = [(center - 0.31, 1.04, 8), (center - 0.31, 1.04, 46)]
    inner += arch_points(center, 0.31, 46, 18, 1.04)
    inner += [(center + 0.31, 1.04, 8)]
    poly(inner, recess, (57, 45, 41, 255))
    front_rect(center - 0.065, center + 0.065, 67.5, 75, red, (116, 48, 42, 230), 1.05)

    # Pyramid roof with restrained procedural tile rows and green eave trim.
    oh = 1.12
    apex = (0.0, 0.0, h + roof_h)
    poly([(oh, -oh, h), (oh, oh, h), apex], roof_side, roof_line)
    poly([(-oh, oh, h), (oh, oh, h), apex], roof_front, roof_line)
    for t in (0.18, 0.36, 0.54, 0.72, 0.88):
        line((-oh * (1-t), oh * (1-t), h + roof_h*t), (oh * (1-t), oh * (1-t), h + roof_h*t), (123, 40, 34, 175))
        line((oh * (1-t), -oh * (1-t), h + roof_h*t), (oh * (1-t), oh * (1-t), h + roof_h*t), (104, 35, 31, 155))
    line((-oh, oh, h), apex, roof_line)
    line((oh, oh, h), apex, roof_line)
    line((oh, -oh, h), apex, roof_line)
    line((-oh, oh, h-1.5), (oh, oh, h-1.5), green, 4)
    line((oh, -oh, h-1.5), (oh, oh, h-1.5), (37, 98, 42, 255), 4)

    # Integral front crest above the arch.
    py = 1.06
    plaque = [
        (0.18, py, 76), (0.77, py, 76), (0.77, py, 88), (0.67, py, 88),
        (0.62, py, 96), (0.48, py, 102), (0.34, py, 96), (0.29, py, 88), (0.18, py, 88),
    ]
    poly(plaque, cream, outline)
    inset = [
        (0.23, py+0.01, 80), (0.72, py+0.01, 80), (0.72, py+0.01, 86), (0.61, py+0.01, 86),
        (0.57, py+0.01, 93), (0.48, py+0.01, 97), (0.39, py+0.01, 93), (0.35, py+0.01, 86), (0.23, py+0.01, 86),
    ]
    poly(inset, blue, (42, 70, 104, 230))
    sx, sy = iso(0.48, py+0.02, 89)
    draw.polygon(star_points(sx, sy, 8.5*SS, 3.8*SS), fill=gold, outline=(143, 101, 35, 255))

    # Roof cap and golden flag stay; they are part of the approved building silhouette.
    cap_z = h + roof_h
    poly([(-0.12, -0.12, cap_z-2), (0.12, -0.12, cap_z-2), (0.12, 0.12, cap_z-2), (-0.12, 0.12, cap_z-2)], cream, outline)
    pole_base = iso(0, 0, cap_z+1)
    pole_top = (pole_base[0], pole_base[1] - 31*SS)
    draw.line([pole_base, pole_top], fill=gold, width=3*SS)
    rr = 3.4*SS
    draw.ellipse((pole_top[0]-rr, pole_top[1]-rr, pole_top[0]+rr, pole_top[1]+rr), fill=(239, 181, 57, 255), outline=(147, 102, 30, 255), width=SS)
    fx, fy = pole_top[0] + 2*SS, pole_top[1] + 4*SS
    draw.polygon([
        (fx, fy), (fx+19*SS, fy+2*SS), (fx+31*SS, fy+8*SS),
        (fx+22*SS, fy+13*SS), (fx+8*SS, fy+11*SS), (fx, fy+9*SS),
    ], fill=gold, outline=(151, 104, 31, 255))

    return image.resize((FINAL_SIZE, FINAL_SIZE), Image.Resampling.LANCZOS)


def review_image(sprite: Image.Image) -> Image.Image:
    review = Image.new("RGBA", (640, 640), (25, 28, 32, 255))
    glow_mask = Image.new("L", review.size, 0)
    gd = ImageDraw.Draw(glow_mask)
    gd.ellipse((70, 55, 570, 575), fill=92)
    glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(90))
    glow = Image.new("RGBA", review.size, (255, 255, 255, 0))
    glow.putalpha(glow_mask)
    review = Image.alpha_composite(review, glow)
    review.alpha_composite(sprite, (64, 64))
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    sprite = render()
    sprite_path = out / "park_ticket_booth_2d_south.png"
    review_path = out / "park_ticket_booth_2d_review.png"
    manifest_path = out / "park_ticket_booth_2d_manifest.json"
    sprite.save(sprite_path)
    review_image(sprite).save(review_path)

    manifest = {
        "contract": "CH_TICKET_BOOTH_2D_PROTOTYPE_V1",
        "status": "prototype_review_only",
        "assetId": "park.ticket_booth.2d.prototype",
        "projection": "CH_CAMERA_V1_orthographic_dimetric_2_to_1",
        "tileReference": [128, 64],
        "direction": "south",
        "frameResolution": [512, 512],
        "transparentCanvas": True,
        "backgroundIncluded": False,
        "footprint": {"widthTiles": 2, "depthTiles": 2},
        "content": ["building", "roof", "flag", "ticket_window", "awning", "arched_entry", "front_crest"],
        "excluded": ["ground", "plants", "fences", "queue_rails", "posts", "lanterns", "adjacent_decor"],
        "alphaBounds": list(sprite.getchannel("A").getbbox() or (0, 0, 512, 512)),
        "runtimeApproved": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(sprite_path)
    print(review_path)
    print(manifest_path)


if __name__ == "__main__":
    main()
