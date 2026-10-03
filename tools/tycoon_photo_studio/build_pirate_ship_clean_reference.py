#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]; CH=ROOT/"tools"/"ch_blender"
for p in (HERE,CH):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
import build_scene as bs
import scene_gate
CONTRACT="CH_PIRATE_SHIP_CLEAN_REFERENCE_V1"; ASSET="attraction.park_pirate_ship.clean_reference"

def argv():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    for n in ("recipe","studio-preset","output"): p.add_argument("--"+n,required=True)
    p.add_argument("--save-blend"); p.add_argument("--stage",default="proxy"); p.add_argument("--preflight-profile")
    return p.parse_args(av)
def load(p): return json.loads(Path(p).read_text())
def material(s): return bs.make_material(s["name"],s["rgba"],float(s.get("roughness",.6)),float(s.get("metallic",0)))
def box(n,loc,dims,m,parent,b=.04):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object;o.name=n;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(m);o.parent=parent
    if b: q=o.modifiers.new("EdgeBreak","BEVEL");q.width=b;q.segments=2
    return o
def beam(n,a,b,w,d,m,parent):
    a=Vector(a);b=Vector(b);v=b-a;o=box(n,(a+b)*.5,(w,d,v.length),m,parent,.03)
    o.rotation_mode='QUATERNION';o.rotation_quaternion=v.to_track_quat('Z','Y');return o
def cyl(n,loc,r,depth,m,parent):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=(math.pi/2,0,0))
    o=bpy.context.object;o.name=n;o.data.materials.append(m);o.parent=parent;return o

def hull(root,M,L,HW,cz):
    xs=[-L/2,-L*.43,-L*.30,-L*.12,0,L*.12,L*.30,L*.43,L/2]
    rings=[]
    for x in xs:
        u=abs(x)/(L/2); hw=max(.38,HW*(1-u**2)**.48)
        keel=cz-2.5+3.5*u**2; gun=cz+1.0+2.4*u**2
        rings.append([(x,0,keel),(x,-hw*.72,cz-1.05+1.6*u),(x,-hw,gun),(x,hw,gun),(x,hw*.72,cz-1.05+1.6*u)])
    verts=[v for r in rings for v in r];faces=[];n=5
    for i in range(len(rings)-1):
        a=i*n;b=(i+1)*n
        faces += [(a,a+1,b+1,b),(a+1,a+2,b+2,b+1),(a+3,a+4,b+4,b+3),(a+4,a,b,b+4)]
    faces += [(0,1,2,3,4),tuple(range((len(rings)-1)*5,(len(rings))*5))]
    me=bpy.data.meshes.new("ShipHullMesh");me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new("DominantPassengerShip",me);bpy.context.scene.collection.objects.link(o);o.data.materials.append(M["hull"]);o.parent=root
    q=o.modifiers.new("HullSoftening","BEVEL");q.width=.12;q.segments=3
    for i,x in enumerate([-7.0,-5.6,-4.2,-2.8,-1.4,0,1.4,2.8,4.2,5.6,7.0]):
        box("Seat_%02d"%i,(x,0,cz+.65),(.52,HW*1.55,.28),M["seat"],root,.05)
        box("SeatBack_%02d"%i,(x+.18,0,cz+1.18),(.16,HW*1.50,.80),M["seat"],root,.04)
    return o

def build(root,c,M):
    d=c["dimensions"];pz=d["pivotZ"];px=d["portalHalfX"];py=d["portalHalfY"];cz=d["shipCenterZ"]
    # Two END portals only: each end is an A, leaving the entire longitudinal swing volume open.
    for x,label in ((-px,"LeftEnd"),(px,"RightEnd")):
        apex=(x,0,pz)
        for y,s in ((-py,"Near"),(py,"Far")):
            beam(label+"_"+s+"Leg",(x,y,0.25),apex,1.0,1.0,M["structure"],root)
        beam(label+"_LowTie",(x,-py*.72,5.0),(x,py*.72,5.0),.38,.38,M["truss"],root)
        beam(label+"_MidTie",(x,-py*.48,11.0),(x,py*.48,11.0),.34,.34,M["truss"],root)
    # High cross axle between end portal apexes: visually one pivot line, not a surrounding cage.
    beam("HighPivotCarrier",(-px,0,pz),(px,0,pz),.95,.95,M["structure"],root)
    cyl("NearBearing",(-px,0,pz),1.35,1.0,M["truss"],root);cyl("FarBearing",(px,0,pz),1.35,1.0,M["truss"],root)
    # Two long pendulum trusses descend from axle ends to ship attachment points.
    attachZ=cz+.25
    for x,label in ((-px,"Left"),(px,"Right")):
        beam(label+"PendulumMain",(x,0,pz),(x*.58,0,attachZ),.72,.72,M["truss"],root)
        beam(label+"PendulumRear",(x,0,pz),(x*.40,0,attachZ+.2),.38,.38,M["truss"],root)
        for k in range(1,6):
            t=k/6; z=pz+(attachZ-pz)*t; xa=x+(x*.58-x)*t; xb=x+(x*.40-x)*t
            beam(label+"PendulumTie"+str(k),(xa,0,z),(xb,0,z),.22,.22,M["truss"],root)
    hull(root,M,d["shipLength"],d["shipHalfWidth"],cz)
    # independent boarding deck below ship; deliberately not structural support.
    deckZ=d["deckZ"];box("BoardingDeck",(0,-4.75,deckZ*.5),(22.5,3.0,deckZ),M["deck"],root,.08)
    for x in (-11.0,11.0): beam("DeckEndRail"+str(x),(x,-6.15,deckZ+1),(x,-3.35,deckZ+1),.1,.1,M["rail"],root)
    beam("DeckOuterRail",(-11,-6.15,deckZ+1),(11,-6.15,deckZ+1),.1,.1,M["rail"],root)
    for x in range(-10,11,2): beam("DeckPost"+str(x),(x,-6.15,deckZ),(x,-6.15,deckZ+1),.1,.1,M["rail"],root)

def main():
    a=argv();c=load(a.recipe)
    if c.get("contract")!=CONTRACT or "four_post_rectangular_cage" not in c.get("forbiddenTopology",[]): raise RuntimeError("clean reference contract required")
    studio=bs.load_json(a.studio_preset);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene();scene=bs.configure_scene(studio,tuple(map(int,studio["render"]["sourceResolution"])),str(out));scene.render.film_transparent=True;scene.render.image_settings.color_mode='RGBA'
    M={k:material(v) for k,v in c["materials"].items()}
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0));root=bpy.context.object;root.name="AssetRoot";root["assetId"]=ASSET;root["cameraContract"]="CH_CAMERA_V1";root["styleContract"]=c["styleContract"];root["footprint"]="7x6";root["proceduralContract"]=CONTRACT
    build(root,c,M)
    recv=studio["shadowReceiver"];rm=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1)))
    ground=bs.add_box("ShadowReceiverPlane",recv["location"],[28,20,float(recv["dimensions"][2])],rm,0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.14);bs.set_direction(root,bs.DIRECTIONS[0]);bpy.context.view_layer.update()
    (out/"studio_metadata.json").write_text(json.dumps({"contract":CONTRACT,"assetId":ASSET,"modelingMethod":"two_end_A_portals_open_swing_volume_long_pendulum_trusses","reference":"user supplied real ride photos"},indent=2))
    profile=scene_gate.load_profile(a.preflight_profile);pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=c["footprint"],profile=profile,asset_id=ASSET,report_path=out/"preflight_report.json");scene_gate.require_pass(pre)
    if a.stage=="proxy":
        rep=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET,direction="south");(out/"proxy_report.json").write_text(json.dumps(rep,indent=2))
    if a.save_blend:
        q=Path(a.save_blend).resolve();q.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(q))
if __name__=="__main__":main()
