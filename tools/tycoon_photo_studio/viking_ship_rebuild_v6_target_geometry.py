"""Target-matched full-scale Viking ship geometry for City Horizon V6.

This module is intentionally independent from Viking V2/V3/V4/V5 geometry.
It redraws the attraction from generic CH Blender primitives to match the
user-approved concept image: massive decorated A-frame, large top axle,
long deep ship, dense seating, raised boarding deck, stairs and railings.
"""
from __future__ import annotations

import math
import bpy
from mathutils import Vector

import build_ferris_wheel as fw


def beam_between(name, a, b, width, depth, mat, parent=None, bevel=0.025):
    a = Vector(a); b = Vector(b); d = b - a
    if d.length <= 1e-6:
        raise ValueError(name)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(a+b)*0.5)
    o = bpy.context.object
    o.name = name
    o.dimensions = (float(width), float(depth), float(d.length))
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = d.to_track_quat('Z','Y')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    if bevel > 0:
        m = o.modifiers.new('EdgeBreak','BEVEL'); m.width = bevel; m.segments = 1
    if parent is not None: o.parent = parent
    return o


def hull_sections(g):
    L = float(g['shipLength']) * 0.5
    W = float(g['shipHalfWidth'])
    return [
        (-L, W*0.18, 0.10, -0.80, -2.65),
        (-L*0.92, W*0.56, -0.05, -1.05, -3.15),
        (-L*0.70, W*0.88, -0.28, -1.28, -3.55),
        (-L*0.38, W, -0.42, -1.42, -3.78),
        (0.0, W*1.03, -0.48, -1.48, -3.88),
        (L*0.38, W, -0.42, -1.42, -3.78),
        (L*0.70, W*0.88, -0.28, -1.28, -3.55),
        (L*0.92, W*0.56, -0.05, -1.05, -3.15),
        (L, W*0.18, 0.10, -0.80, -2.65),
    ]


def _build_hull(boat_root, g, mats):
    sec = hull_sections(g); verts=[]; faces=[]; ring=6
    for x,w,top,mid,bot in sec:
        verts += [(x,-w,top),(x,-w*.92,mid),(x,-w*.34,bot),(x,w*.34,bot),(x,w*.92,mid),(x,w,top)]
    for s in range(len(sec)-1):
        a=s*ring; b=(s+1)*ring
        for r in range(ring):
            n=(r+1)%ring; faces.append((a+r,a+n,b+n,b+r))
    faces.append(tuple(range(ring-1,-1,-1)))
    last=(len(sec)-1)*ring; faces.append(tuple(last+i for i in range(ring)))
    mesh=bpy.data.meshes.new('V6HullMesh'); mesh.from_pydata(verts,[],faces); mesh.update()
    hull=bpy.data.objects.new('VikingHull',mesh); bpy.context.scene.collection.objects.link(hull)
    hull.data.materials.append(mats['wood']); hull.parent=boat_root
    bev=hull.modifiers.new('HullEdgeBreak','BEVEL'); bev.width=.05; bev.segments=1
    # side bands / gunwales
    for side,label in ((-1,'Front'),(1,'Back')):
        for i in range(len(sec)-1):
            x0,w0,z0,_,_=sec[i]; x1,w1,z1,_,_=sec[i+1]
            fw.cylinder_between(f'V6Gunwale_{label}_{i}',(x0,side*w0,z0+.08),(x1,side*w1,z1+.08),.11,mats['gold'],boat_root,vertices=12)
        y=side*(float(g['shipHalfWidth'])+.05)
        fw.box(f'V6HullRedBand_{label}',(0,y,-1.35),(float(g['shipLength'])*.78,.045,.12),mats['red'],.01,boat_root)
        fw.box(f'V6HullGoldBand_{label}',(0,y+side*.03,-.82),(float(g['shipLength'])*.74,.04,.10),mats['gold'],.01,boat_root)
    # deep deck
    fw.box('ShipDeck',(0,0,float(g['shipDeckZ'])),(float(g['shipLength'])*.78,float(g['shipHalfWidth'])*1.46,.18),mats['woodDark'],.02,boat_root)
    return hull


def _build_end_scrolls(boat_root,g,mats):
    L=float(g['shipLength'])*.5
    for sign,label in ((-1,'L'),(1,'R')):
        beam_between(f'V6ProwStem_{label}',(sign*(L*.92),0,-.2),(sign*(L*1.05),0,1.85),.34,.42,mats['gold'],boat_root,.03)
        fw.cylinder(f'V6ProwMedallion_{label}',(sign*(L*1.06),0,1.95),.56,.32,mats['gold'],rotation=(math.radians(90),0,0),parent=boat_root,vertices=24)
        fw.box(f'V6ProwPanel_{label}',(sign*(L*.98),0,1.12),(.70,1.10,.80),mats['red'],.05,boat_root)


def _build_seats(boat_root,g,mats):
    rows=int(g['seatRows']); span=float(g['seatSpan']); W=float(g['shipHalfWidth'])
    for i in range(rows):
        x=-span*.5 + span*(i/max(1,rows-1))
        fw.box(f'V6SeatBase_{i:02d}',(x,0,.10),(.64,W*1.28,.18),mats['seatRed'],.03,boat_root)
        fw.box(f'V6SeatBack_{i:02d}',(x+.18,0,.48),(.14,W*1.22,.66),mats['steelMid'],.03,boat_root)
        fw.cylinder_between(f'V6SafetyBar_{i:02d}',(x-.12,-W*.55,.68),(x-.12,W*.55,.68),.035,mats['steelLight'],boat_root,vertices=10)


def build_base(root,g,mats):
    # raised industrial boarding deck and open steel underframe
    pw=float(g['platformWidth']); pd=float(g['platformDepth']); top=float(g['platformTopZ']); slab=float(g['platformSlabHeight'])
    fw.box('V6PlatformSlab',(0,0,top-slab*.5),(pw,pd,slab),mats['platformWhite'],.02,root)
    # perimeter beams + underframe posts
    for x in (-pw*.46,-pw*.23,0,pw*.23,pw*.46):
        for y in (-pd*.46,pd*.46):
            fw.box(f'V6PlatformPost_{x:.2f}_{y:.2f}',(x,y,top*.5),(.28,.28,top),mats['steelDark'],.01,root)
    for y in (-pd*.46,pd*.46):
        beam_between(f'V6UnderLong_{y:.2f}',(-pw*.48,y,.32),(pw*.48,y,.32),.28,.28,mats['steelDark'],root,.01)
    for x in (-pw*.46,0,pw*.46):
        beam_between(f'V6UnderCross_{x:.2f}',(x,-pd*.48,.32),(x,pd*.48,.32),.24,.24,mats['steelDark'],root,.01)
    return bpy.data.objects.get('V6PlatformSlab')


def _rail_segment(name,a,b,z,g,mats,root):
    h=float(g['railingHeight']); r=float(g['railingPostRadius'])
    fw.cylinder_between(name+'_Top',(a[0],a[1],z+h),(b[0],b[1],z+h),r,mats['steelDark'],root,vertices=10)
    dist=math.hypot(b[0]-a[0],b[1]-a[1]); n=max(2,int(dist/.7))
    for i in range(n+1):
        t=i/n; x=a[0]+(b[0]-a[0])*t; y=a[1]+(b[1]-a[1])*t
        fw.cylinder_between(f'{name}_Post_{i}',(x,y,z),(x,y,z+h),r*.82,mats['steelDark'],root,vertices=8)


def build_loading_zone(root,g,mats):
    pw=float(g['platformWidth']); pd=float(g['platformDepth']); z=float(g['platformTopZ'])
    # railings with front opening for staircase
    _rail_segment('V6RailBack',(-pw*.49,pd*.49),(pw*.49,pd*.49),z,g,mats,root)
    _rail_segment('V6RailLeft',(-pw*.49,-pd*.49),(-pw*.49,pd*.49),z,g,mats,root)
    _rail_segment('V6RailRight',(pw*.49,-pd*.49),(pw*.49,pd*.49),z,g,mats,root)
    gap=float(g['stairWidth'])*.58
    _rail_segment('V6RailFrontL',(-pw*.49,-pd*.49),(-gap,-pd*.49),z,g,mats,root)
    _rail_segment('V6RailFrontR',((gap),-pd*.49),(pw*.49,-pd*.49),z,g,mats,root)
    # broad stairs from ground to deck
    steps=int(g['stairSteps']); sw=float(g['stairWidth']); run=float(g['stairRun'])
    for i in range(steps):
        t=(i+1)/steps; step_z=z*t; y=-pd*.5-run + run*t
        fw.box(f'V6Stair_{i:02d}',(0,y,step_z*.5),(sw,run/steps+.10,step_z),mats['platformWhite'],.01,root)
    for side in (-1,1):
        x=side*sw*.52
        beam_between(f'V6StairRail_{side}',(x,-pd*.5-run,.35),(x,-pd*.5,z+float(g['railingHeight'])),.06,.06,mats['steelDark'],root,.01)
    # decorative fence panels
    for x in (-pw*.36,-pw*.12,pw*.12,pw*.36):
        fw.box(f'V6FencePanel_{x:.2f}',(x,-pd*.495,z+.58),(1.05,.08,.74),mats['red'],.02,root)
        fw.box(f'V6FencePanelGold_{x:.2f}',(x,-pd*.505,z+.58),(.74,.035,.42),mats['gold'],.015,root)
    return root


def build_supports(root,g,mats):
    pz=float(g['pivotZ']); hx=float(g['supportHalfWidth']); hy=float(g['supportHalfDepth']); bw=float(g['supportBeamWidth']); bd=float(g['supportBeamDepth'])
    supports=[]
    # four massive legs, two A-frames front/back
    for ys,side in ((-1,'Front'),(1,'Back')):
        y=ys*hy
        for xs,label in ((-1,'L'),(1,'R')):
            foot=(xs*hx,y,1.0); apex=(xs*.72,y,pz-.45)
            supports.append(beam_between(f'V6MainLeg_{side}_{label}',foot,apex,bw,bd,mats['steelBlue'],root,.04))
            # gold inlay member tracks each main leg
            beam_between(f'V6GoldLeg_{side}_{label}',(foot[0]*.985,y-ys*.05,1.5),(apex[0]*.985,y-ys*.05,pz-1.05),bw*.24,bd*.16,mats['yellow'],root,.02)
            fw.box(f'V6Foot_{side}_{label}',(foot[0],foot[1],.22),(1.55,1.25,.44),mats['steelDark'],.02,root)
        # A-frame lower and mid trusses
        beam_between(f'V6CrossLow_{side}',(-hx*.72,y,6.0),(hx*.72,y,6.0),.34,.30,mats['steelDark'],root,.015)
        beam_between(f'V6CrossMid_{side}',(-hx*.44,y,12.2),(hx*.44,y,12.2),.32,.28,mats['steelDark'],root,.015)
        beam_between(f'V6DiagA_{side}',(-hx*.65,y,6.0),(hx*.40,y,12.2),.22,.22,mats['steelDark'],root,.01)
        beam_between(f'V6DiagB_{side}',(hx*.65,y,6.0),(-hx*.40,y,12.2),.22,.22,mats['steelDark'],root,.01)
    # axle + large bearings
    fw.cylinder_between('MainAxle',(0,-hy-.55,pz),(0,hy+.55,pz),float(g['axleRadius']),mats['steelDark'],root,vertices=24)
    for y,label in ((-hy,'Front'),(hy,'Back')):
        fw.cylinder(f'V6Bearing_{label}',(0,y,pz),float(g['bearingRadius']),float(g['bearingDepth']),mats['gold'],rotation=(math.radians(90),0,0),parent=root,vertices=32)
        fw.cylinder(f'V6BearingHub_{label}',(0,y-0.02,pz),float(g['bearingRadius'])*.56,float(g['bearingDepth'])+.08,mats['steelDark'],rotation=(math.radians(90),0,0),parent=root,vertices=24)
    return supports


def build_swing_group(root,g,mats):
    pz=float(g['pivotZ']); drop=float(g['boatDrop'])
    pivot=fw.empty('SwingPivot',(0,0,pz),root); pivot['runtimeLayer']='motion_overlay'; pivot['rotationAxis']='Y'
    boat=fw.empty('BoatRoot',(0,0,-drop),pivot)
    topx=float(g['suspensionTopHalfX']); endx=float(g['suspensionAttachHalfX']); y=float(g['suspensionHalfDepth'])
    for xs,label in ((-1,'L'),(1,'R')):
        for ys,side in ((-1,'Front'),(1,'Back')):
            start=(xs*topx,ys*y*.88,-.35); end=(xs*endx,ys*y,-drop+.25)
            beam_between(f'V6Suspension_{side}_{label}',start,end,float(g['suspensionWidth']),float(g['suspensionDepth']),mats['yellow'],pivot,.025)
            fw.cylinder(f'V6ShipJoint_{side}_{label}',end,.32,.48,mats['steelDark'],rotation=(math.radians(90),0,0),parent=pivot,vertices=16)
    _build_hull(boat,g,mats); _build_end_scrolls(boat,g,mats); _build_seats(boat,g,mats)
    pivot.rotation_euler[1]=math.radians(float(g.get('previewSwingDegrees',0)))
    return pivot
