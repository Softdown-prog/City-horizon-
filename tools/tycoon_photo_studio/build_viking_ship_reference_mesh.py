#!/usr/bin/env python3
"""Reference-profile Viking ship authoring for City Horizon.

This is intentionally a different modeling method from every earlier Viking pass.
The attraction is authored from explicit silhouette/profile meshes and truss assemblies,
not from the previous generic four-stick A-frame + symmetric canoe construction.
No Viking builder or Viking geometry module is imported here.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
for p in (HERE, CH_BLENDER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs  # noqa: E402
import build_ferris_wheel as fw  # noqa: E402
import scene_gate  # noqa: E402

CONTRACT = "CH_VIKING_SHIP_REFERENCE_MESH_V1"
ASSET_ID = "attraction.park_viking_ship.01"


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend", default=None)
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="preflight")
    p.add_argument("--preflight-profile", default=None)
    return p.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_blend(path):
    if not path:
        return
    target = Path(path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(target))


def prism_xz(name, profile, y_half, material, parent=None, bevel=0.03):
    """Extrude an arbitrary X/Z silhouette through Y."""
    n = len(profile)
    verts = [(x, -y_half, z) for x, z in profile] + [(x, y_half, z) for x, z in profile]
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, n * 2))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(material)
    if parent is not None:
        obj.parent = parent
    if bevel > 0:
        mod = obj.modifiers.new(name="EdgeBreak", type="BEVEL")
        mod.width = bevel
        mod.segments = 1
    return obj


def beam(name, a, b, width, depth, mat, parent=None, bevel=0.02):
    a, b = Vector(a), Vector(b)
    d = b - a
    if d.length < 1e-6:
        raise RuntimeError(f"zero beam {name}")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(a + b) * 0.5)
    o = bpy.context.object
    o.name = name
    o.dimensions = (width, depth, d.length)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if parent is not None:
        o.parent = parent
    if bevel > 0:
        m = o.modifiers.new(name="EdgeBreak", type="BEVEL")
        m.width = bevel
        m.segments = 1
    return o


def build_station(root, g, mats):
    top = float(g["platformTopZ"])
    w = float(g["platformWidth"])
    d = float(g["platformDepth"])
    under = float(g["platformUnderframeHeight"])
    deck = fw.box("StationDeck", (0, 0, top - 0.16), (w, d, 0.32), mats["platform"], 0.025, root)
    contacts = []
    for x in (-w * .43, -w * .14, w * .14, w * .43):
        for y in (-d * .43, d * .43):
            foot = fw.box(f"StationFoot_{x:+.2f}_{y:+.2f}", (x, y, 0.10), (.86, .86, .20), mats["steelDark"], .01, root)
            contacts.append(foot)
            fw.box(f"StationPost_{x:+.2f}_{y:+.2f}", (x, y, under * .5), (.42, .42, under), mats["steelDark"], .012, root)
    for y in (-d * .43, d * .43):
        beam(f"UnderLong_{y:+.2f}", (-w*.44,y,under*.55), (w*.44,y,under*.55), .24,.24,mats["steelDark"],root,.01)
        for x in (-w*.36,-w*.12,w*.12,w*.36):
            beam(f"UnderDiagA_{x:+.2f}_{y:+.2f}", (x-1.25,y,0.20),(x+1.25,y,under),.16,.18,mats["steelDark"],root,.008)
            beam(f"UnderDiagB_{x:+.2f}_{y:+.2f}", (x+1.25,y,0.20),(x-1.25,y,under),.16,.18,mats["steelDark"],root,.008)

    steps = int(g["stairSteps"]); sw=float(g["stairWidth"]); run=float(g["stairRun"])
    sh=top/steps; sd=run/steps; y0=-d*.5-run*.5
    for i in range(steps):
        h=sh*(i+1); y=y0+sd*(i+.5)
        fw.box(f"StationStep_{i:02d}",(0,y,h*.5),(sw,sd*.94,h),mats["platform"],.01,root)

    rh=float(g["railingHeight"]); r=.055
    for side_y in (-d*.5,d*.5):
        for i in range(11):
            x=-w*.5+w*i/10
            if side_y<0 and abs(x)<sw*.60: continue
            fw.cylinder_between(f"RailYPost_{side_y:+.1f}_{i}",(x,side_y,top),(x,side_y,top+rh),r,mats["steelDark"],root,vertices=10)
        for z in (top+rh*.52,top+rh):
            fw.cylinder_between(f"RailY_{side_y:+.1f}_{z:.2f}",(-w*.5,side_y,z),(w*.5,side_y,z),.045,mats["steelDark"],root,vertices=10)
    for side_x in (-w*.5,w*.5):
        for i in range(9):
            y=-d*.5+d*i/8
            fw.cylinder_between(f"RailXPost_{side_x:+.1f}_{i}",(side_x,y,top),(side_x,y,top+rh),r,mats["steelDark"],root,vertices=10)
        for z in (top+rh*.52,top+rh):
            fw.cylinder_between(f"RailX_{side_x:+.1f}_{z:.2f}",(side_x,-d*.5,z),(side_x,d*.5,z),.045,mats["steelDark"],root,vertices=10)
    return deck, contacts


def build_towers(root, g, mats):
    fx=float(g["towerFootHalfX"]); py=float(g["towerPlaneHalfY"]); sx=float(g["towerShoulderX"]); cz=float(g["towerCrownZ"]); th=float(g["towerPlateThickness"])
    contacts=[]; support_objs=[]
    # Each side is a substantial engineered portal made from silhouette plates, not four stick beams.
    left_profile=[(-fx-.72,0.20),(-fx+.72,0.20),(-sx+.65,cz-3.6),(-.85,cz-.55),(-1.55,cz-2.15),(-sx-.55,cz-4.1)]
    right_profile=[(fx+.72,0.20),(fx-.72,0.20),(sx-.65,cz-3.6),(.85,cz-.55),(1.55,cz-2.15),(sx+.55,cz-4.1)]
    for ys,label in ((-1,"Front"),(1,"Back")):
        y=ys*py
        for profile,side in ((left_profile,"L"),(right_profile,"R")):
            o=prism_xz(f"TowerPlate_{label}_{side}",profile,th*.5,mats["steelBlue"],root,.045)
            o.location.y=y
            support_objs.append(o)
            # feet as true ground contacts
            x=-fx if side=="L" else fx
            foot=fw.box(f"TowerFoot_{label}_{side}",(x,y,0.11),(1.80,1.45,.22),mats["steelDark"],.018,root)
            contacts.append(foot)
        # inner gold plated stiffeners following the tower, visually integrated rather than free rods
        beam(f"InsetGoldL_{label}",(-fx+.9,y,1.0),(-1.45,y,cz-1.9),.52,.34,mats["gold"],root,.02)
        beam(f"InsetGoldR_{label}", (fx-.9,y,1.0),(1.45,y,cz-1.9),.52,.34,mats["gold"],root,.02)
        # broad truss bridge and diagonals
        z=cz*.57
        beam(f"TowerBridge_{label}",(-fx*.58,y,z),(fx*.58,y,z),.42,.34,mats["steelDark"],root,.015)
        for i,x in enumerate((-fx*.52,-fx*.26,0,fx*.26,fx*.52)):
            if i<4:
                x2=(-fx*.52,-fx*.26,0,fx*.26,fx*.52)[i+1]
                beam(f"TrussUp_{label}_{i}",(x,y,z-.20),(x2,y,z+1.25),.20,.18,mats["steelDark"],root,.01)
                beam(f"TrussDn_{label}_{i}",(x,y,z+1.25),(x2,y,z-.20),.20,.18,mats["steelDark"],root,.01)
    axle=fw.cylinder("ReferenceMainAxle",(0,0,cz),float(g["axleRadius"]),py*2.20,mats["steelDark"],rotation=(math.radians(90),0,0),parent=root,vertices=32)
    for ys,label in ((-1,"Front"),(1,"Back")):
        y=ys*(py+.12)
        fw.cylinder(f"ReferenceBearing_{label}",(0,y,cz),float(g["bearingRadius"]),.52,mats["gold"],rotation=(math.radians(90),0,0),parent=root,vertices=32)
        fw.cylinder(f"BearingHub_{label}",(0,ys*(py+.40),cz),float(g["bearingRadius"])*.52,.22,mats["steelDark"],rotation=(math.radians(90),0,0),parent=root,vertices=24)
    return contacts,support_objs,axle


def build_ship(root,g,mats):
    cz=float(g["towerCrownZ"]); center=float(g["shipCenterZ"]); L=float(g["shipLength"]); hw=float(g["shipHalfWidth"]); depth=float(g["shipDepth"]); rise=float(g["prowRise"])
    pivot=fw.empty("SwingPivot",(0,0,cz),root)
    boat=fw.empty("BoatRoot",(0,0,center-cz),pivot)
    half=L*.5
    # Side silhouette deliberately has high prow/stern and a deep belly, unlike the old canoe-like ring hull.
    profile=[(-half,1.55+rise),(-half*.93,2.10+rise*.62),(-half*.78,1.45),(-half*.55,.25),(-half*.25,-depth*.74),(0,-depth),(half*.25,-depth*.74),(half*.55,.25),(half*.78,1.45),(half*.93,2.10+rise*.62),(half,1.55+rise)]
    hull=prism_xz("ReferenceHull",profile,hw,mats["wood"],boat,.07)
    # inset side panels/trim create amusement-ride mass and decoration
    for ys,label in ((-1,"Front"),(1,"Back")):
        y=ys*(hw+.055)
        beam(f"HullUpperTrim_{label}",(-half*.78,y,1.43),(half*.78,y,1.43),.18,.10,mats["gold"],boat,.01)
        beam(f"HullLowerTrim_{label}",(-half*.63,y,-1.15),(half*.63,y,-1.15),.13,.08,mats["red"],boat,.008)
        for i in range(7):
            x=-half*.58+i*(half*1.16/6)
            fw.box(f"SidePanel_{label}_{i}",(x,y,0.10),(1.15,.09,.95),mats["red"],.025,boat)
            fw.box(f"SidePanelFrame_{label}_{i}",(x,y+ys*.055,0.10),(1.32,.045,1.10),mats["gold"],.018,boat)
    # deck lip and dense seats
    fw.box("PassengerDeck",(0,0,1.05),(L*.76,hw*1.72,.24),mats["woodLight"],.035,boat)
    rows=int(g["seatRows"]); span=float(g["seatSpan"])
    for i in range(rows):
        x=-span*.5+span*i/max(1,rows-1)
        fw.box(f"SeatBase_{i:02d}",(x,0,1.34),(.78,hw*1.45,.22),mats["seat"],.028,boat)
        fw.box(f"SeatBack_{i:02d}",(x+.25,0,1.76),(.17,hw*1.40,.72),mats["seat"],.025,boat)
        fw.cylinder_between(f"LapBar_{i:02d}",(x-.12,-hw*.64,1.85),(x-.12,hw*.64,1.85),.045,mats["gold"],boat,vertices=10)
    # decorative high end caps
    for s,label in ((-1,"L"),(1,"R")):
        x=s*half*.985
        beam(f"EndSpine_{label}",(x,0,1.8),(s*(half+.32),0,4.75),.34,.55,mats["gold"],boat,.025)
        fw.cylinder(f"EndMedallion_{label}",(s*(half+.34),0,4.85),.52,.30,mats["red"],rotation=(math.radians(90),0,0),parent=boat,vertices=24)

    tx=float(g["suspensionTopHalfX"]); bx=float(g["suspensionBottomHalfX"]); sy=float(g["suspensionHalfY"]); mw=float(g["suspensionMemberWidth"])
    attach_z=(center-cz)+1.45
    # suspension yokes are substantial paired mechanical members, connected visibly into hull shoulders
    for xs,label in ((-1,"L"),(1,"R")):
        for ys,side in ((-1,"Front"),(1,"Back")):
            beam(f"Yoke_{side}_{label}",(xs*tx,ys*sy,-.15),(xs*bx,ys*sy,attach_z),mw,.46,mats["gold"],pivot,.028)
            fw.cylinder(f"HullJoint_{side}_{label}",(xs*bx,ys*sy,attach_z),.46,.30,mats["steelDark"],rotation=(math.radians(90),0,0),parent=pivot,vertices=20)
    pivot.rotation_euler[1]=math.radians(float(g.get("previewSwingDegrees",0)))
    return pivot,hull


def is_descendant(obj,ancestor):
    p=obj.parent
    while p is not None:
        if p==ancestor:return True
        p=p.parent
    return False


def main():
    args=parse_args(); recipe=load_json(args.recipe)
    if recipe.get("contract")!=CONTRACT: raise RuntimeError(f"Expected {CONTRACT}")
    if recipe.get("assetId")!=ASSET_ID: raise RuntimeError(f"Expected {ASSET_ID}")
    pol=recipe.get("authoringPolicy",{})
    if pol.get("previousFullscaleBuilderReuseAllowed") is not False or pol.get("legacyVikingImportsAllowed") is not False:
        raise RuntimeError("CH_VIKING_REFERENCE_MESH_CLEANROOM_POLICY_FAIL")
    studio=bs.load_json(args.studio_preset); out=Path(args.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio["render"]["sourceResolution"])); scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode="RGBA"
    mats=fw.make_materials(recipe); root=fw.empty("AssetRoot"); root["assetId"]=ASSET_ID; root["assetType"]=recipe["assetType"]; root["cameraContract"]="CH_CAMERA_V1"; root["styleContract"]=recipe["styleContract"]; root["footprint"]="7x6"; root["proceduralContract"]=CONTRACT; root["modelingMethod"]="reference_profile_mesh"; root["legacyVikingImportsUsed"]=False
    deck,station_contacts=build_station(root,recipe["geometry"],mats); tower_contacts,supports,axle=build_towers(root,recipe["geometry"],mats); pivot,hull=build_ship(root,recipe["geometry"],mats)
    for o in station_contacts+tower_contacts: scene_gate.tag(o,"attraction.ground_contact",ground_contact=True)
    scene_gate.tag(deck,"attraction.loading_platform",ground_contact=False); scene_gate.tag(hull,"attraction.gondola",ground_contact=False); scene_gate.tag(axle,"attraction.pivot_axle",ground_contact=False)
    for o in supports: scene_gate.tag(o,"attraction.support",ground_contact=False)
    recv=studio["shadowReceiver"]; rmat=bs.make_material("ShadowReceiver",recv["materialColor"],float(recv.get("roughness",1.0))); ground=bs.add_box("ShadowReceiverPlane",recv["location"],[max(float(recv["dimensions"][0]),21.0),max(float(recv["dimensions"][1]),18.0),float(recv["dimensions"][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=="MESH" and o!=ground]
    for o in authored:o["runtimeLayer"]="motion_overlay" if is_descendant(o,pivot) else "static_base"
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.13); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={"contract":CONTRACT,"assetId":ASSET_ID,"stage":"reference_profile_mesh_gate","cameraContract":"CH_CAMERA_V1","footprint":recipe["footprint"],"recipe":"tools/tycoon_photo_studio/assets/park_viking_ship_reference_7x6.viking.json","builder":"tools/tycoon_photo_studio/build_viking_ship_reference_mesh.py","modelingMethod":"reference_profile_mesh","legacyVikingImportsUsed":False,"blenderVersion":bpy.app.version_string,"renderEngine":scene.render.engine}; (out/"studio_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    profile=scene_gate.load_profile(args.preflight_profile); pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=recipe["footprint"],profile=profile,asset_id=ASSET_ID,report_path=out/"preflight_report.json"); scene_gate.require_pass(pre)
    if args.stage=="preflight": save_blend(args.save_blend); return
    if args.stage=="proxy":
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/"proxy_south.png",profile=profile,asset_id=ASSET_ID,direction="south"); (out/"proxy_report.json").write_text(json.dumps(proxy,indent=2),encoding="utf-8"); save_blend(args.save_blend); return
    raise RuntimeError("CH_VIKING_FINAL_NOT_DEFINED: approve reference-profile proxy first")


if __name__=="__main__": main()
