"""Procedural 2D key-art renderer for City Horizon loading screens.

This deliberately avoids gameplay rendering and 3D asset language. It draws a
poster-like city illustration in layers (sky, distant skyline, boulevard,
foreground park, lights and atmosphere) and exports an ordinary PNG for SDL.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

CONTRACT = "CH_LOADING_SPLASH_ART_V1"
PROXY_RES = (1280, 720)
FINAL_RES = (2560, 1440)


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--final", action="store_true")
    return p.parse_args(argv)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp(top, bottom, t)
        for x in range(w):
            px[x, y] = c
    return img


def glow(base, center, radius, color, strength=210):
    w, h = base.size
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = center
    d.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*color, strength))
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.38))
    return Image.alpha_composite(base, layer)


def polygon(draw, pts, fill):
    draw.polygon([(int(x), int(y)) for x, y in pts], fill=fill)


def draw_clouds(img, rng, scale):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = img.size
    for i in range(9):
        cx = rng.randint(int(w * 0.05), int(w * 0.95))
        cy = rng.randint(int(h * 0.07), int(h * 0.34))
        rx = rng.randint(int(55 * scale), int(130 * scale))
        ry = rng.randint(int(12 * scale), int(28 * scale))
        alpha = rng.randint(22, 56)
        col = (255, 211, 190, alpha) if i < 4 else (183, 208, 220, alpha)
        d.ellipse((cx-rx, cy-ry, cx+rx, cy+ry), fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(int(18 * scale)))
    return Image.alpha_composite(img, layer)


def draw_distant_skyline(img, rng, scale, horizon):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w, h = img.size
    x = -20
    palette = [(71, 91, 114, 150), (75, 104, 124, 150), (86, 102, 125, 142), (62, 86, 111, 150)]
    idx = 0
    while x < w + 20:
        bw = rng.randint(int(32*scale), int(70*scale))
        bh = rng.randint(int(55*scale), int(170*scale))
        y0 = horizon - bh
        c = palette[idx % len(palette)]
        d.rounded_rectangle((x, y0, x+bw, horizon+12*scale), radius=int(4*scale), fill=c)
        if rng.random() < 0.22:
            d.rectangle((x+bw*0.42, y0-int(25*scale), x+bw*0.58, y0), fill=(67, 88, 111, 128))
        x += bw + rng.randint(int(5*scale), int(18*scale))
        idx += 1
    layer = layer.filter(ImageFilter.GaussianBlur(int(2.5*scale)))
    return Image.alpha_composite(img, layer)


def building_face(draw, poly, color, shadow=None):
    polygon(draw, poly, color)
    if shadow:
        p0, p1, p2, p3 = poly
        side = [p1, (p1[0]+18, p1[1]-11), (p2[0]+18, p2[1]-11), p2]
        polygon(draw, side, shadow)


def draw_building(layer, rng, x, base_y, w, h, body, window, roof, scale, depth=0):
    d = ImageDraw.Draw(layer)
    left = int(x)
    right = int(x + w)
    top = int(base_y - h)
    skew = int(max(6*scale, w * 0.08))
    front = [(left, base_y), (right, base_y), (right, top), (left, top)]
    side = [(right, base_y), (right+skew, base_y-int(10*scale)), (right+skew, top-int(10*scale)), (right, top)]
    polygon(d, front, body)
    polygon(d, side, tuple(max(0, c-28) for c in body[:3]) + (body[3],))
    roof_poly = [(left, top), (right, top), (right+skew, top-int(10*scale)), (left+skew, top-int(10*scale))]
    polygon(d, roof_poly, roof)

    cols = max(2, int(w // (34*scale)))
    rows = max(2, int(h // (42*scale)))
    padx = w * 0.14
    pady = h * 0.16
    ww = min(18*scale, w * 0.15)
    wh = min(22*scale, h * 0.10)
    for r in range(rows):
        yy = top + pady + r * ((h - 2*pady) / max(1, rows-1))
        for c in range(cols):
            xx = left + padx + c * ((w - 2*padx) / max(1, cols-1))
            if rng.random() < 0.72:
                col = window if rng.random() < 0.76 else (255, 214, 132, 230)
                d.rounded_rectangle((xx-ww/2, yy-wh/2, xx+ww/2, yy+wh/2), radius=int(2*scale), fill=col)
    if w > 100*scale and rng.random() < 0.65:
        aw_y = base_y - int(25*scale)
        d.polygon([(left+10*scale, aw_y), (right-10*scale, aw_y), (right-20*scale, aw_y+16*scale), (left+20*scale, aw_y+16*scale)], fill=(246, 116, 75, 245))


def draw_mid_city(img, rng, scale, horizon):
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    palette = [
        (37, 95, 118, 255), (50, 116, 128, 255), (184, 70, 77, 255),
        (212, 116, 60, 255), (98, 78, 135, 255), (62, 107, 86, 255),
    ]
    x = int(-45*scale)
    base_y = int(horizon + 165*scale)
    i = 0
    while x < img.size[0] * 0.92:
        bw = rng.randint(int(72*scale), int(132*scale))
        bh = rng.randint(int(125*scale), int(260*scale))
        body = palette[i % len(palette)]
        draw_building(layer, rng, x, base_y-rng.randint(0,int(16*scale)), bw, bh, body, (207,229,225,240), (39,47,60,255), scale)
        x += bw - rng.randint(int(6*scale), int(14*scale))
        i += 1
    return Image.alpha_composite(img, layer)


def draw_boulevard(img, scale, horizon):
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    w, h = img.size
    vx, vy = int(w*0.61), int(horizon+22*scale)
    road = [(int(w*0.10), h), (int(w*0.96), h), (vx+65*scale, vy), (vx-22*scale, vy)]
    polygon(d, road, (31, 39, 48, 255))
    left_walk = [(0,h), (int(w*0.10),h), (vx-22*scale,vy), (vx-60*scale,vy+4*scale)]
    right_walk = [(int(w*0.96),h), (w,h), (vx+100*scale,vy+5*scale), (vx+65*scale,vy)]
    polygon(d, left_walk, (139, 136, 126, 255))
    polygon(d, right_walk, (139, 136, 126, 255))
    for i in range(11):
        t0 = i/11
        t1 = min(1,(i+0.46)/11)
        x0 = vx + (w*0.53-vx) * (t0**1.7)
        y0 = vy + (h-vy) * t0
        x1 = vx + (w*0.53-vx) * (t1**1.7)
        y1 = vy + (h-vy) * t1
        width = max(2*scale, 7*scale*t0)
        d.line((x0,y0,x1,y1), fill=(244, 216, 132, 210), width=int(width))
    return Image.alpha_composite(img, layer)


def draw_park_and_water(img, rng, scale, horizon):
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    w,h = img.size
    park = [(0,h), (int(w*0.29),h), (int(w*0.47),int(horizon+78*scale)), (0,int(horizon+105*scale))]
    polygon(d, park, (44, 100, 77, 255))
    water = [(int(w*0.73),h), (w,h), (w,int(horizon+78*scale)), (int(w*0.80),int(horizon+96*scale)), (int(w*0.69),int(horizon+145*scale))]
    polygon(d, water, (33, 106, 142, 255))
    for i in range(14):
        x = rng.randint(int(w*0.75), w-10)
        y = rng.randint(int(horizon+125*scale), h-10)
        ww = rng.randint(int(30*scale), int(110*scale))
        d.arc((x-ww,y-8*scale,x+ww,y+8*scale), 190, 350, fill=(93,168,187,95), width=max(1,int(2*scale)))
    return Image.alpha_composite(img, layer)


def tree(layer, x, y, s, rng, scale):
    d = ImageDraw.Draw(layer)
    trunk = (76, 46, 35, 255)
    d.rounded_rectangle((x-5*s, y-42*s, x+5*s, y), radius=max(1,int(3*s)), fill=trunk)
    leaf_cols = [(43,107,72,255),(55,127,80,255),(78,145,86,255),(37,91,67,255)]
    for ox,oy,rs in [(-18,-46,24),(10,-52,28),(-2,-67,30),(25,-38,20)]:
        c = rng.choice(leaf_cols)
        d.ellipse((x+(ox-rs)*s, y+(oy-rs)*s, x+(ox+rs)*s, y+(oy+rs)*s), fill=c)


def draw_foreground(img, rng, scale):
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    w,h = img.size
    for x,y,s in [(45,h-5,1.5),(145,h-14,1.25),(260,h-8,1.7),(395,h-20,1.25),(1000,h-8,1.45),(1150,h-16,1.7),(1240,h-8,1.35)]:
        tree(layer, int(x*scale), int(y), s*scale, rng, scale)
    d = ImageDraw.Draw(layer)
    # Tiny people silhouettes and a bike so the city feels inhabited.
    for px in [430, 510, 596, 782, 870]:
        x = int(px*scale)
        y = int(h - rng.randint(int(42*scale), int(70*scale)))
        d.ellipse((x-4*scale,y-17*scale,x+4*scale,y-9*scale), fill=(28,35,45,235))
        d.line((x,y-9*scale,x,y+10*scale), fill=(28,35,45,235), width=max(1,int(3*scale)))
        d.line((x,y+2*scale,x-6*scale,y+15*scale), fill=(28,35,45,235), width=max(1,int(2*scale)))
        d.line((x,y+2*scale,x+7*scale,y+15*scale), fill=(28,35,45,235), width=max(1,int(2*scale)))
    return Image.alpha_composite(img, layer)


def draw_crane(img, scale, x, horizon):
    layer = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    c = (42, 48, 56, 190)
    base_y = horizon + int(22*scale)
    top_y = horizon - int(135*scale)
    d.line((x, base_y, x, top_y), fill=c, width=max(2,int(5*scale)))
    d.line((x, top_y, x+155*scale, top_y), fill=c, width=max(2,int(4*scale)))
    d.line((x+40*scale,top_y,x+15*scale,top_y-28*scale), fill=c, width=max(1,int(3*scale)))
    d.line((x+120*scale,top_y,x+120*scale,top_y+80*scale), fill=c, width=max(1,int(2*scale)))
    d.rectangle((x+112*scale,top_y+78*scale,x+128*scale,top_y+91*scale), fill=(198,119,63,180))
    return Image.alpha_composite(img, layer)


def draw_lights(img, rng, scale, horizon):
    glow_layer = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(glow_layer)
    w,h = img.size
    for i in range(21):
        t = i/20
        x = int((w*0.13)*(1-t) + (w*0.61)*t)
        y = int(h*(1-t) + (horizon+26*scale)*t)
        r = max(2,int((10*(1-t)+2)*scale))
        d.ellipse((x-r,y-r,x+r,y+r), fill=(255,192,100,210))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(int(8*scale)))
    return Image.alpha_composite(img, glow_layer)


def add_grain(img, rng, amount=12):
    noise = Image.new("L", img.size)
    px = noise.load()
    w,h = img.size
    for y in range(h):
        for x in range(w):
            px[x,y] = rng.randint(108, 148)
    noise = noise.filter(ImageFilter.GaussianBlur(0.35))
    grain = Image.new("RGBA", img.size, (255,255,255,0))
    grain.putalpha(noise.point(lambda p: int(abs(p-128) * amount / 10)))
    return Image.alpha_composite(img, grain)


def render(recipe, final=False):
    size = FINAL_RES if final else PROXY_RES
    scale = size[0] / 1280.0
    rng = random.Random(int(recipe.get("seed", 26092603)))
    horizon = int(size[1] * 0.49)

    img = vertical_gradient(size, (24,47,78,255), (230,132,91,255))
    img = glow(img, (int(size[0]*0.18), int(size[1]*0.33)), int(145*scale), (255,160,93), 190)
    img = draw_clouds(img, rng, scale)
    img = draw_distant_skyline(img, rng, scale, horizon)
    img = draw_mid_city(img, rng, scale, horizon)
    img = draw_boulevard(img, scale, horizon)
    img = draw_park_and_water(img, rng, scale, horizon)
    img = draw_crane(img, scale, int(size[0]*0.69), horizon)
    img = draw_foreground(img, rng, scale)
    img = draw_lights(img, rng, scale, horizon)

    # Atmospheric glaze separates the image from technical/vector output.
    haze = Image.new("RGBA", size, (56,93,118,20))
    img = Image.alpha_composite(img, haze)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = ImageEnhance.Contrast(img).enhance(1.04)
    img = add_grain(img, rng, 7 if final else 5)
    return img.convert("RGBA")


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    img = render(recipe, final=args.final)
    png = out / ("loading_splash_final.png" if args.final else "loading_splash_proxy.png")
    img.save(png, optimize=True)
    report = {
        "contract": CONTRACT,
        "artId": recipe.get("artId"),
        "status": "ok",
        "renderer": "procedural_2d_illustration",
        "resolution": list(img.size),
        "output": png.name,
        "designIntent": recipe.get("artDirection", {}),
    }
    (out / "loading_splash_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
