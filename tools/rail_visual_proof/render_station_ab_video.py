#!/usr/bin/env python3
"""A/B shuttle video proof: real C++ poses, approved station/train PNGs.
This is a composited runtime trace, not a screen recording of City Horizon.
"""
import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"/"rail_visual_proof"))
from render_live_train_video import images_for, layout_for, sprite_view
W,H,FPS=1280,720,16
ZOOM=0.20
def proj(x,y):
    return W*.5+(x-y)*64*ZOOM, H*.48+(x+y)*32*ZOOM

def font(size):
    try:return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",size)
    except OSError:return ImageFont.load_default()

def main(trace_path,outdir):
    data=json.loads(trace_path.read_text())
    assert data["contract"]=="CH_RAIL_A_B_PROOF_V1"
    frames=data["frames"]
    assert len(frames)==640 and data["fps"]==FPS
    checks=data["checks"]
    assert checks["visits_a"]>=2 and checks["visits_b"]>=1 and checks["reversals"]>=2
    assert checks["full_consist_frames"]==len(frames) and checks["max_coupler_gap_m"]<.75
    stations=data["stations"]
    assert [s["name"] for s in stations]==["A","B"]
    root=(ROOT/"assets"/"buildings"/"rail_terminal_station_b_5x3_01")
    manifest=json.loads((root/"station_runtime_manifest.json").read_text())
    assert manifest["contract"]=="CH_RAIL_TERMINAL_STATION_ASSET_V1"
    station_images={}
    for view in ("north","south"):
        info=manifest["sprites"][view]
        path=ROOT/info["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==info["sha256"]
        station_images[view]=Image.open(path).convert("RGBA").resize((245,245),Image.Resampling.LANCZOS)
    loco,_=images_for("locomotive")
    coach,_=images_for("coach")
    sprites={}
    for role,variants in (("locomotive",loco),("coach",coach)):
        for view,im in variants.items():
            size=round(layout_for(role,view)[0]*ZOOM)
            sprites[(role,view)]=im.resize((size,size),Image.Resampling.LANCZOS)
    # Fixed camera keeps BOTH stations readable in one common rail map.
    mid_x=(stations[0]["x"]+stations[1]["x"])*.5
    mid_y=(stations[0]["y"]+stations[1]["y"])*.5
    shift_x=(mid_x-mid_y)*64*ZOOM
    shift_y=(mid_x+mid_y)*32*ZOOM
    def p(x,y):
        sx,sy=proj(x,y)
        return sx-shift_x,sy-shift_y
    track=[p(x,y) for x,y in data["track"]]
    base=Image.new("RGB",(W,H),(88,120,83))
    canvas=ImageDraw.Draw(base)
    for v in range(-90,100,4):
        canvas.line((p(v,-35),p(v,45)),fill=(95,130,90),width=1)
        canvas.line((p(-90,v),p(100,v)),fill=(95,130,90),width=1)
    canvas.line(track,fill=(72,63,51),width=14)
    canvas.line(track,fill=(139,121,93),width=10)
    for i in range(0,len(track)-2,5):
        px,py=track[i];qx,qy=track[i+2]
        dx,dy=qx-px,qy-py;length=max(1,math.hypot(dx,dy))
        nx,ny=-dy/length,dx/length
        canvas.line((px-nx*9,py-ny*9,px+nx*9,py+ny*9),fill=(72,51,32),width=4)
    for sign in (-1,1):
        pts=[]
        for i,(x,y) in enumerate(track):
            x0,y0=track[max(0,i-1)];x1,y1=track[min(len(track)-1,i+1)]
            dx,dy=x1-x0,y1-y0;l=max(1,math.hypot(dx,dy))
            pts.append((x-sign*dy/l*4,y+sign*dx/l*4))
        canvas.line(pts,fill=(211,216,205),width=2)
    station_items=[]
    for station,view in zip(stations,("north","north")):
        x,y=p(station["x"],station["y"]+2.4)
        station_items.append((station,station_images[view],int(x-122),int(y-171)))
    outdir.mkdir(parents=True,exist_ok=True)
    target=outdir/"estacoes_A_B_viagem_completa.mp4"
    ffmpeg=["ffmpeg","-y","-hide_banner","-loglevel","error","-f","rawvideo","-pix_fmt","rgb24",
            "-s",f"{W}x{H}","-r",str(FPS),"-i","-","-an","-c:v","libx264","-preset","veryfast",
            "-crf","23","-pix_fmt","yuv420p","-movflags","+faststart",str(target)]
    proc=subprocess.Popen(ffmpeg,stdin=subprocess.PIPE)
    titlefont=font(28);bodyfont=font(17)
    try:
        for n,frame in enumerate(frames):
            im=base.copy()
            # Occlusion by ground contact order; station alpha comes from CH Blender.
            objects=[]
            for station,sprite,x,y in station_items:
                objects.append((station["x"]+station["y"]+2.4,0,sprite,x,y))
            for unit in frame["units"]:
                role=unit["kind"]
                view=sprite_view(unit,loco if role=="locomotive" else coach)
                sprite=sprites[(role,view)]
                px,py=p(unit["x"],unit["y"])
                _,pivot_x,pivot_y=layout_for(role,view)
                x=round(px-sprite.width*pivot_x/1024)
                y=round(py-sprite.height*pivot_y/1024)
                objects.append((unit["x"]+unit["y"],1,sprite,x,y))
            for _,_,sprite,x,y in sorted(objects,key=lambda v:(v[0],v[1])):
                im.paste(sprite,(x,y),sprite)
            draw=ImageDraw.Draw(im)
            for station in stations:
                px,py=p(station["x"],station["y"]+4)
                draw.rounded_rectangle((px-44,py+4,px+44,py+31),radius=5,fill=(30,43,37))
                draw.text((px-36,py+7),"ESTAÇÃO "+station["name"],fill=(255,234,172),font=bodyfont)
            draw.rectangle((0,0,W,90),fill=(24,37,34))
            draw.text((30,13),"CITY HORIZON  |  ESTAÇÕES A ↔ B",font=titlefont,fill=(242,237,209))
            draw.text((31,57),"Duas instâncias do mesmo asset 5×3  •  poses reais do motor C++  •  trem + 7 vagões",
                      font=bodyfont,fill=(197,216,202))
            draw.rectangle((0,H-65,W,H),fill=(24,37,34))
            phase="PARADO NA ESTAÇÃO" if frame["dwelling"] else ("A → B" if frame["direction"]>0 else "B → A")
            draw.text((30,H-47),f"ESTADO: {phase}",font=bodyfont,fill=(241,219,144))
            draw.text((520,H-47),f"Quadro {n+1}/640",font=bodyfont,fill=(230,235,222))
            draw.text((810,H-47),f"Tempo: {frame['time_s']:.1f}s",font=bodyfont,fill=(230,235,222))
            draw.text((28,H-20),"Prova por composição de dados C++ — não é captura da janela do jogo",
                      font=font(12),fill=(183,201,185))
            if n==320:im.save(outdir/"estacoes_A_B_preview.png")
            if proc.stdin is None:raise RuntimeError("encoder stdin unavailable")
            proc.stdin.write(im.tobytes())
    finally:
        if proc.stdin is not None:proc.stdin.close()
    if proc.wait()!=0 or not target.is_file() or target.stat().st_size<10000:
        raise RuntimeError("ffmpeg did not generate MP4")
    report={"contract":data["contract"],"capture_type":data["capture_type"],"frame_count":len(frames),
            "fps":FPS,"stations":stations,"checks":checks,"video":target.name,
            "full_gameplay_capture":False,"station_asset_id":manifest["assetId"]}
    (outdir/"estacoes_A_B_relatorio.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--trace",required=True,type=Path)
    parser.add_argument("--outdir",required=True,type=Path)
    args=parser.parse_args()
    main(args.trace,args.outdir)
