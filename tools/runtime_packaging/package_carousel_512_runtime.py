#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
BEAUTY=ROOT/"out"/"carousel512_source"/"beauty"
MASK=ROOT/"out"/"carousel512_source"/"mask"
DEST=ROOT/"assets"/"city_park"/"carousel"/"runtime512"
DEF=ROOT/"assets"/"definitions"/"park_carousel_01.json"
MAN=ROOT/"assets"/"city_park"/"carousel"/"park_carousel_01_runtime_manifest.json"
DIRS=("south","east","west","north")
FRAME_SIZE=512
COLS=8
ROWS=6
FRAMES=48

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def one(root:Path, pattern:str)->Path:
    hits=list(root.rglob(pattern))
    if len(hits)!=1:
        raise RuntimeError(f"{pattern}: expected one file, got {len(hits)}")
    return hits[0]

def resize_mask(src:Image.Image)->Image.Image:
    src=src.convert("RGBA")
    r,g,b,a=src.split()
    r=r.resize((FRAME_SIZE,FRAME_SIZE),Image.Resampling.LANCZOS)
    g=g.resize((FRAME_SIZE,FRAME_SIZE),Image.Resampling.LANCZOS)
    a=a.resize((FRAME_SIZE,FRAME_SIZE),Image.Resampling.LANCZOS)
    # Preserve mutually exclusive stripe families after downsampling.
    rp=r.load(); gp=g.load(); ap=a.load()
    out=Image.new("RGBA",(FRAME_SIZE,FRAME_SIZE),(0,0,0,0))
    op=out.load()
    for y in range(FRAME_SIZE):
        for x in range(FRAME_SIZE):
            alpha=ap[x,y]
            if alpha==0:
                continue
            if rp[x,y]>=gp[x,y]:
                op[x,y]=(255,0,0,alpha)
            else:
                op[x,y]=(0,255,0,alpha)
    return out

def build(kind:str, source:Path, direction:str)->Path:
    atlas=Image.new("RGBA",(FRAME_SIZE*COLS,FRAME_SIZE*ROWS),(0,0,0,0))
    for frame in range(1,FRAMES+1):
        p=one(source,f"{kind}_{direction}_f{frame:02d}.png")
        img=Image.open(p).convert("RGBA")
        if img.size!=(1280,1280):
            raise RuntimeError(f"{p}: expected 1280x1280, got {img.size}")
        img=resize_mask(img) if kind=="mask" else img.resize((FRAME_SIZE,FRAME_SIZE),Image.Resampling.LANCZOS)
        i=frame-1
        atlas.paste(img,((i%COLS)*FRAME_SIZE,(i//COLS)*FRAME_SIZE))
    suffix="mask_animation_512_atlas" if kind=="mask" else "animation_512_atlas"
    out=DEST/f"park_carousel_01_{direction}_{suffix}.png"
    atlas.save(out,"PNG",optimize=True,compress_level=9)
    return out

def main():
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    beauty={}
    masks={}
    for d in DIRS:
        beauty[d]=build("beauty",BEAUTY,d)
        masks[d]=build("mask",MASK,d)

    definition=json.loads(DEF.read_text(encoding="utf-8"))
    rel=lambda p:p.relative_to(ROOT).as_posix()
    definition["texture"]=rel(beauty["south"])
    mapping={"0":"south","1":"west","2":"north","3":"east"}
    definition["sprites"]={k:rel(beauty[d]) for k,d in mapping.items()}
    definition["animation"]={
        "layout":"grid","columns":COLS,"rows":ROWS,
        "frameCount":FRAMES,"frameDurationMs":125,"playback":"loop"
    }
    definition["artScale"]=round(1.0111*(1280/FRAME_SIZE),6)
    definition["renderClass"]="large_asset_512_animated_grid"
    definition["productionStatus"]="runtime_animated_512_four_direction_color_mask_enabled"
    definition["sourceWorkflowRun"]=37495772742
    definition["sourceAuthoringAssetId"]="attraction.park_carousel_city_horizon_06"
    cm=definition.setdefault("colorMask",{})
    cm["contract"]="CH_COLOR_MASK_V1"
    cm["enabled"]=True
    cm["channels"]={"R":"canopy_primary_stripes","G":"canopy_secondary_stripes"}
    cm["alpha"]="coverage"
    cm["sprites"]={k:rel(masks[d]) for k,d in mapping.items()}
    definition["colorCustomizationStatus"]="runtime_enabled_animated_ch_color_mask_v1"
    DEF.write_text(json.dumps(definition,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

    manifest={
      "contract":"CH_CITY_PARK_ANIMATED_ASSET_V1",
      "assetId":"park_carousel_01",
      "displayName":"Carrossel",
      "category":"city_park",
      "subtype":"amusement_ride_rotating",
      "format":"PNG_RGBA",
      "masterFrameSize":[1280,1280],
      "runtimeFrameSize":[FRAME_SIZE,FRAME_SIZE],
      "atlasLayout":{"columns":COLS,"rows":ROWS,"width":FRAME_SIZE*COLS,"height":FRAME_SIZE*ROWS},
      "animation":{"rotationContract":"CH_CAROUSEL_ROTATION_V1","frameCount":FRAMES,
                   "frameDurationMs":125,"fps":8,"rotationPeriodSeconds":6,
                   "angularStepDegrees":7.5,"loopClosureFrame":49,"loopClosureExported":False},
      "directionOrder":["south","east","west","north"],
      "runtimeRepresentation":"2D_RGBA_grid_atlas_four_direction_lazy_loaded",
      "footprint":{"widthTiles":7,"depthTiles":7},
      "beautyAtlases":{d:{"file":rel(beauty[d]),"sha256":sha256(beauty[d]),"bytes":beauty[d].stat().st_size} for d in DIRS},
      "colorMask":{
        "contract":"CH_COLOR_MASK_V1","animated":True,"frameSize":[FRAME_SIZE,FRAME_SIZE],
        "channels":{"R":"canopy_primary_stripes","G":"canopy_secondary_stripes","B":"unused"},
        "alpha":"coverage",
        "atlases":{d:{"file":rel(masks[d]),"sha256":sha256(masks[d]),"bytes":masks[d].stat().st_size} for d in DIRS}
      },
      "sourceAuthoringAssetId":"attraction.park_carousel_city_horizon_06",
      "beautySource":{"workflowRun":37495772742,"artifactId":11434668419},
      "maskSource":{"workflowRun":37517771764,"artifactId":11443920850,
                    "note":"All 192 mask frames were present; workflow failure was limited to non-SOUTH proxy-report validation."},
      "approvedForRuntime":True,
      "approvalScope":"48_frame_rotation_and_512_runtime_packaging",
      "status":"runtime_animated_512_four_direction_color_mask_enabled"
    }
    MAN.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

    total=sum(p.stat().st_size for p in beauty.values())+sum(p.stat().st_size for p in masks.values())
    if total>30*1024*1024:
        raise RuntimeError(f"Runtime carousel package too large: {total} bytes")
    print(json.dumps({"status":"ok","totalBytes":total,
                      "beautyBytes":sum(p.stat().st_size for p in beauty.values()),
                      "maskBytes":sum(p.stat().st_size for p in masks.values())},indent=2))

if __name__=="__main__":
    main()
