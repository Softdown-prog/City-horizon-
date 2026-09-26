"""Deterministic organic scenery renderer for City Horizon 2D props.

This extends Visitor Forge with high-level foliage strokes and an isometric
review gate. It is intentionally procedural and reproducible; no image model
or external raster source is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

CONTRACT = "CH_2D_ORGANIC_SCENERY_V1"
CAMERA_CONTRACT = "CH_CAMERA_V1"
WORK_SCALE = 4


def _hex(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError("colors must be #RRGGBB")
    return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _quad(a: tuple[float,float], b: tuple[float,float], c: tuple[float,float], t: float) -> tuple[float,float]:
    u = 1.0 - t
    return (u*u*a[0] + 2*u*t*b[0] + t*t*c[0], u*u*a[1] + 2*u*t*b[1] + t*t*c[1])


def _alpha_safe_resize(image: Image.Image, size: tuple[int,int]) -> Image.Image:
    rgba = image.convert("RGBA")
    try:
        return rgba.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")
    except (ValueError, OSError):
        return rgba.resize(size, Image.Resampling.LANCZOS)


def _tapered_curve(mask: Image.Image, p0, p1, p2, start_width: float, end_width: float, *, samples: int = 48) -> None:
    draw = ImageDraw.Draw(mask)
    for i in range(samples + 1):
        t = i / samples
        x, y = _quad(p0, p1, p2, t)
        width = _lerp(start_width, end_width, t) * WORK_SCALE
        r = max(1.0, width * 0.5)
        x *= WORK_SCALE; y *= WORK_SCALE
        draw.ellipse((round(x-r), round(y-r), round(x+r), round(y+r)), fill=255)


def _paint(mask: Image.Image, color_top, color_bottom, *, right_shade: float = 0.0, highlight: tuple[float,float,float,float] | None = None) -> Image.Image:
    w, h = mask.size
    top = _hex(color_top); bottom = _hex(color_bottom)
    surface = Image.new("RGBA", (w,h), (0,0,0,0))
    pix = surface.load()
    # deterministic broad lighting; high-res loop is small enough for props.
    for y in range(h):
        ty = y / max(1, h-1)
        for x in range(w):
            tx = x / max(1, w-1)
            base = [_lerp(top[c], bottom[c], ty) for c in range(3)]
            shade = 1.0 - right_shade * tx
            if highlight is not None:
                hx, hy, radius, strength = highlight
                dx = tx-hx; dy = ty-hy
                glow = max(0.0, 1.0 - math.sqrt(dx*dx+dy*dy)/radius) * strength
            else:
                glow = 0.0
            rgb = tuple(max(0,min(255,round(v*shade + 255*glow))) for v in base)
            pix[x,y] = (*rgb,0)
    surface.putalpha(mask)
    return surface


def _composite_layer(work: Image.Image, mask: Image.Image, top: str, bottom: str, *, right_shade=0.0, highlight=None, shadow=None) -> None:
    if shadow:
        dx,dy,blur,opacity,color = shadow
        shifted = Image.new("L", mask.size, 0)
        shifted.paste(mask, (round(dx*WORK_SCALE), round(dy*WORK_SCALE)))
        if blur:
            shifted = shifted.filter(ImageFilter.GaussianBlur(blur*WORK_SCALE))
        sh = Image.new("RGBA", mask.size, (*_hex(color),0))
        sh.putalpha(shifted.point(lambda p: round(p*opacity)))
        work.alpha_composite(sh)
    work.alpha_composite(_paint(mask, top,bottom,right_shade=right_shade,highlight=highlight))


def _branch_cluster(mask: Image.Image, rng: random.Random, root, tip, *, width: float, droop: float, side: int, density: int) -> None:
    rx,ry=root; tx,ty=tip
    control=((rx+tx)*0.5, min(ry,ty)+droop)
    _tapered_curve(mask, root, control, tip, width, 0.7, samples=52)
    draw=ImageDraw.Draw(mask)
    # blade/needle masses follow the branch rather than stacking triangles.
    for j in range(1,density+1):
        t=j/(density+1)
        cx,cy=_quad(root,control,tip,t)
        branch_len=max(4.0,width*(1.15-0.55*t))
        angle=(-0.92 if side<0 else 0.92) + rng.uniform(-0.18,0.18)
        # Two tapered sidelets per station produce a feathered bough.
        for sign in (-1,1):
            a=angle*sign
            ex=cx + math.cos(a)*branch_len
            ey=cy + abs(math.sin(a))*branch_len*0.55 + rng.uniform(-1.2,1.4)
            _tapered_curve(mask,(cx,cy),((cx+ex)*0.5,cy+rng.uniform(-1.0,2.0)),(ex,ey),max(2.0,width*0.34),0.45,samples=24)
        # a small angular needle fan, softened only by final supersampling
        r=max(2.0,width*0.32)*WORK_SCALE
        x=cx*WORK_SCALE; y=cy*WORK_SCALE
        draw.ellipse((x-r,y-r*0.55,x+r,y+r*0.55),fill=255)


def _soft_irregular_mass(mask: Image.Image, rng: random.Random, center, rx: float, ry: float, lobes: int = 14) -> None:
    cx,cy=center
    pts=[]
    for i in range(lobes):
        a=2*math.pi*i/lobes
        jitter=1.0+rng.uniform(-0.13,0.13)
        pts.append((round((cx+math.cos(a)*rx*jitter)*WORK_SCALE), round((cy+math.sin(a)*ry*jitter)*WORK_SCALE)))
    ImageDraw.Draw(mask).polygon(pts, fill=255)


def render(recipe: dict) -> tuple[Image.Image, dict]:
    if recipe.get("contract") != CONTRACT:
        raise ValueError(f"recipe must declare {CONTRACT}")
    canvas=recipe.get("canvas",[192,256])
    if canvas != [192,256]:
        raise ValueError("pine v1 organic gate currently uses canonical 192x256 canvas")
    anchor=recipe.get("anchor",[96,239])
    if recipe.get("camera",{}).get("contract") != CAMERA_CONTRACT:
        raise ValueError("organic gameplay scenery must declare CH_CAMERA_V1")
    if recipe["camera"].get("tile") != [128,64]:
        raise ValueError("CH_CAMERA_V1 review requires 128x64 tile")
    seed=int(recipe.get("seed",1)); rng=random.Random(seed)
    palette=recipe["palette"]
    W,H=canvas[0]*WORK_SCALE,canvas[1]*WORK_SCALE
    work=Image.new("RGBA",(W,H),(0,0,0,0))

    # Ground contact: 2:1 ellipse echoes the dimetric ground plane.
    sm=Image.new("L",(W,H),0)
    ImageDraw.Draw(sm).ellipse((48*WORK_SCALE,229*WORK_SCALE,145*WORK_SCALE,244*WORK_SCALE),fill=180)
    sm=sm.filter(ImageFilter.GaussianBlur(2.2*WORK_SCALE))
    sh=Image.new("RGBA",(W,H),(*_hex(palette["ground_shadow"]),0)); sh.putalpha(sm)
    work.alpha_composite(sh)

    # Trunk: screen-vertical world height with slightly visible left lit plane.
    trunk=Image.new("L",(W,H),0); d=ImageDraw.Draw(trunk)
    d.polygon([(83*WORK_SCALE,124*WORK_SCALE),(109*WORK_SCALE,126*WORK_SCALE),(105*WORK_SCALE,239*WORK_SCALE),(86*WORK_SCALE,239*WORK_SCALE)],fill=255)
    _composite_layer(work,trunk,palette["trunk_top"],palette["trunk_bottom"],right_shade=.17,highlight=(.43,.47,.26,.15),shadow=(2,2,1.2,.28,"#16251E"))
    bark=Image.new("L",(W,H),0); bd=ImageDraw.Draw(bark)
    for xoff,y0,y1 in [(-5,168,226),(2,151,211),(7,186,232)]:
        bd.line(((96+xoff)*WORK_SCALE,y0*WORK_SCALE,(94+xoff)*WORK_SCALE,y1*WORK_SCALE),fill=120,width=round(1.0*WORK_SCALE))
    hi=Image.new("RGBA",(W,H),(*_hex(palette["trunk_light"]),0)); hi.putalpha(bark); work.alpha_composite(hi)

    # Back crown creates depth behind the main whorls.
    back=Image.new("L",(W,H),0)
    tiers=recipe["tiers"]
    for i,tier in enumerate(tiers):
        y=float(tier["y"]); span=float(tier["span"]); thick=float(tier["thickness"])
        skew=float(tier.get("skew",0))
        _soft_irregular_mass(back,rng,(96+skew,y+5),span*.58,thick*.68,16)
        # rear/uphill branches sit slightly higher because we are looking down 30 degrees.
        for side in (-1,1):
            tip=(96+skew+side*span, y+thick*.20+rng.uniform(-2,2))
            _branch_cluster(back,rng,(96+skew,y-3),tip,width=max(6.2,thick*.38),droop=-thick*.10,side=side,density=max(3,int(span/16)))
    _composite_layer(work,back,palette["back_top"],palette["back_bottom"],right_shade=.25,highlight=(.34,.24,.36,.08))

    # Main/front boughs: lower screen position and broader lit top planes give the 3/4 camera read.
    main=Image.new("L",(W,H),0)
    front=Image.new("L",(W,H),0)
    for i,tier in enumerate(tiers):
        y=float(tier["y"]); span=float(tier["span"]); thick=float(tier["thickness"]); skew=float(tier.get("skew",0))
        _soft_irregular_mass(main,rng,(96+skew,y+2),span*.48,thick*.60,14)
        for side in (-1,1):
            asym=1.0+rng.uniform(-.08,.08)
            tip=(96+skew+side*span*asym, y+thick*.58+rng.uniform(-1.2,2.8))
            _branch_cluster(main,rng,(96+skew,y-1),tip,width=max(6.8,thick*.44),droop=thick*.23,side=side,density=max(4,int(span/14)))
        # front/downhill fan hangs lower, making top-facing surfaces visible.
        fspan=span*.70
        _branch_cluster(front,rng,(96+skew,y+1),(96-fspan,y+thick*.94),width=max(6.0,thick*.36),droop=thick*.36,side=-1,density=max(3,int(span/17)))
        _branch_cluster(front,rng,(96+skew,y+1),(96+fspan*.88,y+thick*.90),width=max(5.8,thick*.34),droop=thick*.34,side=1,density=max(3,int(span/17)))
    # Interstitial side boughs break the repeated shelf rhythm without adding
    # random non-determinism. They mimic the partial whorls seen between mature
    # conifer tiers and make the silhouette read as one organism.
    for i in range(len(tiers)-1):
        a=tiers[i]; b=tiers[i+1]
        y=(_lerp(float(a["y"]),float(b["y"]),.53)+rng.uniform(-1.5,1.5))
        span=_lerp(float(a["span"]),float(b["span"]),.50)*.72
        thick=_lerp(float(a["thickness"]),float(b["thickness"]),.50)
        side=-1 if i%2==0 else 1
        _branch_cluster(main,rng,(96+rng.uniform(-2,2),y-2),(96+side*span,y+thick*.52),width=max(4.5,thick*.27),droop=thick*.20,side=side,density=max(3,int(span/18)))
        if i in (2,5):
            _branch_cluster(main,rng,(96+rng.uniform(-1,1),y),(96-side*span*.58,y+thick*.43),width=max(3.8,thick*.22),droop=thick*.16,side=-side,density=3)
    _composite_layer(work,main,palette["mid_top"],palette["mid_bottom"],right_shade=.20,highlight=(.31,.28,.42,.12),shadow=(1,2,.7,.18,"#102C24"))

    _composite_layer(work,front,palette["front_top"],palette["front_bottom"],right_shade=.17,highlight=(.28,.36,.45,.16))

    # Paint broad highlight brushes on upper-left branch surfaces.
    lights=Image.new("L",(W,H),0)
    for i,tier in enumerate(tiers[1:]):
        y=float(tier["y"]); span=float(tier["span"]); thick=float(tier["thickness"])
        start=(94,y+2); end=(96-span*.66,y+thick*.50)
        _tapered_curve(lights,start,((start[0]+end[0])*.5,y+thick*.14),end,max(3.0,thick*.18),.7,samples=34)
    lights=lights.filter(ImageFilter.GaussianBlur(.30*WORK_SCALE))
    li=Image.new("RGBA",(W,H),(*_hex(palette["highlight"]),0)); li.putalpha(lights.point(lambda p: round(p*.72))); work.alpha_composite(li)

    frame=_alpha_safe_resize(work,tuple(canvas))
    bounds=frame.getchannel("A").getbbox()
    return frame,{"contract":CONTRACT,"id":recipe["id"],"canvas":canvas,"anchor":anchor,"bounds":list(bounds),"seed":seed,"camera":recipe["camera"],"runtimePromotion":False,"artApproved":False}


def review_board(frame: Image.Image) -> Image.Image:
    w,h=frame.size
    board=Image.new("RGBA",(w*3+48,h*2+40),(76,116,48,255))
    board.alpha_composite(frame,(16,20+h//2))
    board.alpha_composite(frame.resize((w*2,h*2),Image.Resampling.NEAREST),(w+32,20))
    d=ImageDraw.Draw(board); d.text((16,4),"1x / gameplay",fill=(247,244,220,255)); d.text((w+32,4),"2x / inspection",fill=(247,244,220,255))
    return board


def isometric_board(frame: Image.Image, anchor) -> Image.Image:
    board=Image.new("RGBA",(768,480),(46,77,55,255)); d=ImageDraw.Draw(board)
    gx,gy=384,314; hw,hh=64,32
    for x in range(-3,4):
        for y in range(-3,4):
            cx=gx+(x-y)*hw; cy=gy+(x+y)*hh
            poly=[(cx,cy-hh),(cx+hw,cy),(cx,cy+hh),(cx-hw,cy)]
            fill=(76,119,66,255) if (x+y)%2==0 else (71,113,64,255)
            d.polygon(poly,fill=fill,outline=(105,148,93,205))
    d.polygon([(gx,gy-hh),(gx+hw,gy),(gx,gy+hh),(gx-hw,gy)],fill=(82,132,72,255),outline=(174,207,145,255))
    board.alpha_composite(frame,(round(gx-anchor[0]),round(gy-anchor[1])))
    d.ellipse((gx-3,gy-3,gx+3,gy+3),fill=(255,224,132,255))
    d.text((18,16),"CH_CAMERA_V1 / 30deg elevation / 45deg yaw / 128x64",fill=(247,244,220,255))
    d.text((18,36),"gameplay 1x / screen-vertical height / 2:1 ground contact",fill=(220,232,205,255))
    return board


def export(recipe_path: Path, output_dir: Path) -> dict:
    raw=recipe_path.read_bytes(); recipe=json.loads(raw)
    frame,meta=render(recipe); output_dir.mkdir(parents=True,exist_ok=True)
    stem=recipe["id"]
    png=output_dir/f"{stem}.png"; review=output_dir/f"{stem}_review.png"; iso=output_dir/f"{stem}_isometric_review.png"; report=output_dir/f"{stem}.json"
    frame.save(png); review_board(frame).save(review); isometric_board(frame,meta["anchor"]).save(iso)
    meta.update({"recipe":str(recipe_path),"recipeSha256":hashlib.sha256(raw).hexdigest(),"png":str(png),"review":str(review),"isometricReview":str(iso)})
    report.write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
    return {"png":str(png),"review":str(review),"isometricReview":str(iso),"metadata":str(report)}


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--recipe",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
    print(json.dumps(export(args.recipe,args.output),indent=2)); return 0

if __name__ == "__main__":
    raise SystemExit(main())
