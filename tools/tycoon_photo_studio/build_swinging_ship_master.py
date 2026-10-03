#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CH_BLENDER = REPO_ROOT / "tools" / "ch_blender"
for p in (HERE, CH_BLENDER):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import build_scene as bs
import scene_gate

CONTRACT = "CH_SWINGING_SHIP_MASTER_V1"
ASSET_ID = "attraction.park_viking_ship.01"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend")
    p.add_argument("--stage", choices=("preflight","proxy","final"), default="proxy")
    p.add_argument("--preflight-profile")
    return p.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def mat(spec):
    return bs.make_material(spec["name"], spec["rgba"], float(spec.get("roughness", .6)), float(spec.get("metallic", 0)))


def box(name, loc, dims, material, parent=None, bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(loc))
    o = bpy.context.object
    o.name = name
    o.dimensions = tuple(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(material)
    if parent is not None:
        o.parent = parent
    if bevel:
        m = o.modifiers.new("EdgeBreak", "BEVEL")
        m.width = bevel
        m.segments = 2
    return o


def cyl(name, loc, radius, depth, material, rot=(0,0,0), parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=tuple(loc), rotation=rot)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(material)
    if parent is not None:
        o.parent = parent
    return o


def beam(name, a, b, width, depth, material, parent=None):
    a = Vector(a); b = Vector(b); d = b - a
    o = box(name, (a+b)*.5, (width, depth, d.length), material, parent, .025)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z','Y')
    return o


def loft_ship(name, stations, material, parent):
    verts=[]; faces=[]
    for s in stations:
        x=float(s['x']); hw=float(s['halfWidth']); kz=float(s['keelZ']); gz=float(s['gunwaleZ'])
        verts.extend([
            (x,0,kz),
            (x,-hw,gz),
            (x, hw,gz),
        ])
    for i in range(len(stations)-1):
        a=i*3; b=(i+1)*3
        faces += [
            (a,a+1,b+1,b),
            (a+2,a,b,b+2),
            (a+1,a+2,b+2,b+1),
        ]
    faces += [(0,2,1), ((len(stations)-1)*3, (len(stations)-1)*3+1, (len(stations)-1)*3+2)]
    me=bpy.data.meshes.new(name+"Mesh")
    me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(material); o.parent=parent
    bev=o.modifiers.new("HullSoftening","BEVEL"); bev.width=.12; bev.segments=3
    return o


def interp(stations, x):
    ss=sorted(stations,key=lambda s:float(s['x']))
    for a,b in zip(ss,ss[1:]):
        ax,bx=float(a['x']),float(b['x'])
        if ax<=x<=bx:
            t=(x-ax)/(bx-ax)
            return {
                'halfWidth':float(a['halfWidth'])+(float(b['halfWidth'])-float(a['halfWidth']))*t,
                'keelZ':float(a['keelZ'])+(float(b['keelZ'])-float(a['keelZ']))*t,
                'gunwaleZ':float(a['gunwaleZ'])+(float(b['gunwaleZ'])-float(a['gunwaleZ']))*t,
            }
    return ss[0] if x<float(ss[0]['x']) else ss[-1]


def build_supports(root, cfg, M):
    sy=float(cfg['dimensions']['supportSideY']); pz=float(cfg['dimensions']['pivotZ'])
    contacts=[]; supports=[]
    for y,label in ((-sy,'Near'),(sy,'Far')):
        for side,key in ((-1,'left'),(1,'right')):
            pts=[(float(x),y,float(z)) for x,z in cfg['supportFrames'][key]]
            contacts.append(box(f'{label}_{key}_Foot',pts[0],(1.9,1.5,.28),M['platform'],root,.02))
            for i,(a,b) in enumerate(zip(pts,pts[1:])):
                supports.append(beam(f'{label}_{key}_{i}',a,b,1.25,.92,M['frame'],root))
        beam(f'{label}_BearingBridge',(-2.4,y,pz-1.0),(2.4,y,pz-1.0),.74,.58,M['bearing'],root)
    axle=cyl('MainAxle',(0,0,pz),.68,sy*2.30,M['frame'],(math.radians(90),0,0),root,36)
    for y in (-sy-.14,sy+.14):
        cyl('BearingHousing',(0,y,pz),1.50,.76,M['bearing'],(math.radians(90),0,0),root,36)
        cyl('BearingHub',(0,y,pz),.82,.32,M['frame'],(math.radians(90),0,0),root,28)
    # Only three spatial ties: feet and pivot. No cage/ladder bracing.
    beam('PivotTie',(0,-sy,pz-.15),(0,sy,pz-.15),.78,.78,M['frame'],root)
    lx=float(cfg['dimensions']['supportFootX'])
    beam('LeftBaseTie',(-lx,-sy,.48),(-lx,sy,.48),.40,.36,M['frame'],root)
    beam('RightBaseTie',(lx,-sy,.48),(lx,sy,.48),.40,.36,M['frame'],root)
    return contacts,supports,axle


def build_boarding(root, cfg, M):
    b=cfg['boarding']; w=float(b['platformWidth']); d=float(b['platformDepth']); cy=float(b['centerY']); z=float(b['topZ'])
    deck=box('BoardingPlatform',(0,cy,z-.16),(w,d,.32),M['platform'],root,.03)
    contacts=[]
    for x in (-w*.45,-w*.15,w*.15,w*.45):
        for y in (cy-d*.40, cy+d*.40):
            contacts.append(box(f'BoardingFoot_{x}_{y}',(x,y,.10),(.85,.85,.20),M['frame'],root,.02))
    outer=cy-d*.5
    beam('BoardingRail',(-w*.5,outer,z+1.2),(w*.5,outer,z+1.2),.08,.08,M['frame'],root)
    for i in range(13):
        x=-w*.5+w*i/12
        beam(f'BoardingRailPost_{i}',(x,outer,z),(x,outer,z+1.2),.06,.06,M['frame'],root)
    sw=float(b['stairsWidth']); run=float(b['stairsRun']); steps=int(b['steps'])
    sh=z/steps; sd=run/steps; y0=outer-run
    for i in range(steps):
        box(f'BoardingStep_{i}',(0,y0+sd*(i+.5),sh*(i+1)/2),(sw,sd*.95,sh*(i+1)),M['platform'],root,.01)
    return deck,contacts


def build_ship(root, cfg, M):
    pz=float(cfg['dimensions']['pivotZ']); cz=float(cfg['dimensions']['shipCenterZ'])
    stations=cfg['shipStations']
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,pz))
    pivot=bpy.context.object; pivot.name='SwingPivot'; pivot.parent=root
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,cz-pz))
    boat=bpy.context.object; boat.name='ShipRoot'; boat.parent=pivot
    hull=loft_ship('PassengerShipHull',stations,M['wood'],boat)
    for side,label in ((-1,'Port'),(1,'Starboard')):
        pts=[(float(s['x']),side*float(s['halfWidth']),float(s['gunwaleZ'])+.08) for s in stations]
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            beam(f'{label}Gunwale_{i}',a,b,.24,.18,M['bearing'],boat)
    # 14 rows and tall sculpted ends integrated into the ship.
    for i in range(14):
        x=-7.3+14.6*i/13
        s=interp(stations,x); hw=float(s['halfWidth']); kz=float(s['keelZ'])
        box(f'Seat_{i}',(x,0,kz+1.15),(.82,max(1.0,hw*1.50),.28),M['seat'],boat,.035)
        box(f'SeatBack_{i}',(x+.24,0,kz+1.62),(.18,max(1.0,hw*1.45),.82),M['seat'],boat,.025)
    for idx,label in ((0,'Stern'),(-1,'Bow')):
        s=stations[idx]; x=float(s['x']); gz=float(s['gunwaleZ']); hw=float(s['halfWidth'])
        box(f'{label}Tower',(x,0,gz+1.20),(.38,max(1.0,hw*1.7),2.50),M['trim'],boat,.06)
    # Heavy U-shaped hanger assemblies, visually distinct from previous thin diagonals.
    top_x=1.8; top_y=5.3; lower_x=7.0; lower_y=3.45; lower_world=9.4; lower_local=lower_world-pz
    for y,label in ((-lower_y,'Near'),(lower_y,'Far')):
        beam(f'Hanger_{label}_L',(-top_x,y,-.10),(-lower_x,y,lower_local),1.05,.78,M['bearing'],pivot)
        beam(f'Hanger_{label}_R', ( top_x,y,-.10),( lower_x,y,lower_local),1.05,.78,M['bearing'],pivot)
        beam(f'Hanger_{label}_Bottom',(-lower_x,y,lower_local),(lower_x,y,lower_local),.92,.70,M['frame'],pivot)
    beam('UnderShipCradle',(-7.0,0,6.55-pz),(7.0,0,6.55-pz),1.05,1.05,M['frame'],pivot)
    return pivot,hull


def descendant(obj, ancestor):
    p=obj.parent
    while p:
        if p==ancestor:return True
        p=p.parent
    return False


def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))


def main():
    a=parse_args(); cfg=load_json(a.recipe)
    if cfg.get('contract')!=CONTRACT or cfg.get('assetId')!=ASSET_ID:
        raise RuntimeError('swinging ship master contract mismatch')
    policy=cfg.get('authoringPolicy',{})
    if policy.get('freshStart') is not True or policy.get('noVersionLineage') is not True:
        raise RuntimeError('fresh-start authoring policy required')

    studio=bs.load_json(a.studio_preset)
    out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio['render']['sourceResolution']))
    scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:mat(v) for k,v in cfg['materials'].items()}

    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0))
    root=bpy.context.object; root.name='AssetRoot'; root['assetId']=ASSET_ID; root['assetType']=cfg['assetType']; root['cameraContract']='CH_CAMERA_V1'; root['styleContract']=cfg['styleContract']; root['footprint']='7x6'; root['proceduralContract']=CONTRACT; root['geometrySource']='swinging_ship_master'; root['freshStart']=True

    deck,deck_contacts=build_boarding(root,cfg,M)
    support_contacts,supports,axle=build_supports(root,cfg,M)
    pivot,hull=build_ship(root,cfg,M)
    for o in deck_contacts+support_contacts: scene_gate.tag(o,'attraction.ground_contact',ground_contact=True)
    scene_gate.tag(deck,'attraction.loading_platform'); scene_gate.tag(hull,'attraction.gondola'); scene_gate.tag(axle,'attraction.pivot_axle')
    for o in supports: scene_gate.tag(o,'attraction.support')

    recv=studio['shadowReceiver']; rmat=bs.make_material('ShadowReceiver',recv['materialColor'],float(recv.get('roughness',1.0)))
    ground=bs.add_box('ShadowReceiverPlane',recv['location'],[22.5,19.0,float(recv['dimensions'][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=ground]
    for o in authored:o['runtimeLayer']='motion_overlay' if descendant(o,pivot) else 'static_base'

    bs.calibrate_ortho_scale(scene,authored,safety_margin=.20); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={'contract':CONTRACT,'assetId':ASSET_ID,'stage':'master_proxy','cameraContract':'CH_CAMERA_V1','footprint':cfg['footprint'],'recipe':'tools/tycoon_photo_studio/assets/park_swinging_ship_master.json','builder':'tools/tycoon_photo_studio/build_swinging_ship_master.py','modelingMethod':'fresh_start_lofted_ship_heavy_hangers_open_supports','blenderVersion':bpy.app.version_string,'renderEngine':scene.render.engine}
    (out/'studio_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=cfg['footprint'],profile=profile,asset_id=ASSET_ID,report_path=out/'preflight_report.json')
    scene_gate.require_pass(pre)
    if a.stage=='preflight': save_blend(a.save_blend); return
    if a.stage=='proxy':
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/'proxy_south.png',profile=profile,asset_id=ASSET_ID,direction='south')
        (out/'proxy_report.json').write_text(json.dumps(proxy,indent=2),encoding='utf-8'); save_blend(a.save_blend); return
    raise RuntimeError('final blocked until proxy approval')

if __name__=='__main__':
    main()
