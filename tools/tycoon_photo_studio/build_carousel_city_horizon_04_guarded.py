#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CH=ROOT/"tools"/"ch_blender"
for p in (HERE,CH):
    if str(p) not in sys.path: sys.path.insert(0,str(p))
import build_scene as bs
import scene_gate

CONTRACT="CITY_HORIZON_CAROUSEL_V4"
ASSET_ID="attraction.park_carousel_city_horizon_04"

def args():
    av=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p=argparse.ArgumentParser()
    p.add_argument("--recipe",required=True)
    p.add_argument("--studio-preset",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--save-blend")
    p.add_argument("--stage",choices=("preflight","proxy","final"),default="preflight")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def mat(name,s):
    return bs.make_material(name,s["rgba"],float(s.get("roughness",.65)),float(s.get("metallic",0)))

def empty(name,parent=None):
    o=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(o); o.parent=parent; return o

def cube(name,parent,loc,dims,m,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    o=bpy.context.object; o.name=name; o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(m); o.parent=parent
    if bevel:
        q=o.modifiers.new("SoftEdge","BEVEL"); q.width=bevel; q.segments=2
    return o

def cyl(name,parent,loc,radius,depth,m,verts=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius,depth=depth,location=loc)
    o=bpy.context.object; o.name=name; o.data.materials.append(m); o.parent=parent; return o

def sphere(name,parent,loc,scale,m):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=18,ring_count=10,radius=1,location=loc)
    o=bpy.context.object; o.name=name; o.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.data.materials.append(m); o.parent=parent
    for p in o.data.polygons: p.use_smooth=True
    return o

def between(name,parent,a,b,r,m,verts=10):
    a=Vector(a); b=Vector(b); v=b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=v.length,location=(a+b)*.5)
    o=bpy.context.object; o.name=name; o.rotation_euler=v.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(m); o.parent=parent; return o

def roof_wedge(name,parent,a0,a1,r0,r1,zi,zo,t,m):
    top=[(r0*math.cos(a0),r0*math.sin(a0),zi),(r0*math.cos(a1),r0*math.sin(a1),zi),
         (r1*math.cos(a1),r1*math.sin(a1),zo),(r1*math.cos(a0),r1*math.sin(a0),zo)]
    bot=[(x,y,z-t) for x,y,z in top]
    verts=top+bot
    faces=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.parent=parent; o.data.materials.append(m); return o

def ring_sector(name,parent,a0,a1,r0,r1,z0,z1,m):
    pts=[]
    for z in (z0,z1):
        pts += [(r0*math.cos(a0),r0*math.sin(a0),z),(r0*math.cos(a1),r0*math.sin(a1),z),
                (r1*math.cos(a1),r1*math.sin(a1),z),(r1*math.cos(a0),r1*math.sin(a0),z)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(pts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.parent=parent; o.data.materials.append(m); return o

def horse(i,parent,angle,r,z,s,M):
    root=empty(f"Horse_{i:02d}",parent)
    root.location=(r*math.cos(angle),r*math.sin(angle),0)
    root.rotation_euler[2]=angle+math.pi*.5
    cyl(f"Pole_{i:02d}",root,(0,0,1.48),.03,1.72,M["gold"],10)
    sphere(f"Body_{i:02d}",root,(0,0,z),(.43*s,.17*s,.23*s),M["horse"])
    neck=sphere(f"Neck_{i:02d}",root,(.36*s,0,z+.28*s),(.12*s,.10*s,.28*s),M["horse"])
    neck.rotation_euler[1]=math.radians(-20)
    sphere(f"Head_{i:02d}",root,(.56*s,0,z+.45*s),(.20*s,.12*s,.13*s),M["horse"])
    sphere(f"Mane_{i:02d}",root,(.24*s,0,z+.28*s),(.075*s,.13*s,.22*s),M["brown"])
    cube(f"Saddle_{i:02d}",root,(-.02*s,0,z+.20*s),(.29*s,.23*s,.07*s),M["red"],.02)
    between(f"Tail_{i:02d}",root,(-.38*s,0,z+.02*s),(-.58*s,0,z-.13*s),.04*s,M["brown"])
    pose=1 if i%2==0 else -1
    legs=[((.22*s,-.09*s,z-.09*s),(.44*s,-.09*s,z-.43*s-.04*pose)),
          ((.15*s,.09*s,z-.09*s),(.00*s,.09*s,z-.46*s+.04*pose)),
          ((-.20*s,-.09*s,z-.08*s),(-.42*s,-.09*s,z-.40*s+.04*pose)),
          ((-.18*s,.09*s,z-.08*s),(-.02*s,.09*s,z-.46*s-.04*pose))]
    for n,(a,b) in enumerate(legs): between(f"Leg_{i:02d}_{n}",root,a,b,.042*s,M["horse"])

def build(recipe,studio,out):
    bs.clear_scene()
    scene=bs.configure_scene(studio,tuple(map(int,studio["render"]["sourceResolution"])),str(out))
    scene.render.film_transparent=True; scene.render.image_settings.color_mode="RGBA"
    M={k:mat("Carousel_"+k,v) for k,v in recipe["materials"].items()}
    g=recipe["geometry"]

    root=empty("AssetRoot")
    root["assetId"]=ASSET_ID; root["cameraContract"]="CH_CAMERA_V1"; root["styleContract"]=recipe["styleContract"]
    root["lifecycleStatus"]="draft"; root["exemplarStatus"]="not_approved_exemplar"; root["footprint"]="7x7"

    br=float(g["baseRadius"]); bh=float(g["baseHeight"]); pz=float(g["platformTopZ"])
    cyl("Foundation",root,(0,0,bh*.5),br,bh,M["dark_red"],64)
    cyl("BaseCreamRing",root,(0,0,bh*.60),br+.025,.09,M["cream"],64)
    cyl("BaseGoldLip",root,(0,0,bh+.035),br+.03,.05,M["gold"],64)

    rotor=empty("CarouselRotor",root)
    cyl("PlatformRedDeck",rotor,(0,0,pz-.055),br-.09,.11,M["red"],64)
    cyl("PlatformCreamEdge",rotor,(0,0,pz-.005),br-.03,.045,M["cream"],64)

    cr=float(g["centerColumnRadius"])
    cyl("CenterColumnGold",rotor,(0,0,1.48),cr,1.80,M["gold"],40)
    cyl("CenterColumnRed",rotor,(0,0,1.48),cr*.70,1.65,M["red"],40)

    seg=int(g["canopySegments"]); rr=float(g["canopyRadius"]); r0=float(g["canopyInnerRadius"])
    zo=float(g["canopyOuterZ"]); zi=float(g["canopyInnerZ"]); th=float(g["canopyThickness"])
    for i in range(seg):
        a0=2*math.pi*i/seg; a1=2*math.pi*(i+1)/seg
        roof_wedge(f"Roof_{i:02d}",rotor,a0,a1,r0,rr,zi,zo,th,M["red"] if i%2==0 else M["cream"])
    cyl("RoofCenterCap",rotor,(0,0,zi+.02),.44,.09,M["gold"],36)

    vh=float(g["valanceHeight"]); vs=int(g["valanceSegments"])
    for i in range(vs):
        a0=2*math.pi*i/vs; a1=2*math.pi*(i+1)/vs
        ring_sector(f"ValanceRed_{i:02d}",rotor,a0,a1,rr-.09,rr+.005,zo-vh,zo,M["red"])
    # thin gold separators instead of large gold blocks
    for i in range(vs):
        a=2*math.pi*i/vs; x,y=rr*math.cos(a),rr*math.sin(a)
        sep=cube(f"ValanceGoldSep_{i:02d}",rotor,(x,y,zo-vh*.5),(.045,.08,vh),M["gold"],.005)
        sep.rotation_euler[2]=a+math.pi*.5

    sc=int(g["supportCount"]); sr=float(g["supportRadius"])
    for i in range(sc):
        a=2*math.pi*i/sc; x,y=sr*math.cos(a),sr*math.sin(a)
        cyl(f"Support_{i:02d}",rotor,(x,y,(pz+zo)*.5),.034,zo-pz,M["gold"],10)

    hc=int(g["horseCount"]); hr=float(g["horseRadius"]); hs=float(g["horseScale"]); hz=float(g["horseBodyZ"])
    for i in range(hc): horse(i,rotor,2*math.pi*i/hc,hr,hz,hs,M)

    sw=float(g["stairWidth"]); sd=float(g["stairDepth"]); sh=float(g["stairHeight"]); xo=float(g["stairLateralOffset"])
    y=-(br+sd*.31)
    for idx,x in enumerate((-xo,xo)):
        cube(f"Stair_{idx}_Lower",root,(x,y,sh*.22),(sw,sd,sh*.44),M["red"],.02)
        cube(f"Stair_{idx}_Upper",root,(x,y+sd*.24,sh*.63),(sw,sd*.56,sh*.34),M["red"],.02)
        for side in (-1,1):
            cube(f"Stair_{idx}_Rail_{side}",root,(x+side*sw*.51,y+.04,sh*.61),(.055,sd*.76,.48),M["gold"],.015)

    cyl("CrownStem",rotor,(0,0,zi+.40),.043,.72,M["gold"],10)
    sphere("CrownBall",rotor,(0,0,zi+.77),(.09,.09,.09),M["gold"])
    flag=cube("Flag",rotor,(.19,0,zi+.69),(.31,.025,.14),M["red"],.008); flag.rotation_euler[2]=.12

    recv=studio["shadowReceiver"]; rm=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1)))
    ground=bs.add_box("ShadowReceiverPlane",recv["location"],recv["dimensions"],rm,0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.14); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    return scene,root,ground,authored

def main():
    a=args(); recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=CONTRACT: raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V4 recipe")
    if recipe.get("lifecycle",{}).get("status")!="draft": raise RuntimeError("V4 must remain draft")
    if recipe.get("lifecycle",{}).get("exemplarStatus")!="not_approved_exemplar": raise RuntimeError("Draft must not be exemplar")
    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    scene,root,ground,authored=build(recipe,studio,out)
    (out/"draft_metadata.json").write_text(json.dumps({
      "contract":"CH_CAROUSEL_DRAFT_METADATA_V1","assetId":ASSET_ID,"status":"draft",
      "exemplarStatus":"not_approved_exemplar","reference":recipe["reference"],"designIntent":recipe["designIntent"]
    },indent=2),encoding="utf-8")
    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=recipe["footprint"],profile=profile,asset_id=ASSET_ID,report_path=out/"preflight_report.json")
    scene_gate.require_pass(pre)
    if a.stage=="proxy":
        rep=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET_ID,direction="south")
        (out/"proxy_report.json").write_text(json.dumps(rep,indent=2),encoding="utf-8")
        print(f"[CH_GATE] Carousel V4 proxy ready: {rep['sha256']}")
    elif a.stage=="preflight":
        print("[CH_GATE] Carousel V4 preflight PASS")
    else:
        raise RuntimeError("CH_FINAL_BLOCKED_DRAFT: explicit human approval required")
    if a.save_blend:
        p=Path(a.save_blend).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))
if __name__=="__main__": main()
