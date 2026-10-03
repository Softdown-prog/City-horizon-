#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
REPO_ROOT=HERE.parents[1]
CH_BLENDER=REPO_ROOT/"tools"/"ch_blender"
for p in (HERE,CH_BLENDER):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
import build_scene as bs
import scene_gate

CONTRACT="CH_SWINGING_SHIP_SUPPORT_REFERENCE_V1"
ASSET_ID="attraction.park_viking_ship.support.study"

def args():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--recipe",required=True); p.add_argument("--studio-preset",required=True)
    p.add_argument("--output",required=True); p.add_argument("--save-blend")
    p.add_argument("--stage",choices=("preflight","proxy","final"),default="proxy")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def mat(s): return bs.make_material(s["name"],s["rgba"],float(s.get("roughness",.6)),float(s.get("metallic",0)))

def box(name,loc,dims,m,parent=None,bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1,location=tuple(loc)); o=bpy.context.object; o.name=name
    o.dimensions=tuple(dims); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(m); o.parent=parent
    if bevel:
        b=o.modifiers.new("EdgeBreak","BEVEL"); b.width=bevel; b.segments=2
    return o

def beam(name,a,b,w,d,m,parent):
    a=Vector(a); b=Vector(b); v=b-a
    o=box(name,(a+b)*.5,(w,d,v.length),m,parent,.025)
    o.rotation_mode='QUATERNION'; o.rotation_quaternion=v.to_track_quat('Z','Y')
    return o

def cyl(name,loc,r,depth,m,parent,rot=(math.pi/2,0,0)):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; o.data.materials.append(m); o.parent=parent
    b=o.modifiers.new("MachinedEdge","BEVEL"); b.width=.06; b.segments=3
    return o

def build(root,cfg,M):
    s=cfg["structure"]; L=float(s["stationLength"]); W=float(s["stationWidth"]); dz=float(s["deckZ"])
    tx=float(s["towerX"]); ty=float(s["towerY"]); pz=float(s["pivotZ"])
    lw=float(s["legWidth"]); ld=float(s["legDepth"]); bw=float(s["crossBraceWidth"])
    box("StationDeck",(0,0,dz*.5),(L,W,dz),M["deck"],root,.10)
    # Four independent tapered tower legs. No arch/crown chain.
    tops={}
    for side in (-1,1):
        for lane in (-1,1):
            key=(side,lane)
            foot=(side*tx,lane*ty,dz)
            top=(side*6.35,lane*5.25,pz)
            tops[key]=top
            beam(f"TowerLeg_{side}_{lane}",foot,top,lw,ld,M["steel"],root)
            box(f"Foot_{side}_{lane}",(foot[0],foot[1],.20),(2.0,1.75,.40),M["steel"],root,.06)
    # Dense X bracing in each end tower creates a real industrial portal rather than the old A-frame silhouette.
    for side in (-1,1):
        x0=side*tx; xt=side*6.35
        levels=[4.0,8.0,12.0,16.0]
        prev=(-1*ty,1*ty)
        for i,z in enumerate(levels):
            t=(z-dz)/(pz-dz); x=x0+(xt-x0)*t; y=ty+(5.25-ty)*t
            box(f"EndTie_{side}_{i}",(x,0,z),(bw,2*y,bw),M["brace"],root,.02)
        # diagonal braces across each end face
        beam(f"EndX_A_{side}",(x0,-ty,3.0),(xt,5.25,pz-1.2),bw,bw,M["brace"],root)
        beam(f"EndX_B_{side}",(x0,ty,3.0),(xt,-5.25,pz-1.2),bw,bw,M["brace"],root)
    # Longitudinal top trusses and axle carrier.
    for lane in (-1,1):
        y=lane*5.25
        beam(f"TopChord_{lane}",(-6.35,y,pz),(6.35,y,pz),.72,.72,M["steel"],root)
        beam(f"LowerChord_{lane}",(-6.35,y,pz-2.1),(6.35,y,pz-2.1),.42,.42,M["brace"],root)
        for x in (-5.0,-2.5,0,2.5,5.0):
            beam(f"TrussDiag_{lane}_{x}",(x-1.2,y,pz-2.1),(x+1.2,y,pz),bw,bw,M["brace"],root)
    # Axle runs across ride depth, with explicit bearing blocks on both structural planes.
    cyl("MainAxle",(0,0,pz),float(s["axleRadius"]),float(s["pivotSpan"]),M["steel"],root)
    for lane in (-1,1):
        y=lane*5.25
        cyl(f"Bearing_{lane}",(0,y,pz),float(s["bearingRadius"]),.72,M["mechanical"],root)
        box(f"BearingPedestal_{lane}",(0,y,pz-1.25),(2.2,1.15,1.7),M["mechanical"],root,.10)
    # Perimeter rail and broad front stair.
    railz=dz+1.05
    for y in (-W*.5,W*.5):
        beam(f"RailLong_{y}",(-L*.5,y,railz),(L*.5,y,railz),.10,.10,M["rail"],root)
    for x in (-L*.5,L*.5):
        beam(f"RailEnd_{x}",(x,-W*.5,railz),(x,W*.5,railz),.10,.10,M["rail"],root)
    for x in [(-L*.5+i*2.0) for i in range(int(L/2)+1)]:
        for y in (-W*.5,W*.5): beam(f"Post_{x}_{y}",(x,y,dz),(x,y,railz),.10,.10,M["rail"],root)
    steps=8
    for i in range(steps):
        box(f"Stair_{i}",(-L*.5-1.8-i*.38,0,.10+i*(dz/steps)),(.78,5.0,.20),M["deck"],root,.025)

def save(p):
    if p:
        q=Path(p).resolve(); q.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(q))

def main():
    a=args(); cfg=load(a.recipe)
    if cfg.get("contract")!=CONTRACT or cfg.get("assetId")!=ASSET_ID: raise RuntimeError("support contract mismatch")
    pol=cfg.get("authoringPolicy",{})
    if pol.get("scope")!="support_only" or pol.get("noGondola") is not True or pol.get("noSegmentedArch") is not True:
        raise RuntimeError("fresh support-only policy required")
    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); res=tuple(map(int,studio["render"]["sourceResolution"]))
    scene=bs.configure_scene(studio,res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:mat(v) for k,v in cfg["materials"].items()}
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0)); root=bpy.context.object; root.name="AssetRoot"
    root["assetId"]=ASSET_ID; root["assetType"]=cfg["assetType"]; root["cameraContract"]="CH_CAMERA_V1"
    root["styleContract"]=cfg["styleContract"]; root["footprint"]="7x6"; root["proceduralContract"]=CONTRACT; root["authoringScope"]="support_only"
    build(root,cfg,M)
    recv=studio["shadowReceiver"]; rm=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1.0)))
    ground=bs.add_box("ShadowReceiverPlane",recv["location"],[28,21,float(recv["dimensions"][2])],rm,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    for o in authored: o["runtimeLayer"]="static_base"
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.14); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={"contract":CONTRACT,"assetId":ASSET_ID,"stage":"support_reference_proxy","modelingMethod":"independent_trussed_towers_no_arch_no_gondola","cameraContract":"CH_CAMERA_V1","footprint":cfg["footprint"],"blenderVersion":bpy.app.version_string}
    (out/"studio_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=cfg["footprint"],profile=profile,asset_id=ASSET_ID,report_path=out/"preflight_report.json")
    scene_gate.require_pass(pre)
    if a.stage=="preflight": save(a.save_blend); return
    if a.stage=="proxy":
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET_ID,direction="south")
        (out/"proxy_report.json").write_text(json.dumps(proxy,indent=2),encoding="utf-8"); save(a.save_blend); return
    raise RuntimeError("final blocked until support silhouette is approved")
if __name__=="__main__": main()
