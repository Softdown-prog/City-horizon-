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
def cyl_x(n,loc,r,depth,m,parent):
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=depth,location=loc,rotation=(0,math.pi/2,0))
    o=bpy.context.object;o.name=n;o.data.materials.append(m);o.parent=parent;return o
def round_mast(n,a,b,r,m,parent):
    a=Vector(a); b=Vector(b); v=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=48,radius=r,depth=v.length,location=tuple((a+b)*.5))
    o=bpy.context.object; o.name=n; o.data.materials.append(m); o.parent=parent
    o.rotation_mode='QUATERNION'; o.rotation_quaternion=v.to_track_quat('Z','Y')
    bev=o.modifiers.new("MastEdge","BEVEL"); bev.width=.035; bev.segments=2
    return o

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
    d=c["dimensions"]; pz=d["pivotZ"]; sy=d["sideFrameHalfY"]; lx=d["sideLegHalfX"]; cz=d["shipCenterZ"]
    for y,label in ((-sy,"NearSide"),(sy,"FarSide")):
        apex=(0,y,pz)
        beam(label+"_FrontLeg",(-lx,y,0.25),apex,1.0,1.0,M["structure"],root)
        beam(label+"_RearLeg",(lx,y,0.25),apex,1.0,1.0,M["structure"],root)
        beam(label+"_LowTie",(-lx*.72,y,5.0),(lx*.72,y,5.0),.40,.40,M["truss"],root)
        beam(label+"_MidTie",(-lx*.46,y,11.2),(lx*.46,y,11.2),.34,.34,M["truss"],root)
    beam("TransversePivotAxle",(0,-sy,pz),(0,sy,pz),1.05,1.05,M["structure"],root)
    for y,label in ((-sy,"Near"),(sy,"Far")):
        cyl_x(label+"BearingHousing",(0,y,pz),1.35,1.10,M["truss"],root)
    attach_z=cz+.35; attach_x=d["shipLength"]*.40
    for y,label in ((-1.2,"NearPendulum"),(1.2,"FarPendulum")):
        beam(label+"_BowMain",(0,y,pz),(-attach_x,y,attach_z),.62,.62,M["truss"],root)
        beam(label+"_SternMain",(0,y,pz),(attach_x,y,attach_z),.62,.62,M["truss"],root)
        beam(label+"_BowInner",(0,y,pz-1.0),(-attach_x*.72,y,attach_z+.2),.28,.28,M["truss"],root)
        beam(label+"_SternInner",(0,y,pz-1.0),(attach_x*.72,y,attach_z+.2),.28,.28,M["truss"],root)
        for k in range(1,5):
            t=k/5
            bx=-attach_x*t; sx=attach_x*t; z=pz+(attach_z-pz)*t
            beam(label+"_BowTie"+str(k),(bx,y-.22,z),(bx,y+.22,z),.16,.16,M["truss"],root)
            beam(label+"_SternTie"+str(k),(sx,y-.22,z),(sx,y+.22,z),.16,.16,M["truss"],root)
    # Central round pendulum mast: descends from the axle center and carries the ship at its midpoint.
    mast_attach_z=float(d.get("centralMastAttachZ",cz+.45)); mast_r=float(d.get("centralMastRadius",.46))
    round_mast("CentralRoundPendulumMast",(0,0,pz-.55),(0,0,mast_attach_z),mast_r,M["truss"],root)
    cyl_x("CentralPivotCollar",(0,0,pz-.18),mast_r*1.55,1.35,M["structure"],root)
    cyl_x("CentralShipMount",(0,0,mast_attach_z),mast_r*1.35,1.80,M["truss"],root)
    hull(root,M,d["shipLength"],d["shipHalfWidth"],cz)
    deckZ=d["deckZ"];box("BoardingDeck",(0,-5.15,deckZ*.5),(18.5,2.4,deckZ),M["deck"],root,.08)
    beam("DeckOuterRail",(-9.0,-6.25,deckZ+1),(9.0,-6.25,deckZ+1),.10,.10,M["rail"],root)
    for x in range(-8,9,2): beam("DeckPost"+str(x),(x,-6.25,deckZ),(x,-6.25,deckZ+1),.10,.10,M["rail"],root)

def main():
    a=argv();c=load(a.recipe)
    forbidden=c.get("forbiddenTopology",[])
    if c.get("contract")!=CONTRACT or "end_portals_at_bow_and_stern" not in forbidden: raise RuntimeError("corrected clean reference contract required")
    studio=bs.load_json(a.studio_preset);out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene();scene=bs.configure_scene(studio,tuple(map(int,studio["render"]["sourceResolution"])),str(out));scene.render.film_transparent=True;scene.render.image_settings.color_mode='RGBA'
    M={k:material(v) for k,v in c["materials"].items()}
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0));root=bpy.context.object;root.name="AssetRoot";root["assetId"]=ASSET;root["cameraContract"]="CH_CAMERA_V1";root["styleContract"]=c["styleContract"];root["footprint"]="7x6";root["proceduralContract"]=CONTRACT
    build(root,c,M)
    recv=studio["shadowReceiver"];rm=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1)))
    ground=bs.add_box("ShadowReceiverPlane",recv["location"],[28,20,float(recv["dimensions"][2])],rm,0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.14);bs.set_direction(root,bs.DIRECTIONS[0]);bpy.context.view_layer.update()
    (out/"studio_metadata.json").write_text(json.dumps({"contract":CONTRACT,"assetId":ASSET,"modelingMethod":"two_side_A_frames_central_transverse_axle_auxiliary_trusses_plus_round_center_mast","reference":"user supplied real ride photos"},indent=2))
    profile=scene_gate.load_profile(a.preflight_profile);pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=c["footprint"],profile=profile,asset_id=ASSET,report_path=out/"preflight_report.json");scene_gate.require_pass(pre)
    if a.stage=="proxy":
        rep=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET,direction="south");(out/"proxy_report.json").write_text(json.dumps(rep,indent=2))
    if a.save_blend:
        q=Path(a.save_blend).resolve();q.parent.mkdir(parents=True,exist_ok=True);bpy.ops.wm.save_as_mainfile(filepath=str(q))
if __name__=="__main__":main()
