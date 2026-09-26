"""Guarded CH Blender authoring for residential_suburban_cottage_3x3_01.

Original geometry based only on broad art direction from the user-supplied
reference. Quality path: preflight -> SOUTH proxy -> approval -> final 4 views.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CH_BLENDER = ROOT / "tools" / "ch_blender"
for p in (HERE, CH_BLENDER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs  # noqa: E402
import scene_gate  # noqa: E402

ASSET_ID = "residential_suburban_cottage_3x3_01"
DEFAULT_RECIPE = "tools/tycoon_photo_studio/assets/residential_suburban_cottage_3x3_01.house.json"


def args_parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", default=DEFAULT_RECIPE)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    p.add_argument("--approval-proxy-sha", default=None)
    p.add_argument("--save-blend", default=None)
    return p.parse_args(argv)


def repo_path(value):
    p = (ROOT / value).resolve()
    p.relative_to(ROOT)
    return p


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def empty(name, parent=None):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_mode = "XYZ"
    o.parent = parent
    return o


def box(name, loc, dims, mat, parent, bevel=0.035):
    o = bs.add_box(name, loc, dims, mat, bevel)
    o.parent = parent
    return o


def mesh(name, verts, faces, mat, parent, bevel=0.025):
    m = bpy.data.meshes.new(name + "Mesh")
    m.from_pydata(verts, [], faces)
    m.update()
    o = bpy.data.objects.new(name, m)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.parent = parent
    if bevel:
        mod = o.modifiers.new("EdgeSoftening", "BEVEL")
        mod.width, mod.segments = bevel, 2
    return o


def sphere(name, loc, radius, mat, parent, scale=(1, 1, 1), seg=16, rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=radius, location=loc)
    o = bpy.context.object
    o.name, o.parent, o.scale = name, parent, scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    return o


def gable_x(name, cx, cy, w, d, eave, ridge, mat, parent):
    hw, hd = w / 2, d / 2
    v = [(cx-hw,cy-hd,eave),(cx-hw,cy,ridge),(cx+hw,cy,ridge),(cx+hw,cy-hd,eave),
         (cx-hw,cy+hd,eave),(cx+hw,cy+hd,eave)]
    return mesh(name, v, [(0,1,2,3),(1,4,5,2)], mat, parent, 0.03)


def gable_y(name, cx, cy, w, d, eave, ridge, mat, parent):
    hw, hd = w / 2, d / 2
    v = [(cx-hw,cy-hd,eave),(cx,cy-hd,ridge),(cx,cy+hd,ridge),(cx-hw,cy+hd,eave),
         (cx+hw,cy-hd,eave),(cx+hw,cy+hd,eave)]
    return mesh(name, v, [(0,1,2,3),(1,4,5,2)], mat, parent, 0.03)


def make_materials(recipe):
    out = {}
    for key, s in recipe["materials"].items():
        out[key] = bs.make_material(s["name"], s["rgba"], float(s.get("roughness", .78)),
                                    float(s.get("metallic", 0)), recipe=s.get("recipe", "solid"),
                                    seed=int(s.get("seed", 0)), strength=float(s.get("strength", .05)))
    glass = out["glass"]
    if glass.use_nodes:
        node = glass.node_tree.nodes.get("Principled BSDF")
        if node:
            rgba = tuple(recipe["materials"]["glass"]["rgba"])
            k = "Emission Color" if "Emission Color" in node.inputs else "Emission"
            if k in node.inputs:
                node.inputs[k].default_value = rgba
            if "Emission Strength" in node.inputs:
                node.inputs["Emission Strength"].default_value = .55
    return out


def window(root, mats, name, side, a, b, z, w, h):
    if side in ("south", "north"):
        outward = -1 if side == "south" else 1
        box(name+"Frame", (a,b,z), (w+.20,.12,h+.20), mats["frame"], root, .022)
        box(name+"Glow", (a,b+outward*.068,z), (w,.045,h), mats["glass"], root, .01)
        box(name+"V", (a,b+outward*.098,z), (.06,.045,h), mats["frame"], root, .01)
        box(name+"H", (a,b+outward*.098,z), (w,.045,.06), mats["frame"], root, .01)
        box(name+"Sill", (a,b+outward*.105,z-h*.56), (w+.24,.20,.10), mats["trim"], root, .018)
    else:
        outward = 1 if side == "east" else -1
        box(name+"Frame", (a,b,z), (.12,w+.20,h+.20), mats["frame"], root, .022)
        box(name+"Glow", (a+outward*.068,b,z), (.045,w,h), mats["glass"], root, .01)
        box(name+"V", (a+outward*.098,b,z), (.045,.06,h), mats["frame"], root, .01)
        box(name+"H", (a+outward*.098,b,z), (.045,w,.06), mats["frame"], root, .01)
        box(name+"Sill", (a+outward*.105,b,z-h*.56), (.20,w+.24,.10), mats["trim"], root, .018)


def build_house(root, mats, r):
    m, roof, dorm, ent, win, land = (r[k] for k in ("mass","roof","dormers","entry","windows","landscaping"))
    fw, fd, fh = map(float, (m["foundationWidth"],m["foundationDepth"],m["foundationHeight"]))
    bw, bd, wh, z0 = map(float, (m["bodyWidth"],m["bodyDepth"],m["wallHeight"],m["wallBaseZ"]))
    foundation = box("BuildingFoundation", (0,0,fh/2), (fw,fd,fh), mats["foundation"], root, .055)
    scene_gate.tag(foundation, "building.foundation", ground_contact=True)
    box("HouseBody", (0,0,z0+wh/2), (bw,bd,wh), mats["wall"], root, .055)

    for i in range(1,7):
        z = z0 + wh*i/7
        for name,loc,dims in (
            (f"SidingS{i}",(0,-bd/2-.022,z),(bw-.1,.035,.035)),
            (f"SidingN{i}",(0, bd/2+.022,z),(bw-.1,.035,.035)),
            (f"SidingE{i}",( bw/2+.022,0,z),(.035,bd-.1,.035)),
            (f"SidingW{i}",(-bw/2-.022,0,z),(.035,bd-.1,.035))):
            box(name, loc, dims, mats["trim"], root, .006)

    rw, rd, eave, ridge = map(float, (roof["width"],roof["depth"],roof["eaveZ"],roof["ridgeZ"]))
    gable_x("MainRoof",0,0,rw,rd,eave,ridge,mats["roof"],root)
    box("SouthFascia",(0,-rd/2-.025,eave-.02),(rw+.04,.11,.14),mats["roofEdge"],root,.018)
    box("NorthFascia",(0, rd/2+.025,eave-.02),(rw+.04,.11,.14),mats["roofEdge"],root,.018)
    box("RidgeCap",(0,0,ridge+.025),(rw+.02,.11,.10),mats["roofEdge"],root,.018)
    for side,sign in (("S",-1),("N",1)):
        rows=int(roof.get("tileRows",7))
        for i in range(1,rows):
            t=i/rows
            box(f"RoofRow{side}{i}",(0,sign*(rd/2)*(1-t),eave+(ridge-eave)*t+.018),
                (rw-.12,.035,.035),mats["roofEdge"],root,.006)

    cy,bw_d,bd_d,bh,cz = map(float,(dorm["centerY"],dorm["bodyWidth"],dorm["bodyDepth"],dorm["bodyHeight"],dorm["bodyCenterZ"]))
    de,dr,dd = map(float,(dorm["roofEaveZ"],dorm["roofRidgeZ"],dorm["roofDepth"]))
    for i,xv in enumerate(dorm["centersX"]):
        x=float(xv)
        box(f"DormerBody{i}",(x,cy,cz),(bw_d,bd_d,bh),mats["wall"],root,.035)
        gable_y(f"DormerRoof{i}",x,cy,bw_d+.30,dd,de,dr,mats["roof"],root)
        box(f"DormerRidge{i}",(x,cy,dr+.018),(.08,dd+.02,.08),mats["roofEdge"],root,.012)
        window(root,mats,f"DormerWindow{i}","south",x,cy-bd_d/2-.075,cz,
               float(win["dormerWidth"]),float(win["dormerHeight"]))

    front=-bd/2
    ex=float(ent["centerX"]); door_h=float(ent["doorHeight"]); door_w=float(ent["doorWidth"])
    door=box("FrontDoor",(ex,front-.075,z0+door_h/2),(door_w,.16,door_h),mats["door"],root,.035)
    scene_gate.tag(door,"building.entrance")
    box("DoorInset",(ex,front-.166,z0+door_h/2),(door_w*.66,.035,door_h*.70),mats["frame"],root,.012)
    sphere("DoorKnob",(ex+door_w*.30,front-.205,1.08),.055,mats["trim"],root,(1,.45,1),14,8)
    pw,pd,pe,pr = map(float,(ent["porticoWidth"],ent["porticoDepth"],ent["porticoEaveZ"],ent["porticoRidgeZ"]))
    py=front-pd*.47
    gable_y("PorticoRoof",ex,py,pw,pd,pe,pr,mats["roof"],root)
    box("PorticoRidge",(ex,py,pr+.018),(.09,pd+.02,.08),mats["roofEdge"],root,.012)
    spacing=float(ent["columnSpacing"])
    for side,cx in (("L",ex-spacing/2),("R",ex+spacing/2)):
        post=box("EntryColumn"+side,(cx,py-pd*.30,pe/2),(.18,.18,pe),mats["trim"],root,.025)
        scene_gate.tag(post,"building.porch_post",ground_contact=True)
        box("EntryColumnBase"+side,(cx,py-pd*.30,.27),(.34,.34,.54),mats["foundation"],root,.035)
    box("FrontStoop",(ex,front-.38,.16),(1.45,.78,.20),mats["foundation"],root,.035)
    box("FrontStep",(ex,front-.76,.08),(1.60,.44,.16),mats["path"],root,.025)

    c=r["chimney"]
    cx,cyc=float(c["x"]),float(c["y"]); cw,cd=float(c["width"]),float(c["depth"]); ch=float(c["bodyHeight"]); ccz=float(c["bodyCenterZ"])
    box("ChimneyBody",(cx,cyc,ccz),(cw,cd,ch),mats["wall"],root,.035)
    box("ChimneyBand",(cx,cyc,ccz+ch*.30),(cw+.12,cd+.12,.13),mats["trim"],root,.02)
    box("ChimneyCap",(cx,cyc,ccz+ch/2+float(c["capHeight"])/2),(float(c["capWidth"]),float(c["capDepth"]),float(c["capHeight"])),mats["roof"],root,.025)

    fy=front-.065
    for i,xv in enumerate(win["frontCentersX"]):
        window(root,mats,f"FrontWindow{i}","south",float(xv),fy,float(win["frontCenterZ"]),float(win["frontWidth"]),float(win["frontHeight"]))
    sx=bw/2+.065
    window(root,mats,"EastWindow","east", sx, float(win["sideCenterY"]),float(win["sideCenterZ"]),float(win["sideWidth"]),float(win["sideHeight"]))
    window(root,mats,"WestWindow","west",-sx,-float(win["sideCenterY"]),float(win["sideCenterZ"]),float(win["sideWidth"]),float(win["sideHeight"]))
    window(root,mats,"RearWindow","north",1.32,bd/2+.065,float(win["sideCenterZ"]),float(win["sideWidth"]),float(win["sideHeight"]))

    rad=float(land["shrubRadius"])
    for group,coords in (("Front",land["frontShrubs"]),("Side",land["sideShrubs"])):
        for i,(x,y) in enumerate(coords):
            sphere(f"{group}Shrub{i}",(float(x),float(y),rad*.92),rad,mats["greenLight" if i%2 else "green"],root,(1.1,.95,.92))
    for bi,(x,y) in enumerate(land["flowerBeds"]):
        x,y=float(x),float(y)
        box(f"FlowerBed{bi}",(x,y,.09),(1.04,.46,.16),mats["foundation"],root,.025)
        for j,dx in enumerate((-.32,-.10,.12,.32)):
            sphere(f"Leaf{bi}_{j}",(x+dx,y,.25),.15,mats["green"],root,(1.05,.86,.82),14,8)
            sphere(f"Flower{bi}_{j}",(x+dx,y-.08,.38),.065,mats["flower"],root,(1,.72,.55),12,6)
            sphere(f"FlowerCenter{bi}_{j}",(x+dx,y-.115,.39),.028,mats["flowerCenter"],root,(1,.65,.65),10,5)
    box("PrivateEntryPath",(ex,-fd/2-float(land["privatePathDepth"])*.45,.035),
        (float(land["privatePathWidth"]),float(land["privatePathDepth"]),.07),mats["path"],root,.02)


def load_recipe(path):
    r=json.loads(Path(path).read_text(encoding="utf-8"))
    if r.get("contract")!="CITY_HORIZON_HOUSE_V1" or r.get("assetId")!=ASSET_ID:
        raise RuntimeError("CH_HOUSE_RECIPE_CONTRACT")
    if r.get("footprint")!={"widthTiles":3,"depthTiles":3}:
        raise RuntimeError("CH_HOUSE_FOOTPRINT: pilot must remain 3x3")
    return r


def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(p))


def build_context(a):
    recipe_path=repo_path(a.recipe); r=load_recipe(recipe_path)
    ref_path=repo_path(r["referenceDescriptor"]); ref=json.loads(ref_path.read_text(encoding="utf-8")); ref["descriptorSha256"]=sha256(ref_path)
    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    (out/"reference_descriptor.json").write_text(json.dumps(ref,indent=2),encoding="utf-8")
    bs.clear_scene(); src=tuple(map(int,studio["render"]["sourceResolution"])); scene=bs.configure_scene(studio,src,str(out))
    scene.render.film_transparent=True; scene.render.image_settings.color_mode="RGBA"
    root=empty("AssetRoot")
    for k,v in {"assetId":ASSET_ID,"assetType":"building","cameraContract":"CH_CAMERA_V1","studioPreset":"CH_TYCOON_STUDIO_V1",
                "styleContract":"CH_STYLIZED_PRERENDER_V1","artDirectionContract":r["styleContract"],"groundIncludedInAsset":False,
                "runtimeRepresentation":"2D_RGBA_pre_rendered_sprite","footprint":"3x3","referenceDescriptor":r["referenceDescriptor"],
                "referenceSourceSha256":ref["sourceSha256"],"directionPolicy":"rotate_asset_root_keep_camera_lights_fixed",
                "qualityGateContract":"CH_SCENE_PREFLIGHT_V1"}.items():
        root[k]=v
    mats=make_materials(r); build_house(root,mats,r)
    rec=studio["shadowReceiver"]; gmat=bs.make_material("ShadowReceiver",rec["materialColor"],float(rec.get("roughness",1)))
    ground=bs.add_box("ShadowReceiverPlane",rec["location"],rec["dimensions"],gmat,0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.14); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    return recipe_path,r,ref,studio,out,scene,root,ground,authored


def render_final(ctx):
    recipe_path,r,ref,studio,out,scene,root,ground,authored=ctx; directions=[]
    for d in bs.DIRECTIONS:
        bs.set_direction(root,d); bpy.context.view_layer.update()
        color=f"{ASSET_ID}_{d['id']}_color_source.png"; shadow=f"{ASSET_ID}_{d['id']}_shadow_source.png"
        bs.render_color_pass(scene,authored,ground,str(out/color)); origin=bs.ground_origin_source_px(scene)
        bs.render_shadow_pass(scene,authored,ground,str(out/shadow))
        directions.append({"id":d["id"],"quarterTurns":d["quarterTurns"],"rotationDegrees":d["rotationDegrees"],"colorSource":color,"shadowSource":shadow,"groundOriginSourcePx":origin})
    meta={"sourceObject":ASSET_ID,"assetType":"building","sourceContract":"DIRECT_CH_BLENDER_GUARDED_V1",
          "assetConfig":recipe_path.relative_to(ROOT).as_posix(),"builder":"tools/tycoon_photo_studio/build_residential_suburban_cottage_guarded.py",
          "reference":{"descriptor":r["referenceDescriptor"],"sourceSha256":ref["sourceSha256"],"usage":ref["usage"]},
          "studioPreset":studio["id"],"styleContract":"CH_STYLIZED_PRERENDER_V1","artDirectionContract":r["styleContract"],
          "cameraContract":"CH_CAMERA_V1","gridContract":"CH_GRID_V1","projection":"orthographic_dimetric_2_to_1",
          "yawDegrees":45,"elevationDegrees":30,"tileWidth":128,"tileHeight":64,"footprint":r["footprint"],
          "blenderVersion":bpy.app.version_string,"renderEngine":scene.render.engine,"directionOrder":[d["id"] for d in bs.DIRECTIONS],
          "sourceSummary":{"groundIncludedInAsset":False,"publicSidewalkIncluded":False,"largeTreeIncluded":False,
                           "pairedDormers":True,"warmWindowRead":True,"referenceUsedAsArtDirectionOnly":True},"directions":directions}
    (out/"studio_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")


def main():
    a=args_parse(); profile=scene_gate.load_profile(a.preflight_profile); ctx=build_context(a)
    recipe_path,r,ref,studio,out,scene,root,ground,authored=ctx
    report=scene_gate.run_preflight(scene=scene,authored=authored,footprint=r["footprint"],profile=profile,asset_id=ASSET_ID,report_path=out/"preflight_report.json")
    scene_gate.require_pass(report)
    if a.stage=="preflight":
        save_blend(a.save_blend); print("[CH_GATE] residential cottage preflight PASS"); return
    if a.stage=="proxy":
        bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET_ID,direction="south")
        (out/"proxy_report.json").write_text(json.dumps(proxy,indent=2),encoding="utf-8")
        save_blend(a.save_blend); print(f"[CH_GATE] SOUTH proxy ready: {proxy['sha256']}"); return
    approval=(a.approval_proxy_sha or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}",approval):
        raise RuntimeError("CH_FINAL_REQUIRES_APPROVED_PROXY: review proxy_south.png first")
    (out/"proxy_approval.json").write_text(json.dumps({"contract":"CH_PROXY_APPROVAL_V1","assetId":ASSET_ID,"proxySha256":approval,"reviewed":True},indent=2),encoding="utf-8")
    render_final(ctx); save_blend(a.save_blend); print("[CH_GATE] final four-direction source bake complete")


if __name__ == "__main__":
    main()
