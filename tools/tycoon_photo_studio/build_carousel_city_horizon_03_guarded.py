#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CH = ROOT / "tools" / "ch_blender"
for p in (HERE, CH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs
import scene_gate

CONTRACT = "CITY_HORIZON_CAROUSEL_V3"
ASSET_ID = "attraction.park_carousel_city_horizon_03"

def args():
    av = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend")
    p.add_argument("--stage", choices=("preflight","proxy","final"), default="preflight")
    p.add_argument("--preflight-profile")
    return p.parse_args(av)

def mat(name, spec):
    return bs.make_material(name, spec["rgba"], float(spec.get("roughness",0.65)), float(spec.get("metallic",0.0)))

def empty(name, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(o)
    o.parent = parent
    return o

def cube(name, parent, loc, dims, material, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.object; o.name = name; o.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material); o.parent = parent
    if bevel:
        m = o.modifiers.new("SoftEdge","BEVEL"); m.width = bevel; m.segments = 2
    return o

def cyl(name, parent, loc, radius, depth, material, vertices=48):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    o = bpy.context.object; o.name = name; o.data.materials.append(material); o.parent = parent
    return o

def sphere(name, parent, loc, scale, material, segments=20, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc)
    o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material); o.parent = parent
    for p in o.data.polygons: p.use_smooth = True
    return o

def cylinder_between(name, parent, a, b, radius, material, vertices=12):
    a = Vector(a); b = Vector(b); v = b-a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=v.length, location=(a+b)*0.5)
    o = bpy.context.object; o.name = name; o.rotation_euler = v.to_track_quat("Z","Y").to_euler()
    o.data.materials.append(material); o.parent = parent
    return o

def radial_wedge(name, parent, a0, a1, r0, r1, z0_inner, z0_outer, thickness, material):
    top=[(r0*math.cos(a0),r0*math.sin(a0),z0_inner),
         (r0*math.cos(a1),r0*math.sin(a1),z0_inner),
         (r1*math.cos(a1),r1*math.sin(a1),z0_outer),
         (r1*math.cos(a0),r1*math.sin(a0),z0_outer)]
    bot=[(x,y,z-thickness) for x,y,z in top]
    verts=top+bot
    faces=[(0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.parent=parent; o.data.materials.append(material)
    return o

def vertical_sector(name, parent, a0, a1, r0, r1, z0, z1, material):
    pts=[]
    for z in (z0,z1):
        pts += [(r0*math.cos(a0),r0*math.sin(a0),z),
                (r0*math.cos(a1),r0*math.sin(a1),z),
                (r1*math.cos(a1),r1*math.sin(a1),z),
                (r1*math.cos(a0),r1*math.sin(a0),z)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(pts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(o); o.parent=parent; o.data.materials.append(material)
    return o

def horse(i, parent, angle, radius, z, s, M):
    root=empty(f"Horse_{i:02d}",parent)
    root.location=(radius*math.cos(angle),radius*math.sin(angle),0.0)
    root.rotation_euler[2]=angle+math.pi*0.5
    cyl(f"HorsePole_{i:02d}",root,(0,0,1.47),0.032,1.72,M["gold"],12)

    sphere(f"HorseBody_{i:02d}",root,(0,0,z),(0.42*s,0.17*s,0.23*s),M["horse"])
    chest=sphere(f"HorseChest_{i:02d}",root,(0.29*s,0,z+0.10*s),(0.19*s,0.15*s,0.24*s),M["horse"])
    neck=sphere(f"HorseNeck_{i:02d}",root,(0.39*s,0,z+0.31*s),(0.13*s,0.115*s,0.31*s),M["horse"])
    neck.rotation_euler[1]=math.radians(-20)
    head=sphere(f"HorseHead_{i:02d}",root,(0.58*s,0,z+0.47*s),(0.21*s,0.13*s,0.14*s),M["horse"])
    head.rotation_euler[1]=math.radians(-8)
    sphere(f"HorseMuzzle_{i:02d}",root,(0.74*s,0,z+0.43*s),(0.10*s,0.09*s,0.08*s),M["cream"],16,8)
    sphere(f"HorseMane_{i:02d}",root,(0.26*s,0,z+0.31*s),(0.08*s,0.14*s,0.25*s),M["brown"],16,8)
    cylinder_between(f"HorseTail_{i:02d}",root,(-0.40*s,0,z+0.03*s),(-0.63*s,0,z-0.15*s),0.045*s,M["brown"],10)

    saddle=cube(f"HorseSaddle_{i:02d}",root,(-0.02*s,0,z+0.22*s),(0.30*s,0.24*s,0.075*s),M["red"],0.03)
    cube(f"HorseSaddleGold_{i:02d}",root,(-0.02*s,0,z+0.26*s),(0.18*s,0.25*s,0.025*s),M["gold"],0.01)

    for ear_n,y in enumerate((-0.07*s,0.07*s)):
        e=cube(f"HorseEar_{i:02d}_{ear_n}",root,(0.52*s,y,z+0.63*s),(0.035*s,0.025*s,0.09*s),M["horse"],0.01)
        e.rotation_euler[1]=math.radians(-18)

    pose=1 if i%2==0 else -1
    legs=[((0.24*s,-0.10*s,z-0.10*s),(0.49*s,-0.10*s,z-0.47*s-0.05*pose)),
          ((0.17*s, 0.10*s,z-0.10*s),(0.00*s, 0.10*s,z-0.49*s+0.05*pose)),
          ((-0.23*s,-0.10*s,z-0.08*s),(-0.47*s,-0.10*s,z-0.42*s+0.05*pose)),
          ((-0.20*s, 0.10*s,z-0.08*s),(-0.03*s, 0.10*s,z-0.49*s-0.05*pose))]
    for n,(a,b) in enumerate(legs):
        cylinder_between(f"HorseLeg_{i:02d}_{n}",root,a,b,0.045*s,M["horse"],10)

def build(recipe, studio, out):
    bs.clear_scene()
    scene=bs.configure_scene(studio,tuple(map(int,studio["render"]["sourceResolution"])),str(out))
    scene.render.film_transparent=True; scene.render.image_settings.color_mode="RGBA"
    M={k:mat("Carousel_"+k,v) for k,v in recipe["materials"].items()}
    g=recipe["geometry"]

    root=empty("AssetRoot")
    root["assetId"]=ASSET_ID; root["cameraContract"]="CH_CAMERA_V1"; root["styleContract"]=recipe["styleContract"]
    root["lifecycleStatus"]="draft"; root["exemplarStatus"]="not_approved_exemplar"; root["footprint"]="7x7"

    base_r=float(g["baseRadius"]); base_h=float(g["baseHeight"]); platform_z=float(g["platformTopZ"])
    foundation=cyl("CarouselFoundation",root,(0,0,base_h*0.5),base_r,base_h,M["dark_red"],64)
    cyl("BaseCreamBand",root,(0,0,base_h*0.58),base_r+0.035,0.11,M["cream"],64)
    cyl("BaseGoldLip",root,(0,0,base_h+0.055),base_r+0.05,0.08,M["gold"],64)

    rotor=empty("CarouselRotor",root)
    cyl("CarouselPlatform",rotor,(0,0,platform_z-0.07),base_r-0.10,0.16,M["red"],64)
    cyl("PlatformOuterTrim",rotor,(0,0,platform_z+0.015),base_r-0.04,0.05,M["cream"],64)

    cr=float(g["centerColumnRadius"])
    cyl("CenterColumn",rotor,(0,0,1.48),cr,1.82,M["gold"],40)
    cyl("CenterColumnCore",rotor,(0,0,1.48),cr*0.72,1.68,M["red"],40)
    cyl("CenterColumnLowerBand",rotor,(0,0,0.76),cr*1.03,0.10,M["cream"],40)
    cyl("CenterColumnUpperBand",rotor,(0,0,2.17),cr*1.03,0.10,M["cream"],40)

    segs=int(g["canopySegments"]); r=float(g["canopyRadius"]); r0=float(g["canopyInnerRadius"])
    zo=float(g["canopyOuterZ"]); zi=float(g["canopyInnerZ"]); th=float(g["canopyThickness"])
    for i in range(segs):
        a0=2*math.pi*i/segs; a1=2*math.pi*(i+1)/segs
        radial_wedge(f"Canopy_{i:02d}",rotor,a0,a1,r0,r,zi,zo,th,M["red"] if i%2==0 else M["cream"])
    cyl("CanopyCenterCap",rotor,(0,0,zi+0.02),0.46,0.10,M["gold"],40)

    vh=float(g["valanceHeight"]); vs=int(g["valanceSegments"])
    for i in range(vs):
        a0=2*math.pi*i/vs; a1=2*math.pi*(i+1)/vs
        vertical_sector(f"Valance_{i:02d}",rotor,a0,a1,r-0.10,r+0.01,zo-vh,zo,M["gold"] if i%4==1 else M["red"])

    sc=int(g["supportCount"]); sr=float(g["supportRadius"])
    for i in range(sc):
        a=2*math.pi*i/sc; x,y=sr*math.cos(a),sr*math.sin(a)
        cyl(f"Support_{i:02d}",rotor,(x,y,(platform_z+zo)*0.5),0.038,zo-platform_z,M["gold"],12)

    hc=int(g["horseCount"]); hs=float(g["horseScale"])
    for i in range(hc):
        rr=float(g["horseOuterRadius"] if i%2==0 else g["horseInnerRadius"])
        horse(i,rotor,2*math.pi*i/hc,rr,float(g["horseBodyZ"]),hs,M)

    # Two front entrances, matching the user's concept more closely.
    sw=float(g["stairWidth"]); sd=float(g["stairDepth"]); sh=float(g["stairHeight"]); xo=float(g["stairLateralOffset"])
    y=-(base_r+sd*0.32)
    for idx,x in enumerate((-xo,xo)):
        cube(f"Stair_{idx}_0",root,(x,y,sh*0.23),(sw,sd,sh*0.46),M["red"],0.025)
        cube(f"Stair_{idx}_1",root,(x,y+sd*0.26,sh*0.66),(sw,sd*0.58,sh*0.34),M["red"],0.025)
        cube(f"StairRailL_{idx}",root,(x-sw*0.52,y,sh*0.68),(0.08,sd*0.9,0.62),M["gold"],0.02)
        cube(f"StairRailR_{idx}",root,(x+sw*0.52,y,sh*0.68),(0.08,sd*0.9,0.62),M["gold"],0.02)

    cyl("CrownStem",rotor,(0,0,zi+0.42),0.045,0.76,M["gold"],12)
    sphere("CrownBall",rotor,(0,0,zi+0.81),(0.10,0.10,0.10),M["gold"])
    flag=cube("Flag",rotor,(0.20,0,zi+0.72),(0.34,0.03,0.15),M["red"],0.01); flag.rotation_euler[2]=0.12

    recv=studio["shadowReceiver"]; rm=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1)))
    ground=bs.add_box("ShadowReceiverPlane",recv["location"],recv["dimensions"],rm,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    bs.calibrate_ortho_scale(scene,authored,safety_margin=0.14); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    return scene,root,ground,authored

def main():
    a=args(); recipe=json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    if recipe.get("contract")!=CONTRACT: raise RuntimeError("Expected CITY_HORIZON_CAROUSEL_V3 recipe")
    if recipe.get("lifecycle",{}).get("status")!="draft": raise RuntimeError("V3 must remain draft")
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
        print(f"[CH_GATE] Carousel V3 proxy ready: {rep['sha256']}")
    elif a.stage=="preflight":
        print("[CH_GATE] Carousel V3 preflight PASS")
    else:
        raise RuntimeError("CH_FINAL_BLOCKED_DRAFT: explicit human approval required")
    if a.save_blend:
        p=Path(a.save_blend).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))

if __name__=="__main__":
    main()
