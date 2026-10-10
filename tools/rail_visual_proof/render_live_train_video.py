#!/usr/bin/env python3
"""Render an MP4 directly from City Horizon C++ rail runtime output.

This is a runtime motion validation, NOT footage captured from the interactive
city_builder executable. Positions, heading, speed, station dwell and spacing
come solely from the compiled C++ engine; only compositing is done by Pillow.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
W, H, FPS = 1280, 720, 16
ZOOM = 0.42
FONT_FILE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def font(size, bold=False):
    p = FONT_FILE.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") if bold else FONT_FILE
    try:
        return ImageFont.truetype(p, size)
    except OSError:
        return ImageFont.load_default()

F12=font(17)
F18=font(21, True)
F28=font(29, True)

def project(x, y, ox, oy):
    # Official CH_CAMERA_V1 r0, kTileWidth 128 / kTileHeight 64.
    return ((W/2 + (x-y)*64*ZOOM-ox), (H*0.41 + (x+y)*32*ZOOM-oy))

def sprite_view(unit):
    # CH_CAMERA_V1: exactly the same orientation as the production C++ adapter.
    tx,ty=unit["tx"],unit["ty"]
    if abs(tx)>=abs(ty):
        return "north" if tx>=0 else "south"
    return "east" if ty>=0 else "west"

def layout_for(role, view):
    # CH_RAIL_VISUAL_ALIGNMENT_V2: the same immutable 1024px source sprite.
    if role == "locomotive":
        return 385, *{
            "south": (475,755), "east": (475,851),
            "west": (549,811), "north": (549,844)
        }[view]
    return 300, 512, (882 if view in ("east","west") else 872)

def images_for(role):
    folder=ROOT/"assets"/"vehicles"/("steam_train_locomotive_01" if role=="locomotive" else "steam_train_coach_01")
    m=json.loads((folder/"steam_train_unit_runtime.json").read_text())
    if m["contract"]!="CH_RUNTIME_VEHICLE_TRAIN_UNIT_V1" or not m["approvedForRuntime"]:
        raise ValueError("Unapproved CH runtime PNG set")
    images={}
    for direction, info in m["views"].items():
        src=folder/info["file"]
        actual=hashlib.sha256(src.read_bytes()).hexdigest()
        if actual!=info["sha256"]:
            raise ValueError("Manifest hash mismatch: "+str(src))
        images[direction]=Image.open(src).convert("RGBA")
    return images, m

def render(trace, out):
    trace=json.loads(trace.read_text())
    assert trace["contract"]=="CH_RAIL_LIVE_VIDEO_PROOF_V1"
    checks=trace["checks"]
    assert checks["moved"] and checks["station_dwell"] and checks["curve_heading_change"] and checks["eight_units"]
    assert checks["max_units"]==8
    frames=trace["frames"]
    assert len(frames)==trace["frame_count"] and trace["fps"]==FPS
    loco,loco_manifest=images_for("locomotive")
    coach,coach_manifest=images_for("coach")
    # Sprite scales and pivots are an exact copy of production render_unit.
    sprites={}
    for role, variants in (("locomotive",loco),("coach",coach)):
        for direction, im in variants.items():
            size=round(max(0.35, ZOOM)*layout_for(role,direction)[0])
            sprites[(role,direction)]=im.resize((size,size),Image.Resampling.LANCZOS)
    track=trace["track"]
    if len(track)<12:
        raise ValueError("Canonical polyline too short")
    out.mkdir(parents=True,exist_ok=True)
    target=out/"locomotiva_trilhos_runtime.mp4"
    ffmpeg=["ffmpeg","-y","-hide_banner","-loglevel","error","-f","rawvideo",
            "-pix_fmt","rgb24","-s",f"{W}x{H}","-r",str(FPS),"-i","-",
            "-an","-c:v","libx264","-preset","fast","-crf","20",
            "-pix_fmt","yuv420p","-movflags","+faststart",str(target)]
    proc=subprocess.Popen(ffmpeg,stdin=subprocess.PIPE)
    base=Image.new("RGB",(W,H),(67,97,73))
    poster_saved=False
    focus_x=focus_y=None
    for n,frame in enumerate(frames):
        units=frame["units"]
        if not units:
            raise ValueError("No train for frame")
        # Camera follows midpoint of loco and visible last coach, avoiding
        # one abrupt camera jump as the seven wagons progressively enter.
        x=(units[0]["x"]+units[-1]["x"])*0.5
        y=(units[0]["y"]+units[-1]["y"])*0.5
        if focus_x is None:
            focus_x,focus_y=x,y
        else:
            focus_x += (x-focus_x)*0.14
            focus_y += (y-focus_y)*0.14
        ox=(focus_x-focus_y)*64*ZOOM
        oy=(focus_x+focus_y)*32*ZOOM
        im=base.copy()
        draw=ImageDraw.Draw(im)
        # World plane / isometric reference grid.
        for gx in range(-70,76,4):
            a=project(gx,-34,ox,oy); b=project(gx,60,ox,oy)
            draw.line([a,b], fill=(74,112,82), width=1)
        for gy in range(-34,64,4):
            a=project(-70,gy,ox,oy); b=project(76,gy,ox,oy)
            draw.line([a,b],fill=(74,112,82),width=1)
        ps=[project(p[0],p[1],ox,oy) for p in track]
        # Real route geometry, layer order: shadow, ballast, parallel rails.
        draw.line([(a+1,b+4) for a,b in ps],fill=(29,54,41),width=19,joint="curve")
        draw.line(ps,fill=(93,84,68),width=19,joint="curve")
        draw.line(ps,fill=(143,128,100),width=13,joint="curve")
        # Sleepers every N canonical polyline points.
        for i in range(4,len(ps)-4,6):
            ax,ay=ps[i-2];bx,by=ps[i+2]
            dx,dy=bx-ax,by-ay
            length=max(1.0,math.hypot(dx,dy))
            nx,ny=-dy/length,dx/length
            cx,cy=ps[i]
            draw.line([(cx-nx*11,cy-ny*11),(cx+nx*11,cy+ny*11)],fill=(77,53,36),width=5)
        for sign in (-1,1):
            shifted=[]
            for i,(px,py) in enumerate(ps):
                p=ps[max(0,i-1)];q=ps[min(len(ps)-1,i+1)]
                dx,dy=q[0]-p[0],q[1]-p[1]
                length=max(1,math.hypot(dx,dy))
                shifted.append((px-sign*dy/length*6,py+sign*dx/length*6))
            draw.line(shifted,fill=(46,48,47),width=5,joint="curve")
            draw.line(shifted,fill=(209,217,207),width=2,joint="curve")
        # Station location is read from the genuine C++ compiled route.
        station_d=trace["station_distance_m"]
        lengths=[0.0]
        for i in range(1,len(track)):
            lengths.append(lengths[-1]+math.dist(track[i-1],track[i]))
        sidx=min(range(len(lengths)),key=lambda j:abs(lengths[j]-station_d))
        sx,sy=ps[sidx]
        draw.ellipse((sx-11,sy-11,sx+11,sy+11),fill=(244,203,97),outline=(33,35,28),width=3)
        draw.text((sx+14,sy-32),"ESTAÇÃO",font=F12,fill=(246,235,176),stroke_width=2,stroke_fill=(29,43,33))
        # Frame-accurate depth sorting via world ground contact plane.
        for unit in sorted(units,key=lambda u:u["x"]+u["y"]):
            role=unit["kind"]
            view=sprite_view(unit)
            dst=sprites[(role,view)]
            px,py=project(unit["x"],unit["y"],ox,oy)
            _,pivot_x,pivot_y=layout_for(role,view)
            dx=round(px-dst.width*pivot_x/1024)
            dy=round(py-dst.height*pivot_y/1024)
            # subtle contact shadow. Depth placement from actual runtime pose.
            sh=ImageDraw.Draw(im)
            sh.ellipse((px-16,py-4,px+16,py+7),fill=(40,65,47))
            im.paste(dst,(dx,dy),dst)
        draw=ImageDraw.Draw(im)
        draw.rectangle((0,0,W,102),fill=(21,36,32))
        draw.text((34,15),"CITY HORIZON  •  PRIMEIRA VIAGEM",font=F28,fill=(239,236,207))
        draw.text((35,61),"Motor C++ real  |  Trilhos + curva + estação  |  Locomotiva + 7 vagões",font=F12,fill=(185,220,197))
        draw.rounded_rectangle((28,H-87,W-28,H-22),radius=12,fill=(18,33,29))
        phase=("PARADA NA ESTAÇÃO" if frame["dwelling"] else ("EM MOVIMENTO" if frame["speed_mps"]>0.01 else "PARTIDA"))
        draw.text((47,H-70),f"STATUS: {phase}",font=F18,fill=(250,211,125) if frame["dwelling"] else (157,235,177))
        draw.text((409,H-68),f"COMPOSIÇÃO: 1 + {len(units)-1}/7",font=F12,fill=(235,232,209))
        draw.text((745,H-68),f"PERCURSO: {frame['distance_m']:.1f} m",font=F12,fill=(235,232,209))
        draw.text((1038,H-68),f"{frame['time_s']:.1f}s",font=F12,fill=(235,232,209))
        draw.text((33,H-18),"PROVA DO RUNTIME • visualização dos dados reais do motor, não filmagem da tela do jogo",font=font(11),fill=(238,240,221))
        if not poster_saved and n>=int(len(frames)*0.58):
            im.save(out/"locomotiva_trilhos_runtime_preview.png",optimize=True)
            poster_saved=True
        if proc.stdin is None:
            raise RuntimeError("FFmpeg pipe unavailable")
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    result=proc.wait()
    if result!=0 or not target.exists() or target.stat().st_size<10000:
        raise RuntimeError("FFmpeg failed to encode MP4")
    report={
        "contract":"CH_RAIL_LIVE_VIDEO_PROOF_V1",
        "capture_type":trace["capture_type"],
        "origin":"Native C++ TrainRuntime + real approved CH Blender sprites",
        "visual_alignment_contract":"CH_RAIL_VISUAL_ALIGNMENT_V2",
        "full_gameplay_capture":False,
        "frame_count":len(frames),"fps":FPS,
        "route_length_m":trace["route_length_m"],
        "station_distance_m":trace["station_distance_m"],
        "checks":checks,
        "approved_locomotive_asset":loco_manifest["assetId"],
        "approved_coach_asset":coach_manifest["assetId"],
        "video":target.name}
    (out/"rail_video_proof_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--trace",type=Path,required=True)
    ap.add_argument("--outdir",type=Path,required=True)
    args=ap.parse_args()
    render(args.trace,args.outdir)
