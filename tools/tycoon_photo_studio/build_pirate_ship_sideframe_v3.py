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

CONTRACT = "CH_PIRATE_SHIP_SIDEFRAME_V3"
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


def box(name, loc, dims, mat, parent=None, bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(loc))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = tuple(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    if bevel:
        mod = obj.modifiers.new("EdgeBreak", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def cyl(name, loc, radius, depth, mat, rot=(0,0,0), parent=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=tuple(loc), rotation=rot)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
    return obj


def beam(name, a, b, width, depth, mat, parent=None):
    a = Vector(a); b = Vector(b); d = b - a
    obj = box(name, (a+b)*0.5, (width, depth, d.length), mat, parent, .03)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = d.to_track_quat('Z','Y')
    return obj


def loft_open_hull(name, stations, mat, parent):
    verts=[]; faces=[]
    for s in stations:
        x=float(s['x']); hw=float(s['halfWidth']); fz=float(s['floorZ']); gz=float(s['gunwaleZ'])
        verts.extend([(x,-hw,fz),(x,-hw,gz),(x,hw,gz),(x,hw,fz)])
    for i in range(len(stations)-1):
        a=i*4; b=(i+1)*4
        faces += [(a,b,b+1,a+1),(a+3,a+2,b+2,b+3),(a,a+3,b+3,b)]
    last=(len(stations)-1)*4
    faces += [(0,3,2,1),(last,last+1,last+2,last+3)]
    mesh=bpy.data.meshes.new(name+"Mesh")
    mesh.from_pydata(verts,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat); obj.parent=parent
    mod=obj.modifiers.new("HullSoftening","BEVEL"); mod.width=.12; mod.segments=2
    return obj


def interp_station(stations,x):
    ordered=sorted(stations,key=lambda s:float(s['x']))
    if x<=float(ordered[0]['x']): return ordered[0]
    if x>=float(ordered[-1]['x']): return ordered[-1]
    for a,b in zip(ordered,ordered[1:]):
        ax,bx=float(a['x']),float(b['x'])
        if ax<=x<=bx:
            t=(x-ax)/(bx-ax)
            return {
                'halfWidth':float(a['halfWidth'])+(float(b['halfWidth'])-float(a['halfWidth']))*t,
                'floorZ':float(a['floorZ'])+(float(b['floorZ'])-float(a['floorZ']))*t,
                'gunwaleZ':float(a['gunwaleZ'])+(float(b['gunwaleZ'])-float(a['gunwaleZ']))*t,
            }
    return ordered[-1]


def build_station(root,cfg,M):
    w=float(cfg['deckWidth']); d=float(cfg['deckDepth']); y=float(cfg['deckCenterY']); z=float(cfg['topZ'])
    deck=box('BoardingDeck',(0,y,z-.16),(w,d,.32),M['platform'],root,.03)
    contacts=[]
    for x in (-w*.46,-w*.16,w*.16,w*.46):
        for yy in (y-d*.44,y+d*.44):
            contacts.append(box(f'DeckFoot_{x}_{yy}',(x,yy,.11),(.95,.95,.22),M['frame'],root,.02))
    rh=float(cfg['railHeight'])
    # rails only on the outer side of the boarding dock: no empty square enclosure around the ride
    outer_y=y-d*.5
    beam('BoardingRailTop',(-w*.5,outer_y,z+rh),(w*.5,outer_y,z+rh),.08,.08,M['frame'],root)
    for i in range(13):
        x=-w*.5+w*i/12
        beam(f'BoardingRailPost_{i}',(x,outer_y,z),(x,outer_y,z+rh),.06,.06,M['frame'],root)
    sw=float(cfg['stairsWidth']); run=float(cfg['stairsRun']); steps=int(cfg['steps'])
    sh=z/steps; sd=run/steps; y0=outer_y-run
    for i in range(steps):
        box(f'BoardingStep_{i}',(0,y0+sd*(i+.5),sh*(i+1)/2),(sw,sd*.95,sh*(i+1)),M['platform'],root,.01)
    return deck,contacts


def build_sideframes(root,cfg,M):
    fy=float(cfg['frameY']); pz=float(cfg['pivotZ']); fx=float(cfg['footX']); tx=float(cfg['topHalfX'])
    bw=float(cfg['mainBeamWidth']); bd=float(cfg['mainBeamDepth']); pad=cfg['concretePad']
    contacts=[]; supports=[]
    # Two OPEN triangular side frames. No horizontal ladder braces.
    for y,label in ((-fy,'Front'),(fy,'Back')):
        for x,slabel in ((-fx,'L'),(fx,'R')):
            contacts.append(box(f'ConcretePad_{label}_{slabel}',(x,y,float(pad[2])*.5),tuple(map(float,pad)),M['concrete'],root,.03))
            contacts.append(box(f'SteelFoot_{label}_{slabel}',(x,y,.34),(1.35,1.20,.30),M['frame'],root,.02))
        supports.append(beam(f'{label}_MainLeg_L',(-fx,y,.48),(-tx,y,pz-.55),bw,bd,M['frame'],root))
        supports.append(beam(f'{label}_MainLeg_R',(fx,y,.48),(tx,y,pz-.55),bw,bd,M['frame'],root))
        beam(f'{label}_TopSaddle',(-tx,y,pz-.55),(tx,y,pz-.55),1.05,float(cfg['topTieDepth']),M['accent'],root)
        # short lower knee braces only; preserves an open silhouette
        beam(f'{label}_Knee_L',(-fx*.72,y,6.2),(-fx*.40,y,11.6),.46,.34,M['accent'],root)
        beam(f'{label}_Knee_R',(fx*.72,y,6.2),(fx*.40,y,11.6),.46,.34,M['accent'],root)
    # cross-ride ties are concentrated at the pivot and feet, not repeated as a cage
    beam('TopCrossTie',(0,-fy,pz-.55),(0,fy,pz-.55),.82,.82,M['frame'],root)
    beam('LeftFootTie',(-fx,-fy,.55),(-fx,fy,.55),.44,.40,M['frame'],root)
    beam('RightFootTie',(fx,-fy,.55),(fx,fy,.55),.44,.40,M['frame'],root)
    axle=cyl('MainAxle',(0,0,pz),float(cfg['axleRadius']),fy*2.35,M['frame'],(math.radians(90),0,0),root,36)
    br=float(cfg['bearingRadius'])
    for y in (-fy-.16,fy+.16):
        cyl('BearingHousing',(0,y,pz),br,.80,M['accent'],(math.radians(90),0,0),root,36)
        cyl('BearingHub',(0,y,pz),br*.54,.34,M['frame'],(math.radians(90),0,0),root,28)
    return contacts,supports,axle


def build_boat(root,cfg,M,pivot_z):
    center=float(cfg['centerZ']); stations=cfg['stations']
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,pivot_z))
    pivot=bpy.context.object; pivot.name='SwingPivot'; pivot.parent=root
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,center-pivot_z))
    boat=bpy.context.object; boat.name='BoatRoot'; boat.parent=pivot
    hull=loft_open_hull('SideFrameHull',stations,M['wood'],boat)

    # large continuous trim rails emphasize the ship, not the support frame
    for side,label in ((-1,'Port'),(1,'Starboard')):
        pts=[(float(s['x']),side*float(s['halfWidth']),float(s['gunwaleZ'])+.06) for s in stations]
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            beam(f'{label}Gunwale_{i}',a,b,.22,.18,M['accent'],boat)
    rows=int(cfg['seatRows']); span=float(cfg['seatSpan'])
    for i in range(rows):
        x=-span*.5+span*i/max(1,rows-1)
        s=interp_station(stations,x); hw=float(s['halfWidth']); fz=float(s['floorZ'])
        box(f'SeatBase_{i}',(x,0,fz+.78),(.76,max(1.0,hw*1.54),.24),M['seat'],boat,.04)
        box(f'SeatBack_{i}',(x+.24,0,fz+1.28),(.18,max(1.0,hw*1.48),.80),M['seat'],boat,.03)
    # tall ship ends, integrated into hull
    for idx,label in ((0,'Stern'),(-1,'Bow')):
        s=stations[idx]; x=float(s['x']); hw=float(s['halfWidth']); gz=float(s['gunwaleZ'])
        box(f'{label}DecorativeEnd',(x,0,gz+.85),(.34,max(.9,hw*1.65),1.95),M['trim'],boat,.06)

    # Heavy CRADLE: two side triangles plus a rigid under-boat beam. No four thin diagonal hangers.
    c=cfg['cradle']; ux=float(c['upperHalfX']); lx=float(c['lowerHalfX']); sy=float(c['sideY'])
    lower_world=float(c['lowerZWorld']); lower_local=lower_world-pivot_z
    under_world=float(c['underBoatZWorld']); under_local=under_world-pivot_z
    bw=float(c['beamWidth']); bd=float(c['beamDepth'])
    for y,label in ((-sy,'Near'),(sy,'Far')):
        beam(f'Cradle_{label}_Left',(-ux,y,-.20),(-lx,y,lower_local),bw,bd,M['accent'],pivot)
        beam(f'Cradle_{label}_Right',(ux,y,-.20),(lx,y,lower_local),bw,bd,M['accent'],pivot)
        beam(f'Cradle_{label}_Bottom',(-lx,y,lower_local),(lx,y,lower_local),bw*.82,bd*.90,M['frame'],pivot)
    beam('CradleUnderBoat',(-float(c['underBoatHalfX']),0,under_local),(float(c['underBoatHalfX']),0,under_local),1.00,1.00,M['frame'],pivot)
    for x in (-lx,lx):
        beam(f'CradleDrop_{x}',(x,-sy,lower_local),(x,sy,lower_local),.54,.48,M['frame'],pivot)
    return pivot,hull


def descendant(obj,ancestor):
    p=obj.parent
    while p:
        if p==ancestor:return True
        p=p.parent
    return False


def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))


def main():
    a=parse_args(); recipe=load_json(a.recipe)
    if recipe.get('contract')!=CONTRACT or recipe.get('assetId')!=ASSET_ID:
        raise RuntimeError('sideframe v3 contract mismatch')
    pol=recipe.get('authoringPolicy',{})
    if not pol.get('geometryComesFromRecipe') or pol.get('legacyVikingGeometryAllowed') is not False or pol.get('forbidReferenceDrivenV2Topology') is not True:
        raise RuntimeError('sideframe v3 clean-sheet policy required')

    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio['render']['sourceResolution']))
    scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:material(v) for k,v in recipe['materials'].items()}

    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0))
    root=bpy.context.object; root.name='AssetRoot'; root['assetId']=ASSET_ID; root['assetType']=recipe['assetType']; root['cameraContract']='CH_CAMERA_V1'; root['styleContract']=recipe['styleContract']; root['footprint']='7x6'; root['proceduralContract']=CONTRACT; root['geometrySource']='sideframe_v3'; root['cleanSheet']=True

    deck,deck_contacts=build_station(root,recipe['station'],M)
    frame_contacts,supports,axle=build_sideframes(root,recipe['structure'],M)
    pivot,hull=build_boat(root,recipe['boat'],M,float(recipe['structure']['pivotZ']))

    for o in deck_contacts+frame_contacts: scene_gate.tag(o,'attraction.ground_contact',ground_contact=True)
    scene_gate.tag(deck,'attraction.loading_platform'); scene_gate.tag(hull,'attraction.gondola'); scene_gate.tag(axle,'attraction.pivot_axle')
    for o in supports: scene_gate.tag(o,'attraction.support')

    recv=studio['shadowReceiver']; rmat=bs.make_material('ShadowReceiver',recv['materialColor'],float(recv.get('roughness',1.0)))
    ground=bs.add_box('ShadowReceiverPlane',recv['location'],[22.0,19.0,float(recv['dimensions'][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=ground]
    for o in authored:o['runtimeLayer']='motion_overlay' if descendant(o,pivot) else 'static_base'

    bs.calibrate_ortho_scale(scene,authored,safety_margin=.18); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={'contract':CONTRACT,'assetId':ASSET_ID,'stage':'sideframe_v3','cameraContract':'CH_CAMERA_V1','footprint':recipe['footprint'],'recipe':'tools/tycoon_photo_studio/assets/pirate_ship_ride_sideframe_v3_7x6.json','builder':'tools/tycoon_photo_studio/build_pirate_ship_sideframe_v3.py','modelingMethod':'open_triangular_sideframes_plus_heavy_cradle','blenderVersion':bpy.app.version_string,'renderEngine':scene.render.engine}
    (out/'studio_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=recipe['footprint'],profile=profile,asset_id=ASSET_ID,report_path=out/'preflight_report.json')
    scene_gate.require_pass(pre)
    if a.stage=='preflight': save_blend(a.save_blend); return
    if a.stage=='proxy':
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/'proxy_south.png',profile=profile,asset_id=ASSET_ID,direction='south')
        (out/'proxy_report.json').write_text(json.dumps(proxy,indent=2),encoding='utf-8'); save_blend(a.save_blend); return
    raise RuntimeError('final blocked until proxy approval')

if __name__=='__main__': main()
