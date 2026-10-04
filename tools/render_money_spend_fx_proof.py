from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# CH_MONEY_SPEND_VIDEO_PROOF_V1
OUT = Path("out/money-spend-fx-proof")
FRAMES = OUT / "frames"
W, H = 960, 540
FPS = 30
DURATION = 4.0
LIFETIME_MS = 950.0


def font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


FONT_SMALL = font(22)
FONT_MONEY = font(30, True)
FONT_TITLE = font(28, True)


def iso_to_screen(x: int, y: int, ox=480, oy=160):
    return ox + (x-y)*64, oy + (x+y)*32


def draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, fill, outline=None):
    pts = [(cx, cy-32), (cx+64, cy), (cx, cy+32), (cx-64, cy)]
    draw.polygon(pts, fill=fill, outline=outline)


def blend(base, overlay, alpha):
    return tuple(int(base[i]*(1-alpha)+overlay[i]*alpha) for i in range(3))


def main():
    FRAMES.mkdir(parents=True, exist_ok=True)

    events = [
        (0.70, 40, 480, 268, "PEDRA"),
        (1.70, 25, 610, 300, "MADEIRA"),
        (2.75, 1200, 355, 235, "CONSTRUCAO"),
    ]

    total = int(DURATION*FPS)
    for i in range(total):
        tsec = i/FPS
        img = Image.new("RGBA", (W,H), (35,49,60,255))
        d = ImageDraw.Draw(img, "RGBA")

        d.rectangle((0,0,W,H), fill=(37,53,64,255))
        d.text((28,22), "CH_MONEY_SPEND_FX_V1 — VIDEO DE TESTE", font=FONT_TITLE, fill=(245,245,240,255))
        d.text((30,58), "Gasto real confirmado -> valor sobe e desaparece", font=FONT_SMALL, fill=(190,205,212,255))

        for gy in range(5):
            for gx in range(6):
                cx, cy = iso_to_screen(gx, gy)
                grass = (101,145,76,255) if (gx+gy)%2==0 else (96,138,72,255)
                draw_diamond(d, cx, cy, grass, (75,110,58,255))

        draw_diamond(d, 480, 300, (138,132,122,255), (82,78,72,255))
        for off in (-36,-12,12,36):
            d.line((480+off,268,480+off+28,300), fill=(100,96,91,170), width=2)
        draw_diamond(d, 608, 332, (137,91,54,255), (77,47,28,255))
        for off in (-42,-18,6,30):
            d.line((608+off,300,608+off+26,332), fill=(82,50,29,210), width=3)

        d.polygon([(355,202),(397,223),(355,244),(313,223)], fill=(188,178,160,255))
        d.polygon([(313,223),(355,244),(355,309),(313,287)], fill=(147,137,123,255))
        d.polygon([(397,223),(355,244),(355,309),(397,287)], fill=(122,113,101,255))
        d.text((308,315), "CASA", font=FONT_SMALL, fill=(230,230,225,220))

        for started, amount, sx, sy, label in events:
            dt = tsec-started
            if -0.12 <= dt < 0:
                pulse = (dt+0.12)/0.12
                r = 10+int(18*pulse)
                d.ellipse((sx-r,sy-r,sx+r,sy+r), outline=(255,255,255,int(180*(1-pulse))), width=3)
            if 0 <= dt < LIFETIME_MS/1000.0:
                ms = dt*1000.0
                tt = max(0.0,min(1.0,ms/LIFETIME_MS))
                eased = 1.0-(1.0-tt)*(1.0-tt)
                yy = sy-18.0-34.0*eased
                alpha = int(255.0*(1.0-tt))
                text = f"-${amount}"
                d.text((sx+2,yy+2), text, font=FONT_MONEY, anchor="mm", fill=(22,18,14,int(alpha*0.70)))
                d.text((sx,yy), text, font=FONT_MONEY, anchor="mm", fill=(255,214,92,alpha))
                d.text((sx,sy+40), label, font=FONT_SMALL, anchor="mm", fill=(235,235,230,190))

        x0, x1 = 80, 880
        y = 500
        d.line((x0,y,x1,y), fill=(130,145,150,180), width=2)
        px = x0 + (x1-x0)*(tsec/DURATION)
        d.ellipse((px-5,y-5,px+5,y+5), fill=(255,214,92,255))

        img.convert("RGB").save(FRAMES/f"frame_{i:04d}.png", quality=95)

    mp4 = OUT/"money_spend_fx_test.mp4"
    cmd = [
        "ffmpeg","-y","-framerate",str(FPS),"-i",str(FRAMES/"frame_%04d.png"),
        "-c:v","libx264","-pix_fmt","yuv420p","-movflags","+faststart",str(mp4)
    ]
    subprocess.run(cmd, check=True)
    print(mp4)


if __name__ == "__main__":
    main()
