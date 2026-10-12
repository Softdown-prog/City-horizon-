#!/usr/bin/env python3
"""Audit the real promoted train sprites for unexpected opaque black mattes.

No edits to asset PNGs. A matte outside the visible silhouette can affect
both automated captures and the interactive runtime.
"""
from pathlib import Path
from PIL import Image
import json
roots=[Path("assets/vehicles/steam_train_coach_01"),
       Path("assets/vehicles/steam_train_locomotive_01")]
rows=[]
for root in roots:
    for path in sorted(root.glob("steam_train_*.png")):
        with Image.open(path) as img:
            rgba=img.convert("RGBA")
            alpha=rgba.getchannel("A")
            black=0
            opaque_black=0
            corner=[]
            for x,y in [(0,0),(rgba.width-1,0),(0,rgba.height-1),(rgba.width-1,rgba.height-1)]:
                corner.append(rgba.getpixel((x,y)))
            for r,g,b,a in rgba.getdata():
                if r<7 and g<7 and b<7:
                    black+=1
                    if a>=250:
                        opaque_black+=1
            rows.append({"file":str(path),"size":rgba.size,"corners":corner,
                         "black_pixels":black,"opaque_black_pixels":opaque_black,
                         "alpha_extrema":alpha.getextrema()})
for row in rows: print(json.dumps(row,ensure_ascii=False))
Path("out/rail-sdl-capture").mkdir(parents=True,exist_ok=True)
Path("out/rail-sdl-capture/sprite_alpha_audit.json").write_text(
    json.dumps(rows,indent=2)+"\n",encoding="utf-8")
