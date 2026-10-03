#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
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

CONTRACT = "CH_SWINGING_SHIP_GONDOLA_REFERENCE_V1"
ASSET_ID = "attraction.park_viking_ship.gondola.study"


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


def make_mat(spec):
    return bs.make_material(spec["name"], spec["rgba"], float(spec.get("roughness", .6)), float(spec.get("metallic", 0)))


def box(name, loc, dims, mat, parent=None, bevel=.04):
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(loc))
    o = bpy.context.object
    o.name = name
    o.dimensions = tuple(dims)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if parent is not None:
        o.parent = parent
    if bevel:
        m = o.modifiers.new("EdgeBreak", "BEVEL")
        m.width = bevel
        m.segments = 2
    return o


def beam(name, a, b, width, depth, mat, parent=None):
    a = Vector(a); b = Vector(b); d = b - a
    o = box(name, (a+b)*.5, (width, depth, d.length), mat, parent, .025)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z', 'Y')
    return o


def section_points(s, inset=0.0, zraise=0.0):
    x=float(s['x']); hw=max(.10, float(s['halfWidth'])-inset)
    kz=float(s['keelZ'])+zraise
    cz=float(s['chineZ'])+zraise
    gz=float(s['gunwaleZ'])+zraise
    return [
        (x, 0.0, kz),
        (x, -hw*.68, cz),
        (x, -hw, gz),
        (x, hw, gz),
        (x, hw*.68, cz),
    ]


def loft_shell(name, sections, mat, parent, inset=0.0, zraise=0.0, flip=False):
    rings=[section_points(s,inset,zraise) for s in sections]
    verts=[v for ring in rings for v in ring]
    faces=[]; n=5
    # Four longitudinal strips: keel->port chine->port gunwale and mirrored starboard.
    for i in range(len(rings)-1):
        a=i*n; b=(i+1)*n
        quads=[(a+0,a+1,b+1,b+0),(a+1,a+2,b+2,b+1),(a+3,a+4,b+4,b+3),(a+4,a+0,b+0,b+4)]
        faces += [tuple(reversed(q)) if flip else q for q in quads]
    # close only bow/stern cross-sections, leave top open
    for base in (0,(len(rings)-1)*n):
        cap=(base+0,base+1,base+2,base+3,base+4)
        faces.append(tuple(reversed(cap)) if flip else cap)
    me=bpy.data.meshes.new(name+"Mesh")
    me.from_pydata(verts,[],faces); me.update()
    o=bpy.data.objects.new(name,me); bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat); o.parent=parent
    bev=o.modifiers.new("HullEdgeSoftening","BEVEL"); bev.width=.10 if not inset else .06; bev.segments=3
    return o


def interp(sections, x):
    ss=sorted(sections,key=lambda s:float(s['x']))
    if x<=float(ss[0]['x']): return ss[0]
    if x>=float(ss[-1]['x']): return ss[-1]
    for a,b in zip(ss,ss[1:]):
        ax,bx=float(a['x']),float(b['x'])
        if ax<=x<=bx:
            t=(x-ax)/(bx-ax)
            return {
                'halfWidth':float(a['halfWidth'])+(float(b['halfWidth'])-float(a['halfWidth']))*t,
                'keelZ':float(a['keelZ'])+(float(b['keelZ'])-float(a['keelZ']))*t,
                'chineZ':float(a['chineZ'])+(float(b['chineZ'])-float(a['chineZ']))*t,
                'gunwaleZ':float(a['gunwaleZ'])+(float(b['gunwaleZ'])-float(a['gunwaleZ']))*t,
            }
    return ss[-1]


def build_gondola(root, cfg, M):
    h=cfg['hull']; sections=h['sections']; wall=float(h['wallThickness'])
    outer=loft_shell('GondolaOuterHull',sections,M['outerHull'],root)
    inner=loft_shell('GondolaInnerShell',sections,M['innerHull'],root,inset=wall,zraise=.16,flip=True)

    # Strong continuous sheer rails follow the real hull silhouette.
    for side,label in ((-1,'Port'),(1,'Starboard')):
        pts=[(float(s['x']),side*float(s['halfWidth']),float(s['gunwaleZ'])+.08) for s in sections]
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            beam(f'{label}Sheer_{i}',a,b,.20,.16,M['trim'],root)

    # Interior floor follows the keel rise instead of being one flat rectangular slab.
    seat_rows=int(h['seatRows']); span=float(h['seatSpan'])
    xs=[-span*.5+span*i/max(1,seat_rows-1) for i in range(seat_rows)]
    for i,x in enumerate(xs):
        s=interp(sections,x); hw=float(s['halfWidth']); floor=max(float(s['chineZ'])+.22,float(s['keelZ'])+.65)
        # deck plank and transverse seat row
        box(f'FloorPlank_{i}',(x,0,floor),(.66,max(.9,hw*1.55),.16),M['floor'],root,.025)
        box(f'Bench_{i}',(x,0,floor+.68),(.58,max(.8,hw*1.46),.24),M['seat'],root,.045)
        box(f'BenchBack_{i}',(x+.20,0,floor+1.12),(.16,max(.8,hw*1.40),.72),M['seat'],root,.035)

    # Deep bow/stern transoms with tall decorative rise; these are part of the ship, not ride supports.
    for idx,label,extra in ((0,'Stern',float(h['sternRise'])),(-1,'Bow',float(h['bowRise']))):
        s=sections[idx]; x=float(s['x']); hw=float(s['halfWidth']); gz=float(s['gunwaleZ'])
        box(f'{label}Transom',(x,0,gz+.55),(.34,max(.90,hw*1.90),1.20),M['outerHull'],root,.08)
        box(f'{label}Crest',(x,0,gz+1.35+extra*.35),(.28,max(.72,hw*1.38),1.20+extra*.45),M['trim'],root,.08)

    # Rubbing strakes and keel give the silhouette more mass and remove the old canoe read.
    for side,label in ((-1,'Port'),(1,'Starboard')):
        pts=[]
        for s in sections[1:-1]:
            x=float(s['x']); hw=float(s['halfWidth']); z=(float(s['chineZ'])+float(s['gunwaleZ']))*.56
            pts.append((x,side*(hw+.035),z))
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            beam(f'{label}Rubrail_{i}',a,b,.16,.11,M['trim'],root)
    keel_pts=[(float(s['x']),0,float(s['keelZ'])-.08) for s in sections]
    for i,(a,b) in enumerate(zip(keel_pts,keel_pts[1:])):
        beam(f'Keel_{i}',a,b,.22,.24,M['trim'],root)
    return outer


def save_blend(path):
    if path:
        p=Path(path).resolve(); p.parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(p))


def main():
    a=parse_args(); cfg=load_json(a.recipe)
    if cfg.get('contract')!=CONTRACT or cfg.get('assetId')!=ASSET_ID:
        raise RuntimeError('gondola reference contract mismatch')
    policy=cfg.get('authoringPolicy',{})
    if policy.get('scope')!='gondola_only' or policy.get('noSupportFrame') is not True or policy.get('noPivot') is not True:
        raise RuntimeError('gondola-only fresh authoring policy required')

    studio=bs.load_json(a.studio_preset); out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=True)
    bs.clear_scene(); source_res=tuple(map(int,studio['render']['sourceResolution']))
    scene=bs.configure_scene(studio,source_res,str(out)); scene.render.film_transparent=True; scene.render.image_settings.color_mode='RGBA'
    M={k:make_mat(v) for k,v in cfg['materials'].items()}

    bpy.ops.object.empty_add(type='PLAIN_AXES',location=(0,0,0))
    root=bpy.context.object; root.name='AssetRoot'; root['assetId']=ASSET_ID; root['assetType']=cfg['assetType']; root['cameraContract']='CH_CAMERA_V1'; root['styleContract']=cfg['styleContract']; root['footprint']='7x3'; root['proceduralContract']=CONTRACT; root['authoringScope']='gondola_only'
    hull=build_gondola(root,cfg,M)
    scene_gate.tag(hull,'attraction.gondola',ground_contact=False)

    recv=studio['shadowReceiver']; rmat=bs.make_material('ShadowReceiver',recv['materialColor'],float(recv.get('roughness',1.0)))
    ground=bs.add_box('ShadowReceiverPlane',recv['location'],[22.0,10.0,float(recv['dimensions'][2])],rmat,0.0)
    authored=[o for o in bpy.context.scene.objects if o.type=='MESH' and o!=ground]
    for o in authored:o['runtimeLayer']='motion_overlay'

    bs.calibrate_ortho_scale(scene,authored,safety_margin=.18); bs.set_direction(root,bs.DIRECTIONS[0]); bpy.context.view_layer.update()
    meta={'contract':CONTRACT,'assetId':ASSET_ID,'stage':'gondola_reference_proxy','cameraContract':'CH_CAMERA_V1','footprint':cfg['footprint'],'recipe':'tools/tycoon_photo_studio/assets/swinging_ship_gondola_reference.json','builder':'tools/tycoon_photo_studio/build_swinging_ship_gondola_reference.py','modelingMethod':'gondola_only_multistrake_open_hull','blenderVersion':bpy.app.version_string,'renderEngine':scene.render.engine}
    (out/'studio_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')

    profile=scene_gate.load_profile(a.preflight_profile)
    pre=scene_gate.run_preflight(scene=scene,authored=authored,footprint=cfg['footprint'],profile=profile,asset_id=ASSET_ID,report_path=out/'preflight_report.json')
    scene_gate.require_pass(pre)
    if a.stage=='preflight': save_blend(a.save_blend); return
    if a.stage=='proxy':
        proxy=scene_gate.render_proxy(scene=scene,authored=authored,output_path=out/'proxy_south.png',profile=profile,asset_id=ASSET_ID,direction='south')
        (out/'proxy_report.json').write_text(json.dumps(proxy,indent=2),encoding='utf-8'); save_blend(a.save_blend); return
    raise RuntimeError('final blocked until gondola silhouette is approved')

if __name__=='__main__':
    main()
