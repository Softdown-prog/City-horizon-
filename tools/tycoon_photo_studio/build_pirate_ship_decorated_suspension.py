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
                sleeve_between(f'{label}_{side}_{names[idx]}Cuff_{i}',(0,y,pz),(x,y,attach_z),float(t),.62,.70,.70,palette[idx],root)
            lower_idx=(side_index+2+(0 if y<0 else 1))%len(palette)
            sleeve_between(f'{label}_{side}_{names[lower_idx]}LowerCollar',(0,y,pz),(x,y,attach_z),.91,.42,.76,.76,palette[lower_idx],root)

    mast_top=pz-.65
    mast_bottom=float(d.get('centralMastAttachZ',cz+.45))
    mast_r=float(d.get('centralMastRadius',.42))
    mast_fracs=d.get('mastDecorationFractions',[.24,.46,.68,.86])
    for i,t in enumerate(mast_fracs):
        z=mast_top+(mast_bottom-mast_top)*float(t)
        idx=i%len(palette)
        base.cyl_axis(f'CentralMast{names[idx]}Band_{i}',(0,0,z),mast_r*1.30,.26,'Z',palette[idx],root)

    base.cyl_axis('CentralMastUpperRedCollar',(0,0,mast_top-.25),mast_r*1.42,.42,'Z',M['funRed'],root)
    base.cyl_axis('CentralMastLowerBlueCollar',(0,0,mast_bottom+.30),mast_r*1.42,.42,'Z',M['funBlue'],root)

    med_z=mast_top+(mast_bottom-mast_top)*.55
    for side_index,y in enumerate((-.48,.48)):
        outer=M['funYellow'] if side_index==0 else M['funRed']
        hub=M['funBlue'] if side_index==0 else M['funYellow']
        side='Near' if y<0 else 'Far'
        base.cyl_axis(f'CentralMastMedallion_{side}',(0,y,med_z),.70,.16,'Y',outer,root)
        base.cyl_axis(f'CentralMastMedallionHub_{side}',(0,y*1.04,med_z),.34,.20,'Y',hub,root)


def decorate_ship(root,c,M):
    d=c['dimensions']; L=float(d['shipLength']); HW=float(d['shipHalfWidth']); cz=float(d['shipCenterZ'])
    palette,names=park_palette(M)

    # Flush decorative panels replace the earlier floating side badges.
    panel_x=(-6.4,-3.2,0.0,3.2,6.4)
    for side,side_name in ((-1,'Port'),(1,'Starboard')):
        y=side*(HW+.025)
        for i,x in enumerate(panel_x):
            idx=(i+(0 if side<0 else 1))%3
            z=cz+.14+.12*(abs(x)/(L*.5))
            panel=base.box(f'{side_name}HullInset_{names[idx]}_{i}',(x,y,z),(.72,.10,.46),palette[idx],root,.055)
            panel.rotation_euler[0]=math.radians(4*side)
            base.box(f'{side_name}HullInsetTrim_{i}',(x,y*1.002,z-.30),(.84,.08,.08),M['gold'],root,.025)

    for x,label,mat in ((-L*.5,'Stern',M['funBlue']),(L*.5,'Bow',M['funRed'])):
        for side in (-1,1):
            base.box(f'{label}ColorInset_{"Near" if side<0 else "Far"}',(x+(-.19 if x>0 else .19),side*.55,cz+4.28),(.10,.62,.92),mat,root,.035)
        base.box(f'{label}YellowCrown',(x,0,cz+5.62),(.46,1.34,.20),M['funYellow'],root,.055)

    # Small carnival bulbs follow the visible sheer line; they read as integrated trim,
    # not loose geometry, and stay large enough to survive the 1k isometric bake.
    bulb_x=(-7.6,-5.1,-2.6,0.0,2.6,5.1,7.6)
    for side,side_name in ((-1,'Port'),(1,'Starboard')):
        y=side*(HW+.09)
        for i,x in enumerate(bulb_x):
            idx=(i+(1 if side>0 else 0))%3
            u=abs(x)/(L*.5)
            z=cz+1.02+2.10*u*u
            base.cyl_axis(f'{side_name}SheerLamp_{names[idx]}_{i}',(x,y,z),.16,.10,'Y',palette[idx],root)


def decorate_frame(root,c,M):
    d=c['dimensions']; pz=float(d['pivotZ']); sy=float(d['sideFrameHalfY']); lx=float(d['sideLegHalfX'])
    palette,names=park_palette(M)

    for side_index,(y,label) in enumerate(((-sy,'NearSide'),(sy,'FarSide'))):
        apex=(0,y,pz)
        for leg_index,(x,leg) in enumerate(((-lx,'Front'),(lx,'Rear'))):
            foot=(x,y,.25)
            for cuff_index,t in enumerate((.30,.62)):
                idx=(side_index+leg_index+cuff_index)%3
                sleeve_between(f'{label}_{leg}_{names[idx]}ParkCuff_{cuff_index}',foot,apex,t,.66,1.10,1.10,palette[idx],root)

    for side_index,y in enumerate((-sy,sy)):
        mat=palette[side_index]
        base.cyl_axis(f'PivotColorCap_{side_index}',(0,y*1.002,pz),.46,.16,'Y',mat,root)

    # Decorative top-center crest connects the color language to the axle assembly.
    base.box('TopCenterSignPlate',(0,-sy-.16,pz-1.90),(2.30,.22,1.05),M['funBlue'],root,.10)
    base.box('TopCenterSignTrim',(0,-sy-.30,pz-1.90),(2.55,.10,1.28),M['funYellow'],root,.08)
    base.box('TopCenterSignCore',(0,-sy-.36,pz-1.90),(1.30,.08,.48),M['funRed'],root,.06)


def refine_boarding_deck(root,c,M):
    d=c['dimensions']; deckZ=float(d['deckZ']); deckY=-5.15
    # Give the flush deck a deliberate station edge instead of reading as a leftover slab.
    base.box('BoardingDeckFrontFascia',(0,deckY-1.43,deckZ*.72),(18.7,.16,.72),M['structure'],root,.05)
    for x in (-8.5,-4.25,0,4.25,8.5):
        base.box(f'BoardingDeckPanel_{x}',(x,deckY-1.53,deckZ*.75),(2.2,.08,.42),M['funBlue' if int(abs(x))%2==0 else 'funRed'],root,.035)
    base.beam('BoardingDeckTopAccent',(-9.1,deckY-1.56,deckZ+1.02),(9.1,deckY-1.56,deckZ+1.02),.09,.09,M['funYellow'],root)


_original_build=base.build

def decorated_build(root,c,M):
    _original_build(root,c,M)
    remove_boarding_stairs()
    decorate_suspension(root,c,M)
    decorate_ship(root,c,M)
    decorate_frame(root,c,M)
    refine_boarding_deck(root,c,M)

base.build=decorated_build

if __name__=='__main__':
    base.main()
