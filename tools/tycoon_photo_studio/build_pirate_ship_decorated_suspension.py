#!/usr/bin/env python3
from __future__ import annotations
import math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
import build_pirate_ship_clean_reference as base


def sleeve_between(name,a,b,t,length,width,depth,mat,parent):
    a=Vector(a); b=Vector(b); v=b-a
    direction=v.normalized(); center=a+v*t
    half=length*.5
    start=center-direction*half; end=center+direction*half
    o=base.box(name,tuple(center),(width,depth,length),mat,parent,.035)
    o.rotation_mode='QUATERNION'
    o.rotation_quaternion=(end-start).to_track_quat('Z','Y')
    return o


def park_palette(M):
    return [M['funRed'],M['funBlue'],M['funYellow']], ['Red','Blue','Yellow']


def remove_boarding_stairs():
    # The approved attraction does not use the small rear staircase. Keep only the
    # flush boarding platform and its perimeter railing.
    for obj in list(bpy.data.objects):
        if obj.name.startswith('BoardingStep_') or obj.name.startswith('StairRail_'):
            bpy.data.objects.remove(obj, do_unlink=True)


def decorate_suspension(root,c,M):
    d=c['dimensions']; pz=float(d['pivotZ']); cz=float(d['shipCenterZ'])
    attach_z=cz+.35; attach_x=float(d['shipLength'])*.40
    fractions=d.get('armDecorationFractions',[.22,.48,.74])
    palette,names=park_palette(M)

    for y,label in ((-1.2,'NearPendulum'),(1.2,'FarPendulum')):
        for side_index,(x,side) in enumerate(((-attach_x,'Bow'),(attach_x,'Stern'))):
            for i,t in enumerate(fractions):
                idx=(i+side_index+(0 if y<0 else 1))%len(palette)
                sleeve_between(
                    f'{label}_{side}_{names[idx]}Cuff_{i}',
                    (0,y,pz),(x,y,attach_z),float(t),.66,.72,.72,
                    palette[idx],root)
            lower_idx=(side_index+2+(0 if y<0 else 1))%len(palette)
            sleeve_between(
                f'{label}_{side}_{names[lower_idx]}LowerCollar',
                (0,y,pz),(x,y,attach_z),.91,.46,.78,.78,
                palette[lower_idx],root)

    mast_top=pz-.65
    mast_bottom=float(d.get('centralMastAttachZ',cz+.45))
    mast_r=float(d.get('centralMastRadius',.42))
    mast_fracs=d.get('mastDecorationFractions',[.24,.46,.68,.86])
    for i,t in enumerate(mast_fracs):
        z=mast_top+(mast_bottom-mast_top)*float(t)
        idx=i%len(palette)
        base.cyl_axis(
            f'CentralMast{names[idx]}Band_{i}',
            (0,0,z),mast_r*1.34,.30,'Z',palette[idx],root)

    base.cyl_axis('CentralMastUpperRedCollar',(0,0,mast_top-.25),mast_r*1.46,.48,'Z',M['funRed'],root)
    base.cyl_axis('CentralMastLowerBlueCollar',(0,0,mast_bottom+.30),mast_r*1.46,.48,'Z',M['funBlue'],root)

    med_z=mast_top+(mast_bottom-mast_top)*.55
    for side_index,y in enumerate((-.48,.48)):
        outer=M['funYellow'] if side_index==0 else M['funRed']
        hub=M['funBlue'] if side_index==0 else M['funYellow']
        side='Near' if y<0 else 'Far'
        base.cyl_axis(f'CentralMastMedallion_{side}',(0,y,med_z),.76,.18,'Y',outer,root)
        base.cyl_axis(f'CentralMastMedallionHub_{side}',(0,y*1.04,med_z),.38,.22,'Y',hub,root)


def decorate_ship(root,c,M):
    d=c['dimensions']; L=float(d['shipLength']); HW=float(d['shipHalfWidth']); cz=float(d['shipCenterZ'])
    palette,names=park_palette(M)

    # Carnival-style side badges: readable splashes of color without repainting
    # the wooden hull or changing its silhouette.
    badge_x=(-6.6,-3.3,0.0,3.3,6.6)
    for side,side_name in ((-1,'Port'),(1,'Starboard')):
        for i,x in enumerate(badge_x):
            idx=(i+(0 if side<0 else 1))%3
            y=side*(HW+.10)
            z=cz+.05+.18*(abs(x)/(L*.5))
            base.cyl_axis(f'{side_name}HullBadge_{names[idx]}_{i}',(x,y,z),.34,.12,'Y',palette[idx],root)
            base.cyl_axis(f'{side_name}HullBadgeHub_{i}',(x,y*1.003,z),.14,.15,'Y',M['gold'],root)

    # Colored inset panels on the high bow/stern crests give the ride a stronger
    # amusement-park identity while preserving the approved dark hull mass.
    for x,label,mat in ((-L*.5,'Stern',M['funBlue']),(L*.5,'Bow',M['funRed'])):
        for side in (-1,1):
            base.box(f'{label}ColorInset_{"Near" if side<0 else "Far"}',
                     (x+(-.19 if x>0 else .19),side*.55,cz+4.28),
                     (.10,.62,.92),mat,root,.035)
        base.box(f'{label}YellowCrown',(x,0,cz+5.62),(.46,1.34,.20),M['funYellow'],root,.055)


def decorate_frame(root,c,M):
    d=c['dimensions']; pz=float(d['pivotZ']); sy=float(d['sideFrameHalfY']); lx=float(d['sideLegHalfX'])
    palette,names=park_palette(M)

    # Broad colored clamps on the four main A-frame legs. They are decoration
    # only; structural members and geometry stay untouched.
    for side_index,(y,label) in enumerate(((-sy,'NearSide'),(sy,'FarSide'))):
        apex=(0,y,pz)
        for leg_index,(x,leg) in enumerate(((-lx,'Front'),(lx,'Rear'))):
            foot=(x,y,.25)
            for cuff_index,t in enumerate((.30,.62)):
                idx=(side_index+leg_index+cuff_index)%3
                sleeve_between(f'{label}_{leg}_{names[idx]}ParkCuff_{cuff_index}',
                               foot,apex,t,.72,1.12,1.12,palette[idx],root)

    # Small colored hub caps make the pivot hardware read as a finished ride.
    for side_index,y in enumerate((-sy,sy)):
        mat=palette[side_index]
        base.cyl_axis(f'PivotColorCap_{side_index}',(0,y*1.002,pz),.48,.16,'Y',mat,root)


_original_build=base.build

def decorated_build(root,c,M):
    _original_build(root,c,M)
    remove_boarding_stairs()
    decorate_suspension(root,c,M)
    decorate_ship(root,c,M)
    decorate_frame(root,c,M)

base.build=decorated_build

if __name__=='__main__':
    base.main()
