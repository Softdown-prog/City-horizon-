"""2D paint-over / finishing pass for City Horizon loading key art.

Input is the 3D foundation PNG. Output is a stylized poster treatment with
color grading, atmospheric paint, glow, texture and framing. This is not a
runtime asset-normalization step; it is presentation art finishing.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

CONTRACT = "CH_LOADING_SPLASH_ART_V1"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    return p.parse_args()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def screen(base, layer):
    return ImageChops.screen(base.convert("RGB"), layer.convert("RGB")).convert("RGBA")


def soft_light_like(base, overlay, opacity=0.25):
    blended = Image.blend(base.convert("RGB"), ImageChops.overlay(base.convert("RGB"), overlay.convert("RGB")), opacity)
    return blended.convert("RGBA")


def vertical_gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", size)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(4))
        for x in range(w):
            px[x, y] = c
    return img


def add_atmosphere(img, rng):
    w, h = img.size
    haze = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(haze, "RGBA")

    # Broad painterly haze bands soften the rigid 3D silhouette language.
    for i in range(14):
        cx = int(w * (0.08 + rng.random() * 0.86))
        cy = int(h * (0.16 + rng.random() * 0.50))
        rx = int(w * (0.08 + rng.random() * 0.18))
        ry = int(h * (0.025 + rng.random() * 0.08))
        warm = i % 3 == 0
        color = (255, 132, 78, 22) if warm else (110, 156, 220, 18)
        d.ellipse((cx-rx, cy-ry, cx+rx, cy+ry), fill=color)
    haze = haze.filter(ImageFilter.GaussianBlur(radius=max(10, w // 90)))
    return Image.alpha_composite(img, haze)


def add_bloom(img):
    rgb = img.convert("RGB")
    lum = rgb.convert("L")
    # Keep only bright areas, then blur into a warm photographic glow.
    mask = lum.point(lambda p: 0 if p < 165 else min(255, int((p - 165) * 2.7)))
    glow = Image.new("RGBA", img.size, (255, 160, 76, 0))
    glow.putalpha(mask.filter(ImageFilter.GaussianBlur(radius=16)))
    return Image.alpha_composite(img, glow)


def add_painted_sky(img, rng):
    w, h = img.size
    paint = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(paint, "RGBA")

    # Sunset brush masses concentrated around the upper-left title-safe zone.
    cloud_specs = [
        (0.13, 0.16, 0.22, 0.07, (255, 136, 90, 35)),
        (0.30, 0.12, 0.18, 0.055, (255, 182, 118, 28)),
        (0.53, 0.20, 0.24, 0.06, (120, 150, 215, 20)),
        (0.77, 0.10, 0.16, 0.05, (170, 124, 200, 20)),
    ]
    for cx, cy, rx, ry, col in cloud_specs:
        for j in range(5):
            ox = (rng.random() - 0.5) * rx * w * 0.55
            oy = (rng.random() - 0.5) * ry * h * 0.55
            rr_x = rx * w * (0.45 + rng.random() * 0.45)
            rr_y = ry * h * (0.55 + rng.random() * 0.55)
            x = cx*w + ox
            y = cy*h + oy
            d.ellipse((x-rr_x, y-rr_y, x+rr_x, y+rr_y), fill=col)
    paint = paint.filter(ImageFilter.GaussianBlur(radius=max(14, w // 70)))
    return Image.alpha_composite(img, paint)


def add_light_streaks(img):
    w, h = img.size
    streaks = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(streaks, "RGBA")
    # Hand-painted traffic / boulevard highlights, intentionally stylized.
    segments = [
        ((0.18, 0.68), (0.28, 0.64)),
        ((0.31, 0.61), (0.42, 0.58)),
        ((0.46, 0.56), (0.56, 0.54)),
        ((0.61, 0.51), (0.70, 0.48)),
    ]
    for i, (a, b) in enumerate(segments):
        color = (255, 206, 116, 120) if i % 2 == 0 else (110, 210, 255, 95)
        d.line((a[0]*w, a[1]*h, b[0]*w, b[1]*h), fill=color, width=max(2, w//420))
    streaks = streaks.filter(ImageFilter.GaussianBlur(radius=4))
    return Image.alpha_composite(img, streaks)


def add_foreground_paint(img, rng):
    w, h = img.size
    fg = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(fg, "RGBA")
    # Loose foliage silhouettes break the clean render frame at the bottom corners.
    for side in (0, 1):
        base_x = -0.03*w if side == 0 else 1.03*w
        for i in range(13):
            x = base_x + ((1 if side == 0 else -1) * rng.uniform(0.00, 0.15) * w)
            y = h * rng.uniform(0.73, 1.02)
            r = rng.uniform(0.025, 0.075) * w
            col = (21, 56, 44, rng.randint(45, 85))
            d.ellipse((x-r, y-r*0.72, x+r, y+r*0.72), fill=col)
    fg = fg.filter(ImageFilter.GaussianBlur(radius=2.0))
    return Image.alpha_composite(img, fg)


def add_vignette(img):
    w, h = img.size
    mask = Image.new("L", (w, h), 255)
    m = ImageDraw.Draw(mask)
    pad_x = int(w * 0.08)
    pad_y = int(h * 0.06)
    m.ellipse((-pad_x, -pad_y, w+pad_x, h+pad_y), fill=70)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(60, w//10)))
    dark = Image.new("RGBA", img.size, (6, 12, 24, 0))
    dark.putalpha(mask.point(lambda p: max(0, 105-p)))
    return Image.alpha_composite(img, dark)


def add_texture(img, rng):
    w, h = img.size
    # Low-amplitude monochrome texture prevents the polished-CG plastic feel.
    noise = Image.effect_noise((w, h), 20).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.45)
    tex = Image.merge("RGBA", (noise, noise, noise, noise.point(lambda p: 8)))
    return soft_light_like(img, tex, 0.16)


def make_review(base, final):
    w, h = base.size
    review = Image.new("RGB", (w*2, h), (16, 18, 24))
    review.paste(base.convert("RGB"), (0, 0))
    review.paste(final.convert("RGB"), (w, 0))
    d = ImageDraw.Draw(review)
    d.rectangle((0, 0, 220, 34), fill=(10, 12, 18))
    d.rectangle((w, 0, w+240, 34), fill=(10, 12, 18))
    d.text((12, 10), "3D FOUNDATION", fill=(240, 240, 240))
    d.text((w+12, 10), "2D PAINTOVER", fill=(240, 240, 240))
    return review


def main():
    args = parse_args()
    recipe = load_json(args.recipe)
    if recipe.get("contract") != CONTRACT:
        raise RuntimeError(f"Expected {CONTRACT}")

    source = Path(args.input)
    if not source.is_file():
        raise FileNotFoundError(source)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(int(recipe.get("seed", 26092604)) + 771)
    base = Image.open(source).convert("RGBA")

    # First grade the render away from neutral-CG output.
    graded = ImageEnhance.Color(base).enhance(1.16)
    graded = ImageEnhance.Contrast(graded).enhance(1.08)
    graded = ImageEnhance.Brightness(graded).enhance(0.98)

    # Warm highlights at top, cooler / deeper lower frame.
    grade = vertical_gradient(graded.size, (255, 122, 72, 34), (38, 86, 142, 26))
    graded = soft_light_like(graded, grade, 0.34)

    final = add_painted_sky(graded, rng)
    final = add_atmosphere(final, rng)
    final = add_bloom(final)
    final = add_light_streaks(final)
    final = add_foreground_paint(final, rng)
    final = add_texture(final, rng)
    final = add_vignette(final)
    final = final.filter(ImageFilter.UnsharpMask(radius=1.2, percent=85, threshold=4))

    final_path = out / "loading_splash_hybrid_proxy.png"
    review_path = out / "loading_splash_hybrid_review.png"
    final.convert("RGB").save(final_path, quality=95)
    make_review(base, final).save(review_path, quality=95)

    report = {
        "contract": CONTRACT,
        "artId": recipe.get("artId"),
        "status": "hybrid_finished",
        "source3d": source.name,
        "output": final_path.name,
        "review": review_path.name,
        "passes": [
            "3d_foundation", "color_grade", "painted_sky", "atmospheric_haze",
            "bloom", "painted_light_streaks", "foreground_foliage", "surface_texture", "vignette"
        ],
    }
    (out / "loading_splash_hybrid_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
