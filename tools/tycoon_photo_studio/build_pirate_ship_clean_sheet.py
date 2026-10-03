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

CONTRACT="CH_PIRATE_SHIP_CLEAN_SHEET_V1"
ASSET_ID="attraction.park_viking_ship.01"

def args():
    a=sys.argv; a=a[a.index("--")+1:] if "--" in a else []
    p=argparse.ArgumentParser(); p.add_argument("--recipe",required=True); p.add_argument("--studio-preset",required=True); p.add_argument("--output",required=True); p.add_argument("--save-blend"); p.add_argument("--stage",choices=("preflight","proxy","final"),default="proxy"); p.add_argument("--preflight-profile"); return p.parse_args(a)

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def mat(name,cfg): return bs.make_material(name,cfg["rgba"],float(cfg.get("roughness",.6)),float(cfg.get("metallic",0)))

def box(name,loc,dim,m,parent=None,bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=dim; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(m)
    if parent:o.parent=parent
    if bevel:
        mod=o.modifiers.new("EdgeBreak","BEVEL"); mod.width=bevel; mod.segments=2
    return o

def cyl(name,loc,r,depth,m,rot=(0,0,0),parent=None,verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc,rotation=rot); o=bpy.context.object; o.name=name; o.data.materials.append(m)
    if parent:o.parent=parent
    return o

def beam(name,a,b,width,depth,m,parent=None):
    a,b=Vector(a),Vector(b); d=b-a
    o=box(name,(a+b)*.5,(width,depth,d.length),m,parent,.03); o.rotation_mode='QUATERNION'; o.rotation_quaternion=d.to_track_quat('Z','Y'); return o

def prism_xz(name,profile,yhalf,m,parent=None):
    n=len(profile); verts=[(x,-yhalf,z) for x,z in profile]+[(x,yhalf,z) for x,z in profile]; faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
    for i in range(n):
        j=(i+1)%n; faces.append((i,j,n+j,n+i))
    me=bpy.data.meshes.new(name+"Mesh"); me.from_pydata(verts,[],faces); me.update(); o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o); o.data.materials.append(m)
    if parent:o.parent=parent
    mod=o.modifiers.new("HullSoftening","BEVEL"); mod.width=.08; mod.segments=2
    return o

def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))

def build_station(root,g,M):
    w,d,z=float(g['platformWidth']),float(g['platformDepth']),float(g['platformTopZ'])
    deck=box('LoadingDeck',(0,0,z-.16),(w,d,.32),M['platform'],root,.03); contacts=[]
    for x in (-w*.43,-w*.14,w*.14,w*.43):
        for y in (-d*.42,d*.42):
            contacts.append(box(f'Foot_{x}_{y}',(x,y,.10),(.9,.9,.20),M['frame'],root,.02)); box(f'Post_{x}_{y}',(x,y,z*.48),(.42,.42,z*.82),M['frame'],root,.02)
    for y in (-d*.5,d*.5):
        for x in [(-w*.5)+(w*i/12) for i in range(13)]: beam(f'RailPost_{x}_{y}',(x,y,z),(x,y,z+1.25),.07,.07,M['frame'],root)
        beam(f'RailTop_{y}',(-w*.5,y,z+1.25),(w*.5,y,z+1.25),.08,.08,M['frame'],root)
    sw,run=float(g['stairWidth']),float(g['stairRun']); steps=10; sh=z/steps; sd=run/steps; y0=-d*.5-run
    for i in range(steps): box(f'Step_{i}',(0,y0+sd*(i+.5),sh*(i+1)/2),(sw,sd*.94,sh*(i+1)),M['platform'],root,.01)
    return deck,contacts

def build_portals(root,g,M):
    fx,hy,pz,sz=float(g['towerFootHalfX']),float(g['towerHalfY']),float(g['pivotZ']),float(g['portalShoulderZ'])
    contacts=[]; supports=[]
    for ys,label in ((-hy,'Front'),(hy,'Back')):
        for sign,slabel in ((-1,'L'),(1,'R')):
            x=sign*fx
            contacts.append(box(f'PortalFoot_{label}_{slabel}',(x,ys,.13),(1.8,1.55,.26),M['frame'],root,.02))
            a=(x,ys,.26); b=(x*.86,ys,sz); c=(sign*2.1,ys,pz-1.7); d=(sign*.9,ys,pz)
            supports += [beam(f'Column_{label}_{slabel}',a,b,1.20,.92,M['frame'],root),beam(f'Shoulder_{label}_{slabel}',b,c,1.30,.94,M['frame'],root),beam(f'CrownLeg_{label}_{slabel}',c,d,1.18,.92,M['frame'],root)]
            beam(f'GoldLower_{label}_{slabel}',(x-sign*.16,ys-.02,.8),(x*.87-sign*.12,ys-.02,sz-.6),.38,.20,M['gold'],root)
            beam(f'GoldUpper_{label}_{slabel}',(x*.85-sign*.12,ys-.02,sz+.1),(sign*2.2,ys-.02,pz-2.0),.38,.20,M['gold'],root)
        z=sz*.70; beam(f'BridgeBottom_{label}',(-fx*.62,ys,z),(fx*.62,ys,z),.46,.40,M['frame'],root); beam(f'BridgeTop_{label}',(-fx*.56,ys,z+1.70),(fx*.56,ys,z+1.70),.36,.32,M['frame'],root)
        xs=[-fx*.56,-fx*.28,0,fx*.28,fx*.56]
        for i in range(4): beam(f'TrussA_{label}_{i}',(xs[i],ys,z),(xs[i+1],ys,z+1.70),.20,.18,M['frame'],root); beam(f'TrussB_{label}_{i}',(xs[i],ys,z+1.70),(xs[i+1],ys,z),.20,.18,M['frame'],root)
    axle=cyl('MainAxle',(0,0,pz),.66,hy*2.38,M['frame'],(math.radians(90),0,0),root,32)
    for y in (-hy-.14,hy+.14):
        cyl('Bearing', (0,y,pz),1.45,.64,M['gold'],(math.radians(90),0,0),root,32); cyl('Hub',(0,y+(.30 if y>0 else -.30),pz),.78,.28,M['frame'],(math.radians(90),0,0),root,24)
    return contacts,supports,axle

def build_boat(root,g,M):
    pz,cz,L,hw,depth=float(g['pivotZ']),float(g['boatCenterZ']),float(g['boatLength']),float(g['boatHalfWidth']),float(g['boatDepth']); half=L/2
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,pz)); pivot=bpy.context.object; pivot.name='SwingPivot'; pivot.parent=root
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,cz-pz)); boat=bpy.context.object; boat.name='BoatRoot'; boat.parent=pivot

    outer=[(-half,2.55),(-half*.95,4.25),(-half*.82,2.85),(-half*.62,1.30),(-half*.34,.10),(0,-1.15),(half*.34,.10),(half*.62,1.30),(half*.82,2.85),(half*.95,4.25),(half,2.55)]
    inner=[(half*.90,2.40),(half*.76,2.02),(half*.56,.95),(half*.30,.05),(0,-.62),(-half*.30,.05),(-half*.56,.95),(-half*.76,2.02),(-half*.90,2.40)]
    side_profile=outer+inner
    hull_parts=[]
    for sy,label in ((-1,'Front'),(1,'Back')):
        wall=prism_xz(f'HullSide_{label}',side_profile,.18,M['wood'],boat); wall.location.y=sy*(hw-.18); hull_parts.append(wall)
        rim_pts=[(-half*.93,sy*hw,3.90),(-half*.78,sy*hw,2.55),(-half*.56,sy*hw,1.16),(0,sy*hw,-.42),(half*.56,sy*hw,1.16),(half*.78,sy*hw,2.55),(half*.93,sy*hw,3.90)]
        for i in range(len(rim_pts)-1): beam(f'Gunwale_{label}_{i}',rim_pts[i],rim_pts[i+1],.18,.12,M['gold'],boat)
        for i,x in enumerate((-6.0,-4.0,-2.0,0,2.0,4.0,6.0)):
            box(f'Fascia_{label}_{i}',(x,sy*(hw+.07),.58),(1.15,.10,.86),M['trim'],boat,.025)

    box('PassengerFloor',(0,0,.46),(L*.72,hw*1.55,.24),M['wood'],boat,.03)
    beam('Keel',(-half*.74,0,-1.02),(half*.74,0,-1.02),.30,.36,M['frame'],boat)
    for x in (-6.2,-4.1,-2.0,0,2.0,4.1,6.2):
        beam(f'CrossRib_{x}',(x,-hw*.88,.28),(x,hw*.88,.28),.16,.18,M['gold'],boat)

    rows=int(g['seatRows'])
    seat_span=L*.62
    for i in range(rows):
        x=-seat_span*.5+(seat_span*i/max(1,rows-1))
        box(f'SeatBase_{i}',(x,0,.88),(.74,hw*1.38,.24),M['seat'],boat,.04)
        box(f'SeatBack_{i}',(x+.23,0,1.28),(.18,hw*1.34,.66),M['seat'],boat,.03)
        beam(f'LapBar_{i}',(x-.10,-hw*.60,1.42),(x-.10,hw*.60,1.42),.07,.07,M['gold'],boat)

    for s,label in ((-1,'L'),(1,'R')):
        beam(f'ProwSpine_{label}',(s*half*.91,0,2.65),(s*(half+.42),0,5.55),.46,.66,M['gold'],boat)
        cyl(f'ProwMedallion_{label}',(s*(half+.44),0,5.68),.68,.38,M['trim'],(math.radians(90),0,0),boat,24)

    top_x=1.20; attach_x=6.35; top_y=2.42; attach_y=hw+.10
    attach_z=(cz-pz)+2.12
    for sx in (-1,1):
        for sy in (-1,1):
            beam(f'Yoke_{sx}_{sy}',(sx*top_x,sy*top_y,-.20),(sx*attach_x,sy*attach_y,attach_z),.72,.54,M['gold'],pivot)
            cyl(f'HullJoint_{sx}_{sy}',(sx*attach_x,sy*attach_y,attach_z),.48,.50,M['frame'],(math.radians(90),0,0),pivot,20)
            cyl(f'HullJointCap_{sx}_{sy}',(sx*attach_x,sy*(attach_y+.18),attach_z),.27,.14,M['gold'],(math.radians(90),0,0),pivot,18)
    return pivot,hull_parts[0]

def desc(o,a):
    p=o.parent
    while p:
        if p==a:return True
        p=p.parent
    return False

def main():
    a=args(); recipe=load(a.recipe)
    if recipe.get('contract')!=CONTRACT or recipe.get('assetId')!=ASSET_ID: raise RuntimeError('clean-sheet contract mismatch')
    if recipe.get('authoringPolicy',{}).get('cleanSheet') is not True: raise RuntimeError('clean-sheet policy required')
    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio['render']['sourceResolution'])); scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:mat(v['name'],v) for k,v in recipe['materials'].items()}
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0)); root=bpy.context.object; root.name='AssetRoot'; root['assetId']=ASSET_ID; root['assetType']=recipe['assetType']; root['cameraContract']='CH_CAMERA_V1'; root['styleContract']=recipe['styleContract']; root['footprint']='7x6'; root['proceduralContract']=CONTRACT; root['cleanSheet']=True
    deck,station_contacts=build_station(root,recipe['geometry'],M); tower_contacts,supports,axle=build_portals(root,recipe['geometry'],M); pivot,hull=build_boat(root,recipe['geometry'],M)
    for o in station_contacts+tower_contacts: scene_gate.tag(o,'attraction.ground_contact',ground_contact=True)
    scene_gate.tag(deck,'attraction.loading_platform',ground_contact=False); scene_gate.tag(hull,'attraction.gondola',ground_contact=False); scene_gate.tag(axle,'attraction.pivot_axle',ground_contact=False)
    for o in supports: scene_gate.tag(o,'attraction.support',ground_contact=False)
    recv=studio['shadowReceiver']; rmat=bs.make_material('ShadowReceiver',recv['materialColor'],float(recv.get('roughness',1.0))); ground=bs.add_box('ShadowReceiverPlane',recv['location'],[max(float(recv['dimensions'][0]),21.0),max(float(recv['dimensions'][1]),18.0),float(recv['dimensions'][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=ground]
    for o in authored:o['runtimeLayer']='motion_overlay' if desc(o,pivot) else 'static_base'
    bs.calibrate_ortho_scale(scene,authored,safety_margin=.28); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={'contract':CONTRACT,'assetId':ASSET_ID,'stage':'clean_sheet_gate','cameraContract':'CH_CAMERA_V1','footprint':recipe['footprint'],'recipe':'tools/tycoon_photo_studio/assets/pirate_ship_ride_clean_7x6.json','builder':'tools/tycoon_photo_studio/build_pirate_ship_clean_sheet.py','modelingMethod':'segmented_portal_plus_open_gondola','blenderVersion':bpy.app.version_string,'renderEngine':scene.render.engine}; (out/'studio_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    profile=scene_gate.load_profile(a.preflight_profile); pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=recipe['footprint'],profile=profile,asset_id=ASSET_ID,report_path=out/'preflight_report.json'); scene_gate.require_pass(pre)
    if a.stage=='preflight': save_blend(a.save_blend); return
    if a.stage=='proxy':
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/'proxy_south.png',profile=profile,asset_id=ASSET_ID,direction='south'); (out/'proxy_report.json').write_text(json.dumps(proxy,indent=2),encoding='utf-8'); save_blend(a.save_blend); return
    raise RuntimeError('final blocked until proxy approval')
if __name__=='__main__': main()
