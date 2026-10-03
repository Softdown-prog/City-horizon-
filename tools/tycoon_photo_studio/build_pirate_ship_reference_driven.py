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

CONTRACT = "CH_PIRATE_SHIP_REFERENCE_DRIVEN_V2"
ASSET_ID = "attraction.park_viking_ship.01"


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--recipe", required=True)
    p.add_argument("--studio-preset", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--save-blend")
    p.add_argument("--stage", choices=("preflight", "proxy", "final"), default="proxy")
    p.add_argument("--preflight-profile")
    return p.parse_args(argv)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def material(spec):
    return bs.make_material(spec["name"], spec["rgba"], float(spec.get("roughness", .6)), float(spec.get("metallic", 0)))


def box(name, loc, dims, mat, parent=None, bevel=.035):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(loc))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("EdgeBreak", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def cylinder(name, loc, radius, depth, mat, rot=(0,0,0), parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=tuple(loc), rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent:
        obj.parent = parent
    return obj


def beam(name, a, b, width, depth, mat, parent=None):
    a = Vector(a); b = Vector(b); delta = b - a
    obj = box(name, (a+b)*.5, (width, depth, delta.length), mat, parent, .025)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = delta.to_track_quat('Z', 'Y')
    return obj


def loft_hull(name, stations, mat, parent):
    """Build a real open boat volume from recipe stations; no hardcoded Viking side-profile."""
    verts = []
    faces = []
    # four rails per station: port floor/gunwale and starboard floor/gunwale
    for s in stations:
        x = float(s['x']); hw = float(s['halfWidth']); fz = float(s['floorZ']); gz = float(s['gunwaleZ'])
        verts.extend([(x,-hw,fz),(x,-hw,gz),(x,hw,gz),(x,hw,fz)])
    for i in range(len(stations)-1):
        a = i*4; b = (i+1)*4
        faces += [
            (a+0,b+0,b+1,a+1),   # port side
            (a+3,a+2,b+2,b+3),   # starboard side
            (a+0,a+3,b+3,b+0),   # bottom
        ]
    # bow/stern caps leave the top open
    faces += [(0,3,2,1), ((len(stations)-1)*4, (len(stations)-1)*4+1, (len(stations)-1)*4+2, (len(stations)-1)*4+3)]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.parent = parent
    bevel = obj.modifiers.new("HullEdgeSoftening", "BEVEL")
    bevel.width = .10
    bevel.segments = 2
    return obj


def interp_station(stations, x):
    ordered = sorted(stations, key=lambda s: float(s['x']))
    if x <= float(ordered[0]['x']): return ordered[0]
    if x >= float(ordered[-1]['x']): return ordered[-1]
    for a,b in zip(ordered, ordered[1:]):
        ax,bx = float(a['x']), float(b['x'])
        if ax <= x <= bx:
            t = (x-ax)/(bx-ax)
            return {
                'halfWidth': float(a['halfWidth']) + (float(b['halfWidth'])-float(a['halfWidth']))*t,
                'floorZ': float(a['floorZ']) + (float(b['floorZ'])-float(a['floorZ']))*t,
                'gunwaleZ': float(a['gunwaleZ']) + (float(b['gunwaleZ'])-float(a['gunwaleZ']))*t,
            }
    return ordered[-1]


def build_station(root, cfg, M):
    d = cfg['deck']; w, dep, z = float(d['width']), float(d['depth']), float(d['topZ'])
    deck = box('LoadingDeck',(0,0,z-.16),(w,dep,.32),M['platform'],root,.03)
    contacts=[]
    for x in (-w*.45,-w*.15,w*.15,w*.45):
        for y in (-dep*.44,dep*.44):
            contacts.append(box(f'StationFoot_{x}_{y}',(x,y,.10),(.9,.9,.20),M['frame'],root,.02))
    rail_h=float(cfg['railHeight'])
    for y in (-dep*.5,dep*.5):
        beam(f'Rail_{y}',(-w*.5,y,z+rail_h),(w*.5,y,z+rail_h),.08,.08,M['frame'],root)
        for i in range(13):
            x=-w*.5+w*i/12
            beam(f'RailPost_{y}_{i}',(x,y,z),(x,y,z+rail_h),.06,.06,M['frame'],root)
    st=cfg['stairs']; sw,run,steps=float(st['width']),float(st['run']),int(st['steps'])
    sh=z/steps; sd=run/steps; y0=-dep*.5-run
    for i in range(steps):
        box(f'Step_{i}',(0,y0+sd*(i+.5),sh*(i+1)/2),(sw,sd*.95,sh*(i+1)),M['platform'],root,.01)
    return deck, contacts


def build_structure(root, cfg, M):
    fy=float(cfg['frameY']); pz=float(cfg['pivotZ']); bw,bd=map(float,cfg['towerBeam'])
    contacts=[]; supports=[]
    for y,label in ((-fy,'Front'),(fy,'Back')):
        for side,key in ((-1,'leftTower'),(1,'rightTower')):
            pts=[(float(x),y,float(z)) for x,z in cfg[key]]
            contacts.append(box(f'{label}_{key}_Foot',pts[0],(1.65,1.45,.24),M['frame'],root,.02))
            for i,(a,b) in enumerate(zip(pts,pts[1:])):
                supports.append(beam(f'{label}_{key}_{i}',a,b,bw,bd,M['frame'],root))
        # horizontal braces now connect the two shaped towers; not an A-frame crown
        for zi in cfg['crossBracesZ']:
            zi=float(zi)
            left_x=next((float(p[0]) for p in cfg['leftTower'] if abs(float(p[1])-zi)<.01), -6.8)
            right_x=-left_x
            beam(f'{label}_Cross_{zi}',(left_x,y,zi),(right_x,y,zi),.36,.32,M['frame'],root)
        # bearing saddle and axle carrier
        beam(f'{label}_BearingCarrier',(-2.5,y,pz-1.05),(2.5,y,pz-1.05),.72,.58,M['accent'],root)
    axle=cylinder('MainAxle',(0,0,pz),float(cfg['axleRadius']),fy*2.28,M['frame'],(math.radians(90),0,0),root,32)
    br=float(cfg['bearingRadius'])
    for y in (-fy-.10,fy+.10):
        cylinder('BearingHousing',(0,y,pz),br,.74,M['accent'],(math.radians(90),0,0),root,32)
        cylinder('BearingHub',(0,y,pz),br*.56,.30,M['frame'],(math.radians(90),0,0),root,24)
    return contacts,supports,axle


def build_boat(root, cfg, M, pivot_z):
    center=float(cfg['centerZ']); stations=cfg['stations']
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,pivot_z))
    pivot=bpy.context.object; pivot.name='SwingPivot'; pivot.parent=root
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0,0,center-pivot_z))
    boat=bpy.context.object; boat.name='BoatRoot'; boat.parent=pivot

    hull=loft_hull('ReferenceDrivenHull',stations,M['wood'],boat)
    # gunwale rails follow recipe station coordinates, producing a long real-ride silhouette
    for side,label in ((-1,'Port'),(1,'Starboard')):
        pts=[(float(s['x']),side*float(s['halfWidth']),float(s['gunwaleZ'])+.05) for s in stations]
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            beam(f'{label}Gunwale_{i}',a,b,.20,.16,M['accent'],boat)
    # ribs and floor beams derived from stations
    for i,s in enumerate(stations[1:-1],1):
        x=float(s['x']); hw=float(s['halfWidth']); fz=float(s['floorZ'])+.14
        beam(f'CrossRib_{i}',(x,-hw*.92,fz),(x,hw*.92,fz),.16,.18,M['accent'],boat)
    # passenger benches: transverse rows, following the curved floor
    rows=int(cfg['seatRows']); span=float(cfg['seatSpan'])
    for i in range(rows):
        x=-span*.5+span*i/max(1,rows-1)
        s=interp_station(stations,x); hw=float(s['halfWidth']); floor=float(s['floorZ'])
        box(f'SeatBase_{i}',(x,0,floor+.72),(.72,max(.8,hw*1.52),.22),M['seat'],boat,.035)
        box(f'SeatBack_{i}',(x+.23,0,floor+1.18),(.16,max(.8,hw*1.48),.74),M['seat'],boat,.025)
    # tall decorative bow/stern plates follow end stations instead of the old fixed prow spine
    for idx,label in ((0,'Stern'),(-1,'Bow')):
        s=stations[idx]; x=float(s['x']); hw=float(s['halfWidth']); gz=float(s['gunwaleZ'])
        box(f'{label}Crest',(x,0,gz+.65),(.30,hw*1.55,1.55),M['trim'],boat,.05)

    susp=cfg['suspension']
    for i,(top,attach) in enumerate(zip(susp['topAnchors'],susp['boatAnchors'])):
        # both coordinates are world-relative to pivot; convert boat anchor into pivot space directly
        beam(f'Suspension_{i}',top,attach,float(susp['beamWidth']),float(susp['beamDepth']),M['accent'],pivot)
        cylinder(f'SuspensionJoint_{i}',attach,.38,.46,M['frame'],(math.radians(90),0,0),pivot,20)
    return pivot,hull


def descendant(obj, ancestor):
    p=obj.parent
    while p:
        if p==ancestor: return True
        p=p.parent
    return False


def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))


def main():
    a=parse_args(); recipe=load_json(a.recipe)
    if recipe.get('contract') != CONTRACT or recipe.get('assetId') != ASSET_ID:
        raise RuntimeError('reference-driven contract mismatch')
    policy=recipe.get('authoringPolicy',{})
    if not policy.get('geometryComesFromRecipe') or policy.get('legacyVikingGeometryAllowed') is not False:
        raise RuntimeError('recipe-driven clean-sheet policy required')

    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio['render']['sourceResolution']))
    scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:material(v) for k,v in recipe['materials'].items()}

    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0))
    root=bpy.context.object; root.name='AssetRoot'; root['assetId']=ASSET_ID; root['assetType']=recipe['assetType']; root['cameraContract']='CH_CAMERA_V1'; root['styleContract']=recipe['styleContract']; root['footprint']='7x6'; root['proceduralContract']=CONTRACT; root['cleanSheet']=True; root['geometrySource']='recipe_v2'

    deck,station_contacts=build_station(root,recipe['station'],M)
    tower_contacts,supports,axle=build_structure(root,recipe['structure'],M)
    pivot,hull=build_boat(root,recipe['boat'],M,float(recipe['structure']['pivotZ']))

    for o in station_contacts+tower_contacts: scene_gate.tag(o,'attraction.ground_contact',ground_contact=True)
    scene_gate.tag(deck,'attraction.loading_platform',ground_contact=False)
    scene_gate.tag(hull,'attraction.gondola',ground_contact=False)
    scene_gate.tag(axle,'attraction.pivot_axle',ground_contact=False)
    for o in supports: scene_gate.tag(o,'attraction.support',ground_contact=False)

    recv=studio['shadowReceiver']; rmat=bs.make_material('ShadowReceiver',recv['materialColor'],float(recv.get('roughness',1.0)))
    ground=bs.add_box('ShadowReceiverPlane',recv['location'],[max(float(recv['dimensions'][0]),22.0),max(float(recv['dimensions'][1]),19.0),float(recv['dimensions'][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=ground]
    for o in authored: o['runtimeLayer']='motion_overlay' if descendant(o,pivot) else 'static_base'

    bs.calibrate_ortho_scale(scene,authored,safety_margin=.16)
    bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={'contract':CONTRACT,'assetId':ASSET_ID,'stage':'reference_driven_v2','cameraContract':'CH_CAMERA_V1','footprint':recipe['footprint'],'recipe':'tools/tycoon_photo_studio/assets/pirate_ship_ride_reference_v2_7x6.json','builder':'tools/tycoon_photo_studio/build_pirate_ship_reference_driven.py','modelingMethod':'recipe_station_loft_plus_shaped_towers','blenderVersion':bpy.app.version_string,'renderEngine':scene.render.engine}
    (out/'studio_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=recipe['footprint'],profile=profile,asset_id=ASSET_ID,report_path=out/'preflight_report.json')
    scene_gate.require_pass(pre)
    if a.stage=='preflight': save_blend(a.save_blend); return
    if a.stage=='proxy':
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/'proxy_south.png',profile=profile,asset_id=ASSET_ID,direction='south')
        (out/'proxy_report.json').write_text(json.dumps(proxy,indent=2),encoding='utf-8'); save_blend(a.save_blend); return
    raise RuntimeError('final blocked until proxy approval')

if __name__=='__main__':
    main()
